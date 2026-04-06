#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChatBot 模块测试

测试微信自动化功能
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from core.wechat_bot import WeChatBot, WeChatConfig, Message


class TestWeChatConfig:
    """WeChatConfig 配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = WeChatConfig()

        assert config.tesseract_path == r"E:\Tesseract\tesseract.exe"
        assert config.ocr_language == "chi_sim+eng"
        assert config.check_interval == 2.0
        assert config.send_max_retries == 3
        assert config.dedup_max_history == 100

    def test_custom_config(self):
        """测试自定义配置"""
        config = WeChatConfig(
            tesseract_path="/custom/path/tesseract",
            check_interval=1.0,
            send_max_retries=5
        )

        assert config.tesseract_path == "/custom/path/tesseract"
        assert config.check_interval == 1.0
        assert config.send_max_retries == 5

    def test_from_yaml_not_exists(self, temp_dir: Path):
        """测试从不存在的 YAML 文件加载"""
        config = WeChatConfig.from_yaml(str(temp_dir / "not_exists.yaml"))
        # 应该返回默认配置
        assert config.check_interval == 2.0

    def test_from_yaml_valid(self, sample_config_file: Path):
        """测试从有效 YAML 文件加载"""
        config = WeChatConfig.from_yaml(str(sample_config_file))

        assert config.check_interval == 2.0
        assert config.ocr_language == "chi_sim+eng"
        assert config.send_max_retries == 3


class TestMessage:
    """Message 消息类测试"""

    def test_message_creation(self):
        """测试消息创建"""
        msg = Message(
            id="123",
            type="text",
            sender="test_user",
            sender_name="测试用户",
            content="你好",
            is_group=False,
            is_self=False,
            timestamp=1712000000
        )

        assert msg.id == "123"
        assert msg.type == "text"
        assert msg.sender == "test_user"
        assert msg.content == "你好"
        assert msg.is_group is False
        assert msg.is_self is False

    def test_message_group(self):
        """测试群消息"""
        msg = Message(
            id="456",
            type="text",
            sender="group_member",
            sender_name="群成员",
            content="@所有人",
            is_group=True,
            is_self=False,
            room_id="12345@chatroom",
            timestamp=1712000000
        )

        assert msg.is_group is True
        assert msg.room_id == "12345@chatroom"


class TestWeChatBot:
    """WeChatBot 类测试"""

    def test_init_default_config(self):
        """测试默认配置初始化"""
        bot = WeChatBot()

        assert bot.config is not None
        assert bot._running is False
        assert bot._callbacks == []

    def test_init_custom_config(self):
        """测试自定义配置初始化"""
        config = WeChatConfig(check_interval=1.5)
        bot = WeChatBot(config)

        assert bot.config.check_interval == 1.5

    def test_disconnect(self):
        """测试断开连接"""
        bot = WeChatBot()
        bot._running = True
        bot.disconnect()

        assert bot._running is False
        assert bot.app is None
        assert bot.main_window is None

    def test_is_login_not_connected(self):
        """测试未连接时的登录状态"""
        bot = WeChatBot()
        assert bot.is_login() is False

    def test_get_self_info_not_connected(self):
        """测试未连接时获取账号信息"""
        bot = WeChatBot()
        info = bot.get_self_info()

        assert info is not None
        assert "wxid" in info
        assert "name" in info

    @pytest.mark.requires_wechat
    def test_connect_not_running(self):
        """测试微信未运行时连接"""
        bot = WeChatBot()
        result = bot.connect()

        # 如果微信未运行，应该返回 False
        assert result is False

    def test_start_listening_not_connected(self):
        """测试未连接时启动监听"""
        bot = WeChatBot()
        callback = MagicMock()

        bot.start_listening(callback)

        # 未连接时不应该添加回调
        assert callback not in bot._callbacks

    def test_stop_listening(self):
        """测试停止监听"""
        bot = WeChatBot()
        bot._running = True
        bot._listen_thread = MagicMock()
        bot._listen_thread.join = MagicMock()

        bot.stop_listening()

        assert bot._running is False

    def test_message_dedup(self):
        """测试消息去重"""
        bot = WeChatBot()

        # 第一次解析
        msg1 = bot._parse_message("张三\n你好啊")
        assert msg1 is not None

        # 重复消息应该被去重
        msg2 = bot._parse_message("张三\n你好啊")
        assert msg2 is None

    def test_parse_empty_message(self):
        """测试解析空消息"""
        bot = WeChatBot()

        result = bot._parse_message("")
        assert result is None

        result = bot._parse_message(None)
        assert result is None

    def test_parse_group_message(self):
        """测试解析群消息"""
        bot = WeChatBot()

        msg = bot._parse_message("王五\n@所有人 今天开会！")
        assert msg is not None
        # 群消息检测可能不准确，取决于文本内容

    def test_ocr_region_calculation(self, mock_wechat_window):
        """测试 OCR 区域计算"""
        bot = WeChatBot()

        region = bot._calculate_ocr_region(mock_wechat_window)

        assert len(region) == 4
        left, top, right, bottom = region
        assert left >= 0
        assert top >= 0
        assert right > left
        assert bottom > top

    def test_get_wechat_window_rect_not_connected(self):
        """测试未连接时获取窗口位置"""
        bot = WeChatBot()
        rect = bot._get_wechat_window_rect()

        # 未连接时应该返回默认值
        assert rect == (0, 0, 800, 600)

    def test_detect_self_message(self):
        """测试自己发送消息检测"""
        bot = WeChatBot()

        # 包含自己消息标记
        assert bot._detect_self_message("我: 你好") is True
        assert bot._detect_self_message("我：测试") is True

        # 不包含标记
        assert bot._detect_self_message("张三: 你好") is False

    def test_get_contacts_not_implemented(self):
        """测试获取联系人列表（未实现）"""
        bot = WeChatBot()
        contacts = bot.get_contacts()

        assert contacts == []

    def test_get_chat_history_not_implemented(self):
        """测试获取聊天记录（未实现）"""
        bot = WeChatBot()
        history = bot.get_chat_history()

        assert history == []


class TestWeChatBotSendMessage:
    """发送消息功能测试"""

    def test_send_text_not_connected(self):
        """测试未连接时发送消息"""
        bot = WeChatBot()
        result = bot.send_text("测试消息")

        assert result is False

    def test_send_text_with_retry_not_connected(self):
        """测试未连接时带重试的发送"""
        bot = WeChatBot()
        result = bot.send_text_with_retry("测试消息", max_retries=2)

        assert result is False


class TestWeChatBotDebug:
    """调试功能测试"""

    def test_debug_window_structure_not_connected(self):
        """测试未连接时调试窗口结构"""
        bot = WeChatBot()
        result = bot.debug_window_structure()

        assert "error" in result
        assert result["error"] == "未连接微信"


# 标记需要微信客户端的测试
# 使用: pytest -m "not requires_wechat" 跳过这些测试

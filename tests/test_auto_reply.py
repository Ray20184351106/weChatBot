#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoReplyManager 模块测试

测试自动回复管理功能
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from core.auto_reply import (
    AutoReplyManager,
    AutoReplyConfig,
    RateLimitState
)


class TestAutoReplyConfig:
    """AutoReplyConfig 配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = AutoReplyConfig()

        assert config.enabled is False
        assert config.min_training_data == 100
        assert config.min_interval == 3.0
        assert config.max_per_minute == 5
        assert config.human_takeover_enabled is True
        assert "#人工" in config.human_takeover_keywords

    def test_custom_config(self):
        """测试自定义配置"""
        config = AutoReplyConfig(
            enabled=True,
            min_interval=5.0,
            max_per_minute=3,
            exclude_contacts=["wxid_spam"]
        )

        assert config.enabled is True
        assert config.min_interval == 5.0
        assert config.max_per_minute == 3
        assert "wxid_spam" in config.exclude_contacts

    def test_from_yaml_not_exists(self, temp_dir: Path):
        """测试从不存在的 YAML 文件加载"""
        config = AutoReplyConfig.from_yaml(str(temp_dir / "not_exists.yaml"))

        # 应该返回默认配置
        assert config.enabled is False

    def test_from_yaml_valid(self, sample_config_file: Path):
        """测试从有效 YAML 文件加载"""
        config = AutoReplyConfig.from_yaml(str(sample_config_file))

        assert config.min_interval == 3.0
        assert config.max_per_minute == 5


class TestRateLimitState:
    """RateLimitState 状态类测试"""

    def test_default_state(self):
        """测试默认状态"""
        state = RateLimitState()

        assert state.last_reply_time == 0.0
        assert state.reply_count == 0
        assert state.minute_start_time == 0.0


class TestAutoReplyManager:
    """AutoReplyManager 类测试"""

    def test_init_default_config(self):
        """测试默认配置初始化"""
        manager = AutoReplyManager()

        assert manager.config is not None
        assert manager.enabled is False

    def test_init_custom_config(self):
        """测试自定义配置初始化"""
        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        assert manager.enabled is True

    def test_enable_disable(self):
        """测试启用/禁用"""
        manager = AutoReplyManager()

        manager.enable()
        assert manager.enabled is True

        manager.disable()
        assert manager.enabled is False

    def test_toggle(self):
        """测试切换状态"""
        manager = AutoReplyManager()

        result = manager.toggle()
        assert result is True
        assert manager.enabled is True

        result = manager.toggle()
        assert result is False
        assert manager.enabled is False

    def test_set_llm(self):
        """测试设置 LLM 引擎"""
        manager = AutoReplyManager()
        mock_llm = MagicMock()

        manager.set_llm(mock_llm)
        assert manager.llm == mock_llm

    def test_set_collector(self):
        """测试设置消息收集器"""
        manager = AutoReplyManager()
        mock_collector = MagicMock()

        manager.set_collector(mock_collector)
        assert manager.collector == mock_collector


class TestAutoReplyCanReply:
    """can_reply 功能测试"""

    def test_can_reply_disabled(self):
        """测试自动回复未启用"""
        manager = AutoReplyManager()
        can_reply, reason = manager.can_reply("wxid_001", "你好")

        assert can_reply is False
        assert "未启用" in reason

    def test_can_reply_enabled(self):
        """测试自动回复已启用"""
        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        can_reply, reason = manager.can_reply("wxid_001", "你好")

        assert can_reply is True

    def test_can_reply_blacklist(self):
        """测试黑名单"""
        config = AutoReplyConfig(
            enabled=True,
            exclude_contacts=["wxid_spam"]
        )
        manager = AutoReplyManager(config)

        can_reply, reason = manager.can_reply("wxid_spam", "你好")
        assert can_reply is False
        assert "黑名单" in reason

    def test_can_reply_whitelist_mode(self):
        """测试白名单模式"""
        config = AutoReplyConfig(
            enabled=True,
            whitelist_contacts=["wxid_friend"],
            whitelist_mode=True
        )
        manager = AutoReplyManager(config)

        # 不在白名单
        can_reply, reason = manager.can_reply("wxid_stranger", "你好")
        assert can_reply is False
        assert "白名单" in reason

        # 在白名单
        can_reply, reason = manager.can_reply("wxid_friend", "你好")
        assert can_reply is True

    def test_can_reply_human_takeover(self):
        """测试人工接管"""
        config = AutoReplyConfig(
            enabled=True,
            human_takeover_enabled=True,
            human_takeover_keywords=["#人工"]
        )
        manager = AutoReplyManager(config)

        # 触发人工接管
        can_reply, reason = manager.can_reply("wxid_001", "你好 #人工")
        assert can_reply is False
        assert "人工接管" in reason

        # 再次检查，应该处于人工模式
        can_reply, reason = manager.can_reply("wxid_001", "你好")
        assert can_reply is False
        assert "人工模式" in reason

    def test_can_reply_exit_human_mode(self):
        """测试退出人工模式"""
        config = AutoReplyConfig(
            enabled=True,
            human_takeover_enabled=True,
            human_takeover_keywords=["#人工"]
        )
        manager = AutoReplyManager(config)

        # 先进入人工模式
        manager.can_reply("wxid_001", "#人工")

        # 发送退出关键词
        can_reply, reason = manager.can_reply("wxid_001", "#自动")
        assert can_reply is True

    def test_can_reply_rate_limit_interval(self):
        """测试频率限制（最小间隔）"""
        config = AutoReplyConfig(
            enabled=True,
            min_interval=1.0
        )
        manager = AutoReplyManager(config)

        # 第一次可以回复
        can_reply, _ = manager.can_reply("wxid_001", "你好")
        assert can_reply is True

        # 记录回复
        manager.record_reply("wxid_001")

        # 立即再次请求，应该被限制
        can_reply, reason = manager.can_reply("wxid_001", "你好")
        assert can_reply is False
        assert "间隔" in reason

    def test_can_reply_rate_limit_per_minute(self):
        """测试频率限制（每分钟限制）"""
        config = AutoReplyConfig(
            enabled=True,
            max_per_minute=2,
            min_interval=0
        )
        manager = AutoReplyManager(config)

        # 第一次
        manager.can_reply("wxid_001", "消息1")
        manager.record_reply("wxid_001")

        # 第二次
        manager.can_reply("wxid_001", "消息2")
        manager.record_reply("wxid_001")

        # 第三次应该被限制
        can_reply, reason = manager.can_reply("wxid_001", "消息3")
        assert can_reply is False
        assert "每分钟限制" in reason


class TestAutoReplyGenerate:
    """generate_reply 功能测试"""

    def test_generate_reply_no_llm(self):
        """测试没有 LLM 引擎"""
        manager = AutoReplyManager()
        reply = manager.generate_reply("wxid_001", "你好")

        assert reply is not None
        assert "忙" in reply or "稍后" in reply

    def test_generate_reply_with_llm(self):
        """测试有 LLM 引擎"""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "这是 LLM 生成的回复"
        mock_llm.get_default_system_prompt.return_value = "系统提示词"

        manager = AutoReplyManager(llm_engine=mock_llm)
        reply = manager.generate_reply("wxid_001", "你好")

        assert reply == "这是 LLM 生成的回复"
        mock_llm.generate.assert_called_once()

    def test_generate_reply_with_context(self):
        """测试带上下文的回复生成"""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "上下文回复"
        mock_llm.get_default_system_prompt.return_value = "系统提示词"

        manager = AutoReplyManager(llm_engine=mock_llm)
        context = [
            {"content": "之前的消息", "is_self": False},
            {"content": "我的回复", "is_self": True}
        ]

        reply = manager.generate_reply("wxid_001", "新消息", context=context)

        assert reply == "上下文回复"

    def test_generate_reply_llm_error(self):
        """测试 LLM 出错"""
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = Exception("LLM 错误")
        mock_llm.get_default_system_prompt.return_value = "系统提示词"

        manager = AutoReplyManager(llm_engine=mock_llm)
        reply = manager.generate_reply("wxid_001", "你好")

        # 应该返回默认回复
        assert reply is not None


class TestAutoReplyProcess:
    """process_message 功能测试"""

    def test_process_message_disabled(self):
        """测试处理消息（自动回复禁用）"""
        manager = AutoReplyManager()
        reply = manager.process_message("wxid_001", "你好")

        assert reply is None

    def test_process_message_success(self):
        """测试处理消息成功"""
        config = AutoReplyConfig(enabled=True)
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "自动回复"
        mock_llm.get_default_system_prompt.return_value = "提示词"

        manager = AutoReplyManager(config=config, llm_engine=mock_llm)
        reply = manager.process_message("wxid_001", "你好")

        assert reply == "自动回复"

    def test_process_message_with_callback(self):
        """测试处理消息带回调"""
        config = AutoReplyConfig(enabled=True)
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "回复"
        mock_llm.get_default_system_prompt.return_value = "提示词"

        callback = MagicMock()
        manager = AutoReplyManager(config=config, llm_engine=mock_llm)
        manager.set_reply_callback(callback)

        reply = manager.process_message("wxid_001", "你好")

        assert reply == "回复"
        callback.assert_called_once_with("wxid_001", "回复")


class TestAutoReplyContactStatus:
    """联系人状态功能测试"""

    def test_get_contact_status(self):
        """测试获取联系人状态"""
        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        status = manager.get_contact_status("wxid_001")

        assert "human_mode" in status
        assert "reply_count" in status
        assert "last_reply_time" in status

    def test_reset_contact(self):
        """测试重置联系人状态"""
        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        # 先进入人工模式
        manager.can_reply("wxid_001", "#人工")

        # 重置
        manager.reset_contact("wxid_001")

        # 检查状态
        status = manager.get_contact_status("wxid_001")
        assert status["human_mode"] is False


class TestAutoReplyStatistics:
    """统计功能测试"""

    def test_get_statistics(self):
        """测试获取统计"""
        config = AutoReplyConfig(
            enabled=True,
            whitelist_contacts=["wxid_friend"],
            exclude_contacts=["wxid_spam"]
        )
        manager = AutoReplyManager(config)

        stats = manager.get_statistics()

        assert stats["enabled"] is True
        assert stats["whitelist_count"] == 1
        assert stats["blacklist_count"] == 1
        assert "human_mode_count" in stats
        assert "active_contacts" in stats


class TestAutoReplyEdgeCases:
    """边界情况测试"""

    def test_empty_message(self):
        """测试空消息"""
        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        can_reply, _ = manager.can_reply("wxid_001", "")
        assert can_reply is True

    def test_special_characters_in_message(self):
        """测试特殊字符消息"""
        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        can_reply, _ = manager.can_reply("wxid_001", "#$%^&*()")
        assert can_reply is True

    def test_multiple_human_takeover_keywords(self):
        """测试多个人工接管关键词"""
        config = AutoReplyConfig(
            enabled=True,
            human_takeover_keywords=["#人工", "#stop", "转人工"]
        )
        manager = AutoReplyManager(config)

        # 测试每个关键词
        for keyword in config.human_takeover_keywords:
            manager.reset_contact("wxid_001")
            can_reply, reason = manager.can_reply("wxid_001", keyword)
            assert can_reply is False
            assert "人工接管" in reason

    def test_concurrent_requests(self):
        """测试并发请求"""
        import threading

        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        results = []

        def check_reply(sender):
            can_reply, _ = manager.can_reply(sender, "测试")
            results.append(can_reply)

        threads = [
            threading.Thread(target=check_reply, args=(f"wxid_{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有请求都应该成功（不同联系人）
        assert all(results)

    def test_long_running_state(self):
        """测试长时间运行的状态管理"""
        config = AutoReplyConfig(enabled=True)
        manager = AutoReplyManager(config)

        # 模拟多个联系人的状态
        for i in range(10):
            sender = f"wxid_{i}"
            manager.can_reply(sender, "测试消息")
            manager.record_reply(sender)

        stats = manager.get_statistics()
        assert stats["active_contacts"] == 10
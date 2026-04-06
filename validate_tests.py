#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试框架验证脚本

手动运行基本测试验证框架是否正常工作
"""

import sys
import tempfile
import shutil
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.message_collector import MessageCollector, ChatPair
from core.llm_engine import LLMEngine, LLMConfig
from core.wechat_bot import WeChatConfig, Message
from training.data_processor import DataProcessor


def test_message_collector():
    """测试消息收集器"""
    print("Testing MessageCollector...")

    temp_dir = Path(tempfile.mkdtemp())
    chat_dir = temp_dir / "chat_history"
    chat_dir.mkdir(parents=True)

    collector = MessageCollector(str(chat_dir))

    # 测试设置用户 ID
    collector.set_user_wxid("wxid_test")
    assert collector._user_wxid == "wxid_test"

    # 创建测试消息
    msg = Message(
        id="123",
        type="text",
        sender="wxid_001",
        sender_name="测试用户",
        content="你好",
        is_self=False,
        timestamp=1712000000
    )

    # 测试接收消息
    collector.on_message_received(msg)
    assert "wxid_001" in collector._pending_messages

    # 测试发送消息
    collector.on_message_sent("你好啊", "wxid_001")

    # 测试获取对话对
    pairs = collector.get_all_chat_pairs()
    assert len(pairs) >= 1

    # 测试统计
    stats = collector.get_statistics()
    assert stats["total_pairs"] >= 1

    # 清理
    shutil.rmtree(temp_dir)

    print("  [PASS] MessageCollector tests passed!")
    return True


def test_data_processor():
    """测试数据处理器"""
    print("Testing DataProcessor...")

    temp_dir = Path(tempfile.mkdtemp())
    chat_dir = temp_dir / "chat_history"
    chat_dir.mkdir(parents=True)

    # 创建测试数据文件
    test_data = [
        {
            "sender_id": "wxid_001",
            "sender_name": "张三",
            "incoming_message": "你好啊，最近怎么样？",
            "outgoing_message": "挺好的，你呢？最近忙啥呢",
            "timestamp": "2026-04-01T10:00:00",
            "room_id": None
        },
        {
            "sender_id": "wxid_001",
            "sender_name": "张三",
            "incoming_message": "在加班，累死了",
            "outgoing_message": "哈哈，辛苦了！记得休息",
            "timestamp": "2026-04-01T10:01:00",
            "room_id": None
        }
    ]

    file_path = chat_dir / "test.jsonl"
    with open(file_path, "w", encoding="utf-8") as f:
        for item in test_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    processor = DataProcessor(str(chat_dir))

    # 测试加载
    raw_data = processor.load_raw_data()
    assert len(raw_data) == 2

    # 测试清洗
    cleaned = processor.clean_data(raw_data)
    assert len(cleaned) == 2

    # 测试格式化 (Alpaca)
    formatted = processor.format_for_training(cleaned, format_type="alpaca")
    assert len(formatted) == 2
    assert "instruction" in formatted[0]

    # 测试格式化 (ChatML)
    formatted_chatml = processor.format_for_training(cleaned, format_type="chatml")
    assert "messages" in formatted_chatml[0]

    # 测试数据集划分
    train, val, test = processor.split_dataset(cleaned)
    assert len(train) + len(val) + len(test) == 2

    # 测试风格分析
    analysis = processor.analyze_style(cleaned)
    assert "avg_reply_length" in analysis

    # 清理
    shutil.rmtree(temp_dir)

    print("  [PASS] DataProcessor tests passed!")
    return True


def test_llm_engine():
    """测试 LLM 引擎"""
    print("Testing LLMEngine...")

    # 测试默认配置
    config = LLMConfig()
    assert config.provider == "openai"
    assert config.temperature == 0.7

    # 测试自定义配置
    custom_config = LLMConfig(
        provider="deepseek",
        temperature=0.5,
        max_tokens=256
    )
    engine = LLMEngine(custom_config)
    assert engine.config.provider == "deepseek"
    assert engine.config.temperature == 0.5

    # 测试系统提示词
    engine.set_system_prompt("测试提示词")
    assert engine._system_prompt == "测试提示词"

    # 测试默认系统提示词
    prompt = engine.get_default_system_prompt()
    assert "微信聊天助手" in prompt

    # 测试未配置时的生成
    result = engine.generate("你好")
    assert result is not None
    assert isinstance(result, str)

    print("  [PASS] LLMEngine tests passed!")
    return True


def test_wechat_config():
    """测试微信配置"""
    print("Testing WeChatConfig...")

    # 测试默认配置
    config = WeChatConfig()
    assert config.check_interval == 2.0
    assert config.ocr_language == "chi_sim+eng"

    # 测试自定义配置
    custom_config = WeChatConfig(
        check_interval=1.0,
        send_max_retries=5
    )
    assert custom_config.check_interval == 1.0
    assert custom_config.send_max_retries == 5

    print("  [PASS] WeChatConfig tests passed!")
    return True


def test_chat_pair():
    """测试对话对数据类"""
    print("Testing ChatPair...")

    pair = ChatPair(
        sender_id="wxid_001",
        sender_name="张三",
        incoming_message="你好",
        outgoing_message="你好啊",
        timestamp="2026-04-01T10:00:00",
        room_id=None
    )

    assert pair.sender_id == "wxid_001"
    assert pair.incoming_message == "你好"
    assert pair.outgoing_message == "你好啊"

    print("  [PASS] ChatPair tests passed!")
    return True


def test_auto_reply():
    """测试自动回复模块"""
    print("Testing AutoReplyManager...")

    from core.auto_reply import AutoReplyManager, AutoReplyConfig

    # 测试默认配置
    config = AutoReplyConfig()
    assert config.enabled is False
    assert config.min_interval == 3.0

    # 测试自定义配置
    custom_config = AutoReplyConfig(
        enabled=True,
        min_interval=5.0,
        exclude_contacts=["wxid_spam"]
    )
    manager = AutoReplyManager(custom_config)

    # 测试启用/禁用
    assert manager.enabled is True
    manager.disable()
    assert manager.enabled is False
    manager.enable()
    assert manager.enabled is True

    # 测试频率限制
    can_reply, reason = manager.can_reply("wxid_001", "你好")
    assert can_reply is True

    manager.record_reply("wxid_001")
    can_reply, reason = manager.can_reply("wxid_001", "你好")
    assert can_reply is False  # 间隔太短

    # 测试黑名单
    can_reply, reason = manager.can_reply("wxid_spam", "你好")
    assert can_reply is False

    # 测试人工接管
    manager.reset_contact("wxid_001")
    can_reply, reason = manager.can_reply("wxid_001", "#人工")
    assert can_reply is False

    # 测试默认回复
    reply = manager.generate_reply("wxid_001", "你好")
    assert reply is not None

    # 测试统计
    stats = manager.get_statistics()
    assert "enabled" in stats
    assert "active_contacts" in stats

    print("  [PASS] AutoReplyManager tests passed!")
    return True


def test_contact_manager():
    """测试联系人管理器"""
    print("Testing ContactManager...")

    from core.contact_manager import ContactManager, Contact
    import tempfile
    import os

    temp_dir = tempfile.mkdtemp()
    cache_path = os.path.join(temp_dir, 'contacts.json')

    manager = ContactManager(cache_path)

    # 测试添加联系人
    manager.add_contact('wxid_001', nickname='张三', remark='好友张三')
    manager.add_contact('wxid_002', nickname='李四')
    manager.add_contact('group@chatroom', is_group=True)

    # 测试获取联系人
    c = manager.get_contact('wxid_001')
    assert c is not None
    assert c.nickname == '张三'

    # 测试昵称索引
    c = manager.get_contact_by_nickname('李四')
    assert c is not None
    assert c.wxid == 'wxid_002'

    # 测试发送者解析
    wxid, name = manager.resolve_sender('张三')
    assert wxid == 'wxid_001'
    assert name == '好友张三'

    # 测试统计
    stats = manager.get_statistics()
    assert stats['total'] == 3
    assert stats['users'] == 2
    assert stats['groups'] == 1

    # 清理
    import shutil
    shutil.rmtree(temp_dir)

    print("  [PASS] ContactManager tests passed!")
    return True


def test_message_types():
    """测试消息类型模块"""
    print("Testing MessageParser...")

    from core.message_types import MessageParser, MessageType

    # 测试消息类型检测
    assert MessageParser.detect_type('你好') == MessageType.TEXT
    assert MessageParser.detect_type('[图片]') == MessageType.IMAGE
    assert MessageParser.detect_type('[文件]') == MessageType.FILE
    assert MessageParser.detect_type('[视频]') == MessageType.VIDEO
    assert MessageParser.detect_type('[语音]') == MessageType.VOICE
    assert MessageParser.detect_type('[表情]') == MessageType.EMOTION
    assert MessageParser.detect_type('https://example.com') == MessageType.LINK
    assert MessageParser.detect_type('撤回了一条消息') == MessageType.SYSTEM

    # 测试解析
    info = MessageParser.parse('[图片]')
    assert info.type == MessageType.IMAGE

    # 测试媒体判断
    assert MessageParser.is_media_message('[图片]') is True
    assert MessageParser.is_media_message('你好') is False

    # 测试训练跳过
    assert MessageParser.should_skip_for_training('[图片]') is True
    assert MessageParser.should_skip_for_training('你好') is False

    print("  [PASS] MessageParser tests passed!")
    return True


def main():
    """运行所有验证测试"""
    print("=" * 50)
    print("WeChatBot Test Framework Validation")
    print("=" * 50)

    tests = [
        test_chat_pair,
        test_wechat_config,
        test_message_collector,
        test_data_processor,
        test_llm_engine,
        test_auto_reply,
        test_contact_manager,
        test_message_types,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
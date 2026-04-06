#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 配置和共享 fixtures

提供测试所需的通用配置和模拟对象
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    创建临时目录用于测试

    Yields:
        临时目录路径
    """
    dir_path = Path(tempfile.mkdtemp())
    yield dir_path
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def temp_data_dir(temp_dir: Path) -> Path:
    """
    创建临时数据目录

    Args:
        temp_dir: 临时目录

    Returns:
        数据目录路径
    """
    data_dir = temp_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def temp_chat_history_dir(temp_data_dir: Path) -> Path:
    """
    创建临时聊天记录目录

    Args:
        temp_data_dir: 临时数据目录

    Returns:
        聊天记录目录路径
    """
    chat_dir = temp_data_dir / "chat_history"
    chat_dir.mkdir(parents=True, exist_ok=True)
    return chat_dir


@pytest.fixture
def sample_chat_pairs() -> list:
    """
    示例对话数据

    Returns:
        对话对列表
    """
    return [
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
        },
        {
            "sender_id": "wxid_002",
            "sender_name": "李四",
            "incoming_message": "周末有空吗？出来吃饭",
            "outgoing_message": "周六下午可以，去哪里？",
            "timestamp": "2026-04-02T14:00:00",
            "room_id": None
        },
        {
            "sender_id": "wxid_group_001",
            "sender_name": "王五",
            "incoming_message": "@所有人 今天开会！",
            "outgoing_message": "收到",
            "timestamp": "2026-04-03T09:00:00",
            "room_id": "12345678@chatroom"
        }
    ]


@pytest.fixture
def sample_chat_file(temp_chat_history_dir: Path, sample_chat_pairs: list) -> Path:
    """
    创建示例聊天记录文件

    Args:
        temp_chat_history_dir: 聊天记录目录
        sample_chat_pairs: 示例对话数据

    Returns:
        文件路径
    """
    file_path = temp_chat_history_dir / "test_chat.jsonl"
    with open(file_path, "w", encoding="utf-8") as f:
        for pair in sample_chat_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    return file_path


@pytest.fixture
def sample_config() -> dict:
    """
    示例配置

    Returns:
        配置字典
    """
    return {
        "wechat": {
            "check_interval": 2.0,
            "min_window_width": 100,
            "min_window_height": 100
        },
        "ocr": {
            "tesseract_path": "E:/Tesseract/tesseract.exe",
            "tessdata_path": "E:/Tesseract/tessdata",
            "language": "chi_sim+eng",
            "offset_ratio": {
                "left": 0.05,
                "top": 0.15,
                "right": 0.05,
                "bottom": 0.20
            },
            "fixed_offset": {
                "left": 50,
                "top": 100,
                "right": 50,
                "bottom": 150
            },
            "preprocessing": {
                "enabled": True,
                "grayscale": True,
                "threshold": False,
                "denoise": True,
                "enhance_contrast": True
            }
        },
        "send": {
            "delays": {
                "window_focus": 0.5,
                "search_contact": 0.3,
                "after_input": 0.2,
                "after_send": 0.5
            },
            "retry": {
                "max_attempts": 3,
                "retry_delay": 1.0
            }
        },
        "parse": {
            "dedup": {
                "max_history": 100
            }
        },
        "auto_reply": {
            "enabled": False,
            "min_training_data": 100,
            "rate_limit": {
                "min_interval": 3.0,
                "max_per_minute": 5
            }
        },
        "llm": {
            "provider": "openai",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "max_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.9
        }
    }


@pytest.fixture
def sample_config_file(temp_dir: Path, sample_config: dict) -> Path:
    """
    创建示例配置文件

    Args:
        temp_dir: 临时目录
        sample_config: 示例配置

    Returns:
        配置文件路径
    """
    import yaml
    config_path = temp_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_config, f, allow_unicode=True)
    return config_path


@pytest.fixture
def mock_wechat_window():
    """
    模拟微信窗口

    Returns:
        模拟的窗口对象
    """
    mock_window = MagicMock()
    mock_window.window_text.return_value = "微信"
    mock_window.is_visible.return_value = True
    mock_window.is_enabled.return_value = True

    # 模拟窗口矩形
    mock_rect = MagicMock()
    mock_rect.left = 100
    mock_rect.top = 100
    mock_rect.right = 900
    mock_rect.bottom = 700
    mock_rect.width.return_value = 800
    mock_rect.height.return_value = 600
    mock_window.rectangle.return_value = mock_rect

    return mock_window


@pytest.fixture
def mock_message():
    """
    创建模拟消息对象

    Returns:
        模拟消息工厂函数
    """
    def _create_message(
        content: str = "测试消息",
        sender: str = "test_sender",
        is_self: bool = False,
        is_group: bool = False,
        room_id: str = None
    ):
        """创建模拟消息"""
        from core.wechat_bot import Message
        return Message(
            id="1234567890",
            type="text",
            sender=sender,
            sender_name=sender,
            content=content,
            is_group=is_group,
            is_self=is_self,
            room_id=room_id,
            timestamp=1712000000
        )
    return _create_message


@pytest.fixture
def mock_llm_response():
    """
    模拟 LLM 响应

    Returns:
        模拟响应内容
    """
    return "这是一个模拟的 LLM 回复消息~"


# 标记：慢速测试
def pytest_configure(config):
    """pytest 配置钩子"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_wechat: marks tests that require WeChat client"
    )

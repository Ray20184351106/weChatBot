# Core module - 核心功能模块
"""
WeChatBot 核心模块

包含微信自动化、消息收集、LLM 引擎、自动回复、联系人管理、消息类型处理等功能
"""

from .wechat_bot import WeChatBot, WeChatConfig, Message
from .message_collector import MessageCollector, ChatPair
from .llm_engine import LLMEngine, LLMConfig
from .auto_reply import AutoReplyManager, AutoReplyConfig
from .contact_manager import ContactManager, Contact
from .message_types import MessageParser, MessageType, MediaInfo

__all__ = [
    "WeChatBot",
    "WeChatConfig",
    "Message",
    "MessageCollector",
    "ChatPair",
    "LLMEngine",
    "LLMConfig",
    "AutoReplyManager",
    "AutoReplyConfig",
    "ContactManager",
    "Contact",
    "MessageParser",
    "MessageType",
    "MediaInfo",
]
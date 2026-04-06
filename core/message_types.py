#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息类型处理模块

负责处理不同类型的微信消息：
- 文本消息
- 图片消息
- 文件消息
- 表情消息
- 链接消息
"""

import re
import base64
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from loguru import logger


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"           # 文本消息
    IMAGE = "image"         # 图片消息
    FILE = "file"           # 文件消息
    EMOTION = "emotion"     # 表情消息
    LINK = "link"           # 链接消息
    VIDEO = "video"         # 视频消息
    VOICE = "voice"         # 语音消息
    LOCATION = "location"   # 位置消息
    SYSTEM = "system"       # 系统消息
    UNKNOWN = "unknown"     # 未知类型


@dataclass
class MediaInfo:
    """媒体信息数据类"""
    type: MessageType
    original_text: str = ""         # 原始文本 (如 [图片])
    file_path: Optional[str] = None  # 文件路径
    file_name: Optional[str] = None  # 文件名
    file_size: Optional[int] = None  # 文件大小 (字节)
    file_ext: Optional[str] = None   # 文件扩展名
    mime_type: Optional[str] = None  # MIME 类型
    thumbnail: Optional[str] = None  # 缩略图 (base64)
    url: Optional[str] = None        # 链接地址
    title: Optional[str] = None      # 标题 (链接/文件)
    description: Optional[str] = None  # 描述


class MessageParser:
    """
    消息解析器

    解析微信消息文本，识别消息类型和内容
    """

    # 消息类型识别模式
    MESSAGE_PATTERNS = {
        MessageType.IMAGE: [
            r'\[图片\]',
            r'\[Photo\]',
            r'\[Image\]',
            r'<img[^>]*>',
        ],
        MessageType.FILE: [
            r'\[文件\]',
            r'\[File\]',
            r'\[文档\]',
            r'\.pdf',
            r'\.docx?',
            r'\.xlsx?',
            r'\.pptx?',
            r'\.zip',
            r'\.rar',
        ],
        MessageType.EMOTION: [
            r'\[表情\]',
            r'\[Sticker\]',
            r'\[动画表情\]',
        ],
        MessageType.VIDEO: [
            r'\[视频\]',
            r'\[Video\]',
            r'\[小视频\]',
            r'\.mp4',
            r'\.mov',
            r'\.avi',
        ],
        MessageType.VOICE: [
            r'\[语音\]',
            r'\[Voice\]',
        ],
        MessageType.LOCATION: [
            r'\[位置\]',
            r'\[Location\]',
            r'位置：',
            r'latitude.*longitude',
        ],
        MessageType.LINK: [
            r'\[链接\]',
            r'\[Link\]',
            r'https?://',
            r'www\.',
            r'<a href',
        ],
        MessageType.SYSTEM: [
            r'\[系统消息\]',
            r'撤回了一条消息',
            r'邀请.*加入了群聊',
            r'修改群名为',
            r'拍了拍',
        ],
    }

    # 文件扩展名到 MIME 类型的映射
    MIME_TYPES = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.zip': 'application/zip',
        '.rar': 'application/x-rar-compressed',
        '.7z': 'application/x-7z-compressed',
        '.txt': 'text/plain',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
    }

    @classmethod
    def detect_type(cls, text: str) -> MessageType:
        """
        检测消息类型

        Args:
            text: 消息文本

        Returns:
            消息类型
        """
        if not text:
            return MessageType.TEXT

        text_lower = text.lower()

        for msg_type, patterns in cls.MESSAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return msg_type

        return MessageType.TEXT

    @classmethod
    def parse(cls, text: str) -> MediaInfo:
        """
        解析消息内容

        Args:
            text: 消息文本

        Returns:
            MediaInfo 对象
        """
        msg_type = cls.detect_type(text)

        media_info = MediaInfo(
            type=msg_type,
            original_text=text
        )

        if msg_type == MessageType.LINK:
            media_info = cls._parse_link(text, media_info)

        elif msg_type == MessageType.FILE:
            media_info = cls._parse_file(text, media_info)

        elif msg_type in [MessageType.IMAGE, MessageType.VIDEO,
                         MessageType.VOICE, MessageType.EMOTION]:
            media_info.description = cls._get_media_description(msg_type)

        return media_info

    @classmethod
    def _parse_link(cls, text: str, info: MediaInfo) -> MediaInfo:
        """解析链接消息"""
        # 提取 URL
        url_match = re.search(r'(https?://[^\s<>"{}|\\^`\[\]]+)', text)
        if url_match:
            info.url = url_match.group(1)

        # 提取标题（如果有）
        title_match = re.search(r'标题[：:]\s*(.+)', text)
        if title_match:
            info.title = title_match.group(1).strip()

        return info

    @classmethod
    def _parse_file(cls, text: str, info: MediaInfo) -> MediaInfo:
        """解析文件消息"""
        # 提取文件名
        file_patterns = [
            r'\[文件[：:]\s*([^\]]+)\]',
            r'文件[：:]\s*(.+?)(?:\n|$)',
            r'([^\s]+\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|7z))',
        ]

        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info.file_name = match.group(1).strip()
                break

        # 提取扩展名
        if info.file_name:
            ext = Path(info.file_name).suffix.lower()
            if ext:
                info.file_ext = ext
                info.mime_type = cls.MIME_TYPES.get(ext)

        # 提取文件大小
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(KB|MB|GB)', text, re.IGNORECASE)
        if size_match:
            size_val = float(size_match.group(1))
            unit = size_match.group(2).upper()

            if unit == 'KB':
                info.file_size = int(size_val * 1024)
            elif unit == 'MB':
                info.file_size = int(size_val * 1024 * 1024)
            elif unit == 'GB':
                info.file_size = int(size_val * 1024 * 1024 * 1024)

        return info

    @classmethod
    def _get_media_description(cls, msg_type: MessageType) -> str:
        """获取媒体消息描述"""
        descriptions = {
            MessageType.IMAGE: "图片消息",
            MessageType.VIDEO: "视频消息",
            MessageType.VOICE: "语音消息",
            MessageType.EMOTION: "表情消息",
        }
        return descriptions.get(msg_type, "媒体消息")

    @classmethod
    def is_media_message(cls, text: str) -> bool:
        """
        检查是否是媒体消息

        Args:
            text: 消息文本

        Returns:
            是否是媒体消息
        """
        msg_type = cls.detect_type(text)
        return msg_type not in [MessageType.TEXT, MessageType.UNKNOWN]

    @classmethod
    def should_skip_for_training(cls, text: str) -> bool:
        """
        检查是否应该在训练中跳过

        Args:
            text: 消息文本

        Returns:
            是否应该跳过
        """
        msg_type = cls.detect_type(text)

        # 媒体消息和系统消息应该跳过
        skip_types = [
            MessageType.IMAGE,
            MessageType.VIDEO,
            MessageType.VOICE,
            MessageType.FILE,
            MessageType.SYSTEM,
            MessageType.UNKNOWN,
        ]

        return msg_type in skip_types

    @classmethod
    def get_summary(cls, text: str, max_length: int = 50) -> str:
        """
        获取消息摘要

        Args:
            text: 消息文本
            max_length: 最大长度

        Returns:
            消息摘要
        """
        if not text:
            return ""

        # 检测消息类型
        msg_type = cls.detect_type(text)

        if msg_type != MessageType.TEXT:
            # 媒体消息返回类型描述
            media_info = cls.parse(text)
            if media_info.file_name:
                return f"[{media_info.type.value}] {media_info.file_name}"
            return f"[{media_info.type.value}]"

        # 文本消息截断
        if len(text) <= max_length:
            return text

        return text[:max_length - 3] + "..."
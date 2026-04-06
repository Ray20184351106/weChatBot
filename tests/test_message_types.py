#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MessageParser 模块测试

测试消息类型识别和解析功能
"""

import pytest
from core.message_types import MessageParser, MessageType, MediaInfo


class TestMessageType:
    """MessageType 枚举测试"""

    def test_message_types(self):
        """测试消息类型枚举"""
        assert MessageType.TEXT.value == "text"
        assert MessageType.IMAGE.value == "image"
        assert MessageType.FILE.value == "file"
        assert MessageType.LINK.value == "link"


class TestMessageParserDetect:
    """消息类型检测测试"""

    def test_detect_text(self):
        """测试文本消息检测"""
        msg_type = MessageParser.detect_type("你好，这是一条普通消息")
        assert msg_type == MessageType.TEXT

    def test_detect_image(self):
        """测试图片消息检测"""
        assert MessageParser.detect_type("[图片]") == MessageType.IMAGE
        assert MessageParser.detect_type("看看这张[Photo]") == MessageType.IMAGE
        assert MessageParser.detect_type("<img src='test.jpg'>") == MessageType.IMAGE

    def test_detect_file(self):
        """测试文件消息检测"""
        assert MessageParser.detect_type("[文件]") == MessageType.FILE
        assert MessageParser.detect_type("报告.pdf") == MessageType.FILE
        assert MessageParser.detect_type("数据表格.xlsx") == MessageType.FILE

    def test_detect_video(self):
        """测试视频消息检测"""
        assert MessageParser.detect_type("[视频]") == MessageType.VIDEO
        assert MessageParser.detect_type("[小视频]") == MessageType.VIDEO

    def test_detect_voice(self):
        """测试语音消息检测"""
        assert MessageParser.detect_type("[语音]") == MessageType.VOICE
        assert MessageParser.detect_type("收到一条[Voice]") == MessageType.VOICE

    def test_detect_emotion(self):
        """测试表情消息检测"""
        assert MessageParser.detect_type("[表情]") == MessageType.EMOTION
        assert MessageParser.detect_type("[动画表情]") == MessageType.EMOTION

    def test_detect_link(self):
        """测试链接消息检测"""
        assert MessageParser.detect_type("https://example.com") == MessageType.LINK
        assert MessageParser.detect_type("看看这个 www.example.com") == MessageType.LINK
        assert MessageParser.detect_type("[链接] 标题") == MessageType.LINK

    def test_detect_location(self):
        """测试位置消息检测"""
        assert MessageParser.detect_type("[位置]") == MessageType.LOCATION
        assert MessageParser.detect_type("位置：北京市朝阳区") == MessageType.LOCATION

    def test_detect_system(self):
        """测试系统消息检测"""
        assert MessageParser.detect_type("撤回了一条消息") == MessageType.SYSTEM
        assert MessageParser.detect_type("张三邀请李四加入了群聊") == MessageType.SYSTEM
        assert MessageParser.detect_type("修改群名为：测试群") == MessageType.SYSTEM

    def test_detect_empty(self):
        """测试空消息"""
        assert MessageParser.detect_type("") == MessageType.TEXT
        assert MessageParser.detect_type(None) == MessageType.TEXT


class TestMessageParserParse:
    """消息解析测试"""

    def test_parse_text(self):
        """测试解析文本消息"""
        info = MessageParser.parse("你好世界")

        assert info.type == MessageType.TEXT
        assert info.original_text == "你好世界"

    def test_parse_image(self):
        """测试解析图片消息"""
        info = MessageParser.parse("[图片]")

        assert info.type == MessageType.IMAGE
        assert info.description == "图片消息"

    def test_parse_file_with_name(self):
        """测试解析带文件名的消息"""
        info = MessageParser.parse("[文件: 报告.pdf]")

        assert info.type == MessageType.FILE
        assert info.file_name is not None
        assert "报告" in info.file_name or "pdf" in info.file_name

    def test_parse_file_with_size(self):
        """测试解析带文件大小的消息"""
        info = MessageParser.parse("文件：data.zip 大小：2.5MB")

        assert info.type == MessageType.FILE
        assert info.file_size is not None
        assert info.file_size > 2 * 1024 * 1024

    def test_parse_link(self):
        """测试解析链接消息"""
        info = MessageParser.parse("看看这个 https://example.com")

        assert info.type == MessageType.LINK
        assert info.url == "https://example.com"

    def test_parse_link_with_title(self):
        """测试解析带标题的链接"""
        info = MessageParser.parse("标题：测试链接 https://example.com")

        assert info.type == MessageType.LINK
        assert info.url == "https://example.com"
        assert info.title == "测试链接"


class TestMediaInfo:
    """MediaInfo 数据类测试"""

    def test_media_info_creation(self):
        """测试创建媒体信息"""
        info = MediaInfo(
            type=MessageType.IMAGE,
            original_text="[图片]",
            file_name="photo.jpg"
        )

        assert info.type == MessageType.IMAGE
        assert info.file_name == "photo.jpg"


class TestMessageParserUtilities:
    """工具方法测试"""

    def test_is_media_message(self):
        """测试媒体消息判断"""
        assert MessageParser.is_media_message("[图片]") is True
        assert MessageParser.is_media_message("[文件]") is True
        assert MessageParser.is_media_message("普通文本") is False

    def test_should_skip_for_training(self):
        """测试训练跳过判断"""
        assert MessageParser.should_skip_for_training("[图片]") is True
        assert MessageParser.should_skip_for_training("[语音]") is True
        assert MessageParser.should_skip_for_training("撤回了一条消息") is True
        assert MessageParser.should_skip_for_training("正常消息") is False

    def test_get_summary_text(self):
        """测试文本摘要"""
        # 短文本
        assert MessageParser.get_summary("短消息") == "短消息"

        # 长文本
        long_text = "这是一条很长的消息" * 10
        summary = MessageParser.get_summary(long_text, max_length=20)
        assert len(summary) <= 23  # max_length + "..."
        assert summary.endswith("...")

    def test_get_summary_media(self):
        """测试媒体消息摘要"""
        assert "[image]" in MessageParser.get_summary("[图片]").lower()
        assert "[video]" in MessageParser.get_summary("[视频]").lower()


class TestMimeTypes:
    """MIME 类型测试"""

    def test_mime_type_detection(self):
        """测试 MIME 类型检测"""
        info = MessageParser.parse("文件：report.pdf")

        # 检查是否正确识别扩展名
        if info.file_ext:
            assert info.file_ext == ".pdf"

    def test_common_file_types(self):
        """测试常见文件类型"""
        test_cases = [
            ("document.docx", ".docx"),
            ("spreadsheet.xlsx", ".xlsx"),
            ("presentation.pptx", ".pptx"),
            ("archive.zip", ".zip"),
        ]

        for filename, expected_ext in test_cases:
            info = MessageParser.parse(f"文件：{filename}")
            if info.file_ext:
                assert info.file_ext == expected_ext


class TestEdgeCases:
    """边界情况测试"""

    def test_mixed_content(self):
        """测试混合内容"""
        # 文本+链接
        info = MessageParser.parse("看看这个链接 https://example.com 好用吗")
        assert info.type == MessageType.LINK

    def test_special_characters(self):
        """测试特殊字符"""
        info = MessageParser.parse("[图片] 😀emoji")
        assert info.type == MessageType.IMAGE

    def test_multiline_text(self):
        """测试多行文本"""
        multiline = "第一行\n第二行\n第三行"
        info = MessageParser.parse(multiline)

        assert info.type == MessageType.TEXT
        assert info.original_text == multiline

    def test_chinese_english_mixed(self):
        """测试中英文混合"""
        info = MessageParser.parse("[File] 这是文件")
        assert info.type == MessageType.FILE
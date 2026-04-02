#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChatFerry 封装模块

提供微信消息收发、联系人管理等功能的统一接口
"""

import ctypes
import time
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger

# 尝试导入 wcferry
try:
    from wcferry import Wcf, WxMsg
except ImportError:
    logger.warning("wcferry 未安装，部分功能不可用")
    Wcf = None
    WxMsg = None


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = 1
    IMAGE = 3
    VOICE = 34
    VIDEO = 43
    FILE = 49
    SYSTEM = 10000


@dataclass
class Message:
    """消息数据类"""
    id: int
    type: MessageType
    sender: str
    content: str
    room_id: Optional[str] = None
    timestamp: int = 0
    is_self: bool = False
    is_group: bool = False


class WeChatBot:
    """
    微信机器人封装类

    基于 WeChatFerry 实现微信消息的收发功能
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 10086):
        """
        初始化微信机器人

        Args:
            host: RPC 服务器地址
            port: RPC 服务器端口
        """
        self.host = host
        self.port = port
        self.wcf: Optional[Wcf] = None
        self._running = False
        self._callbacks: List[Callable[[Message], None]] = []

        logger.info(f"初始化 WeChatBot: {host}:{port}")

    def connect(self) -> bool:
        """
        连接到微信

        Returns:
            连接是否成功
        """
        if Wcf is None:
            logger.error("wcferry 未安装")
            return False

        try:
            self.wcf = Wcf(self.host, self.port)
            self._running = True
            logger.info("微信连接成功")
            return True
        except Exception as e:
            logger.error(f"连接失败：{e}")
            return False

    def disconnect(self):
        """断开微信连接"""
        self._running = False
        if self.wcf:
            try:
                self.wcf.cleanup()
            except Exception as e:
                logger.error(f"断开连接异常：{e}")
            self.wcf = None
        logger.info("已断开微信连接")

    def is_login(self) -> bool:
        """
        检查登录状态

        Returns:
            是否已登录
        """
        if not self.wcf:
            return False
        try:
            return self.wcf.is_login()
        except Exception:
            return False

    def get_self_info(self) -> Optional[Dict[str, Any]]:
        """
        获取当前账号信息

        Returns:
            账号信息字典
        """
        if not self.wcf:
            return None
        try:
            info = self.wcf.get_self_info()
            return {
                "wxid": info.get("wxid"),
                "name": info.get("name"),
                "mobile": info.get("mobile"),
                "home_dir": info.get("home_dir")
            }
        except Exception as e:
            logger.error(f"获取账号信息失败：{e}")
            return None

    def get_contacts(self) -> List[Dict[str, Any]]:
        """
        获取联系人列表

        Returns:
            联系人列表
        """
        if not self.wcf:
            return []
        try:
            return self.wcf.get_contacts()
        except Exception as e:
            logger.error(f"获取联系人失败：{e}")
            return []

    def send_text(self, content: str, receiver: str, at_list: Optional[List[str]] = None) -> bool:
        """
        发送文本消息

        Args:
            content: 消息内容
            receiver: 接收者 (wxid 或 room_id)
            at_list: @的用户列表 (群聊时使用)

        Returns:
            发送是否成功
        """
        if not self.wcf:
            logger.error("未连接微信")
            return False

        try:
            if at_list:
                self.wcf.send_text(content, receiver, at_list)
            else:
                self.wcf.send_text(content, receiver)
            logger.debug(f"发送消息到 {receiver}: {content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"发送消息失败：{e}")
            return False

    def send_image(self, image_path: str, receiver: str) -> bool:
        """
        发送图片消息

        Args:
            image_path: 图片路径
            receiver: 接收者

        Returns:
            发送是否成功
        """
        if not self.wcf:
            return False

        try:
            self.wcf.send_image(image_path, receiver)
            logger.debug(f"发送图片到 {receiver}: {image_path}")
            return True
        except Exception as e:
            logger.error(f"发送图片失败：{e}")
            return False

    def enable_msg_receiving(self) -> bool:
        """
        开启消息接收

        Returns:
            操作是否成功
        """
        if not self.wcf:
            return False
        try:
            self.wcf.enable_receiving_msg()
            logger.info("已开启消息接收")
            return True
        except Exception as e:
            logger.error(f"开启消息接收失败：{e}")
            return False

    def disable_msg_receiving(self) -> bool:
        """
        关闭消息接收

        Returns:
            操作是否成功
        """
        if not self.wcf:
            return False
        try:
            self.wcf.disable_receiving_msg()
            logger.info("已关闭消息接收")
            return True
        except Exception as e:
            logger.error(f"关闭消息接收失败：{e}")
            return False

    def start_listening(self, callback: Callable[[Message], None]):
        """
        开始监听消息

        Args:
            callback: 收到消息时的回调函数
        """
        if not self.wcf:
            logger.error("未连接微信")
            return

        self._callbacks.append(callback)
        self._running = True

        def message_handler(wx_msg: WxMsg):
            """消息处理函数"""
            msg = Message(
                id=wx_msg.id,
                type=MessageType(wx_msg.type) if hasattr(MessageType, wx_msg.type) else MessageType.TEXT,
                sender=wx_msg.sender,
                content=wx_msg.content,
                room_id=wx_msg.roomid if wx_msg.roomid else None,
                timestamp=wx_msg.ts,
                is_self=wx_msg.is_self,
                is_group=wx_msg.is_group
            )
            for cb in self._callbacks:
                try:
                    cb(msg)
                except Exception as e:
                    logger.error(f"消息回调异常：{e}")

        self.wcf.enable_receiving_msg()
        self.wcf.listen_message(message_handler)
        logger.info("开始监听消息")

    def stop_listening(self):
        """停止监听消息"""
        self._running = False
        self.disable_msg_receiving()
        logger.info("停止监听消息")

    def get_chat_history(self, room_id: Optional[str] = None, count: int = 100) -> List[Message]:
        """
        获取聊天记录 (通过数据库查询)

        Args:
            room_id: 群聊/会话 ID，None 表示所有会话
            count: 获取数量

        Returns:
            消息列表
        """
        # TODO: 实现数据库查询
        logger.warning("get_chat_history 暂未实现")
        return []

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChatHook 封装模块

提供微信消息收发、联系人管理等功能的统一接口
支持微信版本：3.9.5.81 ~ 4.1.1
"""

from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger

# 尝试导入 wxhook
try:
    from wxhook import Bot
    from wxhook import events
    from wxhook.model import Event
except ImportError:
    logger.warning("wxhook 未安装，请运行：pip install wxhook")
    Bot = None
    events = None
    Event = None


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
    id: str
    type: MessageType
    sender: str
    sender_name: str
    content: str
    room_id: Optional[str] = None
    is_group: bool = False
    is_self: bool = False
    timestamp: int = 0

    @classmethod
    def from_event(cls, event: Event) -> "Message":
        """从 Event 对象创建 Message"""
        return cls(
            id=str(event.id),
            type=MessageType.TEXT if event.type == "text" else MessageType.TEXT,
            sender=event.sender,
            sender_name=event.sender_name,
            content=event.content,
            room_id=event.room_id,
            is_group=event.is_group,
            is_self=event.is_self,
            timestamp=event.timestamp
        )


class WeChatBot:
    """
    微信机器人封装类

    基于 WeChatHook 实现微信消息的收发功能
    支持微信版本：3.9.5.81 ~ 4.1.1
    """

    def __init__(self):
        """
        初始化微信机器人
        """
        self.bot: Optional[Bot] = None
        self._running = False
        self._callbacks: List[Callable[[Message], None]] = []
        self._user_wxid: Optional[str] = None

        logger.info("初始化 WeChatBot (WeChatHook)")

    def connect(self) -> bool:
        """
        连接到微信

        Returns:
            连接是否成功
        """
        if Bot is None:
            logger.error("wxhook 未安装，请运行：pip install wxhook")
            return False

        try:
            # 初始化 Bot
            self.bot = Bot(
                on_login=self._on_login,
                on_start=self._on_start,
                on_stop=self._on_stop
            )
            self._running = True
            logger.info("微信 Bot 初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化失败：{e}")
            return False

    def disconnect(self):
        """断开微信连接"""
        self._running = False
        if self.bot:
            try:
                self.bot.stop()
            except Exception as e:
                logger.error(f"断开连接异常：{e}")
            self.bot = None
        logger.info("已断开微信连接")

    def _on_login(self, bot: Bot, event: Event):
        """登录成功回调"""
        logger.info(f"微信登录成功：{event.sender_name}")
        self._user_wxid = event.sender

    def _on_start(self, bot: Bot):
        """微信客户端打开回调"""
        logger.info("微信客户端已启动")

    def _on_stop(self, bot: Bot):
        """微信客户端关闭回调"""
        logger.info("微信客户端已关闭")
        self._running = False

    def is_login(self) -> bool:
        """
        检查登录状态

        Returns:
            是否已登录
        """
        return self._running and self._user_wxid is not None

    def get_self_info(self) -> Optional[Dict[str, Any]]:
        """
        获取当前账号信息

        Returns:
            账号信息字典
        """
        if not self._user_wxid:
            return None
        return {
            "wxid": self._user_wxid,
            "name": "未知",  # WeChatHook 需要额外调用获取
            "mobile": "",
            "home_dir": ""
        }

    def get_contacts(self) -> List[Dict[str, Any]]:
        """
        获取联系人列表

        Returns:
            联系人列表
        """
        if not self.bot:
            return []
        try:
            # WeChatHook 的 API 调用
            contacts = self.bot.get_contacts()
            return contacts if contacts else []
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
        if not self.bot:
            logger.error("未连接微信")
            return False

        try:
            if at_list and len(at_list) > 0:
                # 群聊 @ 消息
                self.bot.send_at(receiver, content, at_list)
            else:
                self.bot.send_text(receiver, content)
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
        if not self.bot:
            return False

        try:
            self.bot.send_image(receiver, image_path)
            logger.debug(f"发送图片到 {receiver}: {image_path}")
            return True
        except Exception as e:
            logger.error(f"发送图片失败：{e}")
            return False

    def send_file(self, file_path: str, receiver: str) -> bool:
        """
        发送文件消息

        Args:
            file_path: 文件路径
            receiver: 接收者

        Returns:
            发送是否成功
        """
        if not self.bot:
            return False

        try:
            self.bot.send_file(receiver, file_path)
            logger.debug(f"发送文件到 {receiver}: {file_path}")
            return True
        except Exception as e:
            logger.error(f"发送文件失败：{e}")
            return False

    def start_listening(self, callback: Callable[[Message], None]):
        """
        开始监听消息

        Args:
            callback: 收到消息时的回调函数
        """
        if not self.bot:
            logger.error("未连接微信")
            return

        self._callbacks.append(callback)

        # 注册消息处理器
        @self.bot.handle(events.TEXT_MESSAGE)
        def on_text_message(event: Event):
            """文本消息处理"""
            msg = Message.from_event(event)
            for cb in self._callbacks:
                try:
                    cb(msg)
                except Exception as e:
                    logger.error(f"消息回调异常：{e}")

        # 启动 Bot
        logger.info("开始监听消息...")
        self.bot.run()

    def stop_listening(self):
        """停止监听消息"""
        self._running = False
        logger.info("停止监听消息")

    def get_chat_history(self, room_id: Optional[str] = None, count: int = 100) -> List[Message]:
        """
        获取聊天记录

        Args:
            room_id: 群聊/会话 ID，None 表示所有会话
            count: 获取数量

        Returns:
            消息列表
        """
        # TODO: 实现聊天记录获取
        logger.warning("get_chat_history 暂未实现")
        return []

    def get_room_members(self, room_id: str) -> List[Dict[str, Any]]:
        """
        获取群成员列表

        Args:
            room_id: 群 ID

        Returns:
            群成员列表
        """
        if not self.bot:
            return []
        try:
            return self.bot.get_room_members(room_id)
        except Exception as e:
            logger.error(f"获取群成员失败：{e}")
            return []

    def quit_room(self, room_id: str) -> bool:
        """
        退出群聊

        Args:
            room_id: 群 ID

        Returns:
            操作是否成功
        """
        if not self.bot:
            return False
        try:
            self.bot.quit_room(room_id)
            logger.info(f"已退出群聊：{room_id}")
            return True
        except Exception as e:
            logger.error(f"退出群聊失败：{e}")
            return False

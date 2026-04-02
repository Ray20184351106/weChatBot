#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息收集器模块

负责收集和存储用户的聊天记录，用于后续训练
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from loguru import logger
from .wechat_bot import Message


@dataclass
class ChatPair:
    """
    对话对数据类

    用于存储一问一答的对话对
    """
    sender_id: str           # 对方 ID
    sender_name: str         # 对方昵称
    incoming_message: str    # 收到的消息
    outgoing_message: str    # 我的回复
    timestamp: str           # 时间戳
    room_id: Optional[str]   # 群聊 ID (如果是群聊)


class MessageCollector:
    """
    消息收集器

    自动收集用户的聊天数据，构建训练数据集
    """

    def __init__(self, data_dir: str = "data/chat_history"):
        """
        初始化消息收集器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 当前会话缓存
        self._pending_messages: Dict[str, List[Message]] = {}  # room_id -> messages
        self._user_wxid: Optional[str] = None

        logger.info(f"消息收集器已初始化，数据目录：{self.data_dir}")

    def set_user_wxid(self, wxid: str):
        """设置当前用户的 wxid"""
        self._user_wxid = wxid
        logger.info(f"设置用户 wxid: {wxid}")

    def on_message_received(self, message: Message):
        """
        收到消息回调

        Args:
            message: 收到的消息
        """
        room_id = message.room_id or message.sender

        # 初始化该会话的缓存
        if room_id not in self._pending_messages:
            self._pending_messages[room_id] = []

        # 添加消息到缓存
        self._pending_messages[room_id].append(message)
        logger.debug(f"收到消息 [{room_id}]: {message.content[:30]}...")

        # 检查是否有待回复的消息对
        self._try_save_chat_pair(room_id)

    def on_message_sent(self, content: str, receiver: str):
        """
        发送消息回调 (需要外部调用)

        Args:
            content: 发送的内容
            receiver: 接收者
        """
        # 创建一个虚拟的发送消息
        sent_msg = Message(
            id=0,
            type=None,
            sender=self._user_wxid or "self",
            content=content,
            room_id=receiver if receiver.endswith("@chatroom") else None,
            timestamp=int(datetime.now().timestamp()),
            is_self=True,
            is_group=receiver.endswith("@chatroom")
        )

        room_id = receiver
        if room_id not in self._pending_messages:
            self._pending_messages[room_id] = []

        self._pending_messages[room_id].append(sent_msg)
        logger.debug(f"发送消息 [{receiver}]: {content[:30]}...")

        # 检查是否可以保存对话对
        self._try_save_chat_pair(room_id)

    def _try_save_chat_pair(self, room_id: str):
        """
        尝试保存对话对

        检测缓存中的消息序列，如果形成完整的对话对则保存
        """
        messages = self._pending_messages.get(room_id, [])

        if len(messages) < 2:
            return

        # 查找最近的接收 - 发送对
        for i in range(len(messages) - 1):
            msg1 = messages[i]
            msg2 = messages[i + 1]

            # 检查是否形成对话对 (收到 -> 发送)
            if not msg1.is_self and msg2.is_self:
                chat_pair = ChatPair(
                    sender_id=msg1.sender,
                    sender_name=msg1.sender,  # TODO: 从联系人获取昵称
                    incoming_message=msg1.content,
                    outgoing_message=msg2.content,
                    timestamp=datetime.fromtimestamp(msg2.timestamp).isoformat(),
                    room_id=room_id if msg1.is_group else None
                )
                self._save_chat_pair(chat_pair, room_id)

                # 标记为已处理
                msg1.is_self = True  # 临时标记，避免重复处理
                break

    def _save_chat_pair(self, chat_pair: ChatPair, room_id: str):
        """
        保存对话对到文件

        Args:
            chat_pair: 对话对
            room_id: 会话 ID
        """
        # 按会话分文件存储
        file_path = self.data_dir / f"{self._safe_filename(room_id)}.jsonl"

        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(chat_pair), ensure_ascii=False) + "\n")
            logger.debug(f"已保存对话对到 {file_path}")
        except Exception as e:
            logger.error(f"保存对话对失败：{e}")

    def _safe_filename(self, name: str) -> str:
        """生成安全的文件名"""
        return "".join(c for c in name if c.isalnum() or c in "._-")

    def get_all_chat_pairs(self) -> List[ChatPair]:
        """
        获取所有收集的对话对

        Returns:
            对话对列表
        """
        all_pairs = []

        for file_path in self.data_dir.glob("*.jsonl"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        data = json.loads(line.strip())
                        all_pairs.append(ChatPair(**data))
            except Exception as e:
                logger.error(f"读取文件失败 {file_path}: {e}")

        logger.info(f"共加载 {len(all_pairs)} 条对话对")
        return all_pairs

    def get_training_data(self, format: str = "alpaca") -> List[Dict[str, Any]]:
        """
        生成训练数据

        Args:
            format: 数据格式 (alpaca, chatml, custom)

        Returns:
            训练数据列表
        """
        pairs = self.get_all_chat_pairs()
        training_data = []

        for pair in pairs:
            if format == "alpaca":
                item = {
                    "instruction": "模拟用户的聊天风格进行回复",
                    "input": pair.incoming_message,
                    "output": pair.outgoing_message
                }
            elif format == "chatml":
                item = {
                    "messages": [
                        {"role": "user", "content": pair.incoming_message},
                        {"role": "assistant", "content": pair.outgoing_message}
                    ]
                }
            else:  # custom
                item = {
                    "prompt": pair.incoming_message,
                    "completion": pair.outgoing_message
                }

            training_data.append(item)

        logger.info(f"生成 {len(training_data)} 条训练数据 (格式：{format})")
        return training_data

    def export_training_data(self, output_path: str, format: str = "alpaca"):
        """
        导出训练数据到文件

        Args:
            output_path: 输出文件路径
            format: 数据格式
        """
        data = self.get_training_data(format)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                if output_file.suffix == ".json":
                    json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    for item in data:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
            logger.info(f"训练数据已导出到 {output_path}")
        except Exception as e:
            logger.error(f"导出训练数据失败：{e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计数据

        Returns:
            统计信息字典
        """
        pairs = self.get_all_chat_pairs()

        # 按会话统计
        room_stats = {}
        for pair in pairs:
            room_id = pair.room_id or pair.sender_id
            if room_id not in room_stats:
                room_stats[room_id] = 0
            room_stats[room_id] += 1

        return {
            "total_pairs": len(pairs),
            "total_rooms": len(room_stats),
            "rooms": room_stats,
            "data_dir": str(self.data_dir)
        }

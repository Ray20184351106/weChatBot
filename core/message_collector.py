#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息收集器模块

负责收集和存储用户的聊天记录，用于后续训练
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

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

    改进版：支持更可靠的对话对检测
    """

    def __init__(self, data_dir: str = "data/chat_history"):
        """
        初始化消息收集器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 当前会话缓存 - 改进：使用更详细的结构
        # room_id -> {"incoming": [], "outgoing": [], "pairs": []}
        self._session_cache: Dict[str, Dict[str, List]] = defaultdict(lambda: {
            "incoming": [],      # 收到的消息列表
            "outgoing": [],      # 发送的消息列表
            "pending_reply": None  # 等待回复的收到的消息
        })
        self._user_wxid: Optional[str] = None

        # 消息历史用于去重
        self._message_hashes: Dict[str, set] = defaultdict(set)

        # 对话配对配置
        self._pair_timeout = 300  # 配对超时时间（秒）
        self._max_pending = 10    # 最大待配对消息数

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

        # 去重检查
        msg_hash = self._hash_message(message.content, "incoming")
        if msg_hash in self._message_hashes[room_id]:
            logger.debug(f"消息已存在，跳过：{message.content[:30]}...")
            return

        self._message_hashes[room_id].add(msg_hash)

        # 添加到缓存
        session = self._session_cache[room_id]
        session["incoming"].append({
            "content": message.content,
            "sender": message.sender,
            "timestamp": message.timestamp,
            "hash": msg_hash
        })

        # 设置为等待回复状态
        session["pending_reply"] = {
            "content": message.content,
            "sender": message.sender,
            "timestamp": message.timestamp
        }

        # 限制缓存大小
        if len(session["incoming"]) > self._max_pending:
            session["incoming"].pop(0)

        logger.info(f"[收集] 收到消息 [{message.sender}]: {message.content[:30]}...")

    def on_message_sent(self, content: str, receiver: str):
        """
        发送消息回调 (用户手动回复或自动回复)

        Args:
            content: 发送的内容
            receiver: 接收者
        """
        room_id = receiver

        # 去重检查
        msg_hash = self._hash_message(content, "outgoing")
        if msg_hash in self._message_hashes[room_id]:
            logger.debug(f"发送消息已存在，跳过：{content[:30]}...")
            return

        self._message_hashes[room_id].add(msg_hash)

        # 添加到缓存
        session = self._session_cache[room_id]
        session["outgoing"].append({
            "content": content,
            "timestamp": int(time.time()),
            "hash": msg_hash
        })

        # 限制缓存大小
        if len(session["outgoing"]) > self._max_pending:
            session["outgoing"].pop(0)

        logger.info(f"[收集] 发送消息 -> [{receiver}]: {content[:30]}...")

        # 尝试配对
        self._try_pair_messages(room_id)

    def _hash_message(self, content: str, msg_type: str) -> str:
        """生成消息哈希用于去重"""
        return f"{msg_type}:{hash(content)}"

    def _try_pair_messages(self, room_id: str):
        """
        尝试配对消息并保存对话对

        改进版：基于时间窗口和内容匹配
        """
        session = self._session_cache[room_id]
        pending = session["pending_reply"]

        if not pending:
            logger.debug("没有等待回复的消息")
            return

        outgoing = session["outgoing"]
        if not outgoing:
            return

        # 获取最新的发送消息
        latest_outgoing = outgoing[-1]

        # 检查时间窗口（发送消息应该在收到消息之后的一段时间内）
        time_diff = latest_outgoing["timestamp"] - pending["timestamp"]

        if time_diff < 0 or time_diff > self._pair_timeout:
            logger.debug(f"时间窗口不匹配：{time_diff}秒")
            return

        # 创建对话对
        chat_pair = ChatPair(
            sender_id=pending["sender"],
            sender_name=pending["sender"],
            incoming_message=pending["content"],
            outgoing_message=latest_outgoing["content"],
            timestamp=datetime.fromtimestamp(latest_outgoing["timestamp"]).isoformat(),
            room_id=room_id if "@" in room_id else None
        )

        # 保存对话对
        self._save_chat_pair(chat_pair, room_id)

        # 清除等待状态
        session["pending_reply"] = None

        logger.info(f"[配对成功] 对话对已保存：{pending['content'][:20]}... -> {latest_outgoing['content'][:20]}...")

    def _save_chat_pair(self, chat_pair: ChatPair, room_id: str):
        """
        保存对话对到文件

        Args:
            chat_pair: 对话对
            room_id: 会话 ID
        """
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

    def get_pending_status(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        获取等待回复状态

        Args:
            room_id: 会话 ID

        Returns:
            等待回复的消息信息，或 None
        """
        session = self._session_cache.get(room_id)
        if session and session["pending_reply"]:
            return session["pending_reply"]
        return None

    def clear_session(self, room_id: str):
        """
        清除指定会话的缓存

        Args:
            room_id: 会话 ID
        """
        if room_id in self._session_cache:
            del self._session_cache[room_id]
        if room_id in self._message_hashes:
            del self._message_hashes[room_id]
        logger.debug(f"已清除会话缓存：{room_id}")

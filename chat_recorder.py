#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聊天记录收集器

用于收集微信聊天记录，生成训练数据
支持 OCR 实时监听和手动记录两种方式
支持标注联系人，区分不同聊天风格
"""

import sys
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict, field

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} | {message}")

from core.wechat_bot import WeChatBot, WeChatConfig


@dataclass
class ChatMessage:
    """聊天消息"""
    content: str
    is_self: bool  # True=自己发送, False=对方发送
    timestamp: str
    sender: str = ""


@dataclass
class ChatPair:
    """对话对"""
    incoming: str           # 收到的消息
    outgoing: str           # 我的回复
    timestamp: str
    contact_name: str = ""  # 联系人名称（用于区分不同聊天风格）
    contact_id: str = ""    # 联系人ID
    tags: List[str] = field(default_factory=list)  # 标签（如：朋友、同事、家人等）


class ChatRecorder:
    """
    聊天记录收集器

    收集聊天记录并生成训练数据
    支持标注联系人，区分不同聊天风格
    """

    def __init__(self, data_dir: str = "data/chat_history"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.bot: Optional[WeChatBot] = None
        self._running = False
        self._listen_thread: Optional[threading.Thread] = None

        # 当前联系人信息
        self._current_contact: str = ""
        self._current_contact_id: str = ""
        self._current_tags: List[str] = []

        # 当前聊天窗口的消息缓存
        self._messages: List[ChatMessage] = []
        self._last_ocr_text: str = ""

        # 已收集的对话对
        self._chat_pairs: List[ChatPair] = []
        self._pairs_file = self.data_dir / "chat_pairs.jsonl"

        # 联系人列表（用于快速切换）
        self._contacts: Dict[str, str] = {}  # name -> id
        self._contacts_file = self.data_dir / "contacts.json"
        self._load_contacts()

        # 加载已有的对话对
        self._load_existing_pairs()

        logger.info(f"聊天记录收集器已初始化")
        logger.info(f"已有对话对: {len(self._chat_pairs)} 条")
        logger.info(f"已保存联系人: {len(self._contacts)} 个")

    def _load_contacts(self):
        """加载联系人列表"""
        if self._contacts_file.exists():
            try:
                with open(self._contacts_file, "r", encoding="utf-8") as f:
                    self._contacts = json.load(f)
            except Exception as e:
                logger.error(f"加载联系人失败: {e}")

    def _save_contacts(self):
        """保存联系人列表"""
        try:
            with open(self._contacts_file, "w", encoding="utf-8") as f:
                json.dump(self._contacts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存联系人失败: {e}")

    def _load_existing_pairs(self):
        """加载已有的对话对"""
        if self._pairs_file.exists():
            try:
                with open(self._pairs_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line.strip())
                            # 兼容旧格式
                            if "contact_name" not in data:
                                data["contact_name"] = data.get("sender", "")
                            if "tags" not in data:
                                data["tags"] = []
                            self._chat_pairs.append(ChatPair(**data))
            except Exception as e:
                logger.error(f"加载对话对失败: {e}")

    def set_contact(self, name: str, contact_id: str = "", tags: List[str] = None):
        """
        设置当前联系人

        Args:
            name: 联系人名称/昵称
            contact_id: 联系人ID（可选）
            tags: 标签列表，如 ["朋友", "大学同学"]
        """
        self._current_contact = name
        self._current_contact_id = contact_id or name
        self._current_tags = tags or []

        # 保存到联系人列表
        self._contacts[name] = self._current_contact_id
        self._save_contacts()

        # 清空消息缓存（新联系人）
        self._messages = []

        logger.info(f"当前联系人: {name}")
        if self._current_tags:
            logger.info(f"标签: {', '.join(self._current_tags)}")

    def get_contact(self) -> str:
        """获取当前联系人"""
        return self._current_contact

    def list_contacts(self) -> List[str]:
        """列出所有已保存的联系人"""
        return list(self._contacts.keys())

    def connect(self) -> bool:
        """连接微信"""
        config = WeChatConfig.from_yaml("config/config.yaml")
        self.bot = WeChatBot(config)
        return self.bot.connect()

    def disconnect(self):
        """断开连接"""
        self.stop_recording()
        if self.bot:
            self.bot.disconnect()
            self.bot = None

    def start_recording(self, callback: Optional[Callable[[ChatPair], None]] = None):
        """
        开始记录聊天

        Args:
            callback: 新对话对产生时的回调
        """
        if not self.bot or not self.bot._running:
            logger.error("请先连接微信")
            return

        if not self._current_contact:
            logger.warning("未设置联系人，将使用默认设置")
            logger.warning("建议使用 'contact <名称>' 设置联系人")

        self._running = True
        self._callback = callback

        self._listen_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._listen_thread.start()

        logger.info("开始记录聊天...")
        logger.info("请正常使用微信聊天，系统会自动记录对话")

    def stop_recording(self):
        """停止记录"""
        self._running = False
        if self._listen_thread:
            self._listen_thread.join(timeout=3)
        logger.info("停止记录")

    def _record_loop(self):
        """记录循环"""
        check_interval = 2.0

        while self._running:
            time.sleep(check_interval)

            try:
                # 检查窗口
                if not self.bot or not self.bot.main_window:
                    continue

                if not self.bot.main_window.is_visible():
                    continue

                # 获取聊天窗口
                chat_panel = self.bot._find_chat_window()
                if not chat_panel:
                    continue

                # OCR 识别
                region = self.bot._calculate_ocr_region(chat_panel)
                ocr_text = self.bot._ocr_screen(*region)

                if not ocr_text or ocr_text == self._last_ocr_text:
                    continue

                # 检测新消息
                self._process_ocr_text(ocr_text)
                self._last_ocr_text = ocr_text

            except Exception as e:
                logger.debug(f"记录循环错误: {e}")

    def _process_ocr_text(self, ocr_text: str):
        """处理 OCR 文本，提取新消息"""
        # 比较上次的内容，找出新增部分
        if not self._last_ocr_text:
            return

        # 找出新增的内容
        new_content = ocr_text.replace(self._last_ocr_text, "").strip()
        if not new_content:
            return

        # 解析新消息
        lines = new_content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or len(line) < 2:
                continue

            # 判断是否是自己发送的消息
            is_self = self._detect_self_message(line)

            msg = ChatMessage(
                content=line,
                is_self=is_self,
                timestamp=datetime.now().isoformat()
            )

            self._messages.append(msg)
            logger.debug(f"{'[我]' if is_self else '[对方]'} {line[:30]}...")

            # 尝试配对
            self._try_make_pair()

    def _detect_self_message(self, text: str) -> bool:
        """检测是否是自己发送的消息"""
        self_markers = ["我:", "我：", "Me:"]
        for marker in self_markers:
            if text.startswith(marker):
                return True
        return False

    def record_sent_message(self, content: str):
        """
        手动记录发送的消息

        Args:
            content: 发送的消息内容
        """
        msg = ChatMessage(
            content=content,
            is_self=True,
            timestamp=datetime.now().isoformat()
        )
        self._messages.append(msg)
        logger.info(f"[我] {content[:30]}...")

        # 尝试配对
        self._try_make_pair()

    def _try_make_pair(self):
        """尝试形成对话对"""
        if len(self._messages) < 2:
            return

        # 查找最近的 对方消息 -> 我的消息
        for i in range(len(self._messages) - 1, 0, -1):
            prev_msg = self._messages[i - 1]
            curr_msg = self._messages[i]

            # 如果前一条不是自己发的，当前是自己发的，则配对
            if not prev_msg.is_self and curr_msg.is_self:
                pair = ChatPair(
                    incoming=prev_msg.content,
                    outgoing=curr_msg.content,
                    timestamp=curr_msg.timestamp,
                    contact_name=self._current_contact,
                    contact_id=self._current_contact_id,
                    tags=self._current_tags.copy()
                )

                # 避免重复
                if not any(p.incoming == pair.incoming and p.outgoing == pair.outgoing
                          for p in self._chat_pairs):
                    self._chat_pairs.append(pair)
                    self._save_pair(pair)

                    contact_info = f"[{self._current_contact}]" if self._current_contact else ""
                    logger.info(f"新对话对 {contact_info}: [{pair.incoming[:20]}...] -> [{pair.outgoing[:20]}...]")
                    logger.info(f"当前共 {len(self._chat_pairs)} 条对话对")

                    # 回调
                    if self._callback:
                        self._callback(pair)

                # 移除已处理的消息
                self._messages = self._messages[i + 1:]
                break

    def _save_pair(self, pair: ChatPair):
        """保存对话对到文件"""
        try:
            with open(self._pairs_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"保存对话对失败: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        # 按联系人统计
        contact_stats = {}
        for pair in self._chat_pairs:
            name = pair.contact_name or "未知"
            if name not in contact_stats:
                contact_stats[name] = 0
            contact_stats[name] += 1

        return {
            "total_pairs": len(self._chat_pairs),
            "recent_messages": len(self._messages),
            "data_dir": str(self.data_dir),
            "contact_stats": contact_stats,
            "total_contacts": len(contact_stats)
        }

    def export_training_data(self, output_path: str, format: str = "alpaca",
                            contact_filter: str = None):
        """
        导出训练数据

        Args:
            output_path: 输出文件路径
            format: 数据格式 (alpaca, chatml, simple)
            contact_filter: 只导出指定联系人的数据
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        training_data = []
        pairs_to_export = self._chat_pairs

        # 过滤联系人
        if contact_filter:
            pairs_to_export = [p for p in pairs_to_export if p.contact_name == contact_filter]
            logger.info(f"筛选联系人 '{contact_filter}': {len(pairs_to_export)} 条")

        for pair in pairs_to_export:
            if format == "alpaca":
                # 包含联系人信息的 instruction
                instruction = "模拟用户的聊天风格进行微信回复"
                if pair.contact_name:
                    instruction += f"（与{pair.contact_name}的对话风格）"

                item = {
                    "instruction": instruction,
                    "input": pair.incoming,
                    "output": pair.outgoing,
                    "contact": pair.contact_name,
                    "tags": pair.tags
                }
            elif format == "chatml":
                # 系统消息包含联系人信息
                system_msg = "你是一个微信聊天助手，模拟用户的聊天风格进行回复。"
                if pair.contact_name:
                    system_msg += f"当前正在与{pair.contact_name}聊天。"

                item = {
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": pair.incoming},
                        {"role": "assistant", "content": pair.outgoing}
                    ],
                    "contact": pair.contact_name,
                    "tags": pair.tags
                }
            else:  # simple
                item = {
                    "prompt": pair.incoming,
                    "completion": pair.outgoing,
                    "contact": pair.contact_name
                }

            training_data.append(item)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)

        logger.info(f"导出 {len(training_data)} 条训练数据到: {output_path}")

    def clear_messages(self):
        """清空消息缓存"""
        self._messages = []
        logger.info("消息缓存已清空")


def interactive_mode():
    """交互式收集模式"""
    print("=" * 60)
    print(" 聊天记录收集器 (支持联系人标注)")
    print("=" * 60)
    print("""
使用说明:
1. 先用 'contact <名称>' 设置当前联系人
2. 当收到消息时，用 'send <回复>' 记录并发送
3. 可以添加标签: 'tag 朋友 同学' 等

命令:
  contact <名称>     - 设置当前联系人
  tag <标签...>      - 添加标签（如: tag 朋友 同事）
  send <消息>        - 记录发送的消息
  contacts           - 列出已保存的联系人
  stats              - 查看统计
  export [联系人]    - 导出训练数据(可指定联系人)
  clear              - 清空缓存
  quit               - 退出
    """)

    recorder = ChatRecorder()

    print("\n连接微信...")
    if not recorder.connect():
        print("连接失败!")
        return

    print("连接成功!")
    print("\n请先用 'contact <名称>' 设置联系人")
    print("然后开始记录对话\n")

    # 启动记录
    recorder.start_recording()

    running = True
    while running:
        try:
            cmd = input("\n> ").strip()
            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()

            if action == "quit" or action == "q":
                running = False

            elif action == "contact":
                if len(parts) < 2:
                    print("用法: contact <联系人名称>")
                    continue
                name = parts[1]
                recorder.set_contact(name)
                print(f"当前联系人: {name}")

            elif action == "tag":
                if len(parts) < 2:
                    print("用法: tag <标签1> <标签2> ...")
                    continue
                tags = parts[1].split()
                recorder._current_tags = tags
                print(f"已添加标签: {', '.join(tags)}")

            elif action == "send":
                if len(parts) < 2:
                    print("用法: send <消息内容>")
                    continue
                content = parts[1]

                if not recorder.get_contact():
                    print("警告: 未设置联系人，建议先用 'contact <名称>' 设置")

                recorder.record_sent_message(content)

                # 同时发送到微信
                if recorder.bot:
                    recorder.bot.send_text(content)

            elif action == "contacts":
                contacts = recorder.list_contacts()
                if contacts:
                    print("已保存的联系人:")
                    for c in contacts:
                        marker = " *" if c == recorder.get_contact() else ""
                        print(f"  {c}{marker}")
                else:
                    print("暂无已保存的联系人")

            elif action == "stats":
                stats = recorder.get_statistics()
                print(f"总对话对: {stats['total_pairs']} 条")
                print(f"联系人数: {stats['total_contacts']} 个")
                print(f"缓存消息: {stats['recent_messages']} 条")

                if stats['contact_stats']:
                    print("\n各联系人统计:")
                    for name, count in stats['contact_stats'].items():
                        print(f"  {name}: {count} 条")

            elif action == "export":
                contact_filter = parts[1] if len(parts) > 1 else None
                output = f"data/training_data.json"
                recorder.export_training_data(output, contact_filter=contact_filter)

            elif action == "clear":
                recorder.clear_messages()

            elif action == "help":
                print("""
命令:
  contact <名称>     - 设置当前联系人
  tag <标签...>      - 添加标签
  send <消息>        - 记录发送的消息
  contacts           - 列出已保存的联系人
  stats              - 查看统计
  export [联系人]    - 导出训练数据
  clear              - 清空缓存
  quit               - 退出
                """)

            else:
                print(f"未知命令: {action}，输入 'help' 查看帮助")

        except KeyboardInterrupt:
            running = False
        except Exception as e:
            print(f"错误: {e}")

    recorder.stop_recording()
    recorder.disconnect()

    stats = recorder.get_statistics()
    print(f"\n收集完成!")
    print(f"共收集 {stats['total_pairs']} 条对话对")
    print(f"涉及 {stats['total_contacts']} 个联系人")
    print("再见!")


if __name__ == "__main__":
    interactive_mode()
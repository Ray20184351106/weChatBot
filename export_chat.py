#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信聊天记录导出工具

从微信数据库导出聊天记录并转换为训练数据格式

使用方法：
1. 安装 pywxdump: pip install pywxdump
2. 运行此脚本
"""

import os
import sys
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} | {message}")


@dataclass
class WeChatMessage:
    """微信消息"""
    sender: str
    content: str
    timestamp: int
    is_self: bool
    room_id: Optional[str] = None


class WeChatExporter:
    """微信聊天记录导出器"""

    def __init__(self, data_dir: str = "data/chat_history"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def export_from_pywxdump(self, output_file: str = None):
        """
        使用 pywxdump 导出聊天记录

        需要先安装: pip install pywxdump

        Args:
            output_file: 输出文件路径
        """
        try:
            from pywxdump import get_wx_info, decrypt_merge

            logger.info("正在获取微信信息...")

            # 获取微信路径和密钥
            wx_info = get_wx_info(is_logging=False)

            if not wx_info:
                logger.error("未找到微信信息，请确保微信已登录过")
                return False

            for account in wx_info:
                logger.info(f"找到账号: {account.get('name', 'Unknown')}")

                # 微信数据库路径
                msg_db_path = account.get('msg_path', '')
                if not msg_db_path:
                    continue

                # 导出消息
                self._export_from_db(msg_db_path, output_file)

            return True

        except ImportError:
            logger.error("未安装 pywxdump，请运行: pip install pywxdump")
            return False
        except Exception as e:
            logger.error(f"导出失败: {e}")
            return False

    def _export_from_db(self, db_path: str, output_file: str):
        """从数据库导出"""
        logger.info(f"正在读取数据库: {db_path}")

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 查询所有聊天会话
            cursor.execute("""
                SELECT DISTINCT talker
                FROM MSG
                ORDER BY createTime DESC
            """)

            talkers = cursor.fetchall()
            logger.info(f"找到 {len(talkers)} 个聊天会话")

            # 导出每个会话
            total_pairs = 0

            for (talker,) in talkers:
                if not talker:
                    continue

                # 查询消息
                cursor.execute("""
                    SELECT content, createTime, isSend
                    FROM MSG
                    WHERE talker = ?
                    ORDER BY createTime ASC
                """, (talker,))

                messages = cursor.fetchall()
                pairs = self._messages_to_pairs(messages, talker)

                if pairs:
                    # 保存到文件
                    safe_name = re.sub(r'[^\w\-]', '_', talker)
                    file_path = self.data_dir / f"{safe_name}.jsonl"

                    with open(file_path, 'w', encoding='utf-8') as f:
                        for pair in pairs:
                            f.write(json.dumps(pair, ensure_ascii=False) + '\n')

                    total_pairs += len(pairs)
                    logger.info(f"导出 {talker}: {len(pairs)} 条对话对")

            conn.close()
            logger.info(f"总共导出 {total_pairs} 条对话对")

        except Exception as e:
            logger.error(f"数据库读取失败: {e}")

    def _messages_to_pairs(self, messages: List, talker: str) -> List[Dict]:
        """将消息列表转换为对话对"""
        pairs = []

        pending_incoming = None

        for content, timestamp, is_send in messages:
            # 跳过空消息和系统消息
            if not content or len(content) < 2:
                continue

            # 跳过特殊消息
            if content.startswith('<') or content.startswith('<?xml'):
                continue

            # 跳过图片、文件等
            if '[图片]' in content or '[文件]' in content or '[视频]' in content:
                continue

            if is_send == 0:  # 收到的消息
                pending_incoming = {
                    'content': content,
                    'timestamp': timestamp
                }
            else:  # 发送的消息
                if pending_incoming:
                    pair = {
                        'sender_id': talker,
                        'sender_name': talker,
                        'incoming_message': pending_incoming['content'],
                        'outgoing_message': content,
                        'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                        'room_id': talker if '@chatroom' in talker else None
                    }
                    pairs.append(pair)
                    pending_incoming = None

        return pairs

    def import_from_txt(self, txt_file: str, contact_name: str = "导入"):
        """
        从文本文件导入聊天记录

        支持格式：
        1. 每行一条消息，交替为对方消息和我的回复
        2. 格式: "对方: xxx" 或 "我: xxx"

        Args:
            txt_file: 文本文件路径
            contact_name: 联系人名称
        """
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.strip().split('\n')
            pairs = []

            pending_incoming = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 尝试解析格式
                is_self = False
                msg_content = line

                # 格式: "对方: xxx" 或 "我: xxx"
                if line.startswith('对方:') or line.startswith('对方：'):
                    msg_content = line.split(':', 1)[-1].strip() if ':' in line else line.split('：', 1)[-1].strip()
                    is_self = False
                elif line.startswith('我:') or line.startswith('我：'):
                    msg_content = line.split(':', 1)[-1].strip() if ':' in line else line.split('：', 1)[-1].strip()
                    is_self = True
                elif line.startswith('发送:') or line.startswith('发送：'):
                    msg_content = line.split(':', 1)[-1].strip() if ':' in line else line.split('：', 1)[-1].strip()
                    is_self = False
                elif line.startswith('回复:') or line.startswith('回复：'):
                    msg_content = line.split(':', 1)[-1].strip() if ':' in line else line.split('：', 1)[-1].strip()
                    is_self = True

                if not is_self:
                    pending_incoming = msg_content
                else:
                    if pending_incoming:
                        pair = {
                            'sender_id': contact_name,
                            'sender_name': contact_name,
                            'incoming_message': pending_incoming,
                            'outgoing_message': msg_content,
                            'timestamp': datetime.now().isoformat(),
                            'room_id': None
                        }
                        pairs.append(pair)
                        pending_incoming = None

            # 保存
            if pairs:
                output_file = self.data_dir / f"{contact_name}_imported.jsonl"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for pair in pairs:
                        f.write(json.dumps(pair, ensure_ascii=False) + '\n')

                logger.info(f"从 {txt_file} 导入 {len(pairs)} 条对话对")
                logger.info(f"保存到 {output_file}")

            return len(pairs)

        except Exception as e:
            logger.error(f"导入失败: {e}")
            return 0

    def import_from_json(self, json_file: str):
        """
        从 JSON 文件导入

        支持格式：
        [
          {"incoming": "对方消息", "outgoing": "我的回复"},
          ...
        ]

        Args:
            json_file: JSON 文件路径
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            pairs = []
            for item in data:
                # 兼容多种字段名
                incoming = item.get('incoming') or item.get('incoming_message') or item.get('input')
                outgoing = item.get('outgoing') or item.get('outgoing_message') or item.get('output')

                if incoming and outgoing:
                    pair = {
                        'sender_id': item.get('contact', 'imported'),
                        'sender_name': item.get('contact', 'imported'),
                        'incoming_message': incoming,
                        'outgoing_message': outgoing,
                        'timestamp': item.get('timestamp', datetime.now().isoformat()),
                        'room_id': None
                    }
                    pairs.append(pair)

            # 保存
            if pairs:
                output_file = self.data_dir / "imported_from_json.jsonl"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for pair in pairs:
                        f.write(json.dumps(pair, ensure_ascii=False) + '\n')

                logger.info(f"从 {json_file} 导入 {len(pairs)} 条对话对")

            return len(pairs)

        except Exception as e:
            logger.error(f"导入失败: {e}")
            return 0

    def quick_input(self):
        """
        快速输入模式

        交互式快速输入对话对
        """
        print("=" * 50)
        print("快速输入对话模式")
        print("=" * 50)
        print("输入 'q' 退出, 输入 's' 查看统计")
        print("格式: 直接粘贴对方消息，回车后输入你的回复")
        print("-" * 50)

        contact = input("联系人名称 (默认: 默认): ").strip() or "默认"

        pairs = []
        count = 0

        while True:
            print(f"\n[对话 {count + 1}]")

            incoming = input("对方消息: ").strip()
            if incoming.lower() == 'q':
                break
            if incoming.lower() == 's':
                print(f"当前已输入 {len(pairs)} 条对话对")
                continue
            if not incoming:
                continue

            outgoing = input("我的回复: ").strip()
            if not outgoing:
                print("跳过（未输入回复）")
                continue

            pair = {
                'sender_id': contact,
                'sender_name': contact,
                'incoming_message': incoming,
                'outgoing_message': outgoing,
                'timestamp': datetime.now().isoformat(),
                'room_id': None
            }
            pairs.append(pair)
            count += 1

            print(f"✓ 已记录 ({len(pairs)} 条)")

        # 保存
        if pairs:
            output_file = self.data_dir / f"{contact}_quick.jsonl"
            with open(output_file, 'w', encoding='utf-8') as f:
                for pair in pairs:
                    f.write(json.dumps(pair, ensure_ascii=False) + '\n')

            print(f"\n已保存 {len(pairs)} 条对话对到 {output_file}")

            # 同时导出训练格式
            self._export_training_data(pairs, f"data/training_{contact}.json")

        return len(pairs)

    def _export_training_data(self, pairs: List[Dict], output_file: str):
        """导出训练数据格式"""
        training_data = []

        for pair in pairs:
            item = {
                "instruction": "模拟用户的聊天风格进行回复",
                "input": pair['incoming_message'],
                "output": pair['outgoing_message']
            }
            training_data.append(item)

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)

        print(f"训练数据已导出到 {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="微信聊天记录导出工具")
    parser.add_argument("--pywxdump", action="store_true", help="使用 pywxdump 导出")
    parser.add_argument("--import-txt", type=str, help="从文本文件导入")
    parser.add_argument("--import-json", type=str, help="从 JSON 文件导入")
    parser.add_argument("--quick", action="store_true", help="快速输入模式")
    parser.add_argument("--contact", type=str, default="默认", help="联系人名称")

    args = parser.parse_args()

    exporter = WeChatExporter()

    if args.pywxdump:
        exporter.export_from_pywxdump()
    elif args.import_txt:
        exporter.import_from_txt(args.import_txt, args.contact)
    elif args.import_json:
        exporter.import_from_json(args.import_json)
    elif args.quick:
        exporter.quick_input()
    else:
        # 默认快速输入模式
        exporter.quick_input()


if __name__ == "__main__":
    main()
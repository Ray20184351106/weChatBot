#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据处理模块

用于处理和准备训练数据
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from loguru import logger


class DataProcessor:
    """
    数据处理类

    处理聊天数据，生成训练数据集
    """

    def __init__(self, data_dir: str = "data/chat_history"):
        """
        初始化数据处理器

        Args:
            data_dir: 聊天数据目录
        """
        self.data_dir = Path(data_dir)
        logger.info(f"数据处理器已初始化：{self.data_dir}")

    def load_raw_data(self) -> List[Dict[str, Any]]:
        """
        加载原始聊天数据

        Returns:
            原始数据列表
        """
        all_data = []

        for file_path in self.data_dir.glob("*.jsonl"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            all_data.append(json.loads(line.strip()))
            except Exception as e:
                logger.error(f"读取文件失败 {file_path}: {e}")

        logger.info(f"加载 {len(all_data)} 条原始数据")
        return all_data

    def clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        清洗数据

        Args:
            data: 原始数据

        Returns:
            清洗后的数据
        """
        cleaned = []

        for item in data:
            # 跳过无效数据
            if not item.get("incoming_message") or not item.get("outgoing_message"):
                continue

            # 跳过过短或过长的消息
            if len(item["incoming_message"]) < 2 or len(item["incoming_message"]) > 1000:
                continue
            if len(item["outgoing_message"]) < 2 or len(item["outgoing_message"]) > 500:
                continue

            # 跳过包含特殊标记的消息
            if any(marker in item["incoming_message"] for marker in ["[图片]", "[视频]", "[文件]"]):
                continue

            cleaned.append(item)

        logger.info(f"清洗后剩余 {len(cleaned)} 条数据 (原始：{len(data)})")
        return cleaned

    def analyze_style(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析用户聊天风格

        Args:
            data: 聊天数据

        Returns:
            风格分析结果
        """
        if not data:
            return {}

        # 回复长度分析
        reply_lengths = [len(item["outgoing_message"]) for item in data]
        avg_length = sum(reply_lengths) / len(reply_lengths)

        # 常用词分析
        all_words = []
        for item in data:
            # 简单分词 (按字符)
            all_words.extend(list(item["outgoing_message"]))

        word_freq = Counter(all_words)
        top_words = word_freq.most_common(20)

        # 语气词检测
        modal_particles = ["啊", "呢", "吧", "嘛", "啦", "哦", "哈", "呀"]
        particle_usage = {p: sum(1 for item in data if p in item["outgoing_message"]) for p in modal_particles}

        # 表情符号使用
        emoji_count = sum(
            1 for item in data
            if any(ord(c) > 127 for c in item["outgoing_message"])
        )

        style_analysis = {
            "avg_reply_length": round(avg_length, 2),
            "top_words": top_words,
            "modal_particles": particle_usage,
            "emoji_usage_rate": round(emoji_count / len(data), 2) if data else 0,
            "total_samples": len(data)
        }

        logger.info(f"风格分析完成：平均回复长度={avg_length:.1f}")
        return style_analysis

    def format_for_training(
        self,
        data: List[Dict[str, Any]],
        format_type: str = "alpaca",
        output_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        格式化数据为训练格式

        Args:
            data: 聊天数据
            format_type: 格式类型 (alpaca / chatml / custom)
            output_path: 输出路径 (可选)

        Returns:
            格式化后的数据
        """
        formatted = []

        for item in data:
            if format_type == "alpaca":
                formatted_item = {
                    "instruction": "模拟用户的聊天风格进行微信回复",
                    "input": item["incoming_message"],
                    "output": item["outgoing_message"]
                }
            elif format_type == "chatml":
                formatted_item = {
                    "messages": [
                        {"role": "user", "content": item["incoming_message"]},
                        {"role": "assistant", "content": item["outgoing_message"]}
                    ]
                }
            elif format_type == "simple":
                formatted_item = {
                    "prompt": item["incoming_message"],
                    "completion": item["outgoing_message"]
                }
            else:
                logger.warning(f"未知格式：{format_type}，使用 alpaca 格式")
                formatted_item = {
                    "instruction": "模拟用户的聊天风格进行微信回复",
                    "input": item["incoming_message"],
                    "output": item["outgoing_message"]
                }

            formatted.append(formatted_item)

        # 保存到文件
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                if output_file.suffix == ".json":
                    json.dump(formatted, f, ensure_ascii=False, indent=2)
                else:
                    for item in formatted:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")

            logger.info(f"训练数据已保存到：{output_path}")

        return formatted

    def split_dataset(
        self,
        data: List[Dict[str, Any]],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1
    ) -> Tuple[List, List, List]:
        """
        划分训练集、验证集、测试集

        Args:
            data: 数据
            train_ratio: 训练集比例
            val_ratio: 验证集比例

        Returns:
            (train_data, val_data, test_data)
        """
        import random
        random.shuffle(data)

        n = len(data)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_data = data[:train_end]
        val_data = data[train_end:val_end]
        test_data = data[val_end:]

        logger.info(f"数据集划分：训练集={len(train_data)}, 验证集={len(val_data)}, 测试集={len(test_data)}")
        return train_data, val_data, test_data

    def get_statistics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取数据统计信息

        Args:
            data: 数据

        Returns:
            统计信息
        """
        if not data:
            return {}

        incoming_lengths = [len(item["incoming_message"]) for item in data]
        outgoing_lengths = [len(item["outgoing_message"]) for item in data]

        return {
            "total_samples": len(data),
            "avg_incoming_length": sum(incoming_lengths) / len(incoming_lengths),
            "avg_outgoing_length": sum(outgoing_lengths) / len(outgoing_lengths),
            "max_incoming_length": max(incoming_lengths),
            "max_outgoing_length": max(outgoing_lengths),
            "min_incoming_length": min(incoming_lengths),
            "min_outgoing_length": min(outgoing_lengths)
        }

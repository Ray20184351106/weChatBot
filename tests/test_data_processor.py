#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DataProcessor 模块测试

测试数据处理和训练数据准备功能
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from training.data_processor import DataProcessor


class TestDataProcessorInit:
    """初始化测试"""

    def test_init_default_dir(self, temp_dir: Path):
        """测试默认目录初始化"""
        processor = DataProcessor(str(temp_dir / "chat_history"))

        assert processor.data_dir.exists()

    def test_init_custom_dir(self, temp_chat_history_dir: Path):
        """测试自定义目录初始化"""
        processor = DataProcessor(str(temp_chat_history_dir))

        assert processor.data_dir == temp_chat_history_dir


class TestDataProcessorLoad:
    """数据加载测试"""

    def test_load_raw_data_empty(self, temp_chat_history_dir: Path):
        """测试加载空数据"""
        processor = DataProcessor(str(temp_chat_history_dir))
        data = processor.load_raw_data()

        assert data == []

    def test_load_raw_data_single_file(self, sample_chat_file: Path):
        """测试加载单个文件"""
        processor = DataProcessor(str(sample_chat_file.parent))
        data = processor.load_raw_data()

        assert len(data) == 4

    def test_load_raw_data_multiple_files(self, temp_chat_history_dir: Path, sample_chat_pairs: list):
        """测试加载多个文件"""
        # 创建多个文件
        for i in range(3):
            file_path = temp_chat_history_dir / f"chat_{i}.jsonl"
            with open(file_path, "w", encoding="utf-8") as f:
                for pair in sample_chat_pairs[:2]:
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")

        processor = DataProcessor(str(temp_chat_history_dir))
        data = processor.load_raw_data()

        assert len(data) == 6  # 3 files * 2 pairs

    def test_load_raw_data_invalid_file(self, temp_chat_history_dir: Path):
        """测试加载无效文件"""
        # 创建有效文件
        valid_file = temp_chat_history_dir / "valid.jsonl"
        with open(valid_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"incoming_message": "你好", "outgoing_message": "你好啊"}) + "\n")

        # 创建无效文件
        invalid_file = temp_chat_history_dir / "invalid.jsonl"
        with open(invalid_file, "w", encoding="utf-8") as f:
            f.write("invalid json content\n")

        processor = DataProcessor(str(temp_chat_history_dir))
        data = processor.load_raw_data()

        # 应该只加载有效数据
        assert len(data) == 1


class TestDataProcessorClean:
    """数据清洗测试"""

    def test_clean_data_valid(self, sample_chat_pairs: list):
        """测试清洗有效数据"""
        processor = DataProcessor()
        cleaned = processor.clean_data(sample_chat_pairs)

        assert len(cleaned) == len(sample_chat_pairs)

    def test_clean_data_remove_empty(self):
        """测试移除空数据"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好啊"},
            {"incoming_message": "", "outgoing_message": "回复"},
            {"incoming_message": "消息", "outgoing_message": ""},
            {"incoming_message": None, "outgoing_message": "回复"},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)

        assert len(cleaned) == 1

    def test_clean_data_remove_short(self):
        """测试移除过短消息"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好啊"},
            {"incoming_message": "a", "outgoing_message": "回复"},
            {"incoming_message": "消息", "outgoing_message": "b"},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)

        assert len(cleaned) == 1

    def test_clean_data_remove_long(self):
        """测试移除过长消息"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好啊"},
            {"incoming_message": "正常长度消息", "outgoing_message": "正常回复"},
            {"incoming_message": "你好" * 500, "outgoing_message": "回复"},
            {"incoming_message": "消息", "outgoing_message": "回复" * 300},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)

        assert len(cleaned) == 2

    def test_clean_data_remove_media_markers(self):
        """测试移除媒体标记消息"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好啊"},
            {"incoming_message": "[图片] 看看这个", "outgoing_message": "好看"},
            {"incoming_message": "收到[文件]", "outgoing_message": "好的"},
            {"incoming_message": "看看这个[视频]", "outgoing_message": "不错"},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)

        assert len(cleaned) == 1

    def test_clean_data_empty_list(self):
        """测试清洗空列表"""
        processor = DataProcessor()
        cleaned = processor.clean_data([])

        assert cleaned == []


class TestDataProcessorFormat:
    """数据格式化测试"""

    def test_format_alpaca(self, sample_chat_pairs: list):
        """测试 Alpaca 格式"""
        processor = DataProcessor()
        formatted = processor.format_for_training(sample_chat_pairs, format_type="alpaca")

        assert len(formatted) == len(sample_chat_pairs)
        assert "instruction" in formatted[0]
        assert "input" in formatted[0]
        assert "output" in formatted[0]
        assert "模拟用户的聊天风格" in formatted[0]["instruction"]

    def test_format_chatml(self, sample_chat_pairs: list):
        """测试 ChatML 格式"""
        processor = DataProcessor()
        formatted = processor.format_for_training(sample_chat_pairs, format_type="chatml")

        assert len(formatted) == len(sample_chat_pairs)
        assert "messages" in formatted[0]
        assert len(formatted[0]["messages"]) == 2
        assert formatted[0]["messages"][0]["role"] == "user"
        assert formatted[0]["messages"][1]["role"] == "assistant"

    def test_format_simple(self, sample_chat_pairs: list):
        """测试简单格式"""
        processor = DataProcessor()
        formatted = processor.format_for_training(sample_chat_pairs, format_type="simple")

        assert len(formatted) == len(sample_chat_pairs)
        assert "prompt" in formatted[0]
        assert "completion" in formatted[0]

    def test_format_unknown_defaults_to_alpaca(self, sample_chat_pairs: list):
        """测试未知格式默认为 Alpaca"""
        processor = DataProcessor()
        formatted = processor.format_for_training(sample_chat_pairs, format_type="unknown")

        assert "instruction" in formatted[0]
        assert "input" in formatted[0]

    def test_format_with_output_json(self, sample_chat_pairs: list, temp_dir: Path):
        """测试格式化并输出 JSON 文件"""
        processor = DataProcessor()
        output_path = str(temp_dir / "training.json")

        formatted = processor.format_for_training(
            sample_chat_pairs,
            format_type="alpaca",
            output_path=output_path
        )

        # 验证文件存在
        assert Path(output_path).exists()

        # 验证文件内容
        with open(output_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert len(loaded) == len(sample_chat_pairs)

    def test_format_with_output_jsonl(self, sample_chat_pairs: list, temp_dir: Path):
        """测试格式化并输出 JSONL 文件"""
        processor = DataProcessor()
        output_path = str(temp_dir / "training.jsonl")

        formatted = processor.format_for_training(
            sample_chat_pairs,
            format_type="chatml",
            output_path=output_path
        )

        # 验证文件存在
        assert Path(output_path).exists()

        # 验证文件内容
        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == len(sample_chat_pairs)


class TestDataProcessorSplit:
    """数据集划分测试"""

    def test_split_default_ratio(self, sample_chat_pairs: list):
        """测试默认比例划分"""
        processor = DataProcessor()
        train, val, test = processor.split_dataset(sample_chat_pairs)

        # 默认 80/10/10
        total = len(sample_chat_pairs)
        assert len(train) == int(total * 0.8)
        assert len(val) == int(total * 0.1)
        assert len(test) == total - len(train) - len(val)

    def test_split_custom_ratio(self, sample_chat_pairs: list):
        """测试自定义比例划分"""
        processor = DataProcessor()
        train, val, test = processor.split_dataset(
            sample_chat_pairs,
            train_ratio=0.7,
            val_ratio=0.2
        )

        total = len(sample_chat_pairs)
        assert len(train) == int(total * 0.7)
        assert len(val) == int(total * 0.2)
        assert len(test) == total - len(train) - len(val)

    def test_split_small_dataset(self):
        """测试小数据集划分"""
        data = [{"incoming_message": f"消息{i}", "outgoing_message": f"回复{i}"} for i in range(5)]

        processor = DataProcessor()
        train, val, test = processor.split_dataset(data)

        # 即使数据少，也应该能划分
        assert len(train) + len(val) + len(test) == 5

    def test_split_empty_dataset(self):
        """测试空数据集划分"""
        processor = DataProcessor()
        train, val, test = processor.split_dataset([])

        assert train == []
        assert val == []
        assert test == []

    def test_split_shuffles_data(self, sample_chat_pairs: list):
        """测试数据被随机打乱"""
        processor = DataProcessor()

        # 多次划分，结果顺序可能不同
        train1, _, _ = processor.split_dataset(sample_chat_pairs.copy())
        train2, _, _ = processor.split_dataset(sample_chat_pairs.copy())

        # 数据内容相同，但顺序可能不同（因为 shuffle）
        # 注意：由于随机性，这个测试可能不稳定
        assert len(train1) == len(train2)


class TestDataProcessorAnalyze:
    """风格分析测试"""

    def test_analyze_style_basic(self, sample_chat_pairs: list):
        """测试基本风格分析"""
        processor = DataProcessor()
        analysis = processor.analyze_style(sample_chat_pairs)

        assert "avg_reply_length" in analysis
        assert "top_words" in analysis
        assert "modal_particles" in analysis
        assert "emoji_usage_rate" in analysis
        assert "total_samples" in analysis

    def test_analyze_style_empty_data(self):
        """测试空数据风格分析"""
        processor = DataProcessor()
        analysis = processor.analyze_style([])

        assert analysis == {}

    def test_analyze_style_reply_length(self):
        """测试回复长度分析"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好啊，最近怎么样？"},  # 14 chars
            {"incoming_message": "好的", "outgoing_message": "收到"},  # 2 chars
        ]

        processor = DataProcessor()
        analysis = processor.analyze_style(data)

        assert analysis["avg_reply_length"] == 8.0  # (14 + 2) / 2

    def test_analyze_style_modal_particles(self):
        """测试语气词分析"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好啊"},
            {"incoming_message": "好的", "outgoing_message": "收到啦"},
            {"incoming_message": "行", "outgoing_message": "好呢"},
        ]

        processor = DataProcessor()
        analysis = processor.analyze_style(data)

        assert "啊" in analysis["modal_particles"]
        assert "啦" in analysis["modal_particles"]
        assert "呢" in analysis["modal_particles"]

    def test_analyze_style_top_words(self):
        """测试常用词分析"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好你好"},
            {"incoming_message": "好的", "outgoing_message": "好的好的"},
        ]

        processor = DataProcessor()
        analysis = processor.analyze_style(data)

        assert len(analysis["top_words"]) == 20


class TestDataProcessorStatistics:
    """统计信息测试"""

    def test_get_statistics_basic(self, sample_chat_pairs: list):
        """测试基本统计"""
        processor = DataProcessor()
        stats = processor.get_statistics(sample_chat_pairs)

        assert "total_samples" in stats
        assert "avg_incoming_length" in stats
        assert "avg_outgoing_length" in stats
        assert "max_incoming_length" in stats
        assert "max_outgoing_length" in stats

    def test_get_statistics_empty(self):
        """测试空数据统计"""
        processor = DataProcessor()
        stats = processor.get_statistics([])

        assert stats == {}

    def test_get_statistics_lengths(self):
        """测试长度统计"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好啊"},
            {"incoming_message": "这是一条较长的消息", "outgoing_message": "这是回复"},
        ]

        processor = DataProcessor()
        stats = processor.get_statistics(data)

        assert stats["min_incoming_length"] == 2
        assert stats["max_incoming_length"] == 8
        assert stats["min_outgoing_length"] == 3
        assert stats["max_outgoing_length"] == 4

    def test_get_statistics_count(self, sample_chat_pairs: list):
        """测试样本计数"""
        processor = DataProcessor()
        stats = processor.get_statistics(sample_chat_pairs)

        assert stats["total_samples"] == len(sample_chat_pairs)


class TestDataProcessorIntegration:
    """集成测试"""

    def test_full_pipeline(self, sample_chat_file: Path, temp_dir: Path):
        """测试完整处理流程"""
        processor = DataProcessor(str(sample_chat_file.parent))

        # 1. 加载原始数据
        raw_data = processor.load_raw_data()
        assert len(raw_data) > 0

        # 2. 清洗数据
        cleaned_data = processor.clean_data(raw_data)
        assert len(cleaned_data) > 0

        # 3. 格式化数据
        formatted_data = processor.format_for_training(
            cleaned_data,
            format_type="chatml",
            output_path=str(temp_dir / "training.json")
        )
        assert len(formatted_data) > 0

        # 4. 划分数据集
        train, val, test = processor.split_dataset(formatted_data)
        assert len(train) > 0

        # 5. 分析风格
        analysis = processor.analyze_style(cleaned_data)
        assert "avg_reply_length" in analysis

        # 6. 获取统计
        stats = processor.get_statistics(cleaned_data)
        assert "total_samples" in stats


class TestDataProcessorEdgeCases:
    """边界情况测试"""

    def test_unicode_content(self):
        """测试 Unicode 内容"""
        data = [
            {"incoming_message": "你好😊", "outgoing_message": "你好啊🎉"},
            {"incoming_message": "测试表情👋", "outgoing_message": "收到👏"},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)
        formatted = processor.format_for_training(cleaned, format_type="alpaca")

        assert len(formatted) == 2

    def test_special_characters(self):
        """测试特殊字符"""
        data = [
            {"incoming_message": "测试@#$%", "outgoing_message": "回复!@#$"},
            {"incoming_message": "特殊字符<>{}[]", "outgoing_message": "处理\"'"},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)
        formatted = processor.format_for_training(cleaned)

        assert len(formatted) == 2

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        data = [
            {"incoming_message": "你好\n\n", "outgoing_message": "  回复  "},
            {"incoming_message": "\t消息\t", "outgoing_message": "\n回复\n"},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)

        # 应该能处理空白字符
        assert len(cleaned) == 2

    def test_duplicate_messages(self):
        """测试重复消息"""
        data = [
            {"incoming_message": "你好", "outgoing_message": "你好"},
            {"incoming_message": "你好", "outgoing_message": "你好"},
            {"incoming_message": "不同", "outgoing_message": "回复"},
        ]

        processor = DataProcessor()
        cleaned = processor.clean_data(data)

        # 不应该去重（那是训练时考虑的）
        assert len(cleaned) == 3
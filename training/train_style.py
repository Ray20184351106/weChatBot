#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聊天风格微调训练脚本

基于收集的聊天记录，微调 LLM 以模拟用户聊天风格
"""

import os
import argparse
from pathlib import Path
from typing import Optional

from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

from training.data_processor import DataProcessor


def check_environment():
    """检查环境"""
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import LoraConfig, get_peft_model, TaskType
        logger.info("环境检查通过")
        return True
    except ImportError as e:
        logger.error(f"缺少依赖：{e}")
        logger.error("请运行：pip install torch transformers peft accelerate")
        return False


def train(
    data_path: str,
    output_dir: str = "data/models/lora",
    model_name: str = "THUDM/chatglm3-6b",
    num_epochs: int = 3,
    batch_size: int = 8,
    learning_rate: float = 2e-4,
    max_length: int = 512
):
    """
    训练函数

    Args:
        data_path: 训练数据路径
        output_dir: 模型输出目录
        model_name: 基础模型名称
        num_epochs: 训练轮数
        batch_size: 批次大小
        learning_rate: 学习率
        max_length: 最大序列长度
    """
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
    from datasets import Dataset

    logger.info(f"开始训练 - 数据：{data_path}, 模型：{model_name}")

    # 1. 加载数据
    processor = DataProcessor()
    raw_data = processor.load_raw_data()

    if not raw_data:
        logger.error("未找到训练数据，请先收集聊天数据")
        return

    # 清洗数据
    cleaned_data = processor.clean_data(raw_data)

    if len(cleaned_data) < 50:
        logger.warning(f"数据量较少 ({len(cleaned_data)} 条)，建议至少收集 100 条")

    # 格式化数据
    formatted_data = processor.format_for_training(cleaned_data, format_type="chatml")

    # 划分数据集
    train_data, val_data, _ = processor.split_dataset(formatted_data)

    logger.info(f"训练集：{len(train_data)}, 验证集：{len(val_data)}")

    # 2. 加载模型和 tokenizer
    logger.info(f"加载模型：{model_name}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        padding_side="right"
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )

    # 3. 配置 LoRA
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        inference_mode=False,
        r=8,  # LoRA 秩
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["query_key_value"]  # 针对 ChatGLM
    )

    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 4. 数据预处理
    def tokenize_function(examples):
        texts = []
        for messages in examples["messages"]:
            # ChatML 格式
            text = "\n".join([
                f"<|{msg['role']}|>\n{msg['content']}"
                for msg in messages
            ]) + "<|endoftext|>"
            texts.append(text)

        return tokenizer(
            texts,
            truncation=True,
            max_length=max_length,
            padding="max_length"
        )

    # 转换为 Dataset
    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data)

    # Tokenize
    tokenized_train = train_dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=["messages"]
    )
    tokenized_val = val_dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=["messages"]
    )

    # 5. 训练配置
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir=f"{output_dir}/logs",
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        fp16=True,
        report_to="none"
    )

    # 6. 开始训练
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_val
    )

    logger.info("开始训练...")
    trainer.train()

    # 7. 保存模型
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    logger.info(f"训练完成，模型已保存到：{output_dir}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="聊天风格微调训练脚本")
    parser.add_argument(
        "--data",
        type=str,
        default="data/chat_history",
        help="训练数据目录"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/models/lora",
        help="模型输出目录"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="THUDM/chatglm3-6b",
        help="基础模型名称"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="训练轮数"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="批次大小"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=2e-4,
        help="学习率"
    )

    args = parser.parse_args()

    # 设置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )

    # 检查环境
    if not check_environment():
        return

    # 开始训练
    train(
        data_path=args.data,
        output_dir=args.output,
        model_name=args.model,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr
    )


if __name__ == "__main__":
    main()

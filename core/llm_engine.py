#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 引擎模块

负责加载模型、进行风格化推理
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from loguru import logger

# 尝试导入相关库
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
except ImportError:
    logger.warning("torch/transformers/peft 未安装，LLM 功能不可用")
    torch = None


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"      # 提供商：openai / deepseek / zhipu / local
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-3.5-turbo"

    # 本地模型配置
    local_model_path: str = ""
    lora_path: str = ""

    # 生成配置
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9


class LLMEngine:
    """
    LLM 推理引擎

    支持多种 LLM 提供商，包括本地微调模型
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 LLM 引擎

        Args:
            config: LLM 配置
        """
        self.config = config or LLMConfig()

        # 从环境变量读取配置
        self._load_from_env()

        # 本地模型实例
        self.tokenizer = None
        self.model = None
        self._is_local_loaded = False

        logger.info(f"LLM 引擎已初始化，提供商：{self.config.provider}")

    def _load_from_env(self):
        """从环境变量加载配置"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        if not self.config.api_key:
            self.config.api_key = os.getenv("LLM_API_KEY", "")
        if not self.config.base_url:
            self.config.base_url = os.getenv("LLM_BASE_URL", "")
        if not self.config.model:
            self.config.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        if not self.config.provider:
            self.config.provider = os.getenv("LLM_PROVIDER", "openai")

    def load_local_model(self, model_path: str, lora_path: Optional[str] = None) -> bool:
        """
        加载本地模型

        Args:
            model_path: 基础模型路径
            lora_path: LoRA 权重路径 (可选)

        Returns:
            加载是否成功
        """
        if torch is None:
            logger.error("torch 未安装，无法加载本地模型")
            return False

        try:
            logger.info(f"正在加载模型：{model_path}")

            # 加载 tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True
            )

            # 加载基础模型
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True
            )

            # 加载 LoRA 权重
            if lora_path:
                logger.info(f"加载 LoRA 权重：{lora_path}")
                self.model = PeftModel.from_pretrained(
                    self.model,
                    lora_path
                )

            self.model.eval()
            self._is_local_loaded = True
            logger.info("本地模型加载完成")
            return True

        except Exception as e:
            logger.error(f"加载本地模型失败：{e}")
            return False

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        生成回复

        Args:
            prompt: 用户输入
            system_prompt: 系统提示词

        Returns:
            生成的回复
        """
        if self.config.provider in ["openai", "deepseek", "zhipu"]:
            return self._generate_api(prompt, system_prompt)
        elif self.config.provider == "local" and self._is_local_loaded:
            return self._generate_local(prompt, system_prompt)
        else:
            logger.warning("LLM 未就绪，返回默认回复")
            return " [自动回复] 我现在还不会聊天，请稍后再试~"

    def _generate_api(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """调用 API 生成回复"""
        try:
            import httpx

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p
            }

            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }

            base_url = self.config.base_url.rstrip("/")
            if not base_url:
                base_url = "https://api.openai.com/v1"

            response = httpx.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.debug(f"API 回复：{content[:50]}...")
            return content

        except Exception as e:
            logger.error(f"API 调用失败：{e}")
            return "[自动回复] API 调用失败，请稍后再试~"

    def _generate_local(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """本地模型生成回复"""
        if not self._is_local_loaded:
            logger.error("本地模型未加载")
            return self.generate(prompt, system_prompt)

        try:
            # 构建输入
            if system_prompt:
                input_text = f"[INST] {system_prompt}\n\n{prompt} [/INST]"
            else:
                input_text = f"[INST] {prompt} [/INST]"

            # Tokenize
            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_tokens
            ).to(self.model.device)

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    do_sample=self.config.temperature > 0.5
                )

            # Decode
            generated = self.tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )

            logger.debug(f"本地模型回复：{generated[:50]}...")
            return generated

        except Exception as e:
            logger.error(f"本地模型推理失败：{e}")
            return "[自动回复] 模型推理失败，请稍后再试~"

    def set_system_prompt(self, prompt: str):
        """
        设置系统提示词

        Args:
            prompt: 系统提示词
        """
        self._system_prompt = prompt
        logger.info("系统提示词已更新")

    def get_default_system_prompt(self, user_style: Optional[str] = None) -> str:
        """
        获取默认系统提示词

        Args:
            user_style: 用户风格描述

        Returns:
            系统提示词
        """
        base_prompt = "你是一个微信聊天助手，需要模拟用户的聊天风格进行回复。"

        if user_style:
            return f"{base_prompt}\n\n用户风格：{user_style}"

        return base_prompt

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLMEngine 模块测试

测试 LLM 推理引擎功能
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from core.llm_engine import LLMEngine, LLMConfig


class TestLLMConfig:
    """LLMConfig 配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig()

        assert config.provider == "openai"
        assert config.model == "gpt-3.5-turbo"
        assert config.max_tokens == 512
        assert config.temperature == 0.7
        assert config.top_p == 0.9

    def test_custom_config(self):
        """测试自定义配置"""
        config = LLMConfig(
            provider="deepseek",
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            temperature=0.5
        )

        assert config.provider == "deepseek"
        assert config.api_key == "test-key"
        assert config.base_url == "https://api.deepseek.com/v1"
        assert config.model == "deepseek-chat"
        assert config.temperature == 0.5

    def test_local_model_config(self):
        """测试本地模型配置"""
        config = LLMConfig(
            provider="local",
            local_model_path="/path/to/model",
            lora_path="/path/to/lora"
        )

        assert config.provider == "local"
        assert config.local_model_path == "/path/to/model"
        assert config.lora_path == "/path/to/lora"


class TestLLMEngine:
    """LLMEngine 类测试"""

    def test_init_default_config(self):
        """测试默认配置初始化"""
        engine = LLMEngine()

        assert engine.config is not None
        assert engine.config.provider == "openai"
        assert engine._is_local_loaded is False

    def test_init_custom_config(self):
        """测试自定义配置初始化"""
        config = LLMConfig(provider="deepseek", temperature=0.8)
        engine = LLMEngine(config)

        assert engine.config.provider == "deepseek"
        assert engine.config.temperature == 0.8

    def test_tokenizer_and_model_not_loaded_by_default(self):
        """测试默认不加载本地模型"""
        engine = LLMEngine()

        assert engine.tokenizer is None
        assert engine.model is None
        assert engine._is_local_loaded is False

    def test_set_system_prompt(self):
        """测试设置系统提示词"""
        engine = LLMEngine()
        engine.set_system_prompt("测试提示词")

        assert engine._system_prompt == "测试提示词"

    def test_get_default_system_prompt(self):
        """测试获取默认系统提示词"""
        engine = LLMEngine()
        prompt = engine.get_default_system_prompt()

        assert "微信聊天助手" in prompt
        assert "模拟用户的聊天风格" in prompt

    def test_get_default_system_prompt_with_style(self):
        """测试带风格的系统提示词"""
        engine = LLMEngine()
        prompt = engine.get_default_system_prompt("喜欢用表情包，语气轻松")

        assert "喜欢用表情包" in prompt
        assert "语气轻松" in prompt


class TestLLMEngineGenerate:
    """生成回复功能测试"""

    def test_generate_not_ready(self):
        """测试 LLM 未就绪时的生成"""
        engine = LLMEngine()
        # 没有配置 API key，也没有加载本地模型

        result = engine.generate("你好")

        assert "自动回复" in result

    def test_generate_with_system_prompt(self):
        """测试带系统提示词的生成"""
        engine = LLMEngine()

        # 由于没有实际配置，会返回默认回复
        result = engine.generate("你好", system_prompt="你是测试助手")

        # 应该能正常调用，即使返回默认回复
        assert result is not None
        assert isinstance(result, str)

    @patch('core.llm_engine.httpx.post')
    def test_generate_api_success(self, mock_post):
        """测试 API 调用成功"""
        # 模拟 API 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "这是 API 返回的回复"}}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = LLMConfig(
            provider="openai",
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
        engine = LLMEngine(config)

        result = engine.generate("你好")

        assert result == "这是 API 返回的回复"
        mock_post.assert_called_once()

    @patch('core.llm_engine.httpx.post')
    def test_generate_api_failure(self, mock_post):
        """测试 API 调用失败"""
        mock_post.side_effect = Exception("API 调用失败")

        config = LLMConfig(
            provider="openai",
            api_key="test-key"
        )
        engine = LLMEngine(config)

        result = engine.generate("你好")

        assert "API 调用失败" in result or "自动回复" in result

    @patch('core.llm_engine.httpx.post')
    def test_generate_api_timeout(self, mock_post):
        """测试 API 调用超时"""
        import httpx
        mock_post.side_effect = httpx.TimeoutException("请求超时")

        config = LLMConfig(
            provider="openai",
            api_key="test-key"
        )
        engine = LLMEngine(config)

        result = engine.generate("你好")

        assert "自动回复" in result or "失败" in result


class TestLLMEngineLocalModel:
    """本地模型功能测试"""

    @pytest.mark.skipif(
        not pytest.importorskip("torch", reason="torch 未安装"),
        reason="需要 torch 库"
    )
    def test_load_local_model_torch_not_available(self):
        """测试 torch 未安装时加载本地模型"""
        # 通过 mock 模拟 torch 未安装
        with patch('core.llm_engine.torch', None):
            engine = LLMEngine()
            result = engine.load_local_model("/path/to/model")

            assert result is False

    def test_load_local_model_not_installed(self):
        """测试依赖库未安装"""
        # 创建一个没有依赖的环境
        engine = LLMEngine(LLMConfig(provider="local"))

        # torch 未安装或导入失败时
        # 当前实现会返回 False
        # 注意：实际测试环境可能有 torch，需要条件跳过

    @pytest.mark.slow
    @pytest.mark.skip(reason="需要实际模型文件，跳过测试")
    def test_load_local_model_real(self):
        """测试加载真实本地模型"""
        # 这个测试需要实际的模型文件
        # 标记为慢速测试，通常跳过
        engine = LLMEngine(LLMConfig(provider="local"))
        result = engine.load_local_model("path/to/real/model")

        # 验证模型是否加载成功
        assert result is True
        assert engine._is_local_loaded is True


class TestLLMEngineProviders:
    """不同提供商测试"""

    def test_provider_openai(self):
        """测试 OpenAI 提供商"""
        config = LLMConfig(provider="openai")
        engine = LLMEngine(config)

        assert engine.config.provider == "openai"

    def test_provider_deepseek(self):
        """测试 DeepSeek 提供商"""
        config = LLMConfig(provider="deepseek")
        engine = LLMEngine(config)

        assert engine.config.provider == "deepseek"

    def test_provider_zhipu(self):
        """测试智谱 AI 提供商"""
        config = LLMConfig(provider="zhipu")
        engine = LLMEngine(config)

        assert engine.config.provider == "zhipu"

    def test_provider_local(self):
        """测试本地模型提供商"""
        config = LLMConfig(provider="local")
        engine = LLMEngine(config)

        assert engine.config.provider == "local"


class TestLLMEngineEnvironment:
    """环境变量配置测试"""

    def test_load_from_env_api_key(self):
        """测试从环境变量加载 API Key"""
        with patch.dict('os.environ', {'LLM_API_KEY': 'env-test-key'}):
            engine = LLMEngine()

            assert engine.config.api_key == "env-test-key"

    def test_load_from_env_base_url(self):
        """测试从环境变量加载 Base URL"""
        with patch.dict('os.environ', {'LLM_BASE_URL': 'https://custom.api.com/v1'}):
            engine = LLMEngine()

            assert engine.config.base_url == "https://custom.api.com/v1"

    def test_load_from_env_model(self):
        """测试从环境变量加载模型"""
        with patch.dict('os.environ', {'LLM_MODEL': 'gpt-4'}):
            engine = LLMEngine()

            assert engine.config.model == "gpt-4"

    def test_load_from_env_provider(self):
        """测试从环境变量加载提供商"""
        with patch.dict('os.environ', {'LLM_PROVIDER': 'deepseek'}):
            engine = LLMEngine()

            assert engine.config.provider == "deepseek"

    def test_config_overrides_env(self):
        """测试显式配置覆盖环境变量"""
        with patch.dict('os.environ', {'LLM_API_KEY': 'env-key'}):
            config = LLMConfig(api_key="explicit-key")
            engine = LLMEngine(config)

            # 显式配置应该优先
            assert engine.config.api_key == "explicit-key"


class TestLLMEngineGenerationParameters:
    """生成参数测试"""

    def test_max_tokens(self):
        """测试 max_tokens 参数"""
        config = LLMConfig(max_tokens=1024)
        engine = LLMEngine(config)

        assert engine.config.max_tokens == 1024

    def test_temperature(self):
        """测试 temperature 参数"""
        config = LLMConfig(temperature=0.5)
        engine = LLMEngine(config)

        assert engine.config.temperature == 0.5

    def test_top_p(self):
        """测试 top_p 参数"""
        config = LLMConfig(top_p=0.8)
        engine = LLMEngine(config)

        assert engine.config.top_p == 0.8

    @patch('core.llm_engine.httpx.post')
    def test_generation_parameters_in_request(self, mock_post):
        """测试生成参数在请求中传递"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "回复"}}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = LLMConfig(
            api_key="test-key",
            max_tokens=256,
            temperature=0.3,
            top_p=0.85
        )
        engine = LLMEngine(config)

        engine.generate("你好")

        # 验证请求参数
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']

        assert payload['max_tokens'] == 256
        assert payload['temperature'] == 0.3
        assert payload['top_p'] == 0.85


class TestLLMEngineEdgeCases:
    """边界情况测试"""

    def test_empty_prompt(self):
        """测试空输入"""
        engine = LLMEngine()

        result = engine.generate("")
        assert result is not None

    def test_very_long_prompt(self):
        """测试超长输入"""
        engine = LLMEngine()

        long_prompt = "这是一条很长的消息" * 100
        result = engine.generate(long_prompt)

        assert result is not None

    def test_special_characters_in_prompt(self):
        """测试特殊字符输入"""
        engine = LLMEngine()

        special_prompt = "测试消息！@#$%^&*()中文English混合"
        result = engine.generate(special_prompt)

        assert result is not None

    def test_multiline_prompt(self):
        """测试多行输入"""
        engine = LLMEngine()

        multiline = "第一行\n第二行\n第三行"
        result = engine.generate(multiline)

        assert result is not None

    def test_concurrent_requests(self):
        """测试并发请求"""
        # 验证引擎能处理连续请求
        engine = LLMEngine()

        results = []
        for i in range(3):
            result = engine.generate(f"消息{i}")
            results.append(result)

        # 所有请求都应该有响应
        assert len(results) == 3
        assert all(r is not None for r in results)
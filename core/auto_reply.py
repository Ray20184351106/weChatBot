#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动回复管理器

负责管理自动回复逻辑，包括：
- 频率限制
- 人机切换
- 联系人过滤
- LLM 回复生成
"""

import time
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path

from loguru import logger

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class RateLimitState:
    """频率限制状态"""
    last_reply_time: float = 0.0
    reply_count: int = 0
    minute_start_time: float = 0.0


@dataclass
class AutoReplyConfig:
    """自动回复配置"""
    enabled: bool = False
    min_training_data: int = 100
    min_interval: float = 3.0
    max_per_minute: int = 5
    human_takeover_enabled: bool = True
    human_takeover_keywords: List[str] = field(default_factory=lambda: ["#人工", "#stop", "停止自动回复"])
    exclude_contacts: List[str] = field(default_factory=list)
    whitelist_contacts: List[str] = field(default_factory=list)
    whitelist_mode: bool = False  # True = 只回复白名单，False = 回复所有人（除黑名单）

    @classmethod
    def from_yaml(cls, config_path: str = "config/config.yaml") -> "AutoReplyConfig":
        """
        从 YAML 文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            AutoReplyConfig 实例
        """
        if not YAML_AVAILABLE:
            logger.warning("yaml 库未安装，使用默认配置")
            return cls()

        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"配置文件不存在：{config_path}，使用默认配置")
            return cls()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return cls()

            auto_reply = data.get("auto_reply", {})
            rate_limit = auto_reply.get("rate_limit", {})
            human_takeover = auto_reply.get("human_takeover", {})

            return cls(
                enabled=auto_reply.get("enabled", False),
                min_training_data=auto_reply.get("min_training_data", 100),
                min_interval=rate_limit.get("min_interval", 3.0),
                max_per_minute=rate_limit.get("max_per_minute", 5),
                human_takeover_enabled=human_takeover.get("enabled", True),
                human_takeover_keywords=human_takeover.get("keywords", ["#人工", "#stop"]),
                exclude_contacts=auto_reply.get("exclude_contacts", []),
                whitelist_contacts=auto_reply.get("whitelist_contacts", []),
                whitelist_mode=bool(auto_reply.get("whitelist_contacts", []))
            )

        except Exception as e:
            logger.error(f"加载配置文件失败：{e}")
            return cls()


class AutoReplyManager:
    """
    自动回复管理器

    管理自动回复的核心逻辑，包括频率控制、人机切换等
    """

    def __init__(
        self,
        config: Optional[AutoReplyConfig] = None,
        llm_engine=None,
        message_collector=None
    ):
        """
        初始化自动回复管理器

        Args:
            config: 自动回复配置
            llm_engine: LLM 引擎实例
            message_collector: 消息收集器实例
        """
        self.config = config or AutoReplyConfig.from_yaml()
        self.llm = llm_engine
        self.collector = message_collector

        # 状态
        self._enabled = self.config.enabled
        self._human_mode_contacts: Dict[str, bool] = {}  # 联系人 -> 是否人工模式
        self._rate_limit_states: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._lock = threading.Lock()

        # 回调
        self._on_reply_callback: Optional[Callable] = None

        logger.info(f"自动回复管理器已初始化，状态：{'启用' if self._enabled else '禁用'}")

    @property
    def enabled(self) -> bool:
        """是否启用自动回复"""
        return self._enabled

    def enable(self):
        """启用自动回复"""
        self._enabled = True
        self.config.enabled = True
        logger.info("自动回复已启用")

    def disable(self):
        """禁用自动回复"""
        self._enabled = False
        self.config.enabled = False
        logger.info("自动回复已禁用")

    def toggle(self) -> bool:
        """切换自动回复状态"""
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    def set_llm(self, llm_engine):
        """设置 LLM 引擎"""
        self.llm = llm_engine
        logger.info("已设置 LLM 引擎")

    def set_collector(self, collector):
        """设置消息收集器"""
        self.collector = collector
        logger.info("已设置消息收集器")

    def set_reply_callback(self, callback: Callable[[str, str], None]):
        """
        设置回复回调

        Args:
            callback: 回调函数 (sender, reply_content) -> None
        """
        self._on_reply_callback = callback

    def can_reply(self, sender: str, content: str) -> tuple:
        """
        检查是否可以自动回复

        Args:
            sender: 发送者 ID
            content: 消息内容

        Returns:
            (can_reply: bool, reason: str)
        """
        with self._lock:
            # 1. 检查是否启用
            if not self._enabled:
                return False, "自动回复未启用"

            # 2. 检查是否在人工模式
            if self._human_mode_contacts.get(sender, False):
                # 检查是否要退出人工模式
                if self._should_exit_human_mode(content):
                    self._human_mode_contacts[sender] = False
                    logger.info(f"联系人 {sender} 退出人工模式")
                else:
                    return False, "人工模式中"

            # 3. 检查人工接管关键词
            if self.config.human_takeover_enabled:
                if self._should_enter_human_mode(content):
                    self._human_mode_contacts[sender] = True
                    logger.info(f"联系人 {sender} 进入人工模式")
                    return False, "触发人工接管"

            # 4. 检查白名单模式
            if self.config.whitelist_mode:
                if sender not in self.config.whitelist_contacts:
                    return False, "不在白名单中"

            # 5. 检查黑名单
            if sender in self.config.exclude_contacts:
                return False, "在黑名单中"

            # 6. 检查频率限制
            rate_state = self._rate_limit_states[sender]
            current_time = time.time()

            # 检查分钟计数
            if current_time - rate_state.minute_start_time >= 60:
                rate_state.reply_count = 0
                rate_state.minute_start_time = current_time

            if rate_state.reply_count >= self.config.max_per_minute:
                return False, f"超过每分钟限制 ({self.config.max_per_minute})"

            # 检查最小间隔
            if current_time - rate_state.last_reply_time < self.config.min_interval:
                return False, f"回复间隔过短 (最小 {self.config.min_interval}s)"

            # 7. 检查训练数据量
            if self.collector:
                stats = self.collector.get_statistics()
                if stats["total_pairs"] < self.config.min_training_data:
                    logger.debug(f"训练数据不足: {stats['total_pairs']}/{self.config.min_training_data}")
                    # 不阻止回复，只是警告

            return True, "可以回复"

    def generate_reply(self, sender: str, content: str, context: Optional[List[Dict]] = None) -> str:
        """
        生成自动回复

        Args:
            sender: 发送者 ID
            content: 收到的消息内容
            context: 上下文消息列表

        Returns:
            生成的回复内容
        """
        if not self.llm:
            logger.warning("LLM 引擎未设置，返回默认回复")
            return self._get_default_reply()

        try:
            # 构建系统提示词
            system_prompt = self.llm.get_default_system_prompt()

            # 构建用户输入
            user_input = content

            # 如果有上下文，添加到输入
            if context:
                context_text = "\n".join([
                    f"{'对方' if not msg.get('is_self') else '我'}: {msg.get('content', '')}"
                    for msg in context[-5:]  # 最近 5 条消息
                ])
                user_input = f"上下文:\n{context_text}\n\n对方: {content}"

            # 生成回复
            reply = self.llm.generate(user_input, system_prompt=system_prompt)

            return reply

        except Exception as e:
            logger.error(f"生成回复失败：{e}")
            return self._get_default_reply()

    def record_reply(self, sender: str):
        """
        记录已发送的回复（用于频率限制）

        Args:
            sender: 发送者 ID
        """
        with self._lock:
            rate_state = self._rate_limit_states[sender]
            rate_state.last_reply_time = time.time()
            rate_state.reply_count += 1

    def process_message(
        self,
        sender: str,
        content: str,
        context: Optional[List[Dict]] = None
    ) -> Optional[str]:
        """
        处理消息并返回自动回复

        Args:
            sender: 发送者 ID
            content: 消息内容
            context: 上下文消息列表

        Returns:
            回复内容，如果不应该回复则返回 None
        """
        # 检查是否可以回复
        can_reply, reason = self.can_reply(sender, content)
        if not can_reply:
            logger.debug(f"不回复 {sender}: {reason}")
            return None

        # 生成回复
        reply = self.generate_reply(sender, content, context)

        # 记录回复
        self.record_reply(sender)

        # 触发回调
        if self._on_reply_callback:
            try:
                self._on_reply_callback(sender, reply)
            except Exception as e:
                logger.error(f"回复回调异常：{e}")

        return reply

    def _should_enter_human_mode(self, content: str) -> bool:
        """检查是否应该进入人工模式"""
        for keyword in self.config.human_takeover_keywords:
            if keyword in content:
                return True
        return False

    def _should_exit_human_mode(self, content: str) -> bool:
        """检查是否应该退出人工模式"""
        exit_keywords = ["#自动", "#auto", "开始自动回复"]
        for keyword in exit_keywords:
            if keyword in content:
                return True
        return False

    def _get_default_reply(self) -> str:
        """获取默认回复"""
        return "我现在有点忙，稍后回复你~"

    def get_contact_status(self, sender: str) -> Dict[str, Any]:
        """
        获取联系人状态

        Args:
            sender: 发送者 ID

        Returns:
            状态信息
        """
        with self._lock:
            rate_state = self._rate_limit_states[sender]
            return {
                "human_mode": self._human_mode_contacts.get(sender, False),
                "reply_count": rate_state.reply_count,
                "last_reply_time": rate_state.last_reply_time,
                "in_whitelist": sender in self.config.whitelist_contacts,
                "in_blacklist": sender in self.config.exclude_contacts
            }

    def reset_contact(self, sender: str):
        """
        重置联系人状态

        Args:
            sender: 发送者 ID
        """
        with self._lock:
            if sender in self._human_mode_contacts:
                del self._human_mode_contacts[sender]
            if sender in self._rate_limit_states:
                del self._rate_limit_states[sender]
        logger.info(f"已重置联系人 {sender} 的状态")

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取自动回复统计

        Returns:
            统计信息
        """
        with self._lock:
            return {
                "enabled": self._enabled,
                "human_mode_count": len([k for k, v in self._human_mode_contacts.items() if v]),
                "active_contacts": len(self._rate_limit_states),
                "whitelist_count": len(self.config.whitelist_contacts),
                "blacklist_count": len(self.config.exclude_contacts)
            }

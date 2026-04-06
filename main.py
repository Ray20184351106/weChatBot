#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信自动回复机器人主入口

基于 pywinauto + OCR 实现 UI 自动化
能够学习用户聊天风格并自动回复消息
支持所有微信版本 (基于 UI 自动化)
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from core.wechat_bot import WeChatBot, WeChatConfig, Message
from core.message_collector import MessageCollector
from core.llm_engine import LLMEngine, LLMConfig
from core.auto_reply import AutoReplyManager, AutoReplyConfig
from core.contact_manager import ContactManager


def setup_logger(log_level: str = "INFO"):
    """
    配置日志

    Args:
        log_level: 日志级别
    """
    logger.remove()
    logger.add(
        "data/logs/bot.log",
        level=log_level,
        rotation="1 day",
        retention="7 days",
        encoding="utf-8"
    )
    logger.add(
        sys.stdout,
        level=log_level,
        format="{time:HH:mm:ss} | {level: <8} | {message}"
    )


class WeChatBotApp:
    """
    微信机器人应用

    整合所有模块，提供完整的自动回复功能
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化应用

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path

        # 模块实例
        self.wechat_config: Optional[WeChatConfig] = None
        self.wechat_bot: Optional[WeChatBot] = None
        self.collector: Optional[MessageCollector] = None
        self.llm: Optional[LLMEngine] = None
        self.auto_reply: Optional[AutoReplyManager] = None
        self.contact_manager: Optional[ContactManager] = None

        # 消息上下文 (用于多轮对话)
        self._message_context: Dict[str, List[Dict]] = {}

        # 运行状态
        self._running = False

        logger.info("微信机器人应用已初始化")

    def load_config(self):
        """加载配置"""
        logger.info(f"加载配置文件：{self.config_path}")

        # 加载微信配置
        self.wechat_config = WeChatConfig.from_yaml(self.config_path)

        # 加载 LLM 配置
        self.llm_config = LLMConfig()
        try:
            import yaml
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                llm_data = data.get("llm", {})
                self.llm_config = LLMConfig(
                    provider=llm_data.get("provider", "openai"),
                    api_key=llm_data.get("api_key", ""),
                    base_url=llm_data.get("base_url", ""),
                    model=llm_data.get("model", "gpt-3.5-turbo"),
                    max_tokens=llm_data.get("max_tokens", 512),
                    temperature=llm_data.get("temperature", 0.7),
                    top_p=llm_data.get("top_p", 0.9)
                )
        except Exception as e:
            logger.warning(f"加载 LLM 配置失败：{e}，使用默认配置")

    def init_modules(self):
        """初始化各模块"""
        logger.info("初始化模块...")

        # 初始化联系人管理器
        self.contact_manager = ContactManager()

        # 初始化消息收集器
        self.collector = MessageCollector()

        # 初始化 LLM 引擎
        self.llm = LLMEngine(self.llm_config)

        # 初始化自动回复管理器
        self.auto_reply = AutoReplyManager(
            config=AutoReplyConfig.from_yaml(self.config_path),
            llm_engine=self.llm,
            message_collector=self.collector
        )

        # 设置回复回调
        self.auto_reply.set_reply_callback(self._on_reply_generated)

        # 初始化微信机器人（传入联系人管理器）
        self.wechat_bot = WeChatBot(self.wechat_config, self.contact_manager)

        logger.info("模块初始化完成")

    def connect(self) -> bool:
        """
        连接微信

        Returns:
            是否连接成功
        """
        if not self.wechat_bot.connect():
            logger.error("微信连接失败，请确保微信客户端已运行")
            return False

        logger.info("微信连接成功")

        # 获取账号信息
        info = self.wechat_bot.get_self_info()
        if info:
            logger.info(f"已登录账号：{info.get('name')} ({info.get('wxid')})")
            self.collector.set_user_wxid(info.get('wxid', ''))

        return True

    def disconnect(self):
        """断开连接"""
        self._running = False
        if self.wechat_bot:
            self.wechat_bot.stop_listening()
            self.wechat_bot.disconnect()
        logger.info("已断开微信连接")

    def _on_message(self, msg: Message):
        """
        消息处理回调

        Args:
            msg: 收到的消息
        """
        # 忽略自己发送的消息
        if msg.is_self:
            # 记录自己发送的消息到收集器
            self.collector.on_message_sent(msg.content, msg.sender)
            return

        sender = msg.sender

        # 更新消息上下文
        if sender not in self._message_context:
            self._message_context[sender] = []
        self._message_context[sender].append({
            "content": msg.content,
            "is_self": False,
            "timestamp": msg.timestamp
        })
        # 保留最近 10 条消息
        if len(self._message_context[sender]) > 10:
            self._message_context[sender] = self._message_context[sender][-10:]

        # 记录收到的消息
        logger.info(f"[收到] {sender}: {msg.content[:50]}{'...' if len(msg.content) > 50 else ''}")

        # 记录到收集器
        self.collector.on_message_received(msg)

        # 显示统计
        stats = self.collector.get_statistics()
        logger.debug(f"已收集 {stats['total_pairs']} 条对话对")

        # 处理自动回复
        self._handle_auto_reply(msg)

    def _handle_auto_reply(self, msg: Message):
        """
        处理自动回复

        Args:
            msg: 收到的消息
        """
        sender = msg.sender
        content = msg.content

        # 检查是否是群消息
        if msg.is_group:
            logger.debug(f"忽略群聊消息：{msg.room_id}")
            return

        # 获取上下文
        context = self._message_context.get(sender, [])

        # 处理消息，生成回复
        reply = self.auto_reply.process_message(sender, content, context)

        if reply:
            # 发送回复
            self._send_reply(sender, reply)

    def _send_reply(self, sender: str, reply: str):
        """
        发送回复

        Args:
            sender: 接收者
            reply: 回复内容
        """
        logger.info(f"[回复] {sender}: {reply[:50]}{'...' if len(reply) > 50 else ''}")

        # 发送消息
        success = self.wechat_bot.send_text(reply, sender)

        if success:
            # 记录发送的消息
            self.collector.on_message_sent(reply, sender)

            # 更新上下文
            if sender not in self._message_context:
                self._message_context[sender] = []
            self._message_context[sender].append({
                "content": reply,
                "is_self": True,
                "timestamp": int(time.time())
            })
        else:
            logger.error(f"发送回复失败：{sender}")

    def _on_reply_generated(self, sender: str, reply: str):
        """
        回复生成回调

        Args:
            sender: 接收者
            reply: 回复内容
        """
        # 可以在这里添加额外的处理逻辑
        pass

    def start(self):
        """启动机器人"""
        logger.info("=" * 60)
        logger.info("微信自动回复机器人")
        logger.info("=" * 60)

        # 加载配置
        self.load_config()

        # 初始化模块
        self.init_modules()

        # 连接微信
        if not self.connect():
            return

        # 显示状态
        self._show_status()

        # 开始监听
        self._running = True
        self.wechat_bot.start_listening(self._on_message)

        logger.info("=" * 60)
        logger.info("机器人已启动，按 Ctrl+C 退出")
        logger.info("=" * 60)

        try:
            # 保持主线程运行
            while self._running and self.wechat_bot._running:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("收到退出信号...")

        finally:
            self.disconnect()
            self._show_summary()

    def stop(self):
        """停止机器人"""
        self._running = False

    def _show_status(self):
        """显示当前状态"""
        stats = self.collector.get_statistics()
        auto_stats = self.auto_reply.get_statistics()

        logger.info("当前状态：")
        logger.info(f"  - 自动回复：{'启用' if auto_stats['enabled'] else '禁用'}")
        logger.info(f"  - 训练数据：{stats['total_pairs']} 条")
        logger.info(f"  - 白名单联系人：{auto_stats['whitelist_count']} 个")
        logger.info(f"  - 黑名单联系人：{auto_stats['blacklist_count']} 个")

        if not auto_stats['enabled']:
            logger.info("")
            logger.info("提示：自动回复当前未启用")
            logger.info("  - 收集训练数据后，修改 config/config.yaml 启用")
            logger.info("  - 或发送 #auto 命令启用")

    def _show_summary(self):
        """显示运行摘要"""
        stats = self.collector.get_statistics()
        logger.info("=" * 60)
        logger.info("运行摘要：")
        logger.info(f"  - 本次收集对话对：{stats['total_pairs']} 条")
        logger.info(f"  - 涉及联系人：{stats['total_rooms']} 个")
        logger.info("=" * 60)

        if stats['total_pairs'] > 0:
            logger.info("导出训练数据：")
            logger.info("  python manage_data.py export")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="微信自动回复机器人")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )
    parser.add_argument(
        "--no-auto-reply",
        action="store_true",
        help="禁用自动回复（仅收集数据）"
    )

    args = parser.parse_args()

    # 配置日志
    setup_logger("DEBUG" if args.debug else "INFO")

    # 创建应用
    app = WeChatBotApp(config_path=args.config)

    # 如果指定禁用自动回复
    if args.no_auto_reply:
        app.auto_reply = AutoReplyManager()
        app.auto_reply.disable()

    # 启动
    app.start()


if __name__ == "__main__":
    main()
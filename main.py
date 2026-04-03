#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信自动回复机器人主入口

基于 WeChatHook + WeClone 实现
能够学习用户聊天风格并自动回复消息
支持微信版本：3.9.5.81 ~ 4.1.1
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from core.wechat_bot import WeChatBot
from core.message_collector import MessageCollector
from core.llm_engine import LLMEngine


def setup_logger():
    """配置日志"""
    logger.remove()
    logger.add(
        "data/logs/bot.log",
        level="INFO",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8"
    )
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )


def main():
    """主函数"""
    setup_logger()
    logger.info("正在启动微信自动回复机器人...")

    # 1. 初始化各模块
    wechat_bot = WeChatBot()
    collector = MessageCollector()
    llm = LLMEngine()

    # 2. 连接微信
    if not wechat_bot.connect():
        logger.error("微信连接失败，请确保微信客户端已运行且版本正确")
        return

    # 3. 获取账号信息
    info = wechat_bot.get_self_info()
    if info:
        logger.info(f"已登录账号：{info.get('name')} ({info.get('wxid')})")
        collector.set_user_wxid(info.get('wxid', ''))

    # 4. 定义消息处理回调
    def on_message(msg):
        """收到消息时的处理"""
        # 忽略自己发送的消息
        if msg.is_self:
            return

        # 忽略群聊 (可根据需要修改)
        if msg.is_group:
            logger.debug(f"忽略群聊消息：{msg.room_id}")
            return

        # 记录消息
        collector.on_message_received(msg)

        # TODO: 自动回复逻辑 (当前仅记录，不自动回复)
        # 当收集到足够数据后再启用自动回复
        stats = collector.get_statistics()
        if stats["total_pairs"] >= 100:
            # 数据充足，可以开始自动回复
            # reply = llm.generate(msg.content)
            # wechat_bot.send_text(reply, msg.sender)
            pass
        else:
            logger.info(f"正在收集数据... 当前：{stats['total_pairs']}/100 条")

    # 5. 启动消息监听
    logger.info("开始监听消息...")
    logger.warning("注意：当前模式仅收集数据，不会自动回复")
    logger.warning("收集至少 100 条对话后再启用自动回复功能")

    try:
        wechat_bot.start_listening(on_message)
    except KeyboardInterrupt:
        logger.info("收到退出信号...")
    finally:
        wechat_bot.stop_listening()
        wechat_bot.disconnect()

    logger.info("机器人已退出")


if __name__ == "__main__":
    main()

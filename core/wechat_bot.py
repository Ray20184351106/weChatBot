#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat UI 自动化模块

基于 pywinauto + OCR 实现微信消息监听和发送
支持所有微信版本 (因为基于 UI 自动化，不依赖特定版本)
"""

import time
import re
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import threading

from loguru import logger

# 尝试导入 pywinauto
try:
    from pywinauto import Application, Desktop, findwindows
    from pywinauto.keyboard import send_keys
    import win32clipboard
    PYWINAUTO_AVAILABLE = True
except ImportError:
    logger.warning("pywinauto 未安装，请运行：pip install pywinauto pywin32")
    PYWINAUTO_AVAILABLE = False

# 尝试导入 OCR 库
try:
    import os
    import pyautogui
    from PIL import Image
    import pytesseract

    # 配置 Tesseract 路径和环境变量
    pytesseract.pytesseract.tesseract_cmd = r'E:\Tesseract\tesseract.exe'
    os.environ['TESSDATA_PREFIX'] = 'E:/Tesseract/tessdata/'

    OCR_AVAILABLE = True
    logger.info("OCR 初始化成功 (Tesseract 5.5.0)")
except ImportError as e:
    logger.warning(f"OCR 库未安装，部分功能不可用：{e}")
    OCR_AVAILABLE = False
except Exception as e:
    logger.warning(f"OCR 初始化失败：{e}")
    OCR_AVAILABLE = False


@dataclass
class Message:
    """消息数据类"""
    id: str
    type: str  # text, image, etc.
    sender: str
    sender_name: str
    content: str
    room_id: Optional[str] = None
    is_group: bool = False
    is_self: bool = False
    timestamp: int = 0


class WeChatBot:
    """
    微信机器人封装类

    基于 pywinauto 实现微信消息的收发功能
    支持所有微信版本
    """

    def __init__(self):
        """初始化微信机器人"""
        self.app: Optional[Application] = None
        self.main_window = None
        self._running = False
        self._callbacks: List[Callable[[Message], None]] = []
        self._user_wxid: Optional[str] = None
        self._listen_thread: Optional[threading.Thread] = None

        # 消息历史用于去重
        self._message_history: List[str] = []
        self._max_history = 100

        # 微信窗口信息
        self._chat_panel = None
        self._message_list = None

        logger.info("初始化 WeChatBot (UI 自动化)")

    def connect(self) -> bool:
        """
        连接到微信

        Returns:
            连接是否成功
        """
        if not PYWINAUTO_AVAILABLE:
            logger.error("pywinauto 未安装")
            return False

        try:
            # 尝试连接已运行的微信 (支持微信 4.x 版本)
            # 微信 4.x 使用 WeChatAppEx.exe，3.x 使用 WeChat.exe
            self.app = None
            for process_name in ["WeChatAppEx.exe", "WeChat.exe"]:
                try:
                    self.app = Application(backend="uia").connect(path=process_name, timeout=3)
                    logger.info(f"通过 {process_name} 连接到微信")
                    break
                except:
                    continue

            if not self.app:
                logger.error("未找到微信进程，请先登录微信")
                return False

            # 使用 Desktop 查找微信窗口 (兼容微信 4.x)
            desktop = Desktop(backend="uia")
            wechat_window = None
            for win in desktop.windows():
                try:
                    title = win.window_text()
                    # 查找主窗口（排除子窗口）
                    if title == "微信" and win.is_visible():
                        rect = win.rectangle()
                        if rect.width() > 100 and rect.height() > 100:
                            wechat_window = win
                            break
                except:
                    continue

            if wechat_window:
                self.main_window = wechat_window
                self._running = True
                logger.info("微信连接成功")
                rect = self.main_window.rectangle()
                logger.info(f"窗口位置：({rect.left}, {rect.top}), 尺寸：{rect.width()}x{rect.height()}")
                return True
            else:
                logger.error("未找到微信窗口，请确保微信已登录")
                return False

        except findwindows.ElementNotFoundError:
            logger.error("未找到微信进程，请先登录微信")
            return False
        except Exception as e:
            logger.error(f"连接失败：{e}")
            return False

    def disconnect(self):
        """断开微信连接"""
        self._running = False
        self.app = None
        self.main_window = None
        logger.info("已断开微信连接")

    def is_login(self) -> bool:
        """检查登录状态"""
        if not self._running or not self.main_window:
            return False
        try:
            return self.main_window.exists(timeout=1)
        except:
            return False

    def get_self_info(self) -> Optional[Dict[str, Any]]:
        """获取当前账号信息"""
        # UI 自动化方式获取账号信息比较复杂
        # 这里返回基本信息
        return {
            "wxid": self._user_wxid or "unknown",
            "name": "当前用户",
            "mobile": "",
            "home_dir": ""
        }

    def _find_chat_window(self, contact_name: str = None) -> Optional[Any]:
        """
        查找聊天窗口

        Args:
            contact_name: 联系人/群聊名称，如果为 None 则返回当前激活的聊天窗口

        Returns:
            聊天窗口控件
        """
        if not self.main_window:
            return None

        try:
            # 尝试不同的控件查找方式
            # 微信的消息列表通常是 List 或 Pane 类型

            # 方式 1: 查找消息列表
            panels = self.main_window.descendants(control_type="Pane")
            for panel in panels:
                try:
                    title = panel.window_text()
                    if title and len(title) > 0:
                        # 可能是聊天窗口
                        return panel
                except:
                    continue

            # 方式 2: 查找列表
            lists = self.main_window.descendants(control_type="List")
            if lists:
                return lists[0]

        except Exception as e:
            logger.debug(f"查找聊天窗口失败：{e}")

        return None

    def _ocr_screen(self, left: int = 0, top: int = 0, right: int = 800, bottom: int = 600) -> str:
        """
        对指定区域进行 OCR

        Args:
            left, top, right, bottom: 屏幕区域坐标

        Returns:
            识别的文字内容
        """
        if not OCR_AVAILABLE:
            return ""

        try:
            # 截取屏幕区域
            screenshot = pyautogui.screenshot(region=(left, top, right - left, bottom - top))

            # OCR 识别
            text = pytesseract.image_to_string(screenshot, lang='chi_sim+eng')
            return text.strip()
        except Exception as e:
            logger.debug(f"OCR 识别失败：{e}")
            return ""

    def _get_wechat_window_rect(self) -> tuple:
        """获取微信窗口位置"""
        if not self.main_window:
            return (0, 0, 800, 600)

        try:
            rect = self.main_window.rectangle()
            return (rect.left, rect.top, rect.right, rect.bottom)
        except:
            return (0, 0, 800, 600)

    def send_text(self, content: str, receiver: str = None, at_list: Optional[List[str]] = None) -> bool:
        """
        发送文本消息

        Args:
            content: 消息内容
            receiver: 接收者名称 (可选，为 None 则发送给当前聊天窗口)
            at_list: @的用户列表

        Returns:
            发送是否成功
        """
        if not self._running or not self.main_window:
            logger.error("未连接微信")
            return False

        try:
            # 1. 激活微信窗口
            self.main_window.set_focus()
            time.sleep(0.5)

            # 2. 如果指定了接收者，先搜索联系人
            if receiver:
                # 使用 Ctrl+F 搜索联系人 (微信快捷键)
                send_keys('^f')
                time.sleep(0.3)

                # 输入联系人名称
                send_keys(receiver)
                time.sleep(0.5)

                # 按 Enter 打开聊天
                send_keys('{ENTER}')
                time.sleep(0.5)

            # 3. 找到输入框并输入内容
            # 微信的输入框通常是 Edit 控件
            edit_boxes = self.main_window.descendants(control_type="Edit")

            if edit_boxes:
                # 找到最后一个（最下面的）输入框
                input_box = edit_boxes[-1]
                input_box.set_focus()
                input_box.set_text(content)

                # 4. 处理 @ 功能
                if at_list:
                    for name in at_list:
                        send_keys(f'@{name}')
                        time.sleep(0.2)
                        send_keys(' ')

                # 5. 发送 (Ctrl+Enter 或 Enter)
                send_keys('^{ENTER}')

                logger.debug(f"发送消息：{content[:50]}...")
                return True
            else:
                # 备用方案：使用剪贴板
                logger.debug("未找到输入框，使用剪贴板方式")
                # 使用 win32clipboard 设置剪贴板内容
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(content)
                win32clipboard.CloseClipboard()
                time.sleep(0.2)
                send_keys('^v')
                time.sleep(0.2)
                send_keys('^{ENTER}')
                return True

        except Exception as e:
            logger.error(f"发送消息失败：{e}")
            return False

    def _parse_message(self, text: str) -> Optional[Message]:
        """
        解析 OCR 识别的消息文本

        Args:
            text: OCR 识别的文本

        Returns:
            Message 对象或 None
        """
        if not text:
            return None

        # 简单的消息解析逻辑
        # 实际格式可能是：
        # 用户名
        # 消息内容
        # 时间

        lines = text.strip().split('\n')
        if len(lines) < 2:
            return None

        # 尝试提取发送者和内容
        sender = lines[0].strip() if lines else "未知"
        content = '\n'.join(lines[1:-1]).strip() if len(lines) > 2 else lines[-1].strip()

        # 去重
        if content in self._message_history:
            return None

        # 添加到历史
        self._message_history.append(content)
        if len(self._message_history) > self._max_history:
            self._message_history.pop(0)

        # 判断是否是群消息
        is_group = '@' in content or '群聊' in text

        return Message(
            id=str(int(time.time() * 1000)),
            type="text",
            sender=sender,
            sender_name=sender,
            content=content,
            is_group=is_group,
            is_self=False,
            timestamp=int(time.time())
        )

    def _listen_loop(self):
        """监听循环（在独立线程中运行）"""
        logger.info("消息监听线程已启动")

        last_check_time = time.time()
        check_interval = 2  # 每 2 秒检查一次

        while self._running:
            time.sleep(check_interval)

            try:
                # 检查微信窗口是否仍然活跃
                if not self.is_login():
                    logger.warning("微信窗口已关闭，停止监听")
                    self._running = False
                    break

                # 获取当前激活的聊天窗口
                chat_panel = self._find_chat_window()
                if not chat_panel:
                    continue

                # 获取窗口位置
                rect = chat_panel.rectangle() if hasattr(chat_panel, 'rectangle') else None
                if not rect:
                    continue

                # OCR 识别消息区域
                # 这里简化处理，实际需要根据微信 UI 结构调整
                ocr_text = self._ocr_screen(
                    left=rect.left + 50,
                    top=rect.top + 100,
                    right=rect.right - 50,
                    bottom=rect.bottom - 150
                )

                # 解析消息
                msg = self._parse_message(ocr_text)
                if msg:
                    logger.info(f"收到消息 [{msg.sender}]: {msg.content[:30]}...")

                    # 调用回调
                    for cb in self._callbacks:
                        try:
                            cb(msg)
                        except Exception as e:
                            logger.error(f"消息回调异常：{e}")

            except Exception as e:
                logger.debug(f"监听循环异常：{e}")
                continue

    def start_listening(self, callback: Callable[[Message], None]):
        """
        开始监听消息

        Args:
            callback: 收到消息时的回调函数
        """
        if not self._running:
            logger.error("未连接微信")
            return

        self._callbacks.append(callback)

        # 启动监听线程
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()

        logger.info("开始监听消息 (UI 自动化模式)")
        logger.warning("注意：UI 自动化模式需要微信窗口保持在前台")
        logger.warning("建议将微信窗口放在屏幕中央，不要最小化")

    def stop_listening(self):
        """停止监听消息"""
        self._running = False
        if self._listen_thread:
            self._listen_thread.join(timeout=3)
        logger.info("停止监听消息")

    def get_contacts(self) -> List[Dict[str, Any]]:
        """获取联系人列表（简化版）"""
        # UI 自动化方式获取联系人比较复杂
        # 这里返回空列表
        logger.warning("get_contacts 暂未实现")
        return []

    def get_chat_history(self, room_id: Optional[str] = None, count: int = 100) -> List[Message]:
        """获取聊天记录"""
        logger.warning("get_chat_history 暂未实现")
        return []

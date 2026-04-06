#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat UI 自动化模块

基于 pywinauto + OCR 实现微信消息监听和发送
支持所有微信版本 (因为基于 UI 自动化，不依赖特定版本)
"""

import time
import re
import os
from typing import Optional, Callable, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading
from pathlib import Path

from loguru import logger

# 尝试导入 YAML 配置
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

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
    import pyautogui
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract

    OCR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OCR 库未安装，部分功能不可用：{e}")
    OCR_AVAILABLE = False
except Exception as e:
    logger.warning(f"OCR 初始化失败：{e}")
    OCR_AVAILABLE = False


@dataclass
class WeChatConfig:
    """
    微信机器人配置类

    支持自定义 Tesseract 路径、OCR 参数、检查间隔等
    """
    # Tesseract 配置
    tesseract_path: str = r"E:\Tesseract\tesseract.exe"
    tessdata_path: str = r"E:\Tesseract\tessdata"
    ocr_language: str = "chi_sim+eng"

    # OCR 区域偏移比例 (相对于窗口尺寸)
    ocr_offset_ratio_left: float = 0.05
    ocr_offset_ratio_top: float = 0.15
    ocr_offset_ratio_right: float = 0.05
    ocr_offset_ratio_bottom: float = 0.20

    # OCR 固定偏移 (像素)
    ocr_fixed_offset_left: int = 50
    ocr_fixed_offset_top: int = 100
    ocr_fixed_offset_right: int = 50
    ocr_fixed_offset_bottom: int = 150

    # 图像预处理选项
    ocr_preprocessing: bool = True
    ocr_grayscale: bool = True
    ocr_threshold: bool = False
    ocr_denoise: bool = True
    ocr_enhance_contrast: bool = True

    # 消息检查间隔
    check_interval: float = 2.0

    # 消息发送延迟配置
    send_delay_window_focus: float = 0.5
    send_delay_search_contact: float = 0.3
    send_delay_after_input: float = 0.2
    send_delay_after_send: float = 0.5

    # 发送重试配置
    send_max_retries: int = 3
    send_retry_delay: float = 1.0

    # 消息去重配置
    dedup_max_history: int = 100

    # 窗口最小尺寸
    min_window_width: int = 100
    min_window_height: int = 100

    @classmethod
    def from_yaml(cls, config_path: str = "config/config.yaml") -> "WeChatConfig":
        """
        从 YAML 文件加载配置

        Args:
            config_path: 配置文件路径

        Returns:
            WeChatConfig 实例
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

            # 解析配置
            ocr_config = data.get("ocr", {})
            wechat_config = data.get("wechat", {})
            send_config = data.get("send", {})
            parse_config = data.get("parse", {})

            # OCR 偏移比例
            offset_ratio = ocr_config.get("offset_ratio", {})
            fixed_offset = ocr_config.get("fixed_offset", {})
            preprocessing = ocr_config.get("preprocessing", {})

            # 发送延迟
            delays = send_config.get("delays", {})
            retry = send_config.get("retry", {})

            return cls(
                tesseract_path=ocr_config.get("tesseract_path", cls.tesseract_path),
                tessdata_path=ocr_config.get("tessdata_path", cls.tessdata_path),
                ocr_language=ocr_config.get("language", cls.ocr_language),
                ocr_offset_ratio_left=offset_ratio.get("left", cls.ocr_offset_ratio_left),
                ocr_offset_ratio_top=offset_ratio.get("top", cls.ocr_offset_ratio_top),
                ocr_offset_ratio_right=offset_ratio.get("right", cls.ocr_offset_ratio_right),
                ocr_offset_ratio_bottom=offset_ratio.get("bottom", cls.ocr_offset_ratio_bottom),
                ocr_fixed_offset_left=fixed_offset.get("left", cls.ocr_fixed_offset_left),
                ocr_fixed_offset_top=fixed_offset.get("top", cls.ocr_fixed_offset_top),
                ocr_fixed_offset_right=fixed_offset.get("right", cls.ocr_fixed_offset_right),
                ocr_fixed_offset_bottom=fixed_offset.get("bottom", cls.ocr_fixed_offset_bottom),
                ocr_preprocessing=preprocessing.get("enabled", cls.ocr_preprocessing),
                ocr_grayscale=preprocessing.get("grayscale", cls.ocr_grayscale),
                ocr_threshold=preprocessing.get("threshold", cls.ocr_threshold),
                ocr_denoise=preprocessing.get("denoise", cls.ocr_denoise),
                ocr_enhance_contrast=preprocessing.get("enhance_contrast", cls.ocr_enhance_contrast),
                check_interval=wechat_config.get("check_interval", cls.check_interval),
                send_delay_window_focus=delays.get("window_focus", cls.send_delay_window_focus),
                send_delay_search_contact=delays.get("search_contact", cls.send_delay_search_contact),
                send_delay_after_input=delays.get("after_input", cls.send_delay_after_input),
                send_delay_after_send=delays.get("after_send", cls.send_delay_after_send),
                send_max_retries=retry.get("max_attempts", cls.send_max_retries),
                send_retry_delay=retry.get("retry_delay", cls.send_retry_delay),
                dedup_max_history=parse_config.get("dedup", {}).get("max_history", cls.dedup_max_history),
                min_window_width=wechat_config.get("min_window_width", cls.min_window_width),
                min_window_height=wechat_config.get("min_window_height", cls.min_window_height),
            )

        except Exception as e:
            logger.error(f"加载配置文件失败：{e}，使用默认配置")
            return cls()

    def setup_tesseract(self):
        """配置 Tesseract 路径"""
        if OCR_AVAILABLE:
            try:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
                os.environ['TESSDATA_PREFIX'] = self.tessdata_path
                logger.info(f"Tesseract 配置完成：{self.tesseract_path}")
            except Exception as e:
                logger.warning(f"Tesseract 配置失败：{e}")


@dataclass
class Message:
    """消息数据类"""
    id: str
    type: str  # text, image, etc.
    sender: str
    sender_name: str = ""
    content: str = ""
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

    def __init__(self, config: Optional[WeChatConfig] = None, contact_manager=None):
        """
        初始化微信机器人

        Args:
            config: 配置对象，如果为 None 则从默认配置加载
            contact_manager: 联系人管理器实例
        """
        self.config = config or WeChatConfig.from_yaml()

        # 配置 Tesseract
        self.config.setup_tesseract()

        self.app: Optional[Application] = None
        self.main_window = None
        self._running = False
        self._callbacks: List[Callable[[Message], None]] = []
        self._user_wxid: Optional[str] = None
        self._listen_thread: Optional[threading.Thread] = None

        # 消息历史用于去重
        self._message_history: List[str] = []
        self._max_history = self.config.dedup_max_history

        # 微信窗口信息
        self._chat_panel = None
        self._message_list = None
        self._last_message_content: str = ""  # 用于发送确认

        # 联系人管理
        self._contact_manager = contact_manager

        logger.info(f"初始化 WeChatBot (UI 自动化) - 检查间隔: {self.config.check_interval}s")

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
                    # 微信 4.x 窗口标题可能是 "微信" 或 "Weixin"
                    is_wechat = title in ["微信", "Weixin", "WeChat"] or "微信" in title
                    if is_wechat and win.is_visible():
                        rect = win.rectangle()
                        if rect.width() > self.config.min_window_width and rect.height() > self.config.min_window_height:
                            # 优先选择可见且尺寸合理的窗口
                            if wechat_window is None or rect.width() * rect.height() > wechat_window.rectangle().width() * wechat_window.rectangle().height():
                                wechat_window = win
                                logger.debug(f"找到微信窗口: {title}")
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
            # 检查窗口是否可见且有效
            return self.main_window.is_visible() and self.main_window.is_enabled()
        except:
            try:
                # 备用检查方式
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

        针对 WeChat 4.x 优化，使用多种查找策略

        Args:
            contact_name: 联系人/群聊名称，如果为 None 则返回当前激活的聊天窗口

        Returns:
            聊天窗口控件
        """
        if not self.main_window:
            return None

        try:
            # WeChat 4.x 特定的控件类名
            wechat4x_class_names = [
                "WeChatMainWndForPC",
                "Chrome_WidgetWin_0",
                "WeChatAppEx"
            ]

            # 策略 1: 查找消息列表控件 (List 类型)
            lists = self.main_window.descendants(control_type="List")
            if lists:
                for list_ctrl in lists:
                    try:
                        rect = list_ctrl.rectangle()
                        # 消息列表通常在窗口中部，有一定高度
                        if rect.height() > 100 and rect.width() > 200:
                            logger.debug(f"找到消息列表控件: {rect.width()}x{rect.height()}")
                            return list_ctrl
                    except:
                        continue

            # 策略 2: 查找 Pane 控件 (WeChat 4.x 消息区域)
            panels = self.main_window.descendants(control_type="Pane")
            if panels:
                for panel in panels:
                    try:
                        rect = panel.rectangle()
                        # 消息区域通常占据窗口大部分宽度
                        window_rect = self.main_window.rectangle()
                        if rect.width() > window_rect.width() * 0.5 and rect.height() > 200:
                            logger.debug(f"找到消息区域 Pane: {rect.width()}x{rect.height()}")
                            return panel
                    except:
                        continue

            # 策略 3: 按 ClassName 查找 (WeChat 4.x)
            for class_name in wechat4x_class_names:
                try:
                    elements = self.main_window.descendants(class_name=class_name)
                    if elements:
                        logger.debug(f"通过 ClassName 找到控件: {class_name}")
                        return elements[0]
                except:
                    continue

            # 策略 4: 遍历所有子控件，找到最大的可见区域
            all_descendants = self.main_window.descendants()
            best_candidate = None
            best_area = 0

            for ctrl in all_descendants:
                try:
                    if not ctrl.is_visible():
                        continue
                    rect = ctrl.rectangle()
                    area = rect.width() * rect.height()
                    if area > best_area and rect.height() > 150:
                        best_area = area
                        best_candidate = ctrl
                except:
                    continue

            if best_candidate:
                logger.debug(f"通过遍历找到消息区域，面积: {best_area}")
                return best_candidate

            # 策略 5: 直接使用主窗口
            logger.warning("未找到消息子控件，使用主窗口")
            return self.main_window

        except Exception as e:
            logger.debug(f"查找聊天窗口失败：{e}")

        return None

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        图像预处理，提升 OCR 精度

        Args:
            image: 原始 PIL 图像

        Returns:
            处理后的图像
        """
        if not self.config.ocr_preprocessing:
            return image

        try:
            # 灰度化
            if self.config.ocr_grayscale:
                image = image.convert("L")

            # 对比度增强
            if self.config.ocr_enhance_contrast:
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)

            # 噪声去除
            if self.config.ocr_denoise:
                image = image.filter(ImageFilter.MedianFilter(size=3))

            # 二值化
            if self.config.ocr_threshold:
                image = image.point(lambda x: 0 if x < 128 else 255, "1")

            return image

        except Exception as e:
            logger.debug(f"图像预处理失败：{e}")
            return image

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

            # 图像预处理
            screenshot = self._preprocess_image(screenshot)

            # OCR 识别
            text = pytesseract.image_to_string(
                screenshot,
                lang=self.config.ocr_language,
                config="--psm 6"  # 假设为均匀分布的文本块
            )
            return text.strip()
        except Exception as e:
            logger.debug(f"OCR 识别失败：{e}")
            return ""

    def _calculate_ocr_region(self, chat_panel) -> Tuple[int, int, int, int]:
        """
        动态计算 OCR 区域

        根据窗口尺寸和配置的偏移比例计算 OCR 区域

        Args:
            chat_panel: 聊天面板控件

        Returns:
            (left, top, right, bottom) 坐标
        """
        if not chat_panel:
            return (0, 0, 800, 600)

        try:
            rect = chat_panel.rectangle()
            width = rect.width()
            height = rect.height()

            # 动态计算偏移
            offset_left = int(width * self.config.ocr_offset_ratio_left) + self.config.ocr_fixed_offset_left
            offset_top = int(height * self.config.ocr_offset_ratio_top) + self.config.ocr_fixed_offset_top
            offset_right = int(width * self.config.ocr_offset_ratio_right) + self.config.ocr_fixed_offset_right
            offset_bottom = int(height * self.config.ocr_offset_ratio_bottom) + self.config.ocr_fixed_offset_bottom

            # 计算最终区域
            left = rect.left + offset_left
            top = rect.top + offset_top
            right = rect.right - offset_right
            bottom = rect.bottom - offset_bottom

            logger.debug(f"OCR 区域: ({left}, {top}) -> ({right}, {bottom}), 尺寸: {right-left}x{bottom-top}")

            return (left, top, right, bottom)

        except Exception as e:
            logger.debug(f"计算 OCR 区域失败：{e}")
            return (0, 0, 800, 600)

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
        发送文本消息到当前聊天窗口

        Args:
            content: 消息内容
            receiver: 已废弃，保留参数兼容性
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
            time.sleep(self.config.send_delay_window_focus)

            # 2. 查找聊天输入框
            edit_boxes = self.main_window.descendants(control_type="Edit")

            input_box = None
            if edit_boxes:
                # 找到最大的 Edit 作为输入框
                for box in edit_boxes:
                    try:
                        rect = box.rectangle()
                        if rect.width() > 200 and rect.height() > 20:
                            input_box = box
                            break
                    except:
                        continue

            if input_box:
                # 使用 set_focus 和 set_text
                input_box.set_focus()
                time.sleep(0.2)
                input_box.set_text(content)
                time.sleep(self.config.send_delay_after_input)

                # 发送
                send_keys('{ENTER}')
                time.sleep(self.config.send_delay_after_send)

                logger.info(f"发送消息成功：{content[:30]}...")
                return True
            else:
                # 备用：剪贴板方式
                logger.debug("使用剪贴板方式")
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(content)
                win32clipboard.CloseClipboard()
                time.sleep(0.2)

                send_keys('^v')
                time.sleep(self.config.send_delay_after_input)
                send_keys('{ENTER}')
                time.sleep(self.config.send_delay_after_send)

                logger.info(f"发送消息成功(剪贴板)：{content[:30]}...")
                return True

        except Exception as e:
            logger.error(f"发送消息失败：{e}")
            return False

    def send_text_with_retry(self, content: str, receiver: str = None, max_retries: int = None) -> bool:
        """
        带重试机制的发送消息

        Args:
            content: 消息内容
            receiver: 接收者名称
            max_retries: 最大重试次数，默认使用配置值

        Returns:
            发送是否成功
        """
        if max_retries is None:
            max_retries = self.config.send_max_retries

        for attempt in range(max_retries):
            if self.send_text(content, receiver):
                # 发送确认检查
                time.sleep(1.0)  # 等待消息出现
                new_content = self._get_last_message_content()
                if new_content != self._last_message_content:
                    logger.debug("消息发送确认成功")
                    return True
                else:
                    logger.warning(f"发送确认失败，重试 {attempt + 1}/{max_retries}")
            else:
                logger.warning(f"发送失败，重试 {attempt + 1}/{max_retries}")

            time.sleep(self.config.send_retry_delay)

        return False

    def _get_last_message_content(self) -> str:
        """
        获取最后一条消息内容（用于发送确认）

        Returns:
            最后一条消息的内容摘要
        """
        try:
            chat_panel = self._find_chat_window()
            if not chat_panel:
                return ""

            region = self._calculate_ocr_region(chat_panel)
            ocr_text = self._ocr_screen(*region)

            # 获取最后几行作为内容标识
            lines = ocr_text.strip().split('\n')
            return '\n'.join(lines[-5:]) if lines else ""

        except Exception as e:
            logger.debug(f"获取最后消息失败：{e}")
            return ""

    def _parse_message(self, text: str) -> Optional[Message]:
        """
        解析 OCR 识别的消息文本

        支持时间戳识别和发送/接收消息区分

        Args:
            text: OCR 识别的文本

        Returns:
            Message 对象或 None
        """
        if not text:
            return None

        # 时间戳识别正则模式
        timestamp_patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})', 'full_date'),  # 2024-01-01 12:34
            (r'昨天\s*(\d{1,2}):(\d{2})', 'yesterday'),  # 昨天 12:34
            (r'前天\s*(\d{1,2}):(\d{2})', 'day_before'),  # 前天 12:34
            (r'(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})', 'short_date'),  # 1/1 12:34
            (r'(\d{1,2}):(\d{2})', 'time_only'),  # 12:34
        ]

        lines = text.strip().split('\n')
        if len(lines) < 1:
            return None

        # 解析时间戳和消息行
        timestamp_str = ""
        timestamp = int(time.time())
        content_lines = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 检查是否是时间戳行
            is_timestamp = False
            for pattern, ptype in timestamp_patterns:
                match = re.search(pattern, line_stripped)
                if match:
                    timestamp_str = line_stripped
                    is_timestamp = True
                    # 尝试解析具体时间
                    timestamp = self._parse_timestamp(match, ptype)
                    break

            if not is_timestamp:
                content_lines.append(line_stripped)

        if not content_lines:
            return None

        # 解析发送者和内容
        sender = "未知"
        content = ""
        is_self = False
        room_id = None

        # 检测是否是自己发送的消息
        is_self, processed_lines = self._detect_and_extract_self(content_lines)
        content_lines = processed_lines

        if content_lines:
            # 第一行通常是发送者名称
            sender = content_lines[0]

            # 剩余行是消息内容
            if len(content_lines) > 1:
                content = '\n'.join(content_lines[1:]).strip()
            else:
                # 只有一行时，可能是纯消息内容（无发送者标记）
                content = sender
                sender = "未知"

        # 清理内容
        content = self._clean_content(content)

        if not content:
            return None

        # 去重
        content_hash = f"{sender}:{content[:50]}"
        if content_hash in self._message_history:
            return None

        # 添加到历史
        self._message_history.append(content_hash)
        if len(self._message_history) > self._max_history:
            self._message_history.pop(0)

        # 判断是否是群消息
        is_group = self._detect_group_message(text, sender)

        # 生成消息 ID
        msg_id = str(int(time.time() * 1000))

        return Message(
            id=msg_id,
            type="text",
            sender=sender,
            sender_name=sender,
            content=content,
            is_group=is_group,
            is_self=is_self,
            room_id=room_id,
            timestamp=timestamp
        )

    def _parse_timestamp(self, match, ptype: str) -> int:
        """
        解析时间戳

        Args:
            match: 正则匹配对象
            ptype: 时间戳类型

        Returns:
            Unix 时间戳
        """
        import datetime

        now = datetime.datetime.now()

        try:
            if ptype == 'full_date':
                year, month, day, hour, minute = map(int, match.groups())
                dt = datetime.datetime(year, month, day, hour, minute)
                return int(dt.timestamp())

            elif ptype == 'yesterday':
                hour, minute = map(int, match.groups())
                dt = now - datetime.timedelta(days=1)
                dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return int(dt.timestamp())

            elif ptype == 'day_before':
                hour, minute = map(int, match.groups())
                dt = now - datetime.timedelta(days=2)
                dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return int(dt.timestamp())

            elif ptype == 'short_date':
                month, day, hour, minute = map(int, match.groups())
                dt = now.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
                return int(dt.timestamp())

            elif ptype == 'time_only':
                hour, minute = map(int, match.groups())
                dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return int(dt.timestamp())

        except Exception:
            pass

        return int(now.timestamp())

    def _detect_and_extract_self(self, lines: List[str]) -> tuple:
        """
        检测并提取自己发送的消息

        Args:
            lines: 消息行列表

        Returns:
            (is_self, processed_lines) 元组
        """
        # 自己发送的消息标记
        self_indicators = ['我:', '我：', '我说的', 'You:', 'Me:']

        for i, line in enumerate(lines):
            for indicator in self_indicators:
                if line.startswith(indicator):
                    # 移除标记
                    remaining = line[len(indicator):].strip()
                    new_lines = lines.copy()
                    if remaining:
                        new_lines[i] = remaining
                    else:
                        new_lines.pop(i)
                    return True, new_lines

        return False, lines

    def _clean_content(self, content: str) -> str:
        """
        清理消息内容

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        # 移除多余空白
        content = re.sub(r'\s+', ' ', content).strip()

        # 移除常见的 OCR 错误
        content = content.replace('|', 'I').replace('｜', 'I')

        return content

    def _detect_group_message(self, text: str, sender: str) -> bool:
        """
        检测是否是群消息

        Args:
            text: 原始文本
            sender: 发送者

        Returns:
            是否是群消息
        """
        # 群聊关键词
        group_keywords = ['@', '群聊', 'chatroom', '@chatroom']

        # 检查文本
        for kw in group_keywords:
            if kw in text.lower():
                return True

        # 检查发送者是否包含群 ID 格式
        if '@chatroom' in sender:
            return True

        return False

    def _listen_loop(self):
        """监听循环（在独立线程中运行）"""
        logger.info("消息监听线程已启动")

        last_check_time = time.time()
        check_interval = self.config.check_interval

        while self._running:
            time.sleep(check_interval)

            try:
                # 检查微信窗口是否仍然活跃
                login_status = self.is_login()
                if not login_status:
                    # 再次检查确认
                    time.sleep(0.5)
                    if not self.is_login():
                        logger.warning("微信窗口已关闭，停止监听")
                        self._running = False
                        break
                    logger.debug("窗口状态暂时不可用，继续监听")

                # 获取当前激活的聊天窗口
                chat_panel = self._find_chat_window()
                if not chat_panel:
                    continue

                # 动态计算 OCR 区域
                ocr_region = self._calculate_ocr_region(chat_panel)

                # OCR 识别消息区域
                ocr_text = self._ocr_screen(*ocr_region)

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
        """
        获取联系人列表

        Returns:
            联系人列表，每个元素包含 wxid, nickname, remark 等字段
        """
        if self._contact_manager:
            contacts = self._contact_manager.get_all_contacts()
            return [
                {
                    "wxid": c.wxid,
                    "nickname": c.nickname,
                    "remark": c.remark,
                    "display_name": c.display_name,
                    "is_group": c.is_group
                }
                for c in contacts
            ]

        # 如果没有联系人管理器，尝试从 UI 获取
        # 注意：UI 自动化方式获取联系人比较复杂且不稳定
        logger.debug("尝试从 UI 获取联系人列表")

        contacts = []
        try:
            if not self.main_window:
                return contacts

            # 尝试查找联系人列表
            # 微信 4.x 联系人列表结构复杂，需要递归遍历
            # 这里提供一个基础实现
            all_controls = self.main_window.descendants()

            contact_names = set()
            for ctrl in all_controls:
                try:
                    text = ctrl.window_text()
                    if text and len(text) > 0 and len(text) < 50:
                        # 过滤掉明显不是联系人的文本
                        if not any(kw in text for kw in ['微信', '搜索', '添加', '设置', '聊天']):
                            contact_names.add(text)
                except:
                    continue

            for name in list(contact_names)[:50]:  # 限制数量
                contacts.append({
                    "wxid": name,
                    "nickname": name,
                    "remark": "",
                    "display_name": name,
                    "is_group": False
                })

        except Exception as e:
            logger.debug(f"获取联系人失败：{e}")

        return contacts

    def get_chat_history(self, room_id: Optional[str] = None, count: int = 100) -> List[Message]:
        """
        获取聊天记录

        Args:
            room_id: 会话 ID（可选）
            count: 获取数量

        Returns:
            消息列表
        """
        messages = []

        try:
            if not self.main_window:
                return messages

            # 获取 OCR 区域
            chat_panel = self._find_chat_window(room_id)
            if not chat_panel:
                return messages

            region = self._calculate_ocr_region(chat_panel)

            # 执行多次 OCR 识别
            # 注意：这种方式获取的是当前可见的消息
            ocr_text = self._ocr_screen(*region)

            # 解析消息
            lines = ocr_text.strip().split('\n')

            # 按时间戳分割消息
            current_msg_lines = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 检查是否是新消息（以时间戳开头）
                is_new_msg = bool(re.match(r'\d{1,2}:\d{2}', line))

                if is_new_msg and current_msg_lines:
                    # 解析上一条消息
                    msg = self._parse_message('\n'.join(current_msg_lines))
                    if msg:
                        messages.append(msg)
                    current_msg_lines = []

                current_msg_lines.append(line)

            # 处理最后一条消息
            if current_msg_lines:
                msg = self._parse_message('\n'.join(current_msg_lines))
                if msg:
                    messages.append(msg)

            # 限制数量
            messages = messages[-count:]

        except Exception as e:
            logger.debug(f"获取聊天记录失败：{e}")

        return messages

    def set_contact_manager(self, contact_manager):
        """
        设置联系人管理器

        Args:
            contact_manager: ContactManager 实例
        """
        self._contact_manager = contact_manager
        logger.info("已设置联系人管理器")

    def debug_window_structure(self, max_depth: int = 5) -> Dict[str, Any]:
        """
        调试工具：输出窗口控件树结构

        用于诊断微信窗口定位问题

        Args:
            max_depth: 最大遍历深度

        Returns:
            窗口结构信息
        """
        if not self.main_window:
            logger.error("未连接微信")
            return {"error": "未连接微信"}

        result = {
            "main_window": {
                "title": self.main_window.window_text(),
                "class_name": self.main_window.element_info.class_name,
                "control_type": self.main_window.element_info.control_type,
                "rectangle": str(self.main_window.rectangle())
            },
            "children": []
        }

        def traverse_controls(control, depth: int = 0, path: str = "") -> List[Dict]:
            if depth >= max_depth:
                return []

            children_info = []
            try:
                children = control.children()
                for i, child in enumerate(children):
                    try:
                        info = {
                            "index": i,
                            "title": child.window_text()[:50] if child.window_text() else "",
                            "class_name": child.element_info.class_name,
                            "control_type": child.element_info.control_type,
                            "visible": child.is_visible() if hasattr(child, 'is_visible') else True,
                            "rectangle": str(child.rectangle()) if hasattr(child, 'rectangle') else "N/A",
                            "path": f"{path}/{i}",
                            "children": traverse_controls(child, depth + 1, f"{path}/{i}")
                        }
                        children_info.append(info)
                    except Exception as e:
                        children_info.append({
                            "index": i,
                            "error": str(e)
                        })
            except Exception as e:
                logger.debug(f"遍历子控件失败：{e}")

            return children_info

        result["children"] = traverse_controls(self.main_window)

        # 输出关键控件信息
        logger.info("=== 微信窗口结构调试 ===")
        logger.info(f"主窗口: {result['main_window']['title']}")
        logger.info(f"类名: {result['main_window']['class_name']}")
        logger.info(f"位置: {result['main_window']['rectangle']}")

        # 统计控件类型
        control_types = {}
        def count_types(children):
            for child in children:
                ct = child.get("control_type", "Unknown")
                control_types[ct] = control_types.get(ct, 0) + 1
                if child.get("children"):
                    count_types(child["children"])

        count_types(result["children"])

        logger.info(f"控件类型统计: {control_types}")

        # 查找可能的消息列表控件
        potential_message_controls = []
        def find_potential_controls(children, depth=0):
            for child in children:
                if child.get("control_type") in ["List", "Pane", "Document"]:
                    rect_str = child.get("rectangle", "")
                    if rect_str and "width" in rect_str.lower() or rect_str.count(",") >= 3:
                        potential_message_controls.append({
                            "path": child.get("path"),
                            "type": child.get("control_type"),
                            "class": child.get("class_name"),
                            "title": child.get("title"),
                            "rectangle": rect_str
                        })
                if child.get("children"):
                    find_potential_controls(child["children"], depth + 1)

        find_potential_controls(result["children"])

        if potential_message_controls:
            logger.info("潜在消息列表控件:")
            for ctrl in potential_message_controls[:5]:
                logger.info(f"  - {ctrl['type']} @ {ctrl['path']}: {ctrl['rectangle']}")

        return result

    def save_debug_screenshot(self, filename: str = "debug_screenshot.png") -> str:
        """
        保存调试截图

        用于诊断 OCR 问题

        Args:
            filename: 输出文件名

        Returns:
            保存的文件路径
        """
        if not OCR_AVAILABLE:
            logger.error("OCR 库未安装")
            return ""

        try:
            chat_panel = self._find_chat_window()
            if not chat_panel:
                logger.error("未找到聊天窗口")
                return ""

            region = self._calculate_ocr_region(chat_panel)

            # 截取屏幕区域
            screenshot = pyautogui.screenshot(region=(region[0], region[1], region[2] - region[0], region[3] - region[1]))

            # 保存原始截图
            output_path = Path("data/debug") / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            screenshot.save(output_path)

            # 如果启用预处理，也保存预处理后的图像
            if self.config.ocr_preprocessing:
                processed = self._preprocess_image(screenshot)
                processed_path = output_path.parent / f"processed_{filename}"
                processed.save(processed_path)
                logger.info(f"预处理截图保存到: {processed_path}")

            logger.info(f"调试截图保存到: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"保存截图失败：{e}")
            return ""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
联系人管理模块

负责管理微信联系人信息，包括：
- 联系人缓存
- 昵称解析
- 群成员管理
"""

import json
import time
import re
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path
from threading import Lock

from loguru import logger


@dataclass
class Contact:
    """联系人数据类"""
    wxid: str                      # 微信 ID
    nickname: str = ""             # 昵称
    remark: str = ""               # 备注
    avatar: str = ""               # 头像路径
    is_group: bool = False         # 是否是群聊
    members: List[str] = field(default_factory=list)  # 群成员列表
    last_active: int = 0           # 最后活跃时间

    @property
    def display_name(self) -> str:
        """获取显示名称（优先备注，其次昵称）"""
        return self.remark or self.nickname or self.wxid


class ContactManager:
    """
    联系人管理器

    管理联系人的缓存、查询和更新
    """

    def __init__(self, cache_path: str = "data/contacts.json"):
        """
        初始化联系人管理器

        Args:
            cache_path: 缓存文件路径
        """
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # 联系人缓存
        self._contacts: Dict[str, Contact] = {}
        self._nickname_index: Dict[str, str] = {}  # 昵称 -> wxid
        self._lock = Lock()

        # 加载缓存
        self._load_cache()

        logger.info(f"联系人管理器已初始化，缓存 {len(self._contacts)} 个联系人")

    def _load_cache(self):
        """加载缓存"""
        if not self.cache_path.exists():
            return

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for wxid, info in data.items():
                self._contacts[wxid] = Contact(
                    wxid=wxid,
                    nickname=info.get("nickname", ""),
                    remark=info.get("remark", ""),
                    avatar=info.get("avatar", ""),
                    is_group=info.get("is_group", False),
                    members=info.get("members", []),
                    last_active=info.get("last_active", 0)
                )
                # 建立昵称索引
                if info.get("nickname"):
                    self._nickname_index[info["nickname"]] = wxid

            logger.debug(f"从缓存加载 {len(self._contacts)} 个联系人")

        except Exception as e:
            logger.error(f"加载联系人缓存失败：{e}")

    def _save_cache(self):
        """保存缓存"""
        try:
            data = {}
            for wxid, contact in self._contacts.items():
                data[wxid] = {
                    "nickname": contact.nickname,
                    "remark": contact.remark,
                    "avatar": contact.avatar,
                    "is_group": contact.is_group,
                    "members": contact.members,
                    "last_active": contact.last_active
                }

            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存联系人缓存失败：{e}")

    def add_contact(
        self,
        wxid: str,
        nickname: str = "",
        remark: str = "",
        is_group: bool = False
    ) -> Contact:
        """
        添加或更新联系人

        Args:
            wxid: 微信 ID
            nickname: 昵称
            remark: 备注
            is_group: 是否是群聊

        Returns:
            联系人对象
        """
        with self._lock:
            if wxid in self._contacts:
                # 更新现有联系人
                contact = self._contacts[wxid]
                if nickname:
                    contact.nickname = nickname
                    self._nickname_index[nickname] = wxid
                if remark:
                    contact.remark = remark
                contact.is_group = is_group
                contact.last_active = int(time.time())
            else:
                # 创建新联系人
                contact = Contact(
                    wxid=wxid,
                    nickname=nickname,
                    remark=remark,
                    is_group=is_group,
                    last_active=int(time.time())
                )
                self._contacts[wxid] = contact
                if nickname:
                    self._nickname_index[nickname] = wxid

            self._save_cache()
            return contact

    def get_contact(self, wxid: str) -> Optional[Contact]:
        """
        获取联系人

        Args:
            wxid: 微信 ID

        Returns:
            联系人对象或 None
        """
        return self._contacts.get(wxid)

    def get_contact_by_nickname(self, nickname: str) -> Optional[Contact]:
        """
        通过昵称获取联系人

        Args:
            nickname: 昵称

        Returns:
            联系人对象或 None
        """
        wxid = self._nickname_index.get(nickname)
        if wxid:
            return self._contacts.get(wxid)
        return None

    def resolve_sender(self, sender_text: str) -> tuple:
        """
        解析发送者信息

        从消息文本中提取发送者，返回 (wxid, nickname)

        Args:
            sender_text: 发送者文本

        Returns:
            (wxid, nickname) 元组
        """
        # 尝试直接匹配昵称
        contact = self.get_contact_by_nickname(sender_text)
        if contact:
            return contact.wxid, contact.display_name

        # 尝试解析 wxid 格式 (wxid_xxx)
        if sender_text.startswith("wxid_"):
            contact = self.get_contact(sender_text)
            if contact:
                return contact.wxid, contact.display_name
            return sender_text, sender_text

        # 尝试解析群成员格式 (昵称 wxid_xxx)
        match = re.match(r"(.+?)\s*(wxid_\w+)", sender_text)
        if match:
            nickname, wxid = match.groups()
            # 更新联系人信息
            self.add_contact(wxid, nickname=nickname.strip())
            return wxid, nickname.strip()

        # 未知发送者
        return sender_text, sender_text

    def update_group_members(self, room_id: str, members: List[str]):
        """
        更新群成员列表

        Args:
            room_id: 群 ID
            members: 成员 wxid 列表
        """
        with self._lock:
            if room_id in self._contacts:
                self._contacts[room_id].members = members
            else:
                self.add_contact(room_id, is_group=True)
                self._contacts[room_id].members = members

            self._save_cache()

    def get_all_contacts(self) -> List[Contact]:
        """获取所有联系人"""
        return list(self._contacts.values())

    def get_recent_contacts(self, limit: int = 20) -> List[Contact]:
        """
        获取最近活跃的联系人

        Args:
            limit: 最大数量

        Returns:
            联系人列表
        """
        contacts = sorted(
            self._contacts.values(),
            key=lambda c: c.last_active,
            reverse=True
        )
        return contacts[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        groups = sum(1 for c in self._contacts.values() if c.is_group)
        users = len(self._contacts) - groups

        return {
            "total": len(self._contacts),
            "users": users,
            "groups": groups,
            "cached_nicknames": len(self._nickname_index)
        }

    def clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._contacts.clear()
            self._nickname_index.clear()
            self._save_cache()
        logger.info("联系人缓存已清空")

    def import_from_wechat(self, contacts_data: List[Dict]):
        """
        从微信数据导入联系人

        Args:
            contacts_data: 微信联系人数据列表
        """
        for data in contacts_data:
            wxid = data.get("wxid", "")
            if not wxid:
                continue

            self.add_contact(
                wxid=wxid,
                nickname=data.get("nickname", ""),
                remark=data.get("remark", ""),
                is_group=data.get("wxid", "").endswith("@chatroom")
            )

        logger.info(f"导入 {len(contacts_data)} 个联系人")
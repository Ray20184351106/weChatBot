#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContactManager 模块测试

测试联系人管理功能
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from core.contact_manager import ContactManager, Contact


class TestContact:
    """Contact 数据类测试"""

    def test_contact_creation(self):
        """测试联系人创建"""
        contact = Contact(
            wxid="wxid_001",
            nickname="张三",
            remark="备注张三"
        )

        assert contact.wxid == "wxid_001"
        assert contact.nickname == "张三"
        assert contact.remark == "备注张三"

    def test_display_name_nickname(self):
        """测试显示名称（无备注）"""
        contact = Contact(
            wxid="wxid_001",
            nickname="张三"
        )

        assert contact.display_name == "张三"

    def test_display_name_remark(self):
        """测试显示名称（有备注）"""
        contact = Contact(
            wxid="wxid_001",
            nickname="张三",
            remark="好友张三"
        )

        # 备注优先
        assert contact.display_name == "好友张三"

    def test_display_name_wxid(self):
        """测试显示名称（只有 wxid）"""
        contact = Contact(wxid="wxid_001")

        assert contact.display_name == "wxid_001"

    def test_group_contact(self):
        """测试群聊联系人"""
        contact = Contact(
            wxid="12345@chatroom",
            nickname="测试群",
            is_group=True,
            members=["wxid_001", "wxid_002"]
        )

        assert contact.is_group is True
        assert len(contact.members) == 2


class TestContactManager:
    """ContactManager 类测试"""

    def test_init(self, temp_dir: Path):
        """测试初始化"""
        cache_path = str(temp_dir / "contacts.json")
        manager = ContactManager(cache_path)

        assert manager.cache_path == Path(cache_path)
        assert len(manager._contacts) == 0

    def test_add_contact(self, temp_dir: Path):
        """测试添加联系人"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        contact = manager.add_contact(
            wxid="wxid_001",
            nickname="张三",
            remark="好友张三"
        )

        assert contact.wxid == "wxid_001"
        assert contact.nickname == "张三"

        # 验证缓存
        assert len(manager._contacts) == 1

    def test_add_contact_update(self, temp_dir: Path):
        """测试更新联系人"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        # 添加
        manager.add_contact("wxid_001", nickname="张三")

        # 更新
        contact = manager.add_contact("wxid_001", remark="好友")

        assert contact.nickname == "张三"
        assert contact.remark == "好友"
        assert len(manager._contacts) == 1  # 还是只有一条

    def test_get_contact(self, temp_dir: Path):
        """测试获取联系人"""
        manager = ContactManager(str(temp_dir / "contacts.json"))
        manager.add_contact("wxid_001", nickname="张三")

        contact = manager.get_contact("wxid_001")
        assert contact is not None
        assert contact.nickname == "张三"

        # 不存在的联系人
        contact = manager.get_contact("wxid_999")
        assert contact is None

    def test_get_contact_by_nickname(self, temp_dir: Path):
        """测试通过昵称获取联系人"""
        manager = ContactManager(str(temp_dir / "contacts.json"))
        manager.add_contact("wxid_001", nickname="张三")

        contact = manager.get_contact_by_nickname("张三")
        assert contact is not None
        assert contact.wxid == "wxid_001"

        # 不存在的昵称
        contact = manager.get_contact_by_nickname("李四")
        assert contact is None

    def test_resolve_sender_by_nickname(self, temp_dir: Path):
        """测试解析发送者（通过昵称）"""
        manager = ContactManager(str(temp_dir / "contacts.json"))
        manager.add_contact("wxid_001", nickname="张三", remark="好友")

        wxid, display_name = manager.resolve_sender("张三")

        assert wxid == "wxid_001"
        assert display_name == "好友"

    def test_resolve_sender_by_wxid(self, temp_dir: Path):
        """测试解析发送者（通过 wxid）"""
        manager = ContactManager(str(temp_dir / "contacts.json"))
        manager.add_contact("wxid_001", nickname="张三")

        wxid, display_name = manager.resolve_sender("wxid_001")

        assert wxid == "wxid_001"
        assert display_name == "张三"

    def test_resolve_sender_unknown(self, temp_dir: Path):
        """测试解析未知发送者"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        wxid, display_name = manager.resolve_sender("陌生人")

        assert wxid == "陌生人"
        assert display_name == "陌生人"

    def test_update_group_members(self, temp_dir: Path):
        """测试更新群成员"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        manager.update_group_members(
            "12345@chatroom",
            ["wxid_001", "wxid_002", "wxid_003"]
        )

        contact = manager.get_contact("12345@chatroom")
        assert contact is not None
        assert contact.is_group is True
        assert len(contact.members) == 3

    def test_get_all_contacts(self, temp_dir: Path):
        """测试获取所有联系人"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        manager.add_contact("wxid_001", nickname="张三")
        manager.add_contact("wxid_002", nickname="李四")
        manager.add_contact("group@chatroom", is_group=True)

        contacts = manager.get_all_contacts()

        assert len(contacts) == 3

    def test_get_recent_contacts(self, temp_dir: Path):
        """测试获取最近联系人"""
        import time

        manager = ContactManager(str(temp_dir / "contacts.json"))

        manager.add_contact("wxid_001", nickname="张三")
        time.sleep(0.1)
        manager.add_contact("wxid_002", nickname="李四")
        time.sleep(0.1)
        manager.add_contact("wxid_003", nickname="王五")

        recent = manager.get_recent_contacts(limit=2)

        assert len(recent) == 2
        # 最近添加的在前面
        assert recent[0].nickname == "王五"

    def test_get_statistics(self, temp_dir: Path):
        """测试获取统计"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        manager.add_contact("wxid_001", nickname="张三")
        manager.add_contact("wxid_002", nickname="李四")
        manager.add_contact("group@chatroom", is_group=True)

        stats = manager.get_statistics()

        assert stats["total"] == 3
        assert stats["users"] == 2
        assert stats["groups"] == 1

    def test_clear_cache(self, temp_dir: Path):
        """测试清空缓存"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        manager.add_contact("wxid_001", nickname="张三")
        assert len(manager._contacts) == 1

        manager.clear_cache()
        assert len(manager._contacts) == 0

    def test_cache_persistence(self, temp_dir: Path):
        """测试缓存持久化"""
        cache_path = str(temp_dir / "contacts.json")

        # 创建并添加联系人
        manager1 = ContactManager(cache_path)
        manager1.add_contact("wxid_001", nickname="张三")

        # 创建新实例加载缓存
        manager2 = ContactManager(cache_path)

        assert len(manager2._contacts) == 1
        contact = manager2.get_contact("wxid_001")
        assert contact is not None
        assert contact.nickname == "张三"

    def test_import_from_wechat(self, temp_dir: Path):
        """测试从微信数据导入"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        contacts_data = [
            {"wxid": "wxid_001", "nickname": "张三", "remark": "好友张三"},
            {"wxid": "wxid_002", "nickname": "李四"},
            {"wxid": "group@chatroom", "nickname": "测试群"},
        ]

        manager.import_from_wechat(contacts_data)

        assert len(manager._contacts) == 3
        assert manager.get_contact("wxid_001").remark == "好友张三"


class TestContactManagerEdgeCases:
    """边界情况测试"""

    def test_empty_cache_file(self, temp_dir: Path):
        """测试空缓存文件"""
        cache_path = str(temp_dir / "contacts.json")

        # 创建空文件
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write("{}")

        manager = ContactManager(cache_path)
        assert len(manager._contacts) == 0

    def test_invalid_cache_file(self, temp_dir: Path):
        """测试无效缓存文件"""
        cache_path = str(temp_dir / "contacts.json")

        # 创建无效文件
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write("invalid json")

        manager = ContactManager(cache_path)
        # 应该不影响初始化
        assert len(manager._contacts) == 0

    def test_special_characters_in_nickname(self, temp_dir: Path):
        """测试昵称中的特殊字符"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        manager.add_contact("wxid_001", nickname="张三👨‍👩‍👧‍👦")

        contact = manager.get_contact("wxid_001")
        assert "👨‍👩‍👧‍👦" in contact.nickname

    def test_very_long_nickname(self, temp_dir: Path):
        """测试很长的昵称"""
        manager = ContactManager(str(temp_dir / "contacts.json"))

        long_name = "这是一个非常长的昵称" * 10
        manager.add_contact("wxid_001", nickname=long_name)

        contact = manager.get_contact("wxid_001")
        assert contact.nickname == long_name

    def test_concurrent_access(self, temp_dir: Path):
        """测试并发访问"""
        import threading

        manager = ContactManager(str(temp_dir / "contacts.json"))

        def add_contact(i):
            manager.add_contact(f"wxid_{i}", nickname=f"用户{i}")

        threads = [
            threading.Thread(target=add_contact, args=(i,))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 应该有 10 个联系人
        assert len(manager._contacts) == 10
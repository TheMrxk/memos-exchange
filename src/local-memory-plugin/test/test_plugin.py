#!/usr/bin/env python3
"""
MemOS Exchange - 本地记忆插件测试
"""

import unittest
import json
import sys
from pathlib import Path

# 添加父目录到路径
PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_DIR))

from db.schema import DatabaseManager, get_database
from search_engine import MemorySearchEngine


class TestDatabaseManager(unittest.TestCase):
    """测试数据库管理器"""

    def setUp(self):
        """设置测试数据库（内存数据库）"""
        self.db = DatabaseManager(':memory:')

    def tearDown(self):
        """清理测试数据库"""
        self.db.close()

    def test_add_conversation(self):
        """测试添加对话"""
        conv_id = self.db.add_conversation(
            session_id='test-session',
            role='user',
            content='测试消息'
        )
        self.assertGreater(conv_id, 0)

    def test_get_conversations(self):
        """测试获取对话"""
        self.db.add_conversation('session-1', 'user', '消息 1')
        self.db.add_conversation('session-1', 'assistant', '回复 1')

        conversations = self.db.get_conversations('session-1', limit=10)
        self.assertEqual(len(conversations), 2)

    def test_add_memory(self):
        """测试添加记忆"""
        import json
        mem_id = self.db.add_memory(
            content='用户喜欢 Python',
            memory_type='preference',
            tags=json.dumps(['python', '编程'])
        )
        self.assertGreater(mem_id, 0)

    def test_search_memories(self):
        """测试搜索记忆"""
        import json
        self.db.add_memory(
            content='我喜欢用 Python 写代码',
            memory_type='preference',
            tags=json.dumps(['python', '编程'])
        )
        self.db.add_memory(
            content='我会用 Flask 开发后端',
            memory_type='skill',
            tags=json.dumps(['flask', '后端'])
        )

        results = self.db.search_memories('Python')
        self.assertGreater(len(results), 0)
        self.assertIn('python', results[0].get('content', '').lower())


class TestMemorySearchEngine(unittest.TestCase):
    """测试检索引擎"""

    def setUp(self):
        """设置测试环境"""
        self.db = DatabaseManager(':memory:')
        self.engine = MemorySearchEngine(self.db)

    def tearDown(self):
        """清理"""
        self.db.close()

    def test_auto_classify_preference(self):
        """测试自动分类 - 偏好"""
        content = '我喜欢用 PyCharm 写代码'
        result = self.engine.auto_classify(content)
        self.assertEqual(result, 'preference')

    def test_auto_classify_skill(self):
        """测试自动分类 - 技能"""
        content = '我会用 Flask 开发后端'
        result = self.engine.auto_classify(content)
        self.assertEqual(result, 'skill')

    def test_auto_classify_experience(self):
        """测试自动分类 - 经验"""
        content = '今天我开发了一个新功能'
        result = self.engine.auto_classify(content)
        self.assertEqual(result, 'experience')

    def test_extract_tags(self):
        """测试标签提取"""
        content = '我用 Python 和 Flask 开发微信小程序'
        tags = self.engine.extract_tags(content)
        self.assertIn('Python', tags)
        self.assertIn('Flask', tags)
        self.assertIn('微信小程序', tags)

    def test_search(self):
        """测试搜索"""
        import json
        self.db.add_memory(
            content='我喜欢用 Python',
            memory_type='preference',
            tags=json.dumps(['python'])
        )

        results = self.engine.search('Python', limit=5)
        self.assertGreater(len(results), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""
MemOS Exchange - 本地记忆数据库 Schema

数据库设计说明:
- 使用 SQLite 存储对话记录和记忆
- 支持关键词全文检索
- 预留向量索引接口（未来支持语义搜索）
"""

import sqlite3
from pathlib import Path
from datetime import datetime


# 数据库 Schema 定义
SCHEMA_SQL = """
-- 对话记录表：存储原始对话
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,           -- OpenClaw 会话 ID
    message_id      TEXT,                     -- 消息 ID（可选）
    role            TEXT NOT NULL,            -- 'user' 或 'assistant'
    content         TEXT NOT NULL,            -- 消息内容
    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- 索引字段
    agent_id        TEXT,                     -- Agent ID（多 Agent 模式）
    channel         TEXT DEFAULT 'openclaw',  -- 来源渠道

    -- 元数据
    tokens_count    INTEGER,                  -- 消息 token 数（可选）
    is_stored       BOOLEAN DEFAULT 1         -- 是否已存储到记忆
);

-- 记忆表：存储提取后的记忆
CREATE TABLE IF NOT EXISTS memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER,                  -- 关联的对话 ID
    user_id         TEXT DEFAULT 'default',   -- 用户 ID

    -- 记忆内容
    content         TEXT NOT NULL,            -- 记忆文本
    memory_type     TEXT NOT NULL,            -- 'fact' | 'preference' | 'skill' | 'experience'

    -- 分类和标签
    tags            TEXT,                     -- JSON 数组：["python", "flask"]
    category        TEXT,                     -- 分类（可选）

    -- 元数据
    source          TEXT DEFAULT 'openclaw',  -- 来源
    confidence      REAL DEFAULT 1.0,         -- 置信度 (0-1)
    access_count    INTEGER DEFAULT 0,        -- 访问次数（用于热度排序）
    last_accessed   DATETIME,                 -- 最后访问时间
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- 外键
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);

-- 向量嵌入表（预留，未来支持语义搜索）
CREATE TABLE IF NOT EXISTS embeddings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id       INTEGER NOT NULL,
    model_name      TEXT NOT NULL,            -- 嵌入模型名称
    vector          BLOB,                     -- 向量数据（二进制）
    dimensions      INTEGER,                  -- 向量维度
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

-- 会话元数据表
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT UNIQUE NOT NULL,
    agent_id        TEXT,
    channel         TEXT DEFAULT 'openclaw',
    started_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity   DATETIME DEFAULT CURRENT_TIMESTAMP,
    message_count   INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT 1
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_role ON conversations(role);
CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversations(agent_id);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories(tags);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_access ON memories(access_count DESC, last_accessed DESC);

CREATE INDEX IF NOT EXISTS idx_embeddings_memory ON embeddings(memory_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model_name);

-- 全文搜索虚拟表 (FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    tags,
    category,
    content='memories',
    content_rowid='id'
);

-- 触发器：同步 FTS 索引
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags, category)
    VALUES (new.id, new.content, new.tags, new.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, category)
    VALUES('delete', old.id, old.content, old.tags, old.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, category)
    VALUES('delete', old.id, old.content, old.tags, old.category);
    INSERT INTO memories_fts(rowid, content, tags, category)
    VALUES (new.id, new.content, new.tags, new.category);
END;
"""

# 默认配置
DEFAULT_CONFIG = {
    'database_path': '~/.openclaw/workspace/memos-exchange.db',
    'backup_enabled': True,
    'backup_interval_hours': 24,
    'max_memory_age_days': 365,
    'auto_vacuum': True,
}


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径，默认 ~/.openclaw/workspace/memos-exchange.db
        """
        if db_path:
            self.db_path = Path(db_path).expanduser()
        else:
            self.db_path = Path.home() / '.openclaw' / 'workspace' / 'memos-exchange.db'

        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = None
        self._connect()
        self._init_schema()

    def _connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0
        )
        self.conn.row_factory = sqlite3.Row

        # 启用外键
        self.conn.execute("PRAGMA foreign_keys = ON")

        # WAL 模式（更好的并发性能）
        self.conn.execute("PRAGMA journal_mode = WAL")

        # 同步模式
        self.conn.execute("PRAGMA synchronous = NORMAL")

        # 缓存大小 (MB)
        self.conn.execute("PRAGMA cache_size = -2000")

    def _init_schema(self):
        """初始化数据库 Schema"""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ==================== 对话操作 ====================

    def add_conversation(self, session_id: str, role: str, content: str,
                         agent_id: str = None, message_id: str = None) -> int:
        """
        添加对话记录

        Args:
            session_id: 会话 ID
            role: 'user' 或 'assistant'
            content: 消息内容
            agent_id: Agent ID（可选）
            message_id: 消息 ID（可选）

        Returns:
            插入的对话 ID
        """
        cursor = self.conn.execute("""
            INSERT INTO conversations (session_id, message_id, role, content, agent_id)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, message_id, role, content, agent_id))

        # 更新会话活跃度
        self._update_session_activity(session_id, agent_id)

        self.conn.commit()
        return cursor.lastrowid

    def get_conversations(self, session_id: str = None, limit: int = 50,
                          offset: int = 0) -> list:
        """
        获取对话记录

        Args:
            session_id: 会话 ID（可选，不传则获取所有）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            对话记录列表
        """
        if session_id:
            cursor = self.conn.execute("""
                SELECT * FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (session_id, limit, offset))
        else:
            cursor = self.conn.execute("""
                SELECT * FROM conversations
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

        return [dict(row) for row in cursor.fetchall()]

    def _update_session_activity(self, session_id: str, agent_id: str = None):
        """更新会话活动记录"""
        self.conn.execute("""
            INSERT OR IGNORE INTO sessions (session_id, agent_id)
            VALUES (?, ?)
        """, (session_id, agent_id))

        self.conn.execute("""
            UPDATE sessions SET
                last_activity = CURRENT_TIMESTAMP,
                message_count = message_count + 1,
                is_active = 1
            WHERE session_id = ?
        """, (session_id,))
        self.conn.commit()

    # ==================== 记忆操作 ====================

    def add_memory(self, content: str, memory_type: str,
                   conversation_id: int = None, tags: list = None,
                   user_id: str = 'default', confidence: float = 1.0) -> int:
        """
        添加记忆

        Args:
            content: 记忆内容
            memory_type: 'fact' | 'preference' | 'skill' | 'experience'
            conversation_id: 关联的对话 ID（可选）
            tags: 标签列表（可选）
            user_id: 用户 ID
            confidence: 置信度 (0-1)

        Returns:
            插入的记忆 ID
        """
        import json
        tags_json = json.dumps(tags) if tags else None

        cursor = self.conn.execute("""
            INSERT INTO memories (content, memory_type, conversation_id, tags, user_id, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (content, memory_type, conversation_id, tags_json, user_id, confidence))

        self.conn.commit()
        return cursor.lastrowid

    def get_memories(self, memory_type: str = None, user_id: str = 'default',
                     limit: int = 50, offset: int = 0) -> list:
        """
        获取记忆列表

        Args:
            memory_type: 记忆类型过滤（可选）
            user_id: 用户 ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            记忆列表
        """
        if memory_type:
            cursor = self.conn.execute("""
                SELECT * FROM memories
                WHERE memory_type = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (memory_type, user_id, limit, offset))
        else:
            cursor = self.conn.execute("""
                SELECT * FROM memories
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))

        return [dict(row) for row in cursor.fetchall()]

    def search_memories(self, query: str, user_id: str = 'default',
                        limit: int = 10, min_score: float = 0.1) -> list:
        """
        全文搜索记忆（使用 FTS5）

        Args:
            query: 搜索关键词
            user_id: 用户 ID
            limit: 返回数量限制
            min_score: 最低相关性分数

        Returns:
            搜索结果列表（按相关性排序）
        """
        # FTS5 搜索，使用 bm25 算法计算相关性分数
        cursor = self.conn.execute("""
            SELECT m.*, bm25(memories_fts) as score
            FROM memories_fts
            JOIN memories m ON m.id = memories_fts.rowid
            WHERE m.user_id = ? AND memories_fts MATCH ?
            ORDER BY score ASC
            LIMIT ?
        """, (user_id, query, limit))

        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            # 归一化分数到 0-1 范围
            raw_score = row_dict.get('score', 0)
            # bm25 分数越低越相关，取反并归一化
            normalized_score = max(0, 1.0 + raw_score / 10.0)
            if normalized_score >= min_score:
                row_dict['score'] = round(normalized_score, 3)
                results.append(row_dict)

        return results

    def update_memory_access(self, memory_id: int):
        """更新记忆访问记录"""
        self.conn.execute("""
            UPDATE memories SET
                access_count = access_count + 1,
                last_accessed = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (memory_id,))
        self.conn.commit()

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict:
        """获取数据库统计信息"""
        stats = {}

        # 对话统计
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM conversations")
        stats['total_conversations'] = cursor.fetchone()['count']

        # 记忆统计
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM memories")
        stats['total_memories'] = cursor.fetchone()['count']

        # 按类型统计记忆
        cursor = self.conn.execute("""
            SELECT memory_type, COUNT(*) as count
            FROM memories
            GROUP BY memory_type
        """)
        stats['memories_by_type'] = {row['memory_type']: row['count'] for row in cursor.fetchall()}

        # 会话统计
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM sessions WHERE is_active = 1")
        stats['active_sessions'] = cursor.fetchone()['count']

        # 数据库大小
        cursor = self.conn.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor = self.conn.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        stats['database_size_bytes'] = page_count * page_size

        return stats

    def vacuum(self):
        """执行数据库整理"""
        self.conn.execute("VACUUM")
        self.conn.commit()


# 单例模式
_db_instance: DatabaseManager = None


def get_database(db_path: str = None) -> DatabaseManager:
    """
    获取数据库实例（单例）

    Args:
        db_path: 数据库路径（可选）

    Returns:
        DatabaseManager 实例
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager(db_path)
    return _db_instance


if __name__ == '__main__':
    # 测试代码
    db = get_database()

    # 添加测试对话
    conv_id = db.add_conversation(
        session_id='test-session-1',
        role='user',
        content='我喜欢用 Python 写代码'
    )
    print(f"添加对话：{conv_id}")

    # 添加测试记忆
    mem_id = db.add_memory(
        content='用户喜欢用 Python 写代码',
        memory_type='preference',
        conversation_id=conv_id,
        tags=['python', '编程']
    )
    print(f"添加记忆：{mem_id}")

    # 搜索记忆
    results = db.search_memories('Python')
    print(f"搜索结果：{results}")

    # 统计信息
    stats = db.get_stats()
    print(f"统计：{stats}")

    db.close()

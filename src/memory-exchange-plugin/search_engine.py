#!/usr/bin/env python3
"""
Memory Exchange - 本地记忆检索引擎

功能：
- 关键词搜索（基于 SQLite FTS5）
- 记忆分类（事实/偏好/技能/经验）
- 标签提取
- 相关性评分

用法：
    python3 search_engine.py search "关键词" --limit 6 --json
    python3 search_engine.py stats
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from db.schema import get_database, DatabaseManager


class MemorySearchEngine:
    """记忆检索引擎"""

    # 技术栈标签关键词
    TECH_KEYWORDS = [
        'Python', 'Flask', 'PyCharm', 'DBeaver', 'SQL', 'JavaScript',
        'Node.js', 'TypeScript', 'React', 'Vue', 'Linux', 'Git',
        'Docker', 'Kubernetes', 'Redis', 'MongoDB', 'PostgreSQL',
        'OpenClaw', 'Telegram', 'QQBot', '微信小程序', 'MemOS'
    ]

    # 记忆类型关键词（中文）
    TYPE_KEYWORDS = {
        'preference': ['喜欢', '不喜欢', '偏好', '习惯', '常用', '爱用', '讨厌', '倾向', '偏好于'],
        'skill': ['会', '学会', '掌握', '技能', '能力', '擅长', '熟练', '懂得', '能用'],
        'experience': ['今天', '昨天', '经历', '事件', '开发', '完成', '参与', '做了', '项目'],
        'fact': ['是', '叫', '名字', '工作', '公司', '地点', '时间', '住在']
    }

    def __init__(self, db: DatabaseManager = None):
        """
        初始化检索引擎

        Args:
            db: 数据库实例（可选，不传则使用默认）
        """
        self.db = db or get_database()

    def auto_classify(self, content: str) -> str:
        """
        自动分类记忆内容

        Args:
            content: 记忆内容

        Returns:
            记忆类型 (preference/skill/experience/fact)
        """
        content_lower = content.lower()

        for mem_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower or keyword.lower() in content_lower:
                    return mem_type

        return 'fact'

    def extract_tags(self, content: str) -> List[str]:
        """
        从内容中提取标签

        Args:
            content: 记忆内容

        Returns:
            标签列表
        """
        tags = []

        # 技术栈标签
        for tech in self.TECH_KEYWORDS:
            if tech.lower() in content.lower() or tech in content:
                tags.append(tech)

        return list(set(tags))

    def search(
        self,
        query: str,
        limit: int = 6,
        min_score: float = 0.1,
        memory_type: str = None,
        tags: List[str] = None,
        user_id: str = 'default'
    ) -> List[Dict]:
        """
        搜索记忆

        Args:
            query: 搜索关键词
            limit: 返回结果数量
            min_score: 最低相关性分数
            memory_type: 记忆类型过滤
            tags: 标签过滤
            user_id: 用户 ID

        Returns:
            搜索结果列表
        """
        # 使用数据库的全文搜索
        results = self.db.search_memories(query, user_id, limit * 2, min_score)

        # 应用类型过滤器
        if memory_type:
            results = [r for r in results if r.get('memory_type') == memory_type]

        # 应用标签过滤器
        if tags:
            filtered = []
            for r in results:
                r_tags = json.loads(r.get('tags', '[]') or '[]')
                if any(t.lower() in [rt.lower() for rt in r_tags] for t in tags):
                    filtered.append(r)
            results = filtered

        # 限制结果数量
        return results[:limit]

    def add_memory_from_conversation(
        self,
        user_content: str,
        assistant_content: str = None,
        conversation_id: int = None,
        user_id: str = 'default'
    ) -> int:
        """
        从对话中提取并保存记忆

        Args:
            user_content: 用户消息内容
            assistant_content: 助手回复内容（可选）
            conversation_id: 对话 ID（可选）
            user_id: 用户 ID

        Returns:
            插入的记忆 ID
        """
        # 合并内容用于分析
        full_content = user_content
        if assistant_content:
            full_content += f"\n助手：{assistant_content}"

        # 自动分类
        memory_type = self.auto_classify(full_content)

        # 提取标签
        tags = self.extract_tags(full_content)

        # 生成记忆内容（优先提取用户消息中的关键信息）
        memory_content = user_content.strip()

        # 保存记忆
        memory_id = self.db.add_memory(
            content=memory_content,
            memory_type=memory_type,
            conversation_id=conversation_id,
            tags=tags,
            user_id=user_id,
            confidence=0.9  # 默认置信度
        )

        return memory_id

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.db.get_stats()


def format_results_human(results: List[Dict]) -> str:
    """格式化结果为人类可读格式"""
    if not results:
        return "📭 未找到相关记忆"

    output = [f"📊 搜索结果 (找到 {len(results)} 条)\n"]

    for i, r in enumerate(results, 1):
        score_pct = int(r.get('score', 0) * 100)
        output.append(f"{i}. [{score_pct}%] {r.get('content', '')[:80]}...")
        output.append(f"   📄 类型：{r.get('memory_type', 'unknown')}")
        output.append(f"   📅 创建：{r.get('created_at', 'unknown')}")

        tags = json.loads(r.get('tags', '[]') or '[]')
        if tags:
            output.append(f"   🏷️ 标签：{', '.join(tags)}")

        output.append("")

    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(description='Memory Exchange 本地记忆检索引擎')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索记忆')
    search_parser.add_argument('query', type=str, help='搜索关键词')
    search_parser.add_argument('--limit', '-n', type=int, default=6, help='返回结果数量')
    search_parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    search_parser.add_argument('--min-score', type=float, default=0.1, help='最低相关性分数')
    search_parser.add_argument('--type', choices=['preference', 'skill', 'experience', 'fact'], help='记忆类型过滤')
    search_parser.add_argument('--tags', type=str, nargs='+', help='标签过滤')
    search_parser.add_argument('--user-id', type=str, default='default', help='用户 ID')

    # stats 命令
    subparsers.add_parser('stats', help='显示统计信息')

    # add 命令
    add_parser = subparsers.add_parser('add', help='手动添加记忆')
    add_parser.add_argument('content', type=str, help='记忆内容')
    add_parser.add_argument('--type', '-t', choices=['preference', 'skill', 'experience', 'fact'], required=True)
    add_parser.add_argument('--tags', type=str, nargs='+', help='标签')

    args = parser.parse_args()

    engine = MemorySearchEngine()

    if args.command == 'search':
        results = engine.search(
            query=args.query,
            limit=args.limit,
            min_score=args.min_score,
            memory_type=args.type,
            tags=args.tags,
            user_id=args.user_id
        )

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(format_results_human(results))

    elif args.command == 'stats':
        stats = engine.get_stats()
        print("📊 记忆系统统计")
        print(f"   对话记录：{stats.get('total_conversations', 0)} 条")
        print(f"   总记忆数：{stats.get('total_memories', 0)} 条")

        by_type = stats.get('memories_by_type', {})
        print(f"   记忆分类:")
        for t, c in by_type.items():
            print(f"      - {t}: {c} 条")

        print(f"   活跃会话：{stats.get('active_sessions', 0)} 个")

        db_size = stats.get('database_size_bytes', 0)
        if db_size > 0:
            print(f"   数据库大小：{db_size / 1024 / 1024:.2f} MB")

    elif args.command == 'add':
        memory_id = engine.db.add_memory(
            content=args.content,
            memory_type=args.type,
            tags=args.tags
        )
        print(f"✅ 记忆已添加，ID: {memory_id}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()

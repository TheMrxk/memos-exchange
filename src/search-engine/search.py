#!/usr/bin/env python3
"""
MemOS Local - 记忆检索引擎

功能：关键词搜索、相关性评分、记忆管理
用法：
    python3 search.py search "关键词" --limit 6 --json
    python3 search.py stats
    python3 search.py reindex
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class MemorySearchEngine:
    """记忆检索引擎"""

    # 技术栈标签关键词
    TECH_KEYWORDS = [
        'Python', 'Flask', 'PyCharm', 'DBeaver', 'SQL', 'JavaScript',
        'Node.js', 'TypeScript', 'React', 'Vue', 'Linux', 'Git',
        'Docker', 'Kubernetes', 'Redis', 'MongoDB', 'PostgreSQL',
        'OpenClaw', 'Telegram', 'QQBot', '微信小程序'
    ]

    # 记忆类型关键词
    TYPE_KEYWORDS = {
        'preference': ['喜欢', '不喜欢', '偏好', '习惯', '常用', '爱用', '讨厌', '倾向'],
        'skill': ['会', '学会', '掌握', '技能', '能力', '擅长', '熟练', '懂得'],
        'experience': ['今天', '昨天', '经历', '事件', '开发', '完成', '参与', '做了'],
        'fact': ['是', '叫', '名字', '工作', '公司', '地点', '时间']
    }

    def __init__(self, memory_dir: str = None):
        """
        初始化检索引擎

        Args:
            memory_dir: 记忆文件目录，默认 ~/.openclaw/workspace/记忆
        """
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        else:
            self.memory_dir = Path.home() / '.openclaw' / 'workspace' / '记忆'

        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def load_memory_files(self, search_type: str = 'all') -> List[Path]:
        """
        加载记忆文件

        Args:
            search_type: 搜索类型 (all/daily/longterm/soul)

        Returns:
            记忆文件路径列表
        """
        files = []

        if search_type in ('all', 'daily'):
            # 加载每日记忆文件 YYYY-MM-DD.md
            for f in self.memory_dir.glob('*.md'):
                if f.name.startswith('_'):
                    continue
                if re.match(r'\d{4}-\d{2}-\d{2}.*\.md', f.name):
                    files.append(f)

        if search_type in ('all', 'longterm'):
            # 加载长期记忆
            longterm = self.memory_dir / '_LONGTERM_MEMORY.md'
            if longterm.exists():
                files.append(longterm)

        if search_type in ('all', 'soul'):
            # 加载灵魂记忆
            soul = self.memory_dir / '_SOUL.md'
            if soul.exists():
                files.append(soul)

        return sorted(files, reverse=True)

    def parse_memory_file(self, file_path: Path) -> Dict:
        """
        解析记忆文件

        Args:
            file_path: 文件路径

        Returns:
            解析后的记忆数据
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            return {'error': str(e)}

        # 提取标题
        title_match = re.search(r'^#\s*(.+)', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.name

        # 提取日期
        date_match = re.search(r'日期\s*[:：]?\s*(\d{4}-\d{2}-\d{2})', content)
        if not date_match:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_path.name)
        date = date_match.group(1) if date_match else None

        # 提取标签（从内容中的 #tag 格式）
        tags = re.findall(r'#(\w+)', content)

        # 提取记忆类型 sections
        sections = {}
        for type_name in ['事实', '偏好', '技能', '经验', 'Fact', 'Preference', 'Skill', 'Experience']:
            pattern = rf'##+.*?{re.escape(type_name)}.*?\n(.*?)(?=##+|$)'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                section_content = match.group(1).strip()
                items = [line.strip().lstrip('- ').lstrip('* ') for line in section_content.split('\n') if line.strip()]
                sections[type_name.lower()] = items

        # 提取对话记录
        conversations = []
        conv_pattern = r'###\s*对话\s*\d+\s*\*\*时间\*\*:\s*(\S+)\s*\*\*会话\*\*:\s*(\S+)\s*\*\*用户\*\*:\s*(.+?)\s*\*\*助手\*\*:\s*(.+?)(?=###|\Z)'
        for match in re.finditer(conv_pattern, content, re.DOTALL):
            conversations.append({
                'time': match.group(1),
                'session': match.group(2),
                'user': match.group(3).strip(),
                'assistant': match.group(4).strip()
            })

        # 生成内容摘要
        content_summary = self._generate_summary(content, sections)

        return {
            'file': file_path.name,
            'path': str(file_path),
            'title': title,
            'date': date,
            'tags': list(set(tags)),
            'sections': sections,
            'conversations': conversations,
            'content': content_summary,
            'full_content': content[:5000]  # 限制长度
        }

    def _generate_summary(self, content: str, sections: Dict) -> str:
        """生成内容摘要"""
        summary_parts = []

        # 添加 sections 内容
        for section_name, items in sections.items():
            for item in items[:3]:  # 每个 section 最多取 3 条
                summary_parts.append(item)

        if summary_parts:
            return '\n'.join(summary_parts)[:1000]

        # 如果没有 sections，返回文件前 500 字符
        return content[:500]

    def calculate_relevance(self, memory: Dict, query_terms: List[str]) -> float:
        """
        计算相关性分数

        Args:
            memory: 记忆数据
            query_terms: 查询关键词列表

        Returns:
            相关性分数 (0-1)
        """
        if not query_terms:
            return 0.0

        score = 0.0
        max_score = 0.0

        # 准备搜索文本
        title = memory.get('title', '').lower()
        content = memory.get('content', '').lower()
        tags = [t.lower() for t in memory.get('tags', [])]

        for term in query_terms:
            term = term.lower()

            # 标题匹配（最高权重 3）
            max_score += 3
            if term in title:
                score += 3
            elif any(term in word for word in title.split()):
                score += 1

            # 内容匹配（权重 2）
            max_score += 2
            if term in content:
                score += 2
            elif any(term in word for word in content.split()):
                score += 1

            # 标签匹配（权重 2）
            max_score += 2
            if term in tags:
                score += 2

        return score / max_score if max_score > 0 else 0.0

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
                if keyword.lower() in content_lower:
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
            if tech.lower() in content.lower():
                tags.append(tech)

        return list(set(tags))

    def search(
        self,
        query: str,
        limit: int = 6,
        min_score: float = 0.1,
        search_type: str = 'all',
        date_from: str = None,
        date_to: str = None,
        tags: List[str] = None,
        mem_type: str = None
    ) -> List[Dict]:
        """
        搜索记忆

        Args:
            query: 搜索关键词
            limit: 返回结果数量
            min_score: 最低相关性分数
            search_type: 搜索类型 (all/daily/longterm/soul)
            date_from: 起始日期 (YYYY-MM-DD)
            date_to: 结束日期 (YYYY-MM-DD)
            tags: 标签列表
            mem_type: 记忆类型 (preference/skill/experience/fact)

        Returns:
            搜索结果列表
        """
        # 解析查询词
        query_terms = query.split()

        # 加载文件
        files = self.load_memory_files(search_type)

        results = []
        for file_path in files:
            memory = self.parse_memory_file(file_path)

            if 'error' in memory:
                continue

            # 应用日期过滤器
            if date_from and memory.get('date'):
                if memory['date'] < date_from:
                    continue
            if date_to and memory.get('date'):
                if memory['date'] > date_to:
                    continue

            # 应用标签过滤器
            if tags:
                memory_tags = [t.lower() for t in memory.get('tags', [])]
                if not any(t.lower() in memory_tags for t in tags):
                    continue

            # 应用类型过滤器
            if mem_type:
                memory_type = self.auto_classify(memory.get('content', ''))
                if memory_type != mem_type:
                    continue

            # 计算相关性分数
            score = self.calculate_relevance(memory, query_terms)

            if score >= min_score:
                results.append({
                    'file': memory['file'],
                    'path': memory['path'],
                    'title': memory['title'],
                    'content': memory['content'],
                    'tags': memory['tags'],
                    'date': memory['date'],
                    'type': self.auto_classify(memory['content']),
                    'score': round(score, 3)
                })

        # 按分数降序排序
        results.sort(key=lambda x: x['score'], reverse=True)

        return results[:limit]

    def get_stats(self) -> Dict:
        """获取记忆统计信息"""
        files = self.memory_dir.glob('*.md')
        total_files = 0
        total_size = 0
        daily_files = 0
        longterm_exists = False
        soul_exists = False

        for f in files:
            total_files += 1
            total_size += f.stat().st_size

            if re.match(r'\d{4}-\d{2}-\d{2}.*\.md', f.name):
                daily_files += 1
            elif f.name == '_LONGTERM_MEMORY.md':
                longterm_exists = True
            elif f.name == '_SOUL.md':
                soul_exists = True

        return {
            'total_files': total_files,
            'daily_files': daily_files,
            'longterm_memory': longterm_exists,
            'soul_memory': soul_exists,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'memory_dir': str(self.memory_dir)
        }


def format_results_human(results: List[Dict]) -> str:
    """格式化结果为人类可读格式"""
    if not results:
        return "📭 未找到相关记忆"

    output = [f"📊 搜索结果 (找到 {len(results)} 条)\n"]

    for i, r in enumerate(results, 1):
        score_pct = int(r['score'] * 100)
        output.append(f"{i}. [{score_pct}%] {r['title']}")
        output.append(f"   📄 文件：{r['file']}")
        if r.get('date'):
            output.append(f"   📅 日期：{r['date']}")
        if r.get('tags'):
            output.append(f"   🏷️ 标签：{' '.join(r['tags'])}")
        output.append(f"   📝 摘要：{r['content'][:100]}...")
        output.append("")

    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(description='MemOS Local 记忆检索引擎')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索记忆')
    search_parser.add_argument('query', type=str, help='搜索关键词')
    search_parser.add_argument('--limit', '-n', type=int, default=6, help='返回结果数量')
    search_parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    search_parser.add_argument('--min-score', type=float, default=0.1, help='最低相关性分数')
    search_parser.add_argument('--type', choices=['all', 'daily', 'longterm', 'soul'], default='all', help='搜索类型')
    search_parser.add_argument('--from', dest='date_from', type=str, help='起始日期 (YYYY-MM-DD)')
    search_parser.add_argument('--to', dest='date_to', type=str, help='结束日期 (YYYY-MM-DD)')
    search_parser.add_argument('--tags', type=str, nargs='+', help='标签过滤')
    search_parser.add_argument('--mem-type', choices=['preference', 'skill', 'experience', 'fact'], help='记忆类型过滤')

    # stats 命令
    subparsers.add_parser('stats', help='显示统计信息')

    # reindex 命令
    subparsers.add_parser('reindex', help='重建索引')

    args = parser.parse_args()

    engine = MemorySearchEngine()

    if args.command == 'search':
        results = engine.search(
            query=args.query,
            limit=args.limit,
            min_score=args.min_score,
            search_type=args.type,
            date_from=args.date_from,
            date_to=args.date_to,
            tags=args.tags,
            mem_type=args.mem_type
        )

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(format_results_human(results))

    elif args.command == 'stats':
        stats = engine.get_stats()
        print("📊 记忆系统统计")
        print(f"   记忆目录：{stats['memory_dir']}")
        print(f"   总文件数：{stats['total_files']}")
        print(f"   每日记忆：{stats['daily_files']} 个")
        print(f"   长期记忆：{'✅' if stats['longterm_memory'] else '❌'}")
        print(f"   灵魂记忆：{'✅' if stats['soul_memory'] else '❌'}")
        print(f"   总大小：{stats['total_size_mb']} MB")

    elif args.command == 'reindex':
        print("🔄 重建索引中...")
        files = engine.load_memory_files()
        for f in files:
            engine.parse_memory_file(f)
        print(f"✅ 索引完成，共处理 {len(files)} 个文件")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()

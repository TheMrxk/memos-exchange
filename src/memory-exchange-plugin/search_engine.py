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

    def summarize_memory(self, user_content: str, assistant_content: str = None) -> str:
        """
        从对话中生成记忆摘要

        策略：
        1. 优先使用大模型生成摘要（如果配置了 API）
        2. 大模型失败时，降级使用规则引擎

        Args:
            user_content: 用户消息内容
            assistant_content: 助手回复内容（可选）

        Returns:
            摘要后的记忆内容
        """
        if not user_content:
            return ""

        # 尝试使用大模型生成摘要
        try:
            from llm_summarizer import LLMSummarizer
            summarizer = LLMSummarizer()
            llm_result = summarizer.summarize(user_content, assistant_content)
            if llm_result:
                # LLM 返回的格式："[type] 内容 (置信度：x.x)" 或多行
                # 提取第一条记忆的内容部分（去掉类型和置信度标记）
                lines = llm_result.strip().split('\n')
                if lines:
                    # 从第一行提取内容：[type] 内容 (置信度：x.x) -> 内容
                    first_line = lines[0]
                    # 尝试去掉类型标记
                    if first_line.startswith('['):
                        bracket_end = first_line.find(']')
                        if bracket_end > 0:
                            content = first_line[bracket_end + 1:].strip()
                            # 去掉置信度标记
                            conf_start = content.rfind(' (置信度：')
                            if conf_start > 0:
                                content = content[:conf_start].strip()
                            return content
                    return first_line
        except Exception as e:
            print(f"[SearchEngine] 大模型摘要失败：{e}，降级使用规则引擎")

        # 大模型不可用时，使用规则引擎
        clean_user = self._clean_system_context(user_content)
        if not clean_user:
            return ""

        summary = self._extract_key_information(clean_user, assistant_content)
        return summary if summary else clean_user.strip()

    def _extract_key_information(self, user_content: str, assistant_content: str = None) -> str:
        """
        从对话中提取关键信息生成记忆

        策略：
        1. 识别用户表达的事实、偏好、技能、经历
        2. 去除情绪性表达和冗余信息
        3. 提取可复用的知识点
        """
        content = user_content.strip()

        # 定义关键词模式和对应的提取规则
        patterns = [
            # 偏好模式：喜欢、爱吃、常用...
            (r'[喜欢爱用常用爱吃爱喝爱玩]+(.{1,50}?)$',
             lambda m: f"用户偏好：{m.group(1).strip()}"),

            # 情绪 + 行为模式：心情不好时想吃...
            (r'([心情情绪不好开心难过]) 时 [想会需要].{1,30}',
             lambda m: f"用户习惯：当{m.group(1)}时会寻求相关行为"),

            # 技能模式：我会、我懂、我能...
            (r'[我会我能我可以我懂我掌握].{1,40}',
             lambda m: f"用户技能：{m.group(0)}"),

            # 事实模式：我是、我在、我有...
            (r'[我是我在我有我家].{1,40}',
             lambda m: f"用户事实：{m.group(0)}"),

            # 项目/经历模式：今天做了、完成了、开发了...
            (r'(今天 | 昨天 | 最近 | 刚).{1,50}?[完成开发做写弄]了',
             lambda m: f"用户经历：{m.group(0)}"),
        ]

        import re

        for pattern, formatter in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                result = formatter(match)
                # 如果提取的结果过长，截断
                if len(result) > 200:
                    result = result[:197] + "..."
                return result

        # 如果没有匹配到模式，检查内容是否简短（<50 字），直接返回
        if len(content) <= 50:
            return content

        # 内容较长时，尝试提取第一句有意义的话
        sentences = re.split(r'[。！？!?；;]', content)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) >= 5 and len(sentence) <= 100:
                return sentence

        # 默认返回清理后的内容
        return content[:150] if len(content) > 150 else content

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
        # 生成记忆摘要（核心功能：从对话中提取关键信息）
        memory_content = self.summarize_memory(user_content, assistant_content)

        if not memory_content:
            return -1

        # 合并内容用于分析（分类和标签）
        full_content = user_content
        if assistant_content:
            full_content += f"\n助手：{assistant_content}"

        # 自动分类
        memory_type = self.auto_classify(full_content)

        # 提取标签
        tags = self.extract_tags(full_content)

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

    def _clean_system_context(self, content: str) -> str:
        """
        清理系统注入的上下文内容，提取用户实际消息

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        if not content:
            return content

        import re

        # 移除零宽空格和其他不可见 Unicode 字符
        content = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', content)

        # 使用 "user 原始 query：" 标记来定位用户实际消息
        # 这个标记是 OpenClaw 注入的，标记后面的内容才是用户实际发送的消息
        marker = "user 原始 query:"
        marker_index = content.rfind(marker)
        if marker_index != -1:
            # 截取标记之后的内容
            content = content[marker_index + len(marker):]

        # 移除 <memories> 标签块（这是系统注入的记忆上下文）
        content = re.sub(r'```text\s*<memories>.*?</memories>\s*```', '', content, flags=re.DOTALL)

        # 移除 "Conversation info" 等系统元数据
        content = re.sub(r'Conversation info \(untrusted metadata\):.*', '', content, flags=re.DOTALL)

        # 移除 "Sender" 等系统元数据块
        content = re.sub(r'Sender \(untrusted metadata\):.*', '', content, flags=re.DOTALL)

        # 移除 "System:" 开头的执行结果行
        content = re.sub(r'^System:\s*\[.*?\]\s*Exec completed.*$', '', content, flags=re.MULTILINE)

        # 移除 "后台检查：" 等系统指令
        content = re.sub(r'^后台检查：.*', '', content, flags=re.MULTILINE)

        # 移除 "When reading" 等系统指令
        content = re.sub(r'^When reading.*', '', content, flags=re.MULTILINE)

        # 移除 "Current time:" 系统时间行
        content = re.sub(r'^Current time:.*', '', content, flags=re.MULTILINE)

        # 移除 JSON 块（可能是系统元数据）
        content = re.sub(r'```json\s*\{[^}]*\}\s*```', '', content, flags=re.DOTALL)

        # 移除空的 Markdown 代码块
        content = re.sub(r'```\s*```', '', content)

        # 移除表格行（Markdown 表格）
        content = re.sub(r'^\|\s*.*\s*\|\s*$', '', content, flags=re.MULTILINE)

        # 移除表格分隔行
        content = re.sub(r'^\|\s*[-:|]+\s*\|\s*$', '', content, flags=re.MULTILINE)

        # 清理开头和结尾的空白字符
        content = content.strip()

        # 清理多余空白
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)

        return content

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

    # add-memory 命令 - 从对话自动生成记忆
    add_memory_parser = subparsers.add_parser('add-memory', help='从对话自动生成记忆')
    add_memory_parser.add_argument('user_content', type=str, help='用户消息内容')
    add_memory_parser.add_argument('assistant_content', type=str, nargs='?', default='', help='助手回复内容')
    add_memory_parser.add_argument('--conversation-id', type=int, default=None, help='对话 ID')
    add_memory_parser.add_argument('--user-id', type=str, default='default', help='用户 ID')

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

    elif args.command == 'add-memory':
        memory_id = engine.add_memory_from_conversation(
            user_content=args.user_content,
            assistant_content=args.assistant_content or '',
            conversation_id=args.conversation_id,
            user_id=args.user_id
        )
        print(f"✅ 记忆已生成，ID: {memory_id}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()

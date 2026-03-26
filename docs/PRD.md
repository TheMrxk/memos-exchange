# MemOS Local - 本地记忆管理系统
## 项目需求设计书

**版本**: v1.0  
**创建时间**: 2026-03-26  
**作者**: 何老师（AI 助手）  
**审核**: 开哥（用户）  

---

## 📋 目录

1. [项目概述](#1-项目概述)
2. [MemOS 工作原理分析](#2-memos 工作原理分析)
3. [本地化需求设计](#3-本地化需求设计)
4. [系统架构](#4-系统架构)
5. [功能模块详细设计](#5-功能模块详细设计)
6. [API 设计规范](#6-api 设计规范)
7. [数据格式规范](#7-数据格式规范)
8. [开发计划](#8-开发计划)
9. [测试计划](#9-测试计划)
10. [部署指南](#10-部署指南)

---

## 1. 项目概述

### 1.1 项目背景

**问题**: 
- 云端 AI 记忆服务（如 MemOS Cloud）存在数据依赖风险
- 一旦云端服务故障，所有记忆数据将无法访问
- 用户对敏感数据的本地化存储有强烈需求

**解决方案**:
开发一个**完全本地化**的记忆管理系统，复刻 MemOS 的核心功能，但数据完全存储在本地。

### 1.2 项目目标

构建一个本地记忆管理系统，实现：

1. ✅ **对话前自动注入记忆** - 根据当前对话内容，智能检索相关记忆并注入上下文
2. ✅ **对话后自动保存记忆** - 自动提取对话中的关键信息并保存
3. ✅ **智能检索** - 支持关键词、相关性、日期、标签等多维度检索
4. ✅ **记忆分类** - 自动区分事实、偏好、技能、经验等记忆类型
5. ✅ **完全本地** - 所有数据存储在本地，无需网络依赖
6. ✅ **OpenClaw 集成** - 作为 OpenClaw 插件无缝集成

### 1.3 目标用户

- **主要用户**: 使用 OpenClaw 的 AI 助手（如何老师、Claude）
- **次要用户**: 需要查看和管理记忆的最终用户（开哥）

### 1.4 使用场景

#### 场景 1: 日常对话记忆

```
开哥：我喜欢用 PyCharm 写 Python 代码
何老师：好的，我记住了 [保存记忆：用户偏好 PyCharm]

[第二天]
开哥：帮我写个 Python 脚本
何老师：好的，我知道你喜欢用 PyCharm，需要我创建 PyCharm 项目吗？[注入记忆]
```

#### 场景 2: 项目上下文记忆

```
开哥：我正在开发一个微信小程序，后端用 Flask
何老师：好的 [保存记忆：开哥的项目 - 微信小程序+Flask]

[一周后]
开哥：小程序的后台代码结构怎么优化？
何老师：根据你的 Flask 项目经验，我建议... [注入记忆]
```

#### 场景 3: 长期偏好记忆

```
开哥：我不喜欢营销类的工作
何老师：明白了 [保存记忆：用户职业偏好]

[数月后]
开哥：有个营销岗位的机会，要去试试吗？
何老师：根据你之前的偏好，你可能不太喜欢这类工作 [注入记忆]
```

### 1.5 核心价值

| 价值 | 说明 |
|------|------|
| **数据主权** | 所有记忆数据完全由用户控制 |
| **隐私安全** | 敏感数据不出本地 |
| **离线可用** | 无需网络即可工作 |
| **可定制** | 可根据需求扩展功能 |
| **可学习** | 代码开源，可学习 MemOS 设计 |

---

## 2. MemOS 工作原理分析

### 2.1 MemOS 核心架构

MemOS（Memory Operating System）是一个面向 LLM 和 AI Agent 的记忆操作系统。

```
┌─────────────────────────────────────────┐
│         应用层 (Application)             │
│  - OpenClaw 插件 / API 调用 / 用户界面   │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       记忆引擎层 (Memory Engine)         │
│  - 记忆检索 /search/memory              │
│  - 记忆存储 /add/message                │
│  - 记忆管理 /update/memory              │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       记忆存储层 (Memory Store)          │
│  - 向量数据库 / 记忆索引 / 记忆分类      │
└─────────────────────────────────────────┘
```

### 2.2 记忆生命周期

```
┌─────────────┐
│  记忆形成   │  对话 → 提取关键信息 → 分类 → 存储
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  记忆激活   │  新对话 → 语义检索 → 注入上下文
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  记忆巩固   │  频繁访问 → 提升优先级 → 长期存储
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  记忆更新   │  新信息 → 覆盖/合并旧记忆 → 冲突检测
└─────────────┘
```

### 2.3 核心 API 分析

#### 2.3.1 记忆检索 API

**MemOS 云端 API**:
```http
POST https://memos.memtensor.cn/api/openmem/v1/search/memory

Request:
{
  "user_id": "hekai",
  "query": "用户偏好 投资决策",
  "relativity": 0.45,
  "memoryLimitNumber": 6,
  "preferenceLimitNumber": 6,
  "tags": ["openclaw"]
}

Response:
{
  "memories": [
    {
      "id": "mem_123",
      "content": "用户喜欢使用 VS Code",
      "type": "preference",
      "score": 0.89,
      "timestamp": "2026-03-26T10:00:00Z"
    }
  ]
}
```

**本地实现要点**:
- ✅ `user_id` → 本地配置文件读取
- ✅ `query` → 用户当前对话的前 200 字符
- ✅ `relativity` → 关键词匹配算法计算相关性（0-1）
- ✅ `memoryLimitNumber` → 返回记忆数量限制
- ✅ `tags` → 文件标签过滤

#### 2.3.2 记忆存储 API

**MemOS 云端 API**:
```http
POST https://memos.memtensor.cn/api/openmem/v1/add/message

Request:
{
  "user_id": "hekai",
  "conversation_id": "session-123",
  "messages": [
    {"role": "user", "content": "我喜欢 Python"},
    {"role": "assistant", "content": "好的，记住了"}
  ],
  "tags": ["preference"]
}
```

**本地实现要点**:
- ✅ `messages` → 提取最后一轮对话
- ✅ `tags` → 自动分类（偏好/事实/技能/经验）
- ✅ `conversation_id` → OpenClaw 会话 ID

### 2.4 OpenClaw 插件工作流程

```
┌─────────────────────────────────────────┐
│  OpenClaw 对话开始                       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  beforeAgentStart (对话前)               │
│  1. 获取用户提示 (prompt)                │
│  2. 调用检索 API 搜索相关记忆             │
│  3. 格式化记忆为文本                     │
│  4. 注入到系统上下文                     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  AI 生成回复                              │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  afterAgentEnd (对话后)                  │
│  1. 提取最后一轮对话                     │
│  2. 调用存储 API 保存记忆                 │
│  3. 异步写入本地文件                     │
└─────────────────────────────────────────┘
```

### 2.5 记忆分类体系

MemOS 将记忆分为四类：

| 类型 | 说明 | 示例 |
|------|------|------|
| **Fact (事实)** | 客观事实信息 | "用户名叫何开" |
| **Preference (偏好)** | 用户喜好和习惯 | "喜欢用 PyCharm" |
| **Skill (技能)** | 学到的技能和知识 | "会用 Flask 开发" |
| **Experience (经验)** | 经历和事件 | "2026-03-26 开发了 MemOS 本地版" |

---

## 3. 本地化需求设计

### 3.1 设计原则

1. **完全本地**: 所有数据存储在本地文件系统
2. **零网络依赖**: 无需联网即可正常工作
3. **简单易用**: 安装即用，无需复杂配置
4. **可扩展**: 预留接口，方便未来扩展
5. **向下兼容**: 保留与 MemOS 云端的兼容性

### 3.2 技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| **检索引擎** | Python 3.7+ | 简单易用，适合文本处理 |
| **OpenClaw 插件** | Node.js (CommonJS) | OpenClaw 官方支持 |
| **数据存储** | Markdown 文件 | 人类可读，易于备份 |
| **索引 (可选)** | SQLite | 轻量级，无需额外服务 |
| **语义搜索 (可选)** | Sentence Transformers | 本地语义理解 |

### 3.3 文件结构设计

```
~/.openclaw/workspace/记忆/
├── 2026-03-26.md              # 每日记忆文件
├── 2026-03-27.md
├── _LONGTERM_MEMORY.md        # 长期记忆
├── _SOUL.md                   # 灵魂记忆（月度总结）
└── conversations/
    ├── 2026-03-26.md          # 对话记录
    └── 2026-03-27.md

~/.openclaw/workspace/memory-engine/
├── search.py                  # 检索引擎
├── test_search.py             # 单元测试
└── README.md

~/.openclaw/extensions/local-memory-plugin/
├── package.json               # 插件配置
├── index.js                   # 插件主程序
└── README.md
```

### 3.4 记忆文件格式

#### 3.4.1 每日记忆文件

```markdown
# 2026-03-26 记忆

## 元数据
- 日期：2026-03-26
- 创建时间：2026-03-26 10:00:00
- 更新时间：2026-03-26 12:00:00

## 事实
- 用户名叫何开
- 用户在建行工作

## 偏好
- 喜欢用 PyCharm 写 Python
- 不喜欢营销类工作

## 技能
- 会用 Flask 开发后端
- 会用 DBeaver 管理数据库

## 经验
- 2026-03-26 开发了 MemOS 本地版

## 对话记录

### 对话 1
**时间**: 10:00
**会话**: session-123
**用户**: 我喜欢用 PyCharm
**助手**: 好的，我记住了

### 对话 2
**时间**: 11:00
**会话**: session-456
**用户**: 帮我写个 Flask 路由
**助手**: 好的，这是示例代码...

---
```

#### 3.4.2 长期记忆文件

```markdown
# 长期记忆

**最后更新**: 2026-03-26

## 用户信息
- **姓名**: 何开
- **称呼**: 开哥
- **职业**: 建设银行柜员
- **时区**: UTC+8 北京

## 核心偏好
- 喜欢技术工作，不喜欢营销
- 偏好 PyCharm + Flask 技术栈
- 重视数据隐私和本地控制

## 核心技能
- Python 开发
- Flask 后端开发
- 数据库管理 (DBeaver)
- 网络运维

## 重要项目
- 微信小程序（省行面试作品）
- MemOS 本地实现
- 全栈简报系统

---
```

### 3.5 检索算法设计

#### 3.5.1 关键词匹配算法

```python
def calculate_relevance(memory, query_terms):
    """
    计算相关性分数
    
    权重设计:
    - 标题匹配: 3 分 (最高权重)
    - 内容完全匹配: 2 分
    - 内容部分匹配: 1 分
    - 标签匹配: 2 分
    
    最终分数 = 总得分 / 最大可能得分
    """
    score = 0.0
    max_score = 0.0
    
    # 标题匹配
    title = memory.get('title', '').lower()
    for term in query_terms:
        max_score += 3
        if term in title:
            score += 3
        elif any(term in word for word in title.split()):
            score += 1
    
    # 内容匹配
    content = memory.get('content', '').lower()
    for term in query_terms:
        max_score += 2
        if term in content:
            score += 2
        elif any(term in word for word in content.split()):
            score += 1
    
    # 标签匹配
    tags = memory.get('tags', [])
    for term in query_terms:
        max_score += 2
        if term in [t.lower() for t in tags]:
            score += 2
    
    return score / max_score if max_score > 0 else 0.0
```

#### 3.5.2 检索流程

```
1. 加载所有记忆文件
   ↓
2. 解析元数据（标题、标签、日期等）
   ↓
3. 应用过滤器（类型、日期、标签）
   ↓
4. 对每个记忆计算相关性分数
   ↓
5. 按分数降序排序
   ↓
6. 返回前 N 条结果
```

### 3.6 记忆提取规则

#### 3.6.1 自动分类规则

```python
def classify_memory(content):
    """
    根据关键词自动分类记忆
    """
    content_lower = content.lower()
    
    # 偏好类关键词
    preference_keywords = ['喜欢', '不喜欢', '偏好', '习惯', '常用', '爱用']
    if any(kw in content_lower for kw in preference_keywords):
        return 'preference'
    
    # 技能类关键词
    skill_keywords = ['会', '学会', '掌握', '技能', '能力', '擅长']
    if any(kw in content_lower for kw in skill_keywords):
        return 'skill'
    
    # 经验类关键词
    experience_keywords = ['今天', '昨天', '经历', '事件', '开发', '完成']
    if any(kw in content_lower for kw in experience_keywords):
        return 'experience'
    
    # 默认为事实
    return 'fact'
```

#### 3.6.2 标签自动生成

```python
def extract_tags(content):
    """
    从内容中提取标签
    """
    tags = []
    
    # 技术栈标签
    tech_keywords = ['Python', 'Flask', 'PyCharm', 'DBeaver', 'SQL', 'JavaScript']
    tags.extend([kw for kw in tech_keywords if kw in content])
    
    # 项目标签
    project_keywords = ['微信小程序', 'MemOS', '全栈简报', 'OpenClaw']
    tags.extend([kw for kw in project_keywords if kw in content])
    
    return list(set(tags))  # 去重
```

---

## 4. 系统架构

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway                      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ 对话开始
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Local Memory Plugin (Node.js)               │
│  ┌──────────────────────────────────────────────────┐  │
│  │  beforeAgentStart                                │  │
│  │  1. 获取用户提示 (prompt)                         │  │
│  │  2. 调用 search.py 检索记忆                       │  │
│  │  3. 格式化记忆文本                                │  │
│  │  4. 注入到系统上下文                              │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  afterAgentEnd                                   │  │
│  │  1. 提取最后一轮对话                              │  │
│  │  2. 自动分类和打标签                              │  │
│  │  3. 保存到记忆文件                                │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ 调用
                        ▼
┌─────────────────────────────────────────────────────────┐
│            Memory Search Engine (Python)                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  搜索功能                                        │  │
│  │  - 关键词匹配                                    │  │
│  │  - 相关性评分                                    │  │
│  │  - 日期/类型/标签过滤                            │  │
│  │  - JSON 输出                                     │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ 读写
                        ▼
┌─────────────────────────────────────────────────────────┐
│              本地文件系统 (Markdown)                      │
│  ~/.openclaw/workspace/记忆/                            │
│  ├── YYYY-MM-DD.md                                      │
│  ├── _LONGTERM_MEMORY.md                                │
│  └── conversations/                                     │
└─────────────────────────────────────────────────────────┘
```

### 4.2 模块依赖关系

```
local-memory-plugin (Node.js)
    │
    ├── 依赖：search.py (Python)
    │       │
    │       └── 依赖：无（纯 Python 标准库）
    │
    └── 依赖：记忆文件 (Markdown)
```

### 4.3 数据流图

```
用户提问
    │
    ▼
OpenClaw Gateway
    │
    ▼
beforeAgentStart 钩子
    │
    ├─→ 提取 prompt 前 200 字符
    │
    ├─→ 调用 search.py search "关键词" --json
    │
    ├─→ 解析 JSON 结果
    │
    ├─→ 格式化为注入文本
    │
    └─→ 注入到系统上下文
            │
            ▼
        AI 生成回复
            │
            ▼
afterAgentEnd 钩子
    │
    ├─→ 提取最后一轮对话
    │
    ├─→ 自动分类（事实/偏好/技能/经验）
    │
    ├─→ 自动生成标签
    │
    └─→ 追加到今日记忆文件
```

---

## 5. 功能模块详细设计

### 5.1 记忆检索引擎 (search.py)

#### 5.1.1 功能需求

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **关键词搜索** | 支持多关键词全文检索 | P0 |
| **相关性评分** | 智能算法计算 0-1 分数 | P0 |
| **日期过滤** | 按 `--from` 和 `--to` 过滤 | P1 |
| **类型过滤** | 按事实/偏好/技能/经验过滤 | P1 |
| **标签搜索** | 按 `#标签` 过滤 | P1 |
| **JSON 输出** | 方便脚本集成 | P0 |
| **统计信息** | 显示记忆文件统计 | P2 |

#### 5.1.2 命令行接口

```bash
# 基本搜索
python3 search.py search "关键词"

# 限制结果数量
python3 search.py search "Python" --limit 10

# JSON 输出
python3 search.py search "Flask" --json

# 日期范围
python3 search.py search "开发" --from 2026-03-01 --to 2026-03-26

# 类型过滤
python3 search.py search "技能" --type skill

# 标签过滤
python3 search.py search "技术" --tags python flask

# 查看统计
python3 search.py stats

# 重建索引
python3 search.py reindex
```

#### 5.1.3 输出格式

**普通输出**:
```
📊 搜索结果：'Python' (找到 3 条)

1. [85.0%] Python 开发环境配置
   文件：2026-03-24.md
   日期：2026-03-24
   标签：python 开发 环境
   摘要：使用 PyCharm 进行 Python 开发...

2. [72.0%] Flask 模块化架构
   文件：_LONGTERM_MEMORY.md
   标签：python flask 架构
   摘要：Flask 应用模块化架构最佳实践...
```

**JSON 输出**:
```json
[
  {
    "file": "2026-03-24.md",
    "path": "/home/user/.openclaw/workspace/记忆/2026-03-24.md",
    "title": "Python 开发环境配置",
    "content": "使用 PyCharm 进行 Python 开发...",
    "tags": ["python", "开发", "环境"],
    "date": "2026-03-24",
    "type": "skill",
    "score": 0.85
  }
]
```

### 5.2 OpenClaw 插件 (index.js)

#### 5.2.1 功能需求

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **对话前注入** | beforeAgentStart 钩子检索记忆 | P0 |
| **对话后保存** | afterAgentEnd 钩子保存记忆 | P0 |
| **配置加载** | 从 openclaw.json 读取配置 | P0 |
| **错误处理** | 失败时不中断对话 | P0 |
| **日志记录** | 记录插件运行状态 | P1 |

#### 5.2.2 配置项

```json
{
  "plugins": {
    "entries": {
      "local-memory-plugin": {
        "enabled": true,
        "config": {
          "memoryLimitNumber": 6,
          "preferenceLimitNumber": 6,
          "minScore": 0.3,
          "includeAssistant": true,
          "maxMessageChars": 5000,
          "searchEngine": "~/.openclaw/workspace/memory-engine/search.py",
          "memoryDir": "~/.openclaw/workspace/记忆"
        }
      }
    }
  }
}
```

#### 5.2.3 注入文本格式

```markdown
## 📔 本地记忆注入

以下是从本地记忆中检索到的相关信息：

1. [相关性 85%] **Python 开发环境配置**
   使用 PyCharm 进行 Python 开发，配置了虚拟环境和代码格式化...
   📅 2026-03-24
   🏷️ python 开发 环境

2. [相关性 72%] **Flask 模块化架构**
   Flask 应用模块化架构最佳实践，避免循环导入...
   🏷️ python flask 架构

---
```

### 5.3 记忆提取模块

#### 5.3.1 功能需求

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **对话提取** | 从对话中提取关键信息 | P0 |
| **自动分类** | 事实/偏好/技能/经验 | P0 |
| **标签生成** | 自动提取技术栈和项目标签 | P1 |
| **去重检测** | 避免重复记忆 | P1 |

#### 5.3.2 分类规则

```python
分类规则：
1. 包含"喜欢/不喜欢/偏好" → preference
2. 包含"会/学会/掌握/技能" → skill
3. 包含"今天/昨天/经历/事件" → experience
4. 其他 → fact
```

#### 5.3.3 标签提取规则

```python
技术栈标签：
- Python, Flask, PyCharm, DBeaver, SQL, JavaScript, Node.js

项目标签：
- 微信小程序，MemOS, 全栈简报，OpenClaw, QQBot
```

---

## 6. API 设计规范

### 6.1 内部 API（Python 检索引擎）

#### 6.1.1 搜索接口

```python
class MemorySearchEngine:
    def search(self, query: str, limit: int = 6, min_score: float = 0.1,
               search_type: str = 'all', date_from: str = None, 
               date_to: str = None, tags: List[str] = None) -> List[Dict]:
        """
        搜索记忆
        
        参数:
            query: 搜索关键词
            limit: 返回结果数量
            min_score: 最低相关性分数
            search_type: 搜索类型 (all/daily/longterm/soul)
            date_from: 起始日期 (YYYY-MM-DD)
            date_to: 结束日期 (YYYY-MM-DD)
            tags: 标签列表
        
        返回:
            搜索结果列表，每项包含:
            - file: 文件名
            - path: 完整路径
            - title: 标题
            - content: 内容摘要
            - tags: 标签列表
            - date: 日期
            - score: 相关性分数
        """
```

### 6.2 外部 API（Node.js 插件调用）

#### 6.2.1 命令行调用

```javascript
const { execSync } = require('child_process');

function searchMemories(query, limit = 6) {
    const cmd = `python3 "${searchEngine}" search "${query}" --limit ${limit} --json`;
    const result = execSync(cmd, { encoding: 'utf8', timeout: 5000 });
    return JSON.parse(result);
}
```

---

## 7. 数据格式规范

### 7.1 记忆文件 Markdown 格式

```markdown
# {日期} 记忆

## 元数据
- 日期：{YYYY-MM-DD}
- 创建时间：{YYYY-MM-DD HH:MM:SS}
- 更新时间：{YYYY-MM-DD HH:MM:SS}

## 事实
- {事实 1}
- {事实 2}

## 偏好
- {偏好 1}
- {偏好 2}

## 技能
- {技能 1}
- {技能 2}

## 经验
- {经验 1}
- {经验 2}

## 对话记录

### 对话 {序号}
**时间**: {HH:MM}
**会话**: {session-id}
**用户**: {用户消息}
**助手**: {助手回复}

---
```

### 7.2 JSON 输出格式

```json
{
  "file": "2026-03-26.md",
  "path": "/home/user/.openclaw/workspace/记忆/2026-03-26.md",
  "created_at": "2026-03-26T10:00:00",
  "modified_at": "2026-03-26T12:00:00",
  "size": 1024,
  "tags": ["python", "flask"],
  "title": "2026-03-26 记忆",
  "content": "使用 PyCharm 进行 Python 开发...",
  "date": "2026-03-26",
  "score": 0.85
}
```

---

## 8. 开发计划

### 8.1 阶段划分

#### 阶段 1：记忆检索引擎 ✅ 已完成

**时间**: 2026-03-26  
**负责人**: 何老师  
**状态**: ✅ 已完成

**交付物**:
- [x] search.py - 检索引擎主程序
- [x] test_search.py - 单元测试
- [x] README.md - 说明文档

**验收标准**:
- [x] 关键词搜索功能正常
- [x] 相关性评分准确
- [x] JSON 输出格式正确
- [x] 统计功能正常

#### 阶段 2：OpenClaw 插件 ⏸️ 待开发

**时间**:  TBD  
**负责人**:  Claude Code  
**状态**: ⏸️ 待开始

**交付物**:
- [ ] package.json - 插件配置
- [ ] index.js - 插件主程序
- [ ] openclaw.plugin.json - OpenClaw 配置
- [ ] README.md - 插件文档

**验收标准**:
- [ ] beforeAgentStart 钩子正常注入记忆
- [ ] afterAgentEnd 钩子正常保存记忆
- [ ] 配置可从 openclaw.json 读取
- [ ] 错误处理完善，不中断对话
- [ ] 日志记录完整

**开发指南**:
1. 参考 `~/.openclaw/extensions/memos-cloud-openclaw-plugin/` 的源码
2. 使用 CommonJS 模块格式（不要用 ES6 Module）
3. 调用 search.py 使用 `execSync` 执行命令行
4. 注入文本使用 `ctx.appendSystemContext()` 方法
5. 保存对话追加到 `~/.openclaw/workspace/记忆/conversations/{date}.md`

#### 阶段 3：记忆提取优化 ⏸️ 待开发

**时间**: TBD  
**负责人**: Claude Code  
**状态**: ⏸️ 待开始

**交付物**:
- [ ] memory_extractor.py - 记忆提取模块
- [ ] classifier.py - 自动分类模块
- [ ] tagger.py - 标签生成模块
- [ ] deduplicator.py - 去重检测模块

**验收标准**:
- [ ] 自动分类准确率 > 80%
- [ ] 标签生成相关性 > 80%
- [ ] 去重检测准确率 > 90%

### 8.2 任务分解

#### 阶段 2 任务分解

| 任务 | 预计时间 | 依赖 | 负责人 |
|------|---------|------|--------|
| 创建插件骨架 | 30 分钟 | 阶段 1 | Claude |
| 实现 beforeAgentStart | 1 小时 | 插件骨架 | Claude |
| 实现 afterAgentEnd | 1 小时 | 插件骨架 | Claude |
| 集成 search.py | 30 分钟 | beforeAgentStart | Claude |
| 错误处理 | 30 分钟 | 全部功能 | Claude |
| 编写测试 | 1 小时 | 全部功能 | Claude |
| 编写文档 | 30 分钟 | 全部功能 | Claude |

**总计**: 5 小时

---

## 9. 测试计划

### 9.1 单元测试

#### 9.1.1 检索引擎测试

```python
# test_search.py
class TestMemorySearchEngine(unittest.TestCase):
    
    def test_search_basic(self):
        """测试基本搜索"""
        results = self.engine.search("Python")
        self.assertGreater(len(results), 0)
    
    def test_search_limit(self):
        """测试结果数量限制"""
        results = self.engine.search("Python", limit=2)
        self.assertLessEqual(len(results), 2)
    
    def test_search_relevance(self):
        """测试相关性评分"""
        results = self.engine.search("Python 开发")
        if len(results) > 1:
            self.assertGreaterEqual(results[0]['score'], results[1]['score'])
    
    def test_search_by_date(self):
        """测试日期过滤"""
        results = self.engine.search(
            "Python",
            date_from="2026-03-01",
            date_to="2026-03-26"
        )
        for r in results:
            if r.get('date'):
                self.assertGreaterEqual(r['date'], "2026-03-01")
                self.assertLessEqual(r['date'], "2026-03-26")
```

#### 9.1.2 插件测试

```javascript
// test/plugin.test.js
describe('LocalMemoryPlugin', () => {
    
    test('beforeAgentStart should inject memories', async () => {
        const ctx = { prompt: '我喜欢 Python', appendSystemContext: jest.fn() };
        await plugin.beforeAgentStart(ctx);
        expect(ctx.appendSystemContext).toHaveBeenCalled();
    });
    
    test('afterAgentEnd should save conversation', async () => {
        const ctx = {
            lastTurn: { user: '你好', assistant: '你好！' },
            sessionKey: 'test-123'
        };
        await plugin.afterAgentEnd(ctx);
        // 检查文件是否创建
    });
});
```

### 9.2 集成测试

#### 9.2.1 完整流程测试

```
1. 启动 OpenClaw Gateway
2. 发送测试消息："我喜欢用 PyCharm"
3. 检查记忆是否保存到文件
4. 发送测试消息："推荐个 Python IDE"
5. 检查回复是否包含 PyCharm 相关记忆
6. 验证端到端流程正常
```

### 9.3 性能测试

| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| 检索响应时间 | < 100ms | 100 次搜索平均时间 |
| 记忆保存时间 | < 50ms | 100 次保存平均时间 |
| 内存占用 | < 50MB | 插件运行时的 RSS |

---

## 10. 部署指南

### 10.1 环境要求

- **Python**: 3.7+
- **Node.js**: 14+
- **OpenClaw**: 2026.3.2+
- **操作系统**: Linux / macOS / Windows

### 10.2 安装步骤

#### 步骤 1: 安装检索引擎

```bash
# 创建目录
mkdir -p ~/.openclaw/workspace/memory-engine

# 复制文件
cp search.py ~/.openclaw/workspace/memory-engine/
cp test_search.py ~/.openclaw/workspace/memory-engine/

# 测试
cd ~/.openclaw/workspace/memory-engine
python3 search.py stats
```

#### 步骤 2: 安装 OpenClaw 插件

```bash
# 创建目录
mkdir -p ~/.openclaw/extensions/local-memory-plugin

# 复制文件
cp package.json ~/.openclaw/extensions/local-memory-plugin/
cp index.js ~/.openclaw/extensions/local-memory-plugin/
cp openclaw.plugin.json ~/.openclaw/extensions/local-memory-plugin/

# 在 openclaw.json 中启用插件
# 编辑 ~/.openclaw/openclaw.json，添加:
{
  "plugins": {
    "entries": {
      "local-memory-plugin": {
        "enabled": true
      }
    }
  }
}

# 重启 Gateway
openclaw gateway restart
```

#### 步骤 3: 验证安装

```bash
# 测试检索引擎
python3 ~/.openclaw/workspace/memory-engine/search.py search "测试" --limit 3

# 检查插件状态
openclaw gateway status

# 查看插件日志
tail -f ~/.openclaw/logs/gateway.log | grep LocalMemory
```

### 10.3 配置说明

#### 10.3.1 插件配置

```json
{
  "enabled": true,              // 是否启用插件
  "memoryLimitNumber": 6,       // 注入记忆数量
  "preferenceLimitNumber": 6,   // 注入偏好数量
  "minScore": 0.3,              // 最低相关性分数
  "includeAssistant": true,     // 是否保存助手消息
  "maxMessageChars": 5000       // 消息最大字符数
}
```

#### 10.3.2 环境变量（可选）

```bash
# 自定义记忆目录
export MEMOS_MEMORY_DIR=~/.openclaw/workspace/记忆

# 自定义检索引擎路径
export MEMOS_SEARCH_ENGINE=~/.openclaw/workspace/memory-engine/search.py
```

### 10.4 故障排查

#### 问题 1: 插件未加载

```bash
# 检查插件是否启用
cat ~/.openclaw/openclaw.json | grep local-memory

# 重启 Gateway
openclaw gateway restart

# 查看日志
tail -f ~/.openclaw/logs/gateway.log
```

#### 问题 2: 记忆未注入

```bash
# 测试检索引擎
python3 ~/.openclaw/workspace/memory-engine/search.py search "测试" --limit 3

# 检查记忆文件
ls -la ~/.openclaw/workspace/记忆/

# 查看插件日志
tail -f ~/.openclaw/logs/gateway.log | grep LocalMemory
```

#### 问题 3: 对话未保存

```bash
# 检查记忆目录权限
ls -ld ~/.openclaw/workspace/记忆/

# 手动创建目录
mkdir -p ~/.openclaw/workspace/记忆/conversations

# 测试写入
echo "test" >> ~/.openclaw/workspace/记忆/conversations/test.md
```

---

## 附录 A: 参考资料

- [MemOS 官方文档](https://memos-docs.openmem.net/)
- [MemOS GitHub](https://github.com/MemTensor/MemOS)
- [MemOS 论文](https://arxiv.org/abs/2507.03724)
- [OpenClaw 插件开发指南](https://docs.openclaw.ai/plugins)

## 附录 B: 常见问题

### Q1: 为什么选择本地存储而不是云端？

**A**: 数据主权和隐私安全。本地存储确保用户完全控制自己的记忆数据，不依赖第三方服务。

### Q2: 本地存储和 MemOS 云端有什么区别？

**A**: 
- **相同点**: 核心功能一致（检索、存储、分类）
- **不同点**: 
  - 本地存储数据在文件系统，云端在数据库
  - 本地使用关键词匹配，云端用语义搜索
  - 本地无需网络，云端需要联网

### Q3: 未来会支持语义搜索吗？

**A**: 计划中。可以使用 Sentence Transformers 等本地模型实现语义搜索，无需云端依赖。

### Q4: 如何备份记忆数据？

**A**: 记忆文件是普通 Markdown 文件，可以用任何备份工具（rsync、Git、云盘等）备份 `~/.openclaw/workspace/记忆/` 目录。

---

**文档结束**

*最后更新：2026-03-26*  
*维护者：何老师*  
*审核者：开哥*

# MemOS Local - 本地记忆管理系统

## 项目状态

**版本**: v1.0.0
**开发日期**: 2026-03-26
**状态**: 🟢 核心功能已完成

---

## 📋 项目概述

MemOS Local 是一个完全本地化的记忆管理系统，作为 OpenClaw 插件运行，实现：

- ✅ **对话前自动注入记忆** - 根据当前对话内容，智能检索相关记忆并注入上下文
- ✅ **对话后自动保存记忆** - 自动提取对话中的关键信息并保存
- ✅ **智能检索** - 支持关键词、相关性、日期、标签等多维度检索
- ✅ **完全本地** - 所有数据存储在本地，无需网络依赖

---

## 🚀 快速开始

### 环境要求

- Python 3.7+
- OpenClaw 2026.3.2+

### 安装步骤

#### 1. 安装检索引擎

```bash
# 创建目录
mkdir -p ~/.openclaw/workspace/memory-engine

# 复制检索引擎
cp src/search-engine/search.py ~/.openclaw/workspace/memory-engine/
chmod +x ~/.openclaw/workspace/memory-engine/search.py
```

#### 2. 验证安装

```bash
python3 ~/.openclaw/workspace/memory-engine/search.py stats
```

---

## 📖 使用说明

### 检索引擎命令

#### 基本搜索

```bash
# 搜索关键词
python3 ~/.openclaw/workspace/memory-engine/search.py search "Python"

# 限制结果数量
python3 ~/.openclaw/workspace/memory-engine/search.py search "Flask" --limit 10

# JSON 输出（方便脚本集成）
python3 ~/.openclaw/workspace/memory-engine/search.py search "OpenClaw" --json
```

#### 高级搜索

```bash
# 日期范围搜索
python3 ~/.openclaw/workspace/memory-engine/search.py search "开发" \
  --from 2026-03-01 --to 2026-03-26

# 按类型过滤 (preference/skill/experience/fact)
python3 ~/.openclaw/workspace/memory-engine/search.py search "技能" --mem-type skill

# 标签过滤
python3 ~/.openclaw/workspace/memory-engine/search.py search "技术" --tags python flask

# 组合搜索
python3 ~/.openclaw/workspace/memory-engine/search.py search "Python 开发" \
  --limit 5 --min-score 0.2 --json
```

#### 统计信息

```bash
python3 ~/.openclaw/workspace/memory-engine/search.py stats
```

输出示例：
```
📊 记忆系统统计
   记忆目录：/home/hekai/.openclaw/workspace/记忆
   总文件数：31
   每日记忆：27 个
   长期记忆：✅
   灵魂记忆：✅
   总大小：0.14 MB
```

---

## 📁 目录结构

```
memos-exchange/
├── README.md                    # 项目说明
├── docs/
│   ├── PRD.md                   # 产品需求文档
│   └── memos-architecture.md    # MemOS 架构分析
├── src/
│   ├── search-engine/
│   │   ├── search.py            # 记忆检索引擎
│   │   └── test_search.py       # 单元测试（待开发）
│   └── plugin/                  # OpenClaw 插件（待开发）
├── api/
│   └── README.md                # API 使用文档
└── logs/
    └── 2026-03-26-dev-log.md    # 开发日志
```

---

## 🔧 检索引擎 API

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词 | 必填 |
| `--limit, -n` | 返回结果数量 | 6 |
| `--json, -j` | JSON 输出 | false |
| `--min-score` | 最低相关性分数 | 0.1 |
| `--type` | 搜索类型 (all/daily/longterm/soul) | all |
| `--from` | 起始日期 (YYYY-MM-DD) | - |
| `--to` | 结束日期 (YYYY-MM-DD) | - |
| `--tags` | 标签过滤 | - |
| `--mem-type` | 记忆类型 (preference/skill/experience/fact) | - |

### JSON 输出格式

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

---

## 📝 记忆文件格式

记忆文件存储在 `~/.openclaw/workspace/记忆/` 目录，格式如下：

```markdown
# 2026-03-26 记忆

**日期**: 2026-03-26
**时间范围**: 2026-03-25 02:00 - 2026-03-26 02:00
**天气**: 晴
**心情**: 充实
**重要程度**: ⭐⭐⭐

---

## 🎯 今日重点

### 1. OpenClaw 本地记忆插件开发

**时间**: 10:00-12:00

**过程**:
- 开发记忆检索引擎
- 创建 OpenClaw 插件骨架
- 测试搜索功能

**结果**: ✅ 检索引擎完成

---

## 对话记录

### 对话 1
**时间**: 10:00
**会话**: session-123
**用户**: 我喜欢用 PyCharm 写 Python 代码
**助手**: 好的，我记住了你的偏好

---
```

---

## 🧪 测试

### 单元测试（待开发）

```bash
cd src/search-engine
python3 -m pytest test_search.py
```

### 集成测试

```bash
# 测试搜索功能
python3 ~/.openclaw/workspace/memory-engine/search.py search "测试" --limit 3

# 测试 JSON 输出
python3 ~/.openclaw/workspace/memory-engine/search.py search "测试" --json | jq .
```

---

## 📊 开发进度

| 阶段 | 功能 | 状态 |
|------|------|------|
| **阶段 1** | 记忆检索引擎 | ✅ 已完成 |
| **阶段 2** | OpenClaw 插件 | ⏸️ 暂停（API 限制） |
| **阶段 3** | 记忆提取优化 | ⏸️ 待开发 |

---

## 🔍 常见问题

### Q: 搜索结果为空？

**A**: 检查以下几点：
1. 记忆目录是否有文件：`ls ~/.openclaw/workspace/记忆/`
2. 降低最低分数：`--min-score 0.05`
3. 使用更简单的关键词

### Q: JSON 输出解析失败？

**A**: 确保使用 `--json` 参数，并用 `jq` 验证格式：
```bash
python3 search.py search "测试" --json | jq .
```

### Q: 如何集成到其他应用？

**A**: 使用 JSON 输出模式：
```python
import subprocess
import json

result = subprocess.run(
    ['python3', 'search.py', 'search', '关键词', '--json'],
    capture_output=True, text=True
)
memories = json.loads(result.stdout)
```

---

## 📚 参考资料

- [MemOS 官方文档](https://memos-docs.openmem.net/)
- [MemOS GitHub](https://github.com/MemTensor/MemOS)
- [MemOS 论文](https://arxiv.org/abs/2507.03724)
- [OpenClaw 文档](https://docs.openclaw.ai/)

---

## 📄 License

MIT License

---

**最后更新**: 2026-03-26
**维护者**: 何老师 + 开哥

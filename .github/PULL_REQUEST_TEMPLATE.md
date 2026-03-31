# Pull Request: 添加本地记忆插件（SQLite + FTS5）

## 📋 概述

本 PR 实现了 MemOS Exchange 本地记忆插件，参考 MemOS Cloud 插件的工作流程，但数据完全存储在本地 SQLite 数据库中。

## ✨ 新增功能

### 1. 数据库模块 (`db/schema.py`)
- SQLite 数据库 Schema 定义
- 支持对话记录、记忆存储、会话管理
- FTS5 全文搜索虚拟表
- 自动触发器同步 FTS 索引
- WAL 模式优化并发性能

### 2. 检索引擎 (`search_engine.py`)
- 关键词全文搜索（基于 FTS5）
- 自动记忆分类（事实/偏好/技能/经验）
- 标签自动提取
- 相关性评分
- CLI 接口支持多种搜索选项

### 3. OpenClaw 插件 (`index.js`, `openclaw.plugin.json`)
- `before_agent_start` 钩子 - 检索记忆并注入上下文
- `agent_end` 钩子 - 保存对话到数据库
- 完整的配置 Schema
- 错误处理（失败不中断对话）

### 4. 测试 (`test/test_plugin.py`)
- 9 个单元测试，全部通过
- 测试覆盖：
  - 数据库操作（对话、记忆、搜索）
  - 自动分类（偏好、技能、经验）
  - 标签提取
  - 搜索功能

## 🔧 技术实现

| 组件 | 技术 | 说明 |
|------|------|------|
| 数据库 | SQLite 3 | 本地存储，无需额外服务 |
| 全文搜索 | FTS5 | SQLite 内置全文搜索引擎 |
| 插件运行时 | Node.js | OpenClaw 插件框架 |
| 检索引擎 | Python 3 | 独立 CLI，可被插件调用 |

## 📊 测试结果

```
$ python3 test/test_plugin.py
test_add_conversation ... ok
test_add_memory ... ok
test_get_conversations ... ok
test_search_memories ... ok
test_auto_classify_experience ... ok
test_auto_classify_preference ... ok
test_auto_classify_skill ... ok
test_extract_tags ... ok
test_search ... ok

Ran 9 tests in 0.061s
OK
```

## 📁 文件清单

```
src/local-memory-plugin/
├── .gitignore
├── README.md                    # 插件文档
├── db/
│   └── schema.py                # 数据库 Schema（~450 行）
├── test/
│   └── test_plugin.py           # 单元测试（~100 行）
├── index.js                     # OpenClaw 插件（~230 行）
├── openclaw.plugin.json         # 插件配置
├── package.json                 # Node.js 配置
└── search_engine.py             # 检索引擎（~220 行）
```

## 🔍 与 MemOS Cloud 的对比

| 特性 | MemOS Cloud | MemOS Exchange Local |
|------|-------------|----------------------|
| 存储 | 云端数据库 | 本地 SQLite |
| 检索 | HTTP API | 本地调用 |
| 认证 | API Key | 无需 |
| 网络依赖 | ❌ 需要 | ✅ 无需 |
| 语义搜索 | ✅ | ⏸️ 预留接口 |
| 数据主权 | 云端 | 完全本地 |

## 🚀 安装指南

```bash
# 1. 克隆/更新仓库
git pull origin main

# 2. 创建目录
mkdir -p ~/.openclaw/workspace/memos-exchange

# 3. 复制插件文件
cp -r src/local-memory-plugin/* ~/.openclaw/workspace/memos-exchange/

# 4. 测试检索引擎
python3 ~/.openclaw/workspace/memos-exchange/search_engine.py stats

# 5. 安装 OpenClaw 插件
mkdir -p ~/.openclaw/extensions/memos-exchange-local-memory
cp ~/.openclaw/workspace/memos-exchange/index.js ~/.openclaw/extensions/memos-exchange-local-memory/
cp ~/.openclaw/workspace/memos-exchange/openclaw.plugin.json ~/.openclaw/extensions/memos-exchange-local-memory/
cp ~/.openclaw/workspace/memos-exchange/package.json ~/.openclaw/extensions/memos-exchange-local-memory/

# 6. 在 ~/.openclaw/openclaw.json 中启用插件
# 7. 重启 OpenClaw Gateway
openclaw gateway restart
```

## 📝 配置示例

```json
{
  "plugins": {
    "entries": {
      "memos-exchange-local-memory": {
        "enabled": true,
        "config": {
          "memoryLimitNumber": 6,
          "minScore": 0.3,
          "includeAssistant": true,
          "userId": "default"
        }
      }
    }
  }
}
```

## 🔮 后续优化方向

1. **向量语义搜索** - 集成 Sentence Transformers 实现语义相似度搜索
2. **记忆去重** - 检测并合并重复记忆
3. **记忆巩固** - 根据访问频率自动提升重要记忆优先级
4. **导出备份** - 支持导出为 Markdown 格式
5. **多用户支持** - 完善用户隔离和权限管理

## ✅ 检查清单

- [x] 代码通过单元测试
- [x] 遵循现有代码风格
- [x] 添加必要的文档注释
- [x] 更新 README 文档
- [x] 无敏感信息泄露

---

**关联 Issue**: N/A（新功能）
**破坏性变更**: 无

# MemOS Exchange - 本地记忆插件

🔌 **完全本地化的 OpenClaw 记忆存储和检索插件**

---

## 📋 项目概述

MemOS Exchange 本地记忆插件是一个参考 MemOS Cloud 插件工作流程实现的本地化方案，提供：

- ✅ **对话前自动注入记忆** - 根据当前对话内容，智能检索相关记忆并注入上下文
- ✅ **对话后自动保存记忆** - 自动提取对话中的关键信息并保存到本地数据库
- ✅ **完全本地存储** - 使用 SQLite 数据库，无需网络依赖
- ✅ **全文搜索** - 基于 SQLite FTS5 的关键词检索和相关性评分
- ✅ **记忆分类** - 自动区分事实、偏好、技能、经验等记忆类型

---

## 🚀 快速开始

### 环境要求

- Python 3.7+
- Node.js 14+
- OpenClaw 2026.3.2+

### 安装步骤

#### 1. 安装检索引擎

```bash
# 创建目录
mkdir -p ~/.openclaw/workspace/memos-exchange

# 复制文件
cp -r src/local-memory-plugin/* ~/.openclaw/workspace/memos-exchange/

# 验证安装
python3 ~/.openclaw/workspace/memos-exchange/search_engine.py stats
```

#### 2. 安装 OpenClaw 插件

```bash
# 创建插件目录
mkdir -p ~/.openclaw/extensions/memos-exchange-local-memory

# 复制插件文件
cp ~/.openclaw/workspace/memos-exchange/index.js ~/.openclaw/extensions/memos-exchange-local-memory/
cp ~/.openclaw/workspace/memos-exchange/openclaw.plugin.json ~/.openclaw/extensions/memos-exchange-local-memory/
cp ~/.openclaw/workspace/memos-exchange/package.json ~/.openclaw/extensions/memos-exchange-local-memory/

# 在 OpenClaw 配置中启用插件
# 编辑 ~/.openclaw/openclaw.json，添加：
{
  "plugins": {
    "entries": {
      "memos-exchange-local-memory": {
        "enabled": true,
        "config": {
          "memoryLimitNumber": 6,
          "minScore": 0.3,
          "includeAssistant": true
        }
      }
    }
  }
}

# 重启 OpenClaw Gateway
openclaw gateway restart
```

---

## 📖 使用说明

### 检索引擎命令

#### 基本搜索

```bash
# 搜索关键词
python3 search_engine.py search "Python"

# 限制结果数量
python3 search_engine.py search "Flask" --limit 10

# JSON 输出（方便脚本集成）
python3 search_engine.py search "OpenClaw" --json
```

#### 高级搜索

```bash
# 按类型过滤 (preference/skill/experience/fact)
python3 search_engine.py search "技能" --type skill

# 标签过滤
python3 search_engine.py search "技术" --tags python flask

# 组合搜索
python3 search_engine.py search "Python 开发" --limit 5 --min-score 0.2 --json
```

#### 手动添加记忆

```bash
python3 search_engine.py add "用户喜欢用 PyCharm" --type preference --tags python 编辑器
```

#### 查看统计

```bash
python3 search_engine.py stats
```

输出示例：
```
📊 记忆系统统计
   对话记录：50 条
   总记忆数：120 条
   记忆分类:
      - preference: 45 条
      - skill: 30 条
      - experience: 35 条
      - fact: 10 条
   活跃会话：5 个
   数据库大小：2.50 MB
```

---

## 📁 目录结构

```
src/local-memory-plugin/
├── db/
│   └── schema.py              # 数据库 Schema 和管理器
├── test/
│   └── test_plugin.py         # 单元测试
├── index.js                   # OpenClaw 插件主程序
├── openclaw.plugin.json       # OpenClaw 插件配置
├── package.json               # Node.js 包配置
├── search_engine.py           # 记忆检索引擎
└── README.md                  # 本文档
```

---

## 🔧 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enabled` | 是否启用插件 | `true` |
| `memoryLimitNumber` | 注入记忆数量上限 | `6` |
| `minScore` | 最低相关性分数阈值 | `0.3` |
| `includeAssistant` | 是否保存助手回复 | `true` |
| `maxMessageChars` | 消息最大字符数 | `5000` |
| `userId` | 用户 ID | `default` |
| `pythonPath` | Python 解释器路径 | `python3` |

---

## 🧪 测试

### 运行单元测试

```bash
cd src/local-memory-plugin
python3 -m pytest test/test_plugin.py -v
```

### 集成测试

```bash
# 测试检索功能
python3 search_engine.py search "测试" --limit 3

# 测试 JSON 输出
python3 search_engine.py search "测试" --json | python3 -m json.tool
```

---

## 📊 数据库 Schema

### 核心表

| 表名 | 说明 |
|------|------|
| `conversations` | 对话记录表 |
| `memories` | 记忆表 |
| `sessions` | 会话元数据表 |
| `embeddings` | 向量嵌入表（预留） |
| `memories_fts` | 全文搜索虚拟表（FTS5） |

详见 `db/schema.py`。

---

## 🔒 安全说明

- ✅ 所有数据存储在本地，无需网络
- ✅ 数据库文件权限建议设为 `chmod 600`
- ✅ 定期备份数据库文件

---

## 🤝 与 MemOS Cloud 的区别

| 特性 | MemOS Cloud | MemOS Exchange Local |
|------|-------------|----------------------|
| 存储 | 云端数据库 | 本地 SQLite |
| 检索 | HTTP API | 本地函数调用 |
| 认证 | API Key | 无需认证 |
| 语义搜索 | ✅ 支持 | ⏸️ 预留接口 |
| 网络依赖 | ❌ 需要 | ✅ 无需 |
| 数据主权 | 云端 | 完全本地 |

---

## 📝 更新日志

### v0.1.0 (2026-03-31)

- ✅ 初始版本
- ✅ SQLite 数据库实现
- ✅ 全文搜索（FTS5）
- ✅ OpenClaw 插件集成
- ✅ 自动记忆分类

---

## 📄 License

MIT License

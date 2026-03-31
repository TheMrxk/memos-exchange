# MemOS Exchange - 本地记忆管理系统

🧠 **完全本地化的 AI 记忆管理方案** - 为 OpenClaw 提供长期记忆能力

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/TheMrxk/memos-exchange)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📋 项目概述

MemOS Exchange 是一个完全本地化的记忆管理系统，参考 [MemOS](https://github.com/MemTensor/MemOS) 设计，为 OpenClaw AI 助手提供：

- ✅ **长期记忆** - 存储和检索历史对话
- ✅ **智能检索** - 关键词全文搜索，相关性评分
- ✅ **Web 管理界面** - 可视化查看和管理记忆
- ✅ **完全本地** - 数据存储在本地 SQLite，无需云端依赖
- ✅ **OpenClaw 集成** - 自动保存对话，自动注入记忆

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│  ┌─────────────────┐         ┌─────────────────────────────────┐│
│  │  OpenClaw       │         │  Web 管理界面                     ││
│  │  (Telegram/     │         │  (Vue 3 + Element Plus)          ││
│  │   QQ/微信等)     │         │  http://localhost:8080           ││
│  └────────┬────────┘         └──────────────┬──────────────────┘│
│           │                                  │                   │
└───────────┼──────────────────────────────────┼───────────────────┘
            │                                  │
┌───────────▼──────────────────────────────────▼───────────────────┐
│                       OpenClaw Gateway                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  local-memory-plugin (Node.js)                               │ │
│  │  - before_agent_start: 检索记忆并注入上下文                   │ │
│  │  - agent_end: 保存对话到数据库                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                    数据存储层                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  memos-exchange.db (SQLite)                                 │ │
│  │  - conversations 表：原始对话记录                             │ │
│  │  - memories 表：提取的记忆                                    │ │
│  │  - sessions 表：会话元数据                                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 三个核心组件的关系

| 组件 | 作用 | 与其他组件的关系 |
|------|------|-----------------|
| **OpenClaw** | AI 助手网关 | 通过插件调用数据库，实现记忆的自动保存和检索 |
| **本地记忆插件** | OpenClaw 插件 | 监听对话事件，读写 SQLite 数据库 |
| **Web 管理界面** | 用户管理界面 | 直接读取数据库，可视化展示和编辑记忆 |

### 实时同步原理

```
┌─────────────────────────────────────────────────────────────────┐
│                    数据流向示意图                                 │
│                                                                  │
│  用户对话 → OpenClaw → local-memory-plugin → SQLite 数据库        │
│                                              ↑                   │
│  用户浏览 ← Web 管理界面 ←─────────────────────┘                   │
│                                                                  │
│  【说明】                                                         │
│  1. OpenClaw 收到用户消息后，插件自动保存对话到 SQLite              │
│  2. Web 管理界面实时读取 SQLite 数据库，显示最新数据                 │
│  3. 用户在 Web 界面添加/编辑/删除记忆，直接修改 SQLite              │
│  4. OpenClaw 下次检索时，能立即看到 Web 界面的修改                   │
│                                                                  │
│  【关键】三个组件共享同一个 SQLite 数据库文件，实现数据同步          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

#### 1. 克隆项目

```bash
git clone https://github.com/TheMrxk/memos-exchange.git
cd memos-exchange
```

#### 2. 修改配置

编辑 `docker-compose.yml`，修改数据库路径为你的实际路径：

```yaml
volumes:
  - /你的路径/.openclaw/workspace/memos-exchange.db:/app/data/memos-exchange.db
```

#### 3. 启动服务

```bash
docker-compose up -d
```

#### 4. 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| Web 管理界面 | http://localhost:8080 | 可视化管理记忆 |
| Backend API | http://localhost:5001 | REST API |
| Health Check | http://localhost:5001/health | 健康检查 |

#### 5. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看后端日志
docker-compose logs -f backend

# 查看前端日志
docker-compose logs -f frontend
```

#### 6. 停止服务

```bash
docker-compose down
```

---

### 方式二：本地部署（开发模式）

#### 环境要求

- Python 3.7+
- Node.js 14+
- OpenClaw 2026.3.2+

#### 1. 安装 Backend API

```bash
cd /home/hekai/memos-exchange/src/web-backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务（端口 5001）
python app.py
```

#### 2. 启动 Web 前端

```bash
cd /home/hekai/memos-exchange/src/web-frontend

# 使用 Python 简单 HTTP 服务器
python3 -m http.server 8080

# 或使用 Node.js
npx serve .
```

#### 3. 安装 OpenClaw 插件

```bash
# 复制插件到 OpenClaw 扩展目录
mkdir -p ~/.openclaw/extensions/local-memory-plugin
cp -r /home/hekai/memos-exchange/src/local-memory-plugin/* \
    ~/.openclaw/extensions/local-memory-plugin/

# 编辑 OpenClaw 配置，启用插件
# ~/.openclaw/openclaw.json
{
  "plugins": {
    "entries": {
      "local-memory-plugin": {
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

### Web 管理界面功能

#### 1. 仪表盘

- 📊 统计信息（对话数、记忆数、数据库大小）
- 📈 记忆分类统计
- 🔗 快速链接

#### 2. 记忆管理

- 🔍 搜索记忆（关键词、类型过滤）
- ➕ 添加记忆（手动创建）
- ✏️ 编辑记忆
- 🗑️ 删除记忆

#### 3. 对话记录

- 💬 查看所有历史对话
- 📅 按时间排序
- 🔎 按会话筛选

---

## 🔧 API 文档

### 端点列表

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/stats` | 获取统计信息 |
| GET | `/api/conversations` | 获取对话列表 |
| GET | `/api/conversations/:id` | 获取对话详情 |
| GET | `/api/memories` | 获取记忆列表 |
| GET | `/api/memories/search?q=` | 搜索记忆 |
| POST | `/api/memories` | 创建记忆 |
| PUT | `/api/memories/:id` | 更新记忆 |
| DELETE | `/api/memories/:id` | 删除记忆 |
| GET | `/api/sessions` | 获取会话列表 |

### 请求示例

```bash
# 获取统计信息
curl http://localhost:5001/api/stats

# 搜索记忆
curl "http://localhost:5001/api/memories/search?q=Python"

# 创建记忆
curl -X POST http://localhost:5001/api/memories \
  -H "Content-Type: application/json" \
  -d '{"content": "用户喜欢用 PyCharm", "memory_type": "preference", "tags": ["python", "编辑器"]}'

# 删除记忆
curl -X DELETE http://localhost:5001/api/memories/1
```

---

## 📁 项目结构

```
memos-exchange/
├── src/
│   ├── local-memory-plugin/     # OpenClaw 插件
│   │   ├── db/
│   │   │   └── schema.py        # 数据库 Schema
│   │   ├── test/
│   │   │   └── test_plugin.py   # 单元测试
│   │   ├── index.js             # 插件主程序
│   │   ├── search_engine.py     # 检索引擎
│   │   └── README.md
│   ├── web-backend/
│   │   ├── app.py               # Flask API
│   │   └── requirements.txt
│   └── web-frontend/
│       ├── index.html           # Vue 3 管理界面
│       ├── Dockerfile
│       └── nginx.conf
├── docker-compose.yml           # Docker 部署配置
├── Dockerfile.backend           # 后端 Docker 镜像
├── DEPLOY.md                    # 部署指南
└── README.md                    # 本文档
```

---

## 🔍 常见问题

### Q1: 数据存在哪里？

数据库文件位于 `~/.openclaw/workspace/memos-exchange.db`（SQLite 文件）。
Docker 部署时会挂载这个文件到容器内，数据不会丢失。

### Q2: OpenClaw 如何保存对话？

OpenClaw 的 `local-memory-plugin` 插件监听 `agent_end` 事件，自动提取最后一轮对话并保存到数据库。

### Q3: Web 界面如何实时更新？

Web 界面直接读取 SQLite 数据库。当 OpenClaw 保存新对话后，刷新 Web 页面即可看到最新数据。

### Q4: 可以多个助手共享记忆吗？

可以！所有对话都存储在同一个数据库中，通过 `session_id` 和 `agent_id` 区分。

### Q5: 数据会上传到云端吗？

不会！所有数据完全存储在本地，没有任何网络请求。

---

## 📊 开发计划

| 阶段 | 功能 | 状态 |
|------|------|------|
| 阶段 1 | 记忆检索引擎（SQLite + FTS5） | ✅ 完成 |
| 阶段 2 | OpenClaw 插件集成 | ✅ 完成 |
| 阶段 3 | Web Backend API | ✅ 完成 |
| 阶段 4 | Web 管理界面 | ✅ 完成 |
| 阶段 5 | Docker 部署 | ✅ 完成 |
| 阶段 6 | 语义搜索（向量数据库） | ⏸️ 待开发 |

---

## 📄 License

MIT License

---

**最后更新**: 2026-04-01  
**维护者**: TheMrxk + 何老师

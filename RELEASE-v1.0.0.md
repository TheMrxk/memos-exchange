# Memory Exchange 1.0.0 发布说明

## 📦 发布信息

- **版本**: v1.0.0
- **发布日期**: 2026-04-01
- **类型**: 初始公开版本

## 🎯 项目简介

Memory Exchange 是一个为 OpenClaw 设计的本地记忆管理插件，支持：
- 对话记录自动保存
- 记忆存储和检索
- Web 管理界面
- 全文搜索功能

完全本地化部署，无需网络依赖，数据隐私可控。

## 🚀 快速开始

### 1. 安装 OpenClaw 插件

```bash
# 插件会自动安装到 ~/.openclaw/extensions/memory-exchange-plugin/
# 在 openclaw.json 中启用插件
```

### 2. Docker 部署 Web 界面

```bash
cd memory-exchange
docker compose up -d
```

访问：
- Web 界面：http://localhost:8080
- API 端点：http://localhost:5001

### 3. 配置插件

编辑 `~/.openclaw/openclaw.json`：

```json
{
  "plugins": {
    "entries": {
      "memory-exchange-plugin": {
        "enabled": true,
        "config": {
          "memoryLimitNumber": 6,
          "preferenceLimitNumber": 6,
          "minScore": 0.3,
          "includeAssistant": true,
          "maxMessageChars": 5000
        }
      }
    }
  }
}
```

## 📁 数据持久化

所有数据存储在：`~/.openclaw/workspace/memory-exchange.db/memory-exchange.db`

Docker 容器已配置卷挂载，重启容器数据不丢失。

## 🔌 插件功能

### 对话前 (`before_agent_start`)
- 检索与用户问题相关的记忆
- 自动注入到系统上下文
- 支持相关性评分和阈值过滤

### 对话后 (`agent_end`)
- 自动保存对话记录
- 生成记忆（当前版本保存原始内容）
- 支持 FTS5 索引更新

## 📊 Web 管理界面功能

| 功能模块 | 说明 |
|---------|------|
| 记忆管理 | 浏览、搜索、编辑、删除记忆 |
| 对话管理 | 查看历史对话记录 |
| 统计信息 | API 调用统计、数据库统计 |
| 连接状态 | OpenClaw 连接健康检查 |

## 🔧 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/memories` | GET | 获取记忆列表 |
| `/api/memories/search` | GET | 搜索记忆 |
| `/api/memories` | POST | 创建记忆 |
| `/api/memories/:id` | PUT | 更新记忆 |
| `/api/memories/:id` | DELETE | 删除记忆 |
| `/api/conversations` | GET | 获取对话列表 |
| `/api/stats` | GET | 获取统计信息 |
| `/health` | GET | 健康检查 |

## 📝 配置选项

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | boolean | `true` | 是否启用插件 |
| `memoryLimitNumber` | integer | `6` | 检索记忆数量上限 |
| `preferenceLimitNumber` | integer | `6` | 检索偏好数量上限 |
| `minScore` | number | `0.3` | 最低相关性分数 |
| `includeAssistant` | boolean | `true` | 是否保存助手回复 |
| `maxMessageChars` | integer | `5000` | 消息最大字符数 |

## 🐛 已知问题

1. **中文搜索限制**: FTS5 对中文分词支持有限，使用 LIKE 模糊匹配作为后备
2. **消息格式**: OpenClaw 系统注入的上下文可能导致原始消息格式复杂
3. **记忆生成**: 当前版本直接保存对话内容，未实现自动摘要

## 🔜 后续计划

- [ ] 对话内容自动摘要生成
- [ ] 改进系统上下文清理
- [ ] 向量嵌入语义搜索
- [ ] 多用户支持
- [ ] 记忆重要性评分

## 📄 许可证

MIT License

## 🙏 致谢

- OpenClaw 团队提供的插件 API
- Vue 3 和 Element Plus 社区
- Flask 和 SQLAlchemy 社区

---

**安装问题？** 请查看 [DEPLOY.md](./DEPLOY.md) 获取详细部署指南。

**使用问题？** 请查看 [README.md](./README.md) 获取完整文档。

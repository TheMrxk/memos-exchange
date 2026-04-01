# 更新日志 (CHANGELOG)

## [1.0.0] - 2026-04-01

### 新增功能

#### OpenClaw 插件
- **本地记忆存储与检索插件** (`memory-exchange-plugin`)
  - 对话前自动检索相关记忆并注入上下文
  - 对话后自动保存对话记录到 SQLite 数据库
  - 支持语义搜索（基于 SQLite FTS5 + LIKE 模糊匹配）
  - 支持记忆自动分类（事实/偏好/技能/经验）
  - 支持标签提取和管理

#### Web 管理界面
- **前端** (Vue 3 + Element Plus)
  - 记忆管理：浏览、搜索、编辑、删除记忆
  - 对话管理：查看历史对话记录
  - 统计仪表盘：
    - API 调用统计（调用次数、响应时间、错误率）
    - 数据库统计（对话总数、记忆总数、分类统计）
    - OpenClaw 连接状态实时监控
  - 自动刷新机制（30 秒健康检查，60 秒统计刷新）

- **后端 API** (Flask)
  - RESTful API 设计
  - 记忆 CRUD 操作
  - 对话记录管理
  - API 调用统计追踪
  - 全文搜索接口

#### Docker 部署
- `docker-compose.yml` 一键部署
- 数据持久化：数据库挂载到 `~/.openclaw/workspace/memory-exchange.db/`
- Nginx 反向代理 + 缓存控制
- 健康检查端点

### 技术特性

#### 数据库设计
- SQLite + FTS5 全文索引
- 支持 WAL 模式（并发写入）
- 表结构：
  - `conversations` - 对话记录
  - `memories` - 记忆存储
  - `sessions` - 会话元数据
  - `embeddings` - 向量嵌入（预留）
  - `api_stats` - API 调用统计

#### 搜索功能
- FTS5 全文搜索（支持英文）
- LIKE 模糊匹配（支持中文）
- 相关性评分和排序
- 记忆类型和标签过滤

#### 系统架构
- 插件热插拔设计（lifecycle 类型）
- 前后端分离架构
- 多数据源支持（预留）

### 配置选项

```json
{
  "enabled": true,
  "memoryLimitNumber": 6,
  "preferenceLimitNumber": 6,
  "minScore": 0.3,
  "includeAssistant": true,
  "maxMessageChars": 5000
}
```

### 文件结构

```
memory-exchange/
├── src/
│   ├── memory-exchange-plugin/   # OpenClaw 插件
│   │   ├── index.js              # 插件主程序
│   │   ├── search_engine.py      # 检索引擎
│   │   └── db/
│   │       └── schema.py         # 数据库管理
│   ├── web-backend/
│   │   └── app.py                # Flask API 后端
│   └── web-frontend/
│       ├── index.html            # Vue 3 前端
│       └── nginx.conf            # Nginx 配置
├── docker-compose.yml            # Docker 编排
├── Dockerfile.backend            # 后端容器构建
├── README.md                     # 项目文档
├── DEPLOY.md                     # 部署指南
└── CHANGELOG.md                  # 更新日志
```

### 已知限制

1. **中文搜索**：FTS5 对中文分词支持有限，使用 LIKE 模糊匹配作为后备
2. **用户消息提取**：OpenClaw 系统注入的上下文可能导致原始用户消息格式复杂化
3. **记忆生成**：当前版本直接保存对话内容，未实现自动摘要/总结功能

### 技术栈

- **前端**: Vue 3, Element Plus
- **后端**: Python 3, Flask, Flask-CORS
- **数据库**: SQLite 3, FTS5
- **容器**: Docker, Docker Compose, Nginx
- **插件**: Node.js, OpenClaw Plugin API

### 端口说明

- **5001**: Flask 后端 API
- **8080**: Nginx 前端服务
- **数据库**: `~/.openclaw/workspace/memory-exchange.db/memory-exchange.db`

---

## 开发计划 (TODO)

### v1.1.0
- [ ] 实现对话内容自动摘要生成记忆
- [ ] 改进系统上下文清理逻辑
- [ ] 添加用户消息来源追溯
- [ ] 支持多用户隔离

### v1.2.0
- [ ] 接入向量嵌入模型（语义搜索）
- [ ] 记忆重要性评分
- [ ] 自动标签建议
- [ ] 记忆去重和合并

### v2.0.0
- [ ] PostgreSQL 支持（可选）
- [ ] Redis 缓存层
- [ ] 记忆导出/导入功能
- [ ] 开放 API 认证

---

## 贡献者

- Hekai <[你的邮箱]>

## 许可证

MIT License

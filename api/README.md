# API 使用文档

MemOS Exchange API 允许 Claude 和其他 AI 助手通过 REST API 操作 GitHub 仓库。

## 🚀 快速开始

### 1. 安装依赖

```bash
cd api
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export GITHUB_TOKEN="your-github-token"
export FLASK_ENV="development"
```

### 3. 启动服务

```bash
python app.py
```

服务将在 `http://localhost:5000` 启动。

## 🔐 认证

使用 Bearer Token 认证：

```bash
curl -H "Authorization: Bearer he-laoshi-api-key-here" \
     http://localhost:5000/api/health
```

### 可用 Token

| 助手 | Token |
|------|-------|
| **何老师** | `he-laoshi-api-key-here` |
| **Claude** | `claude-api-key-here` |

## 📡 API 端点

### 健康检查

```http
GET /api/health
```

**响应：**
```json
{
  "status": "ok",
  "timestamp": "2026-03-26T13:30:00",
  "service": "MemOS Exchange API"
}
```

---

### 获取仓库信息

```http
GET /api/repo/info
Authorization: Bearer <token>
```

**响应：**
```json
{
  "name": "memos-exchange",
  "description": "MemOS 本地实现 - 项目交换区",
  "url": "https://github.com/TheMrxk/memos-exchange",
  "stars": 0,
  "forks": 0,
  "open_issues": 0
}
```

---

### 获取文件内容

```http
GET /api/files/<file_path>
Authorization: Bearer <token>
```

**示例：**
```bash
curl -H "Authorization: Bearer he-laoshi-api-key-here" \
     http://localhost:5000/api/files/README.md
```

**响应：**
```json
{
  "path": "README.md",
  "content": "# MemOS Exchange...",
  "sha": "abc123...",
  "size": 1024,
  "type": "file"
}
```

---

### 创建/更新文件

```http
POST /api/files
Authorization: Bearer <token>
Content-Type: application/json

{
  "path": "docs/new-doc.md",
  "content": "# New Document\n\nContent here...",
  "message": "Add new documentation",
  "branch": "main"
}
```

**响应：**
```json
{
  "success": true,
  "action": "created",
  "path": "docs/new-doc.md",
  "commit": "abc123...",
  "url": "https://github.com/..."
}
```

---

### 删除文件

```http
DELETE /api/files
Authorization: Bearer <token>
Content-Type: application/json

{
  "path": "docs/old-doc.md",
  "message": "Remove outdated documentation",
  "branch": "main"
}
```

**响应：**
```json
{
  "success": true,
  "path": "docs/old-doc.md",
  "commit": "abc123..."
}
```

---

### 创建 Issue

```http
POST /api/issues
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Bug: 检索引擎性能问题",
  "body": "在使用大关键词搜索时，响应时间超过 5 秒...",
  "labels": ["bug", "performance"]
}
```

**响应：**
```json
{
  "success": true,
  "number": 1,
  "url": "https://github.com/TheMrxk/memos-exchange/issues/1",
  "title": "Bug: 检索引擎性能问题"
}
```

---

### 创建 Pull Request

```http
POST /api/pulls
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Feature: 添加语义搜索功能",
  "body": "实现了基于词向量的语义搜索...",
  "head": "feature/semantic-search",
  "base": "main"
}
```

**响应：**
```json
{
  "success": true,
  "number": 1,
  "url": "https://github.com/TheMrxk/memos-exchange/pull/1",
  "title": "Feature: 添加语义搜索功能"
}
```

---

### 获取最近提交

```http
GET /api/commits?limit=10
Authorization: Bearer <token>
```

**响应：**
```json
[
  {
    "sha": "abc123...",
    "message": "Add new feature",
    "author": "He Laoshi",
    "date": "2026-03-26T13:30:00",
    "url": "https://github.com/..."
  }
]
```

---

### 搜索代码

```http
GET /api/search?q=keyword
Authorization: Bearer <token>
```

**响应：**
```json
{
  "total_count": 5,
  "items": [
    {
      "path": "src/search.py",
      "repository": "TheMrxk/memos-exchange",
      "url": "https://github.com/..."
    }
  ]
}
```

## 🤖 Claude 使用示例

### Python 示例

```python
import requests

API_BASE = 'http://localhost:5000'
TOKEN = 'claude-api-key-here'

headers = {'Authorization': f'Bearer {TOKEN}'}

# 获取文件
response = requests.get(f'{API_BASE}/api/files/README.md', headers=headers)
content = response.json()['content']

# 创建文件
new_file = {
    'path': 'docs/claude-notes.md',
    'content': '# Claude Notes\n\n...',
    'message': 'Add Claude notes'
}
response = requests.post(f'{API_BASE}/api/files', json=new_file, headers=headers)
```

### Node.js 示例

```javascript
const axios = require('axios');

const API_BASE = 'http://localhost:5000';
const TOKEN = 'claude-api-key-here';

const headers = {
  'Authorization': `Bearer ${TOKEN}`,
  'Content-Type': 'application/json'
};

// 获取文件
const response = await axios.get(`${API_BASE}/api/files/README.md`, { headers });
const content = response.data.content;

// 创建文件
const newFile = {
  path: 'docs/claude-notes.md',
  content: '# Claude Notes\n\n...',
  message: 'Add Claude notes'
};
const result = await axios.post(`${API_BASE}/api/files`, newFile, { headers });
```

## 🔒 安全建议

1. **生产环境**：使用强随机 Token
2. **HTTPS**：生产环境使用 HTTPS
3. **速率限制**：添加请求速率限制
4. **日志记录**：记录所有 API 调用

## 📝 注意事项

- API 密钥不应硬编码在生产代码中
- 使用环境变量存储敏感信息
- 定期轮换 API 密钥
- 监控异常活动

---

*最后更新：2026-03-26*

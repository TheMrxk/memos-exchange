# MemOS Exchange - Docker 部署

## 快速开始

### 1. 构建镜像

```bash
cd /home/hekai/memos-exchange
docker-compose build
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 访问 Web 界面

- **管理界面**: http://localhost:3000
- **API 文档**: http://localhost:3000/docs
- **健康检查**: http://localhost:3000/health

### 4. 查看日志

```bash
docker-compose logs -f
```

### 5. 停止服务

```bash
docker-compose down
```

---

## 数据持久化

数据库文件存储在宿主机：
```
~/.openclaw/workspace/memos-exchange.db
```

Docker 容器内路径：
```
/app/data/memos-exchange.db
```

即使删除容器，数据也不会丢失。

---

## 环境配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库路径 | `/app/data/memos-exchange.db` |
| `SECRET_KEY` | Flask 密钥 | (自动生成) |
| `PORT` | 服务端口 | `80` |

---

## API 端点

### 健康检查
```bash
curl http://localhost:3000/health
```

### 统计信息
```bash
curl http://localhost:3000/api/stats
```

### 获取对话列表
```bash
curl http://localhost:3000/api/conversations
```

### 获取记忆列表
```bash
curl http://localhost:3000/api/memories
```

### 搜索记忆
```bash
curl "http://localhost:3000/api/memories/search?q=Python"
```

### 删除记忆
```bash
curl -X DELETE http://localhost:3000/api/memories/1
```

---

## 故障排查

### 容器无法启动
```bash
docker-compose logs
```

### 数据库连接失败
检查挂载的数据库文件是否存在：
```bash
ls -la ~/.openclaw/workspace/memos-exchange.db
```

### 端口被占用
修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8080:80"  # 改为 8080
```

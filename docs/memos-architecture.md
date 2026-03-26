# MemOS 架构分析

## 核心设计理念

MemOS 是一个面向 LLM 和 AI Agent 的记忆操作系统，提供统一的记忆存储、检索和管理能力。

## 三层记忆模型

### 1. 应用层（Application Layer）
- OpenClaw 插件
- API 调用
- 用户界面

### 2. 记忆引擎层（Memory Engine）
- 记忆检索 `/search/memory`
- 记忆存储 `/add/message`
- 记忆管理 `/update/memory`

### 3. 记忆存储层（Memory Store）
- 向量数据库
- 记忆索引
- 记忆分类

## 记忆生命周期

1. **形成（Formation）**: 对话 → 提取 → 分类 → 存储
2. **激活（Activation）**: 新对话 → 检索 → 注入上下文
3. **巩固（Consolidation）**: 频繁访问 → 提升优先级
4. **更新（Update）**: 新信息覆盖旧信息，冲突检测

## 核心 API

### 记忆检索
```http
POST /api/openmem/v1/search/memory
{
  "user_id": "hekai",
  "query": "用户偏好",
  "relativity": 0.45,
  "memoryLimitNumber": 6,
  "preferenceLimitNumber": 6
}
```

### 记忆存储
```http
POST /api/openmem/v1/add/message
{
  "user_id": "hekai",
  "conversation_id": "session-123",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

## OpenClaw 插件工作流程

```
对话前 (beforeAgentStart):
  1. 构建检索查询
  2. 调用 MemOS API
  3. 注入到上下文

对话后 (afterAgentEnd):
  1. 提取最后一轮对话
  2. 异步发送到 MemOS
  3. 保存记忆
```

## 本地实现方案

### 优势
- ✅ 数据完全本地控制
- ✅ 无需网络依赖
- ✅ 可自定义扩展

### 挑战
- ⚠️ 语义搜索需要额外工具
- ⚠️ 多设备同步需手动
- ⚠️ 需要自行维护

---

*参考：MemOS 论文 https://arxiv.org/abs/2507.03724*

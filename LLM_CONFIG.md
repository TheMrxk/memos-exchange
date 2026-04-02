# LLM 记忆摘要配置指南

## 快速开始

### 1. 创建配置文件

复制示例配置文件到工作目录：

```bash
cp ~/.openclaw/extensions/memory-exchange-plugin/llm_config.example.json \
   ~/.openclaw/workspace/llm_config.json
```

### 2. 配置 API 密钥

编辑 `~/.openclaw/workspace/llm_config.json`：

```json
{
  "enabled": true,
  "provider": "anthropic",
  "api_key": "sk-xxxxx",
  "model": "claude-sonnet-4-20250514"
}
```

## 支持的服务商

### 阿里云百炼 Coding Plan（推荐）

```json
{
  "enabled": true,
  "provider": "dashscope_coding",
  "api_key": "sk-sp-xxxxx",
  "model": "qwen3.5-plus",
  "api_url": "https://coding.dashscope.aliyuncs.com/v1/chat/completions"
}
```

**支持模型**：qwen3.5-plus, qwen3-max-2026-01-23, glm-4.7, kimi-k2.5, MiniMax-M2.5

### 阿里云百炼 (DashScope 通用)

```json
{
  "enabled": true,
  "provider": "dashscope",
  "api_key": "你的 DashScope API Key",
  "model": "qwen3.5-plus"
}
```

**支持模型**：qwen3.5-plus, qwen3-max-2026-01-23, glm-4.7, kimi-k2.5 等

### Anthropic (Claude)

```json
{
  "enabled": true,
  "provider": "anthropic",
  "api_key": "你的 Claude API Key",
  "model": "claude-sonnet-4-20250514"
}
```

### OpenAI (GPT)

```json
{
  "enabled": true,
  "provider": "openai",
  "api_key": "sk-xxxxx",
  "model": "gpt-4o"
}
```

### DeepSeek

```json
{
  "enabled": true,
  "provider": "deepseek",
  "api_key": "你的 DeepSeek API Key",
  "model": "deepseek-chat"
}
```

### 自定义 API（兼容 OpenAI 格式）

```json
{
  "enabled": true,
  "provider": "custom",
  "api_key": "你的 API Key",
  "model": "your-model-name",
  "api_url": "https://your-api-domain.com/v1/chat/completions"
}
```

## 使用环境变量（可选）

也可以通过环境变量配置：

```bash
export LLM_SUMMARIZER_ENABLED=true
export LLM_PROVIDER=anthropic
export LLM_API_KEY=your-api-key
export LLM_MODEL=claude-sonnet-4-20250514
export LLM_API_URL=  # custom 提供商需要
```

## 测试配置

```bash
cd ~/.openclaw/extensions/memory-exchange-plugin
python3 llm_summarizer.py
```

## 降级策略

- 如果未配置 API 或 API 调用失败，自动降级使用规则引擎
- 规则引擎作为后备，确保功能始终可用

## 成本估算

按每次对话生成摘要约 100 tokens 计算：

- Claude Haiku: ~$0.00025/次
- GPT-3.5: ~$0.0004/次
- DeepSeek: ~$0.00007/次

每天 100 次对话约：
- Claude Haiku: $0.025/天
- GPT-3.5: $0.04/天
- DeepSeek: $0.007/天

## 故障排除

### 日志查看

```bash
tail -f ~/.openclaw/workspace/memory-exchange-plugin.log
```

### 常见错误

1. **API Key 无效**: 检查配置文件中 `api_key` 是否正确
2. **网络连接失败**: 检查是否能访问 API 服务
3. **模型不存在**: 检查 `model` 参数是否拼写正确

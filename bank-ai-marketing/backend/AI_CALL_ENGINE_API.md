# Bank AI Call Engine API 文档

**版本**: 1.0.0  
**日期**: 2026-04-05

---

## 概述

Bank AI Call Engine 是一个独立的 AI 通话引擎服务，不依赖 FreeSWITCH。提供 HTTP API 接口，支持：

- 创建/管理通话会话
- 推送音频流进行实时识别
- ASR → LLM → TTS 完整对话链路
- 独立 TTS 合成接口

---

## 快速开始

### 1. 启动服务

```bash
cd /home/hekai/memory-exchange/bank-ai-marketing/backend

# 使用虚拟环境
source venv/bin/activate

# 启动服务（默认端口 5001）
python3 ai_call_engine_service.py --port 5001

# 或者指定 LLM Key
python3 ai_call_engine_service.py --port 5001 --llm-key sk_your_deepseek_key
```

### 2. 测试健康检查

```bash
curl http://localhost:5001/api/health
```

---

## API 接口

### 健康检查

```http
GET /api/health
```

**响应**:
```json
{
  "status": "ok",
  "timestamp": 1712345678.901234
}
```

---

### 创建会话

```http
POST /api/session/create
Content-Type: application/json
```

**请求体**:
```json
{
  "session_id": "optional_custom_id",
  "config": {
    "max_duration": 300,
    "max_turns": 10,
    "silence_timeout": 10.0,
    "vad_mode": "aggressive",
    "sample_rate": 16000
  },
  "script": {
    "greeting": "您好，欢迎使用银行 AI 客服服务。",
    "closing": "感谢您的接听，祝您生活愉快，再见！",
    "system_prompt": "你是一个专业的银行客服代表..."
  }
}
```

**响应**:
```json
{
  "success": true,
  "session_id": "abc123-def456"
}
```

---

### 启动会话

```http
POST /api/session/{session_id}/start
```

**说明**: 启动会话后，引擎开始：
1. 播放问候语（通过回调通知）
2. 进入监听状态
3. 等待音频输入

**响应**:
```json
{
  "success": true
}
```

---

### 推送音频数据

```http
POST /api/session/{session_id}/audio
Content-Type: application/octet-stream
```

**请求体**: 原始 PCM 音频数据（16kHz 16bit 单声道）

或者使用 Base64 编码：

```http
POST /api/session/{session_id}/audio
Content-Type: application/json
```

```json
{
  "audio": "Base64 编码的 PCM 数据"
}
```

**音频格式要求**:
- 采样率：16000Hz
- 位深：16bit
- 声道：单声道
- 编码：PCM（无头）
- 推荐帧大小：640 字节（20ms）或 960 字节（30ms）

**响应**:
```json
{
  "success": true
}
```

---

### 获取会话信息

```http
GET /api/session/{session_id}/info
```

**响应**:
```json
{
  "success": true,
  "data": {
    "session_id": "abc123",
    "state": "listening",
    "turn_count": 3,
    "created_at": 1712345600.0,
    "started_at": 1712345601.0,
    "duration": 45.5,
    "turns": [
      {
        "turn_id": 1,
        "role": "user",
        "text": "你好，我想了解一下贷款产品。",
        "timestamp": 1712345610.0
      },
      {
        "turn_id": 1,
        "role": "assistant",
        "text": "您好！我行提供多种贷款产品...",
        "timestamp": 1712345615.0
      }
    ]
  }
}
```

**状态说明**:
- `idle`: 空闲
- `initialized`: 已初始化
- `greeting`: 播放问候语
- `listening`: 监听中
- `speaking`: 说话中
- `processing`: 处理中
- `ended`: 已结束

---

### 结束会话

```http
POST /api/session/{session_id}/end
```

**响应**:
```json
{
  "success": true
}
```

---

### TTS 合成（独立接口）

```http
POST /api/tts/synthesize
Content-Type: application/json
```

**请求体**:
```json
{
  "text": "您好，欢迎使用银行 AI 客服服务。"
}
```

**响应**: 音频数据（WAV 格式）

---

## 使用示例

### Python 示例

```python
import requests
import numpy as np

# 1. 创建会话
resp = requests.post('http://localhost:5001/api/session/create', json={
    "script": {
        "greeting": "您好，请问有什么可以帮您？"
    }
})
session_id = resp.json()['session_id']
print(f"会话 ID: {session_id}")

# 2. 启动会话
requests.post(f'http://localhost:5001/api/session/{session_id}/start')

# 3. 推送音频（模拟 1 秒静音）
# 生成 16kHz 16bit 静音数据
silent_audio = bytes(16000 * 2)  # 1 秒静音
requests.post(
    f'http://localhost:5001/api/session/{session_id}/audio',
    data=silent_audio,
    headers={'Content-Type': 'application/octet-stream'}
)

# 4. 查看会话状态
resp = requests.get(f'http://localhost:5001/api/session/{session_id}/info')
print(resp.json())

# 5. 结束会话
requests.post(f'http://localhost:5001/api/session/{session_id}/end')
```

### 使用真实音频文件

```python
import wave
import requests

# 读取 WAV 文件
with wave.open('test.wav', 'rb') as wav:
    audio_data = wav.readframes(wav.getnframes())

# 创建会话并推送
resp = requests.post('http://localhost:5001/api/session/create')
session_id = resp.json()['session_id']

requests.post(f'http://localhost:5001/api/session/{session_id}/start')

# 分帧推送（每帧 20ms）
frame_size = 16000 * 2 * 20 // 1000  # 640 字节
for i in range(0, len(audio_data), frame_size):
    frame = audio_data[i:i+frame_size]
    if len(frame) == frame_size:
        requests.post(
            f'http://localhost:5001/api/session/{session_id}/audio',
            data=frame
        )
        # 模拟实时推送延迟
        import time
        time.sleep(0.02)
```

---

## 配置说明

### CallConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_duration` | int | 300 | 最大通话时长（秒） |
| `max_turns` | int | 10 | 最大对话轮数 |
| `silence_timeout` | float | 10.0 | 静音超时时间（秒） |
| `vad_mode` | str | "aggressive" | VAD 模式 |
| `vad_speech_threshold` | int | 3 | 语音判定帧数 |
| `vad_silence_threshold` | int | 5 | 静音判定帧数 |
| `sample_rate` | int | 16000 | 音频采样率 |
| `frame_duration_ms` | int | 20 | 帧时长（毫秒） |
| `asr_ws_url` | str | (见下文) | ASR WebSocket 地址 |

### ScriptConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `greeting` | str | "您好..." | 问候语 |
| `closing` | str | "感谢..." | 结束语 |
| `system_prompt` | str | "你是..." | LLM 系统提示 |
| `timeout_prompt` | str | "请问您还在听吗？" | 超时提示 |
| `error_prompt` | str | "抱歉..." | 错误提示 |

---

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `LLM_API_KEY` | DeepSeek API Key |
| `LLM_PROVIDER` | LLM 提供商（deepseek/dashscope） |
| `DOUBAO_APPID` | 豆包 APPID（默认 2058216235） |
| `DOUBAO_ACCESS_TOKEN` | 豆包 Access Token |

---

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 会话不存在 |
| 500 | 服务器内部错误 |

---

## 性能指标

| 指标 | 目标值 |
|------|--------|
| 首包延迟 | <500ms |
| ASR 识别延迟 | 300-800ms |
| LLM 响应延迟 | 500-2000ms |
| TTS 合成延迟 | 200-500ms |

---

## 注意事项

1. **音频格式**: 必须是 16kHz 16bit 单声道 PCM
2. **推送频率**: 建议按 20ms/帧 推送，避免队列堆积
3. **会话超时**: 超过 `silence_timeout` 无音频输入会超时
4. **并发限制**: 单实例建议不超过 10 个并发会话

---

## 集成到 FreeSWITCH

FreeSWITCH 模块可以通过以下方式集成：

1. **HTTP 模式**: FreeSWITCH 模块通过 HTTP POST 推送 RTP 转储的音频
2. **嵌入式**: 将 AICallEngine 作为库直接嵌入到 FreeSWITCH 模块中

```python
# FreeSWITCH 模块伪代码
from ai_call_engine_service import AICallEngine

engine = AICallEngine()

def on_rtp_audio(call_uuid, audio_data):
    # RTP G.711 转 PCM 16kHz
    pcm = g711_to_pcm(audio_data)
    engine.push_audio(call_uuid, pcm)
```

---

**最后更新**: 2026-04-05

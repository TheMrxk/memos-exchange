# 项目开发进度报告

**更新日期**: 2026-04-05  
**项目**: Bank AI Marketing - 银行 AI 营销系统

---

## 一、今日完成 (2026-04-05)

### 1. 豆包 TTS 集成 ✅

**状态**: 已完成并测试通过

**技术细节**:
- **服务商**: 火山引擎豆包语音合成模型 2.0
- **Resource ID**: seed-tts-2.0
- **可用音色**: zh_female_vv_uranus_bigtts (vivi 2.0)
- **API 端点**: https://openspeech.bytedance.com/api/v3/tts/unidirectional

**认证方式**:
```
X-Api-App-Key: 2058216235
X-Api-Access-Key: HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W
X-Api-Resource-Id: seed-tts-2.0
```

**输出文件**:
- `services/doubao_tts.py` - 可复用 TTS 服务模块
- `services/tts_client.py` - 已更新 TTS 客户端
- `TTS_INTEGRATION.md` - TTS 集成文档

**测试结果**:
```bash
# 测试合成
python test_tts_final.py
# 输出：✓ 成功！音频已保存到：output_tts_final.mp3 (25.36 KB)
```

**关键发现**:
1. 必须使用 `X-Api-Access-Key` header（不是 `X-Api-Access-Token`）
2. 音色必须是实例绑定的 `zh_female_vv_uranus_bigtts`
3. V3 HTTP 单向流式 API 是最稳定的调用方式

### 2. 豆包 ASR 集成 ✅

**状态**: 已完成并测试通过

**技术细节**:
- **服务商**: 火山引擎豆包流式语音识别模型 2.0
- **实例**: Doubao_Seed_ASR_Streaming_2.02000000693482876194
- **Resource ID**: 
  - 小时版：`volc.seedasr.sauc.duration`
  - 并发版：`volc.seedasr.sauc.concurrent`
- **WebSocket 端点**:
  - 双向流式（推荐）: `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async`
  - 流式输入模式：`wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream`
  - 双向流式旧版：`wss://openspeech.bytedance.com/api/v3/sauc/bigmodel`

**认证方式**:
```
X-Api-App-Key: 2058216235
X-Api-Access-Key: HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W
X-Api-Resource-Id: volc.seedasr.sauc.duration
X-Api-Connect-Id: <UUID>
```

**输出文件**:
- `services/asr_client.py` - 已更新支持火山引擎 ASR
- `test_asr_volcengine.py` - ASR 测试脚本

**协议详情**:
- 二进制协议，4 字节 header
- 支持 Gzip 压缩
- Sequence 机制保证顺序
- 事件类型：
  - 0b0001: Full Client Request (首包配置)
  - 0b0010: Audio Only Request (音频流)
  - 0b1001: Full Server Response (识别结果)
  - 0b1111: Error Response

**测试结果**:
```bash
# 测试识别（16kHz PCM WAV）
python3 asr_websocket_client.py --file test_asr.wav
# 输出：[确定] 你好，欢迎使用银行 AI 客服服务。
```

**ASR 集成到 AI 通话引擎**:
- `ai_call_engine.py` 已集成 `AsrWsClient`
- `_listen_for_speech()` 方法使用真实 ASR 识别
- 支持临时结果和确定结果返回
- 音频格式：16kHz 16bit 单声道 PCM WAV

---

## 二、项目整体状态

### 核心模块进度

| 模块 | 状态 | 完成度 | 说明 |
|------|------|--------|------|
| **数据库模型** | ✅ 完成 | 100% | 9 个核心表已定义并可运行 |
| **Flask 后端 API** | ✅ 完成 | 90% | 基础 CRUD、认证、通话控制 API |
| **Vue3 前端** | ✅ 完成 | 80% | Web 管理界面 |
| **LLM 集成** | ✅ 完成 | 100% | DeepSeek/通义千问已支持 |
| **TTS 集成** | ✅ 完成 | 100% | 豆包语音合成模型 2.0 |
| **ASR 集成** | ✅ 完成 | 100% | 豆包流式语音识别模型 2.0 WebSocket 客户端已测试通过 |
| **FreeSWITCH 电话引擎** | ⏸️ 暂停 | 30% | 需要解决镜像模块问题 |
| **AI 对话引擎** | ✅ 完成 | 95% | ASR→LLM→TTS 完整链路已集成，待 RTP 流接入 | |

### 目录结构

```
bank-ai-marketing/
├── README.md                    # 项目说明
├── PROGRESS.md                  # 本文档
├── TTS_INTEGRATION.md           # TTS 集成文档
├── docker-compose.yml           # Docker 编排
├── backend/
│   ├── app.py                   # Flask 应用入口
│   ├── models.py                # 数据库模型
│   ├── routes_calls.py          # 通话控制 API
│   ├── asr_websocket_client.py  # ASR WebSocket 客户端（新增）
│   └── services/
│       ├── tts_client.py        # TTS 客户端
│       ├── doubao_tts.py        # 豆包 TTS 模块
│       ├── llm_client.py        # LLM 客户端
│       ├── asr_client.py        # ASR 客户端（HTTP 备用方案）
│       ├── ai_call_engine.py    # AI 通话引擎（已集成 ASR）
│       └── freeswitch_client.py # FreeSWITCH 客户端
├── web-frontend/                # Vue3 前端
└── test_*.py                    # 测试脚本集
```

---

## 三、AI 对话引擎架构

### 3.1 完整流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户电话呼入                              │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   FreeSWITCH│───▶│    ASR      │───▶│    LLM      │         │
│  │  (电话引擎)  │    │ (语音识别)   │    │ (DeepSeek)  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                            │                    │               │
│                            │                    ▼               │
│                            │           ┌─────────────┐          │
│                            │           │    TTS      │          │
│                            │           │  (豆包)     │          │
│                            │           └─────────────┘          │
│                            │                    │               │
│                            └────────────────────┘               │
│                                         │                       │
│                                         ▼                       │
│                              播放 AI 回复音频                       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
客户说话 (音频流)
    │
    ▼
ASR 服务 (FunASR / 火山引擎)
    │
    ▼
识别结果 (文本)
    │
    ▼
LLM 处理 (DeepSeek)
    │
    ▼
AI 回复 (文本)
    │
    ▼
TTS 服务 (豆包)
    │
    ▼
合成音频 (MP3/WAV)
    │
    ▼
播放给客户
```

---

## 四、待完成任务

### 4.1 ASR 集成 ✅ 已完成

**实现方式**: 火山引擎豆包流式语音识别模型 2.0 WebSocket API

**技术实现**:
```python
# asr_websocket_client.py
class AsrWsClient:
    async def recognize(self, file_path: str) -> AsyncGenerator[Dict, None]:
        """流式语音识别"""
        # 1. 加载音频文件（自动转换为 16kHz PCM）
        # 2. WebSocket 连接
        # 3. 发送 Full Client Request (配置)
        # 4. 发送 Audio Only Request (音频流，200ms/段)
        # 5. 接收 Full Server Response (识别结果)
```

**测试结果**:
```bash
python3 asr_websocket_client.py --file test_asr.wav
# 输出：[确定] 你好，欢迎使用银行 AI 客服服务。
```

**认证配置**:
```
X-Api-App-Key: 2058216235
X-Api-Access-Key: HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W
X-Api-Resource-Id: volc.seedasr.sauc.duration  # 小时版
WebSocket URL: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
```

### 4.2 AI 对话引擎完善 ✅ 已完成 95%

**当前状态**: 
- ASR 客户端已实现 WebSocket 协议 ✅
- TTS 客户端已完成 ✅
- LLM 客户端已完成 ✅
- `ai_call_engine.py` 已接入真实 ASR ✅

**已完成**:
1. ✅ 在 `ai_call_engine.py` 中调用 ASR 客户端
2. ✅ 实现临时 WAV 文件转换
3. ✅ 支持临时结果和确定结果返回
4. ⏸️ RTP 音频流接收（需要 FreeSWITCH 集成）
5. ⏸️ VAD 语音活动检测（待实现）

**完整数据流**:
```
客户说话 (音频流)
    ↓
FreeSWITCH (RTP 流)
    ↓
音频采集 (PCM 16kHz)
    ↓
ASR 服务 (火山引擎豆包 ASR WebSocket)
    ↓
识别结果 (文本)
    ↓
LLM 处理 (DeepSeek)
    ↓
AI 回复 (文本)
    ↓
TTS 服务 (豆包语音合成 2.0)
    ↓
合成音频 (MP3/WAV)
    ↓
播放给客户 (FreeSWITCH)
```

### 4.3 FreeSWITCH 模块 (优先级：中)

**问题**: mod_funasr 和 mod_aliyun_tts 需要预编译

**解决方案**:
1. 从 easycallcenter365 提取预编译模块
2. 或者使用 HTTP API 方式绕过模块依赖

---

## 五、下一步开发计划

### 阶段 1: ASR 集成 (预计 1-2 天)

- [ ] 选择 ASR 服务商
- [ ] 创建 `services/asr_client.py`
- [ ] 实现流式识别接口
- [ ] 测试识别准确率

### 阶段 2: AI 对话引擎完善 (预计 2-3 天)

- [ ] 实现 RTP 音频流接收
- [ ] 集成 ASR 到对话循环
- [ ] 实现 VAD 打断检测
- [ ] 优化响应延迟

### 阶段 3: 完整测试 (预计 1 天)

- [ ] 端到端通话测试
- [ ] 压力测试
- [ ] 日志和监控

### 阶段 4: FreeSWITCH 集成 (预计 2-3 天)

- [ ] 解决镜像模块问题
- [ ] 配置 NAT 和网络
- [ ] 真实电话线路测试

---

## 六、技术栈总结

| 组件 | 技术选型 | 状态 |
|------|----------|------|
| 后端框架 | Flask 3.0 | ✅ |
| 前端框架 | Vue 3 | ✅ |
| 数据库 | MySQL 8.0 | ✅ |
| LLM | DeepSeek / 通义千问 | ✅ |
| TTS | 豆包语音合成模型 2.0 | ✅ |
| ASR | 火山引擎豆包流式语音识别 2.0 | ✅ |
| 电话引擎 | FreeSWITCH | ⏸️ |
| 容器化 | Docker Compose | ✅ |

---

## 七、关键 API 文档

### 7.1 TTS API (已完成)

```bash
curl -X POST "https://openspeech.bytedance.com/api/v3/tts/unidirectional" \
  -H "X-Api-App-Key: 2058216235" \
  -H "X-Api-Access-Key: HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W" \
  -H "X-Api-Resource-Id: seed-tts-2.0" \
  -H "Content-Type: application/json" \
  -d '{
    "user": {"uid": "bank-ai"},
    "req_params": {
      "text": "您好，欢迎使用银行 AI 客服服务。",
      "speaker": "zh_female_vv_uranus_bigtts",
      "audio_params": {"format": "mp3", "sample_rate": 24000}
    }
  }'
```

### 7.2 ASR API (待实现)

```bash
# 火山引擎 ASR 流式识别 (预期格式)
curl -X POST "https://openspeech.bytedance.com/api/v3/asr/realtime" \
  -H "X-Api-App-Key: 2058216235" \
  -H "X-Api-Access-Key: XXX" \
  -H "X-Api-Resource-Id: seed-asr-2.0" \
  --data-binary @audio.pcm
```

### 7.3 LLM API (已实现)

```bash
curl -X POST "https://api.deepseek.com/chat/completions" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [
      {"role": "system", "content": "你是银行 AI 客服"},
      {"role": "user", "content": "你好"}
    ]
  }'
```

---

## 八、测试脚本清单

| 文件名 | 说明 | 状态 |
|--------|------|------|
| `test_tts_final.py` | TTS 完整测试 | ✅ 通过 |
| `test_tts_success.py` | TTS 成功示例 | ✅ 通过 |
| `test_all_creds.py` | 凭证组合测试 | ✅ 通过 |
| `test_speakers_match.py` | 音色匹配测试 | ✅ 通过 |
| `test_volc_sdk.py` | 火山 SDK 测试 | ⚠️ 待修复 |
| `test_asr_*.py` | ASR 测试 | ❌ 待创建 |

---

## 九、环境变量配置

### .env 文件模板

```bash
# LLM 配置
LLM_PROVIDER=dashscope_coding
LLM_API_KEY=your_deepseek_api_key

# TTS 配置 (豆包 - 火山引擎)
TTS_PROVIDER=doubao
DOUBAO_APPID=2058216235
DOUBAO_ACCESS_TOKEN=HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W
DOUBAO_RESOURCE_ID=seed-tts-2.0
DOUBAO_SPEAKER=zh_female_vv_uranus_bigtts

# ASR 配置 (火山引擎豆包)
ASR_PROVIDER=volcengine_doubao
DOUBAO_APPID=2058216235
DOUBAO_ACCESS_TOKEN=HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W
DOUBAO_ASR_RESOURCE_ID=volc.seedasr.sauc.duration
DOUBAO_ASR_WS_URL=wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async

# FreeSWITCH 配置
FREESWITCH_HOST=localhost
FREESWITCH_PORT=8021
FREESWITCH_PASSWORD=ClueCon

# 启用通话引擎
ENABLE_CALL_ENGINE=true
```

---

## 十、联系人和参考

### 参考文档
- [豆包语音合成模型 2.0 文档](https://www.volcengine.com/docs/6561/1598757)
- [火山引擎 ASR 文档](https://www.volcengine.com/docs/6561/79817)
- [DeepSeek API 文档](https://platform.deepseek.com/docs)

### 客服联系方式
- 火山引擎：952566

---

**最后更新**: 2026-04-05  
**下次更新**: ASR 集成完成后

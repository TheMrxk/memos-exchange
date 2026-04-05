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
| **ASR 集成** | ❌ 待开发 | 0% | 需要集成语音识别 |
| **FreeSWITCH 电话引擎** | ⏸️ 暂停 | 30% | 需要解决镜像模块问题 |
| **AI 对话引擎** | ⏸️ 待开发 | 40% | 等待 ASR 集成 |

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
│   └── services/
│       ├── tts_client.py        # TTS 客户端 (已更新)
│       ├── doubao_tts.py        # 豆包 TTS 模块 (新增)
│       ├── llm_client.py        # LLM 客户端
│       ├── asr_client.py        # ASR 客户端 (待完善)
│       ├── ai_call_engine.py    # AI 通话引擎
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

### 4.1 ASR 集成 (优先级：高)

**目标**: 将客户语音实时转换为文本

**可选方案**:

| 方案 | 服务商 | 优点 | 缺点 |
|------|--------|------|------|
| **方案 A** | FunASR 本地部署 | 免费、离线 | 需要部署服务器 |
| **方案 B** | 火山引擎 ASR | 与 TTS 同平台、稳定 | 按量收费 |
| **方案 C** | 阿里 FunASR 云 | 准确率高 | 需要单独配置 |

**推荐**: 方案 B (火山引擎 ASR)，原因：
1. 与豆包 TTS 同一平台，认证统一
2. 流式识别，延迟低
3. 支持实时打断

**需要实现**:
```python
# services/asr_client.py
class VolcengineASR:
    def recognize_stream(self, audio_chunk) -> str:
        """流式语音识别"""
        pass
    
    def recognize_file(self, audio_file) -> str:
        """文件识别"""
        pass
```

### 4.2 AI 对话引擎完善 (优先级：高)

**当前状态**: `ai_call_engine.py` 中 `_listen_for_speech()` 方法返回模拟数据

**需要实现**:
1. 接收 FreeSWITCH RTP 音频流
2. 调用 ASR 实时识别
3. 流式处理（边说边识别）
4. VAD 语音活动检测（支持打断）

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
| ASR | 待选择 (推荐火山引擎) | ❌ |
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

# ASR 配置 (待配置)
ASR_PROVIDER=volcengine
ASR_ACCESS_TOKEN=XXX
ASR_RESOURCE_ID=seed-asr-2.0

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

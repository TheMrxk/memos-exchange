# 流式识别优化方案

**日期**: 2026-04-05  
**状态**: 架构设计完成

---

## 一、当前架构

### 1.1 数据流

```
FreeSWITCH (RTP G.711)
    ↓
音频流捕获 (RTPAudioStream)
    ↓
VAD 语音活动检测
    ↓
音频队列 (PCM 16kHz 16bit)
    ↓
ASR WebSocket 识别
    ↓
识别文本 → LLM → TTS
```

### 1.2 当前延迟分析

| 阶段 | 延迟 | 说明 |
|------|------|------|
| 音频捕获 | ~20ms | 20ms/帧 |
| VAD 检测 | ~100ms | 3 帧语音阈值 + 5 帧静音阈值 |
| ASR 识别 | 500-1000ms | 网络传输 + 服务端识别 |
| LLM 响应 | 500-2000ms | 取决于回复长度 |
| TTS 合成 | 200-500ms | 首包延迟 |

**总延迟**: 约 1.3-4.5 秒

---

## 二、优化方案

### 2.1 VAD 优化（已完成）

**当前状态**:
- ✅ WebRTC VAD 集成
- ✅ 可配置检测模式
- ✅ 语音段检测

**优化效果**:
- 静音检测：~150ms（5 帧×30ms）
- 语音触发：~90ms（3 帧×30ms）
- 最小语音时长：200ms

**进一步优化**:
- 降低静音阈值至 3 帧（90ms）- 风险：误触发
- 使用更短的帧时长（20ms）- 风险：CPU 增加

### 2.2 ASR 流式优化（已实现基础）

**当前实现**:
- ✅ WebSocket 双向流式协议
- ✅ 200ms 音频分段
- ✅ 实时识别结果返回

**优化方案**:

1. **提前触发识别**
   - 当前：等待 VAD 语音结束后识别
   - 优化：VAD 检测到语音开始后立即建立 ASR 连接
   - 预期收益：减少 200-300ms 连接延迟

2. **增量识别**
   - 当前：语音结束后发送整段音频
   - 优化：边说边发送，实时返回中间结果
   - 预期收益：减少 300-500ms 等待时间

3. **连接池**
   - 当前：每次识别新建 WebSocket 连接
   - 优化：保持 ASR 连接池，复用连接
   - 预期收益：减少 100-200ms 握手时间

### 2.3 音频流优化

**当前实现**:
- ✅ 音频队列缓冲
- ✅ PCM 格式转换

**优化方案**:

1. **RTP 直连处理**
   - 使用 FreeSWITCH mod_callcenter 模块
   - RTP 流转储到本地 UDP 端口
   - G.711 → PCM 实时转换

2. **环形缓冲区**
   - 避免队列满了丢弃数据
   - 保留最近 N 秒音频

### 2.4 LLM 响应优化

**优化方案**:

1. **流式响应**
   - 使用 LLM 的流式 API
   - 边生成边 TTS

2. **预加载 Prompt**
   - 通话开始时预热 LLM
   - 预先发送系统 Prompt

### 2.5 TTS 优化

**优化方案**:

1. **首包播放**
   - 收到第一个音频包即开始播放
   - 无需等待完整音频

2. **TTS 连接预热**
   - 通话开始时建立 TTS 连接池

---

## 三、实现优先级

### 阶段 1: 基础流式识别（已完成 ✅）

- [x] VAD 语音活动检测
- [x] ASR WebSocket 客户端
- [x] 音频流捕获模块
- [x] AI 通话引擎集成

### 阶段 2: 流式识别优化（进行中 🔄）

- [ ] ASR 增量识别（边说边发）
- [ ] VAD 参数优化
- [ ] 连接池实现

### 阶段 3: 端到端优化（待完成 ⏸️）

- [ ] FreeSWITCH RTP 直连
- [ ] LLM 流式响应
- [ ] TTS 首包播放

---

## 四、性能指标

### 目标延迟

| 指标 | 当前 | 目标 |
|------|------|------|
| VAD 触发 | ~150ms | <100ms |
| ASR 首字 | ~500ms | <300ms |
| 端到端延迟 | ~2000ms | <800ms |

### 资源使用

| 指标 | 目标 |
|------|------|
| CPU 单通话 | <5% |
| 内存单通话 | <50MB |
| 网络带宽 | <64kbps/通话 |

---

## 五、代码示例

### 5.1 增量 ASR 识别

```python
async def incremental_asr(audio_stream, vad):
    """增量 ASR 识别"""
    async with AsrWsClient() as client:
        # 发送首包配置
        await client.send_full_request()

        async for frame in audio_stream:
            state = vad.process_frame(frame)

            if state == VADState.SPEECH_START:
                logger.info("语音开始，准备识别")

            if state in [VADState.SPEECH, VADState.SPEECH_START]:
                # 边说边发
                await client.send_audio_frame(frame)

                # 实时接收中间结果
                async for response in client.receive_responses():
                    if response.get('payload'):
                        text = response['payload']['result']['text']
                        logger.info(f"中间结果：{text}")

            if state == VADState.SPEECH_END:
                # 发送结束标志
                await client.send_last_audio_frame()
                break
```

### 5.2 连接池实现

```python
class ASRConnectionPool:
    """ASR 连接池"""

    def __init__(self, pool_size: int = 5):
        self.pool_size = pool_size
        self.connections = []
        self.available = asyncio.Queue()

    async def initialize(self):
        """初始化连接池"""
        for i in range(self.pool_size):
            client = AsrWsClient()
            await client.create_connection()
            self.connections.append(client)
            await self.available.put(client)

    async def acquire(self) -> AsrWsClient:
        """获取可用连接"""
        return await self.available.get()

    async def release(self, client: AsrWsClient):
        """释放连接回池"""
        await self.available.put(client)
```

---

## 六、测试方法

### 6.1 延迟测试

```bash
# VAD 延迟测试
python3 test_vad_latency.py

# ASR 延迟测试
python3 test_asr_latency.py

# 端到端延迟测试
python3 test_e2e_latency.py
```

### 6.2 压力测试

```bash
# 10 路并发测试
python3 test_concurrent_calls.py --count 10

# 长时间稳定性测试
python3 test_stability.py --duration 3600
```

---

## 七、参考文档

- [WebRTC VAD 文档](https://github.com/wiseman/py-webrtcvad)
- [火山引擎 ASR 文档](https://www.volcengine.com/docs/6561/79817)
- [FreeSWITCH ESL 文档](https://freeswitch.org/confluence/display/FREESWITCH/mod_event_socket)

---

**最后更新**: 2026-04-05  
**下次更新**: 增量识别实现完成后

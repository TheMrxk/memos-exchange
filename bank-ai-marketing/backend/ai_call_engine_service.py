#!/usr/bin/env python3
"""
Bank AI Call Engine - 独立 AI 通话引擎服务

不依赖 FreeSWITCH，提供纯 API 接口：
- HTTP API: 发起对话、推送音频、获取结果
- WebSocket: 双向音频流实时对话

可以独立部署，也可以嵌入到 FreeSWITCH 模块中
"""

import os
import sys
import json
import time
import logging
import threading
import queue
import asyncio
import tempfile
import wave
import uuid
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from flask import Flask, Blueprint, request, jsonify, Response

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.doubao_tts import DoubaoTTS
from services.llm_client import LLMClient, init_llm_client, get_llm_client
from services.audio_stream import AudioConfig
from services.vad_detector import VoiceActivityDetector, VADConfig, VADMode, VADState

# 导入 ASR
from asr_websocket_client import AsrWsClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 枚举和数据类 ====================

class SessionState(Enum):
    """会话状态"""
    IDLE = "idle"              # 空闲
    INITIALIZED = "initialized"  # 已初始化
    GREETING = "greeting"      # 播放问候语
    LISTENING = "listening"    # 监听中
    SPEAKING = "speaking"      # 说话中
    PROCESSING = "processing"  # 处理中
    ENDED = "ended"            # 已结束


@dataclass
class CallConfig:
    """通话配置"""
    max_duration: int = 300  # 最大通话时长（秒）
    max_turns: int = 10      # 最大对话轮数
    silence_timeout: float = 10.0  # 静音超时（秒）

    # VAD 配置
    vad_mode: str = "aggressive"
    vad_speech_threshold: int = 3
    vad_silence_threshold: int = 5
    vad_min_speech_duration_ms: int = 200

    # 音频配置
    sample_rate: int = 16000
    frame_duration_ms: int = 20

    # ASR 配置
    asr_ws_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"

    # TTS 配置
    tts_format: str = "wav"
    tts_sample_rate: int = 16000

    def to_vad_config(self) -> VADConfig:
        """转换为 VAD 配置"""
        mode_map = {
            "normal": VADMode.NORMAL,
            "low_bitrate": VADMode.LOW_BITRATE,
            "aggressive": VADMode.AGGRESSIVE,
            "very_aggressive": VADMode.VERY_AGGRESSIVE
        }
        return VADConfig(
            mode=mode_map.get(self.vad_mode, VADMode.AGGRESSIVE),
            sample_rate=self.sample_rate,
            frame_duration_ms=self.frame_duration_ms,
            speech_threshold=self.vad_speech_threshold,
            silence_threshold=self.vad_silence_threshold,
            min_speech_duration_ms=self.vad_min_speech_duration_ms,
            max_silence_duration_ms=3000
        )


@dataclass
class ScriptConfig:
    """脚本配置"""
    greeting: str = "您好，欢迎使用银行 AI 客服服务。"
    closing: str = "感谢您的接听，祝您生活愉快，再见！"
    system_prompt: str = "你是一个专业的银行客服代表，请友好、简洁地回答客户的问题。你所在的银行提供存款、贷款、信用卡、理财等服务。"
    timeout_prompt: str = "请问您还在听吗？"
    error_prompt: str = "抱歉，我没有听清楚，能请您再说一遍吗？"


@dataclass
class ConversationTurn:
    """对话轮次"""
    turn_id: int
    role: str  # "user" or "assistant"
    text: str
    audio_url: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CallSession:
    """通话会话"""
    session_id: str
    config: CallConfig
    script: ScriptConfig
    state: SessionState = SessionState.IDLE

    # 对话历史
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    turns: List[ConversationTurn] = field(default_factory=list)
    turn_count: int = 0

    # 音频队列（用于接收外部推送的音频）
    audio_queue: queue.Queue = field(default_factory=queue.Queue)

    # 时间
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    ended_at: Optional[float] = None

    # 控制
    stop_flag: threading.Event = field(default_factory=threading.Event)
    current_thread: Optional[threading.Thread] = None

    # LLM 消息历史
    llm_messages: List[Dict[str, str]] = field(default_factory=list)


# ==================== AI 通话引擎核心 ====================

class AICallEngine:
    """
    AI 通话引擎核心类

    提供：
    1. 会话管理
    2. 对话循环（ASR → LLM → TTS）
    3. 音频流处理
    4. HTTP API
    """

    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        llm_provider: str = "deepseek",
        tts_app_id: str = "2058216235",
        tts_access_token: str = "HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W"
    ):
        self.config = CallConfig()

        # 初始化客户端
        self.llm_client = self._init_llm(llm_api_key, llm_provider)
        self.tts_client = DoubaoTTS(
            app_id=tts_app_id,
            access_token=tts_access_token,
            format=self.config.tts_format,
            sample_rate=self.config.tts_sample_rate
        )

        # 会话存储
        self.sessions: Dict[str, CallSession] = {}
        self._lock = threading.Lock()

        logger.info("AI 通话引擎初始化完成")

    def _init_llm(self, api_key: Optional[str], provider: str) -> LLMClient:
        """初始化 LLM 客户端"""
        if api_key:
            return init_llm_client(provider, api_key)
        else:
            # 尝试从环境变量获取
            env_key = os.environ.get("LLM_API_KEY")
            if env_key:
                return init_llm_client(provider, env_key)
            else:
                logger.warning("LLM API Key 未配置，将使用占位符")
                return LLMClient(api_key="sk_placeholder", provider=provider)

    def create_session(
        self,
        session_id: Optional[str] = None,
        config: Optional[CallConfig] = None,
        script: Optional[ScriptConfig] = None
    ) -> str:
        """创建新的通话会话"""
        with self._lock:
            session_id = session_id or str(uuid.uuid4())

            if session_id in self.sessions:
                raise ValueError(f"会话已存在：{session_id}")

            session = CallSession(
                session_id=session_id,
                config=config or self.config,
                script=script or ScriptConfig()
            )

            # 初始化 LLM 消息历史
            session.llm_messages = [
                {"role": "system", "content": session.script.system_prompt}
            ]

            self.sessions[session_id] = session
            logger.info(f"创建会话：{session_id}")
            return session_id

    def start_session(self, session_id: str) -> bool:
        """启动会话（开始对话循环）"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在：{session_id}")

        if session.state != SessionState.IDLE:
            logger.warning(f"会话状态不正确：{session.state}")
            return False

        session.state = SessionState.INITIALIZED
        session.started_at = time.time()

        # 启动对话循环线程
        thread = threading.Thread(
            target=self._conversation_loop,
            args=(session,),
            daemon=True
        )
        thread.start()
        session.current_thread = thread

        logger.info(f"会话 {session_id} 已启动")
        return True

    def _conversation_loop(self, session: CallSession):
        """对话循环：问候 → 监听 → ASR → LLM → TTS"""
        config = session.config
        script = session.script

        try:
            # 1. 播放问候语
            session.state = SessionState.GREETING
            greeting_audio = self.tts_client.synthesize(script.greeting)
            if greeting_audio:
                self._on_tts_audio(session, greeting_audio, "greeting")

            # 2. 对话循环
            session.state = SessionState.LISTENING
            turn_count = 0

            while (not session.stop_flag.is_set() and
                   session.state != SessionState.ENDED and
                   turn_count < config.max_turns):

                # 检查超时
                if session.started_at and (time.time() - session.started_at) > config.max_duration:
                    logger.info("通话超时，结束")
                    break

                turn_count += 1
                session.turn_count = turn_count

                # 3. 监听客户说话
                customer_text = self._listen_for_speech(session)

                if not customer_text:
                    # 客户未说话，播放提示
                    timeout_audio = self.tts_client.synthesize(script.timeout_prompt)
                    if timeout_audio:
                        self._on_tts_audio(session, timeout_audio, "timeout")
                    continue

                logger.info(f"[第{turn_count}轮] 客户说：{customer_text}")
                session.turns.append(ConversationTurn(
                    turn_id=turn_count,
                    role="user",
                    text=customer_text
                ))
                session.llm_messages.append({"role": "user", "content": customer_text})

                # 4. LLM 生成回复
                session.state = SessionState.PROCESSING
                assistant_text = self._generate_response(session)

                if not assistant_text:
                    error_audio = self.tts_client.synthesize(script.error_prompt)
                    if error_audio:
                        self._on_tts_audio(session, error_audio, "error")
                    session.state = SessionState.LISTENING
                    continue

                logger.info(f"[第{turn_count}轮] AI 回复：{assistant_text}")
                session.turns.append(ConversationTurn(
                    turn_id=turn_count,
                    role="assistant",
                    text=assistant_text
                ))
                session.llm_messages.append({"role": "assistant", "content": assistant_text})

                # 5. TTS 播放回复
                session.state = SessionState.SPEAKING
                assistant_audio = self.tts_client.synthesize(assistant_text)
                if assistant_audio:
                    self._on_tts_audio(session, assistant_audio, "response")

                # 6. 回到监听状态
                session.state = SessionState.LISTENING

            # 7. 播放结束语
            closing_audio = self.tts_client.synthesize(script.closing)
            if closing_audio:
                self._on_tts_audio(session, closing_audio, "closing")

        except Exception as e:
            logger.error(f"对话循环异常：{e}")
        finally:
            session.state = SessionState.ENDED
            session.ended_at = time.time()
            logger.info(f"会话结束：{session.session_id}, 时长={session.ended_at - session.started_at:.1f}s")

    def _listen_for_speech(self, session: CallSession) -> Optional[str]:
        """监听客户语音并识别"""
        config = session.config
        vad = VoiceActivityDetector(config.to_vad_config())

        audio_chunks: List[bytes] = []
        speech_detected = False
        speech_end_detected = False
        start_time = time.time()
        bytes_per_frame = int(config.sample_rate * 2 * config.frame_duration_ms / 1000)

        logger.debug("开始监听...")

        while (not session.stop_flag.is_set() and
               not speech_end_detected and
               (time.time() - start_time) < config.silence_timeout):

            # 从队列获取音频
            try:
                frame = session.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # VAD 检测
            try:
                state = vad.process_frame(frame)

                if state == VADState.SPEECH_START:
                    logger.debug("检测到语音开始")
                    speech_detected = True
                    audio_chunks = [frame]

                elif state == VADState.SPEECH:
                    if speech_detected:
                        audio_chunks.append(frame)

                elif state == VADState.SPEECH_END:
                    logger.debug("检测到语音结束")
                    speech_end_detected = True

            except Exception as e:
                logger.warning(f"VAD 处理失败：{e}")
                # 降级：能量检测
                if self._is_voice_frame(frame):
                    if not speech_detected:
                        speech_detected = True
                    audio_chunks.append(frame)

        # 检查语音时长
        if not audio_chunks or len(audio_chunks) < 5:
            logger.debug("语音太短")
            return None

        audio_data = b''.join(audio_chunks)
        logger.info(f"收到语音：{len(audio_data)} 字节")

        # ASR 识别
        return self._run_asr_recognition(audio_data, config)

    def _is_voice_frame(self, frame: bytes) -> bool:
        """简单能量检测"""
        import struct
        total = 0
        count = 0
        for i in range(0, len(frame), 2):
            if i + 1 < len(frame):
                sample = struct.unpack('<h', frame[i:i+2])[0]
                total += abs(sample)
                count += 1
        return (total / count if count > 0 else 0) > 100

    def _run_asr_recognition(self, audio_data: bytes, config: CallConfig) -> Optional[str]:
        """ASR 识别"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            with wave.open(f.name, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(config.sample_rate)
                wav.writeframes(audio_data)
            temp_file = f.name

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                full_text = []

                async def recognize():
                    async with AsrWsClient(config.asr_ws_url) as client:
                        async for response in client.recognize(temp_file):
                            payload = response.get("payload", {})
                            if payload:
                                result = payload.get("result", {})
                                text = result.get("text", "")
                                if text:
                                    full_text.append(text)
                                    if result.get("definite", False):
                                        return text

                return loop.run_until_complete(recognize()) or ''.join(full_text) if full_text else None
            finally:
                loop.close()
        finally:
            os.unlink(temp_file)

    def _generate_response(self, session: CallSession) -> Optional[str]:
        """LLM 生成回复"""
        try:
            # 限制消息长度
            messages = session.llm_messages[-12:]  # 保留最近 6 轮

            response = self.llm_client.chat(messages)
            return response.get("content", "")
        except Exception as e:
            logger.error(f"LLM 失败：{e}")
            return None

    def _on_tts_audio(self, session: CallSession, audio_data: bytes, context: str):
        """TTS 音频回调（由外部实现处理播放）"""
        logger.debug(f"TTS 音频：{context}, {len(audio_data)} 字节")
        # 可以通过回调通知外部播放音频

    def push_audio(self, session_id: str, audio_data: bytes) -> bool:
        """推送音频数据到会话"""
        session = self.sessions.get(session_id)
        if not session:
            return False

        try:
            session.audio_queue.put(audio_data, timeout=1)
            return True
        except queue.Full:
            logger.warning("音频队列已满")
            return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "turn_count": session.turn_count,
            "created_at": session.created_at,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "duration": (session.ended_at or time.time()) - session.started_at if session.started_at else 0,
            "turns": [
                {
                    "turn_id": t.turn_id,
                    "role": t.role,
                    "text": t.text,
                    "timestamp": t.timestamp
                }
                for t in session.turns
            ]
        }

    def end_session(self, session_id: str) -> bool:
        """结束会话"""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.stop_flag.set()
        session.state = SessionState.ENDED
        session.ended_at = time.time()
        return True


# ==================== Flask API ====================

def create_app(engine: Optional[AICallEngine] = None) -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False

    # 创建或获取引擎
    if engine is None:
        engine = AICallEngine()

    # 存储引擎到 app
    app.engine = engine

    # ==================== API 路由 ====================

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """健康检查"""
        return jsonify({"status": "ok", "timestamp": time.time()})

    @app.route('/api/session/create', methods=['POST'])
    def create_session():
        """创建会话"""
        data = request.get_json() or {}

        session_id = data.get('session_id')
        config_data = data.get('config', {})
        script_data = data.get('script', {})

        try:
            config = CallConfig(**config_data) if config_data else None
            script = ScriptConfig(**script_data) if script_data else None

            sid = engine.create_session(session_id, config, script)
            return jsonify({
                "success": True,
                "session_id": sid
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route('/api/session/<session_id>/start', methods=['POST'])
    def start_session(session_id: str):
        """启动会话"""
        try:
            success = engine.start_session(session_id)
            return jsonify({"success": success})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route('/api/session/<session_id>/audio', methods=['POST'])
    def push_audio(session_id: str):
        """推送音频数据"""
        # 支持二进制音频或 JSON 包装的 Base64
        if request.content_type == 'application/json':
            data = request.get_json()
            audio_b64 = data.get('audio')
            if not audio_b64:
                return jsonify({"success": False, "error": "缺少 audio 字段"}), 400
            import base64
            audio_data = base64.b64decode(audio_b64)
        else:
            audio_data = request.data

        # 验证音频格式（16kHz 16bit PCM）
        if len(audio_data) % 2 != 0:
            logger.warning("音频数据长度不是 2 的倍数")

        success = engine.push_audio(session_id, audio_data)
        return jsonify({"success": success})

    @app.route('/api/session/<session_id>/info', methods=['GET'])
    def get_session_info(session_id: str):
        """获取会话信息"""
        info = engine.get_session_info(session_id)
        if not info:
            return jsonify({"success": False, "error": "会话不存在"}), 404
        return jsonify({"success": True, "data": info})

    @app.route('/api/session/<session_id>/end', methods=['POST'])
    def end_session(session_id: str):
        """结束会话"""
        success = engine.end_session(session_id)
        return jsonify({"success": success})

    @app.route('/api/tts/synthesize', methods=['POST'])
    def synthesize_tts():
        """TTS 合成（独立接口）"""
        data = request.get_json() or {}
        text = data.get('text')
        if not text:
            return jsonify({"success": False, "error": "缺少 text 字段"}), 400

        audio_data = engine.tts_client.synthesize(text)
        if audio_data:
            return Response(audio_data, mimetype='audio/wav')
        else:
            return jsonify({"success": False, "error": "TTS 合成失败"}), 500

    return app


# ==================== 主程序 ====================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Bank AI Call Engine')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=5001, help='监听端口')
    parser.add_argument('--llm-key', help='LLM API Key')
    parser.add_argument('--llm-provider', default='deepseek', help='LLM 提供商')
    parser.add_argument('--debug', action='store_true', help='调试模式')

    args = parser.parse_args()

    # 创建引擎
    engine = AICallEngine(
        llm_api_key=args.llm_key,
        llm_provider=args.llm_provider
    )

    # 创建 Flask 应用
    app = create_app(engine)

    # 启动服务
    logger.info(f"启动 AI 通话引擎服务：http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)

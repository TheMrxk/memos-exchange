"""
AI 通话引擎
整合 FreeSWITCH、ASR、LLM、TTS 实现智能外拨通话
"""

import threading
import queue
import time
import logging
import asyncio
import tempfile
import wave
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from .freeswitch_client import FreeSWITCHClient, CallState, CallInfo
from .llm_client import LLMClient
from .doubao_tts import DoubaoTTS as TTSClient
from .audio_stream import AudioStreamManager, AudioSourceType, AudioConfig, FileAudioStream
from .vad_detector import VoiceActivityDetector, VADConfig, VADState, VADMode

logger = logging.getLogger(__name__)

# ASR 客户端在 backend 目录下
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from asr_websocket_client import AsrWsClient


class CallDirection(Enum):
    """通话方向"""
    OUTBOUND = "outbound"  # 外拨
    INBOUND = "inbound"  # 呼入


@dataclass
class AIcallConfig:
    """AI 通话配置"""
    max_duration: int = 300  # 最大通话时长（秒）
    vad_sensitivity: float = 0.5  # VAD 灵敏度 (0.0-1.0)
    silence_timeout: float = 3.0  # 沉默超时时间（秒）
    greeting_delay: float = 1.0  # 接通后延迟播放问候语（秒）
    asr_ws_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"  # ASR WebSocket URL

    # 音频流配置
    audio_sample_rate: int = 16000  # 音频采样率
    audio_frame_duration_ms: int = 20  # 音频帧时长 (毫秒)

    # VAD 配置
    vad_mode: str = "aggressive"  # VAD 模式：normal/low_bitrate/aggressive/very_aggressive
    vad_speech_threshold: int = 3  # 判定为语音的帧数阈值
    vad_silence_threshold: int = 5  # 判定为静音的帧数阈值
    vad_min_speech_duration_ms: int = 200  # 最小语音时长
    vad_max_silence_duration_ms: int = 3000  # 最大静音时长

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
            sample_rate=self.audio_sample_rate,
            frame_duration_ms=self.audio_frame_duration_ms,
            speech_threshold=self.vad_speech_threshold,
            silence_threshold=self.vad_silence_threshold,
            min_speech_duration_ms=self.vad_min_speech_duration_ms,
            max_silence_duration_ms=self.vad_max_silence_duration_ms
        )

    def to_audio_config(self) -> AudioConfig:
        """转换为音频配置"""
        return AudioConfig(
            sample_rate=self.audio_sample_rate,
            bits_per_sample=16,
            channels=1,
            frame_duration_ms=self.audio_frame_duration_ms
        )


class AIcallSession:
    """
    AI 通话会话

    管理单次通话的完整生命周期：
    1. 外拨呼叫
    2. 播放问候语
    3. ASR 语音识别
    4. LLM 对话生成
    5. TTS 语音合成
    6. 通话结束处理
    """

    def __init__(
        self,
        session_id: str,
        customer_phone: str,
        script_config: Dict[str, Any],
        freeswitch_client: FreeSWITCHClient,
        llm_client: LLMClient,
        tts_client: TTSClient,
        config: Optional[AIcallConfig] = None
    ):
        self.session_id = session_id
        self.customer_phone = customer_phone
        self.script_config = script_config
        self.fs_client = freeswitch_client
        self.llm_client = llm_client
        self.tts_client = tts_client
        self.config = config or AIcallConfig()

        self.call_uuid: Optional[str] = None
        self.state = "idle"  # idle, calling, connected, conversing, ended
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # 对话历史
        self.conversation_history: list = []

        # 音频队列
        self.audio_queue = queue.Queue()

        # ASR 客户端
        self.asr_client: Optional[AsrWsClient] = None

        # 控制线程
        self._stop_flag = threading.Event()
        self._threads = []

    def start(self) -> bool:
        """
        启动 AI 通话

        Returns:
            bool: 是否成功发起呼叫
        """
        logger.info(f"开始 AI 通话会话：{self.session_id}, 目标号码：{self.customer_phone}")

        # 1. 发起外拨呼叫
        caller_id = self.script_config.get("caller_id", "1000")
        self.call_uuid = self.fs_client.originate_call(
            destination=self.customer_phone,
            caller_id=caller_id
        )

        if not self.call_uuid:
            logger.error("呼叫发起失败")
            return False

        self.state = "calling"
        logger.info(f"呼叫已发起，UUID: {self.call_uuid}")

        # 2. 启动通话监控线程
        monitor_thread = threading.Thread(target=self._monitor_call, daemon=True)
        monitor_thread.start()
        self._threads.append(monitor_thread)

        return True

    def _monitor_call(self):
        """监控通话状态"""
        import time

        start_wait = time.time()
        max_wait = 60  # 最多等待 60 秒接通

        while not self._stop_flag.is_set() and time.time() - start_wait < max_wait:
            call_info = self.fs_client.get_call_info(self.call_uuid)

            if call_info:
                if call_info.state == CallState.ANSWERED:
                    logger.info("客户已接通，开始对话流程")
                    self._on_call_answered()
                    break
                elif call_info.state in [CallState.HANGUP, CallState.FAILED]:
                    logger.info(f"呼叫结束，状态：{call_info.state}, 原因：{call_info.hangup_cause}")
                    self._on_call_ended(call_info.hangup_cause)
                    break

            time.sleep(0.5)

        else:
            # 超时未接通
            logger.warning("呼叫超时未接通")
            self._on_call_ended("TIMEOUT")

    def _on_call_answered(self):
        """客户接通后的处理"""
        self.state = "connected"
        self.start_time = time.time()

        # 播放问候语
        greeting = self.script_config.get("greeting", "您好")
        self._speak_text(greeting)

        # 开始对话循环
        self.state = "conversing"
        self._conversation_loop()

    def _on_call_ended(self, cause: str):
        """通话结束处理"""
        self.state = "ended"
        self.end_time = time.time()
        self._stop_flag.set()

        logger.info(f"通话结束：{self.session_id}, 时长：{int(self.end_time - self.start_time)}秒")

        # TODO: 保存通话记录和录音

    def _conversation_loop(self):
        """对话循环：ASR -> LLM -> TTS"""
        turn_count = 0
        max_turns = self.script_config.get("max_turns", 10)

        while (
            not self._stop_flag.is_set() and
            self.state == "conversing" and
            turn_count < max_turns
        ):
            # 检查是否超时
            if self.start_time and (time.time() - self.start_time) > self.config.max_duration:
                logger.info("通话超时，结束对话")
                break

            turn_count += 1

            # 1. 等待客户说话（通过 ASR 识别）
            customer_speech = self._listen_for_speech()

            if not customer_speech:
                # 客户长时间未说话，播放提示
                self._speak_text("请问您还在听吗？")
                continue

            logger.info(f"客户说：{customer_speech}")
            self.conversation_history.append({"role": "user", "content": customer_speech})

            # 2. 调用 LLM 生成回复
            assistant_response = self._generate_response(customer_speech)

            if not assistant_response:
                logger.error("LLM 生成回复失败")
                self._speak_text("抱歉，我没有听清楚，能请您再说一遍吗？")
                continue

            logger.info(f"AI 回复：{assistant_response}")
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            # 3. TTS 播放回复
            self._speak_text(assistant_response)

        # 对话结束，播放结束语
        closing = self.script_config.get("closing", "感谢您的接听，祝您生活愉快，再见！")
        self._speak_text(closing)

        # 延迟挂断
        time.sleep(2)
        self._on_call_ended("NORMAL_CLEARING")

    def _listen_for_speech(self, timeout: float = 10.0) -> Optional[str]:
        """
        监听客户语音

        流程:
        1. 使用 VAD 检测语音活动
        2. 收集语音片段
        3. 调用 ASR 识别

        Returns:
            str: 识别到的文本，超时无语音返回 None
        """
        logger.debug("开始监听客户语音...")

        # 初始化 VAD
        try:
            vad = VoiceActivityDetector(self.config.to_vad_config())
        except RuntimeError as e:
            logger.warning(f"VAD 不可用，使用超时检测：{e}")
            return self._listen_for_speech_timeout(timeout)

        # 音频缓冲
        audio_chunks: List[bytes] = []
        speech_detected = False
        speech_end_detected = False
        start_time = time.time()

        # 创建临时音频流（用于测试，实际应使用 RTP 流）
        # 这里使用音频队列模拟
        audio_config = self.config.to_audio_config()
        bytes_per_frame = audio_config.bytes_per_frame

        logger.info(f"VAD 已启动，等待客户说话...")

        while (not self._stop_flag.is_set() and
               not speech_end_detected and
               (time.time() - start_time) < timeout):

            # 从音频队列获取数据
            try:
                frame = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                # 无音频数据，检查 VAD 超时
                elapsed = time.time() - start_time
                if elapsed > self.config.silence_timeout:
                    logger.debug("监听超时，无语音")
                    return None
                continue

            # VAD 检测
            try:
                state = vad.process_frame(frame)

                if state == VADState.SPEECH_START:
                    logger.debug("检测到语音开始")
                    speech_detected = True
                    audio_chunks = [frame]  # 清空之前的静音，保留当前帧

                elif state == VADState.SPEECH:
                    if speech_detected:
                        audio_chunks.append(frame)

                elif state == VADState.SPEECH_END:
                    logger.debug("检测到语音结束")
                    speech_end_detected = True

            except Exception as e:
                logger.warning(f"VAD 处理失败：{e}")
                # VAD 失败时使用简单能量检测
                if self._is_voice_frame(frame):
                    if not speech_detected:
                        logger.debug("检测到语音（能量）")
                        speech_detected = True
                    audio_chunks.append(frame)
                else:
                    if speech_detected and len(audio_chunks) > 10:
                        speech_end_detected = True

        # 处理识别结果
        if not audio_chunks or len(audio_chunks) < 5:  # 至少 5 帧
            logger.debug("语音太短，忽略")
            return None

        # 拼接音频数据
        audio_data = b''.join(audio_chunks)
        logger.info(f"收到语音数据：{len(audio_data)} 字节，时长约 {len(audio_data) / 64:.0f}ms")

        # ASR 识别
        return self._run_asr_recognition(audio_data)

    def _listen_for_speech_timeout(self, timeout: float = 10.0) -> Optional[str]:
        """
        超时监听（VAD 不可用时的降级方案）

        Returns:
            str: 识别到的文本
        """
        logger.debug("使用超时监听模式...")

        audio_chunks = []
        start_time = time.time()
        bytes_per_frame = self.config.to_audio_config().bytes_per_frame

        while (not self._stop_flag.is_set() and
               (time.time() - start_time) < timeout):

            try:
                frame = self.audio_queue.get(timeout=0.5)
                audio_chunks.append(frame)

                # 简单的语音时长检测
                if len(audio_chunks) * bytes_per_frame >= 64000:  # 至少 1 秒
                    break

            except queue.Empty:
                continue

        if not audio_chunks:
            return None

        audio_data = b''.join(audio_chunks)
        return self._run_asr_recognition(audio_data)

    def _is_voice_frame(self, audio_frame: bytes) -> bool:
        """
        简单的能量检测，判断是否为语音帧

        Args:
            audio_frame: PCM 音频帧

        Returns:
            bool: 是否可能是语音
        """
        # 计算平均能量
        import struct
        total = 0
        for i in range(0, len(audio_frame), 2):
            if i + 1 < len(audio_frame):
                sample = struct.unpack('<h', audio_frame[i:i+2])[0]
                total += abs(sample)

        avg_energy = total / (len(audio_frame) // 2) if audio_frame else 0
        return avg_energy > 100  # 能量阈值

    def _run_asr_recognition(self, audio_data: bytes) -> Optional[str]:
        """运行 ASR 识别（在单独线程中执行异步代码）"""
        import tempfile

        # 将音频保存为临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            # 写入 WAV 头（16kHz 16bit 单声道）
            import wave
            with wave.open(f.name, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)  # 16-bit = 2 bytes
                wav.setframerate(16000)
                wav.writeframes(audio_data)
            temp_file = f.name

        try:
            # 运行异步 ASR 客户端
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                full_text = []

                async def recognize():
                    async with AsrWsClient(self.config.asr_ws_url) as client:
                        async for response in client.recognize(temp_file):
                            payload = response.get("payload", {})
                            if payload:
                                result = payload.get("result", {})
                                text = result.get("text", "")
                                if text:
                                    full_text.append(text)
                                    # 如果是确定结果，直接返回
                                    if result.get("definite", False):
                                        return text

                final_text = loop.run_until_complete(recognize())
                return final_text or ''.join(full_text) if full_text else None

            finally:
                loop.close()

        finally:
            import os
            os.unlink(temp_file)

    def _generate_response(self, customer_input: str) -> Optional[str]:
        """
        调用 LLM 生成回复

        Args:
            customer_input: 客户说的话

        Returns:
            str: AI 回复内容
        """
        try:
            system_prompt = self.script_config.get(
                "system_prompt",
                "你是一个专业的客服代表，请友好地回答客户的问题。"
            )

            # 构建对话历史
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self.conversation_history[-10:])  # 保留最近 10 轮

            response = self.llm_client.chat(messages)
            return response.get("content", "")

        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return None

    def _speak_text(self, text: str):
        """
        TTS 播放文本

        Args:
            text: 要播放的文本
        """
        if not text:
            return

        try:
            logger.debug(f"播放 TTS: {text}")
            audio_data = self.tts_client.synthesize(text)

            if audio_data:
                # TODO: 将音频发送到 FreeSWITCH 播放
                # 暂时保存到文件用于测试
                with open(f"/var/recordings/tts_{self.session_id}_{int(time.time())}.wav", "wb") as f:
                    f.write(audio_data)
        except Exception as e:
            logger.error(f"TTS 播放失败：{e}")

    def stop(self):
        """停止通话"""
        logger.info(f"手动停止通话：{self.session_id}")
        if self.call_uuid:
            self.fs_client.hangup_call(self.call_uuid)
        self._stop_flag.set()


class AIcallManager:
    """
    AI 通话管理器

    管理多个并发的 AI 通话会话
    """

    def __init__(
        self,
        freeswitch_client: FreeSWITCHClient,
        llm_client: LLMClient,
        tts_client: TTSClient
    ):
        self.fs_client = freeswitch_client
        self.llm_client = llm_client
        self.tts_client = tts_client

        self.sessions: Dict[str, AIcallSession] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        customer_phone: str,
        script_config: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        创建新的 AI 通话会话

        Args:
            customer_phone: 客户手机号
            script_config: 脚本配置
            session_id: 会话 ID（可选，默认自动生成）

        Returns:
            str: 会话 ID，创建失败返回 None
        """
        import uuid

        session_id = session_id or str(uuid.uuid4())

        with self._lock:
            if session_id in self.sessions:
                logger.error(f"会话 ID 已存在：{session_id}")
                return None

            session = AIcallSession(
                session_id=session_id,
                customer_phone=customer_phone,
                script_config=script_config,
                freeswitch_client=self.fs_client,
                llm_client=self.llm_client,
                tts_client=self.tts_client
            )

            self.sessions[session_id] = session

        logger.info(f"创建 AI 通话会话：{session_id}")
        return session_id

    def start_session(self, session_id: str) -> bool:
        """启动指定的 AI 通话会话"""
        with self._lock:
            session = self.sessions.get(session_id)

        if not session:
            logger.error(f"会话不存在：{session_id}")
            return False

        return session.start()

    def stop_session(self, session_id: str) -> bool:
        """停止指定的 AI 通话会话"""
        with self._lock:
            session = self.sessions.get(session_id)

        if not session:
            logger.error(f"会话不存在：{session_id}")
            return False

        session.stop()
        return True

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        with self._lock:
            session = self.sessions.get(session_id)

        if not session:
            return None

        return {
            "session_id": session.session_id,
            "customer_phone": session.customer_phone,
            "state": session.state,
            "call_uuid": session.call_uuid,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "duration": int(session.end_time - session.start_time) if session.end_time and session.start_time else 0,
            "turn_count": len(session.conversation_history) // 2
        }

    def get_active_sessions(self) -> list:
        """获取所有活跃会话"""
        with self._lock:
            return [
                self.get_session_info(sid)
                for sid, session in self.sessions.items()
                if session.state not in ["idle", "ended"]
            ]

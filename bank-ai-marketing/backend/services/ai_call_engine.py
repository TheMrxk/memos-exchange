"""
AI 通话引擎
整合 FreeSWITCH、ASR、LLM、TTS 实现智能外拨通话
"""

import threading
import queue
import time
import logging
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .freeswitch_client import FreeSWITCHClient, CallState, CallInfo
from .llm_client import LLMClient
from .doubao_tts import DoubaoTTS as TTSClient

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
    vad_sensitivity: float = 0.5  # VAD 灵敏度
    silence_timeout: float = 3.0  # 沉默超时时间（秒）
    greeting_delay: float = 1.0  # 接通后延迟播放问候语（秒）
    asr_ws_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"  # ASR WebSocket URL


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

        Returns:
            str: 识别到的文本，超时无语音返回 None
        """
        logger.debug("开始监听客户语音...")

        # TODO: 实现 RTP 音频流接收和 ASR 识别
        # 当前使用 ASR WebSocket 客户端进行测试
        # 后续需要接入 FreeSWITCH 的 RTP 流

        # 从音频队列接收音频数据
        audio_chunks = []
        start_time = time.time()

        while not self._stop_flag.is_set() and (time.time() - start_time) < timeout:
            try:
                chunk = self.audio_queue.get(timeout=0.5)
                if chunk:
                    audio_chunks.append(chunk)
            except queue.Empty:
                continue

        if not audio_chunks:
            logger.debug("未检测到语音活动")
            return None

        # 拼接音频数据
        audio_data = b''.join(audio_chunks)
        logger.debug(f"收到音频数据：{len(audio_data)} 字节")

        # 使用 ASR 进行识别（需要在单独线程中运行异步代码）
        try:
            return self._run_asr_recognition(audio_data)
        except Exception as e:
            logger.error(f"ASR 识别失败：{e}")
            return None

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

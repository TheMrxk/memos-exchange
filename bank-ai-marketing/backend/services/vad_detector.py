#!/usr/bin/env python3
"""
VAD (Voice Activity Detection) 语音活动检测模块

使用 WebRTC VAD 算法检测语音活动
支持实时音频流分析和静音检测

安装依赖:
    pip install webrtcvad
"""

import logging
import threading
import time
import collections
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

try:
    import webrtcvad
except ImportError:
    webrtcvad = None
    logging.warning("webrtcvad 未安装，VAD 功能将不可用。运行：pip install webrtcvad")

logger = logging.getLogger(__name__)


class VADMode(Enum):
    """
    VAD 检测模式

    模式 0: 最宽松，检测到更多语音（可能包含噪音）
    模式 1: 较宽松
    模式 2: 默认模式，平衡准确率和召回率
    模式 3: 最严格，只检测明显的语音（可能漏掉低语）
    """
    NORMAL = 0
    LOW_BITRATE = 1
    AGGRESSIVE = 2
    VERY_AGGRESSIVE = 3


@dataclass
class VADConfig:
    """VAD 配置"""
    mode: VADMode = VADMode.AGGRESSIVE  # 检测模式
    sample_rate: int = 16000  # 采样率
    frame_duration_ms: int = 30  # 帧时长 (10/20/30ms)
    window_duration_ms: int = 300  # 检测窗口时长
    speech_threshold: int = 3  # 判定为语音的帧数阈值
    silence_threshold: int = 5  # 判定为静音的帧数阈值
    min_speech_duration_ms: int = 200  # 最小语音时长
    max_silence_duration_ms: int = 3000  # 最大静音时长 (超时触发)


class VADState(Enum):
    """VAD 状态"""
    SILENCE = "silence"  # 静音中
    SPEECH = "speech"  # 语音中
    SPEECH_START = "speech_start"  # 语音开始
    SPEECH_END = "speech_end"  # 语音结束


class VoiceActivityDetector:
    """
    语音活动检测器

    实时分析音频流，检测语音活动状态
    """

    # WebRTC VAD 支持的帧时长
    SUPPORTED_FRAME_DURATIONS = {10, 20, 30}

    def __init__(self, config: Optional[VADConfig] = None):
        self.config = config or VADConfig()

        if webrtcvad is None:
            raise RuntimeError("webrtcvad 未安装")

        if self.config.frame_duration_ms not in self.SUPPORTED_FRAME_DURATIONS:
            raise ValueError(
                f"不支持的帧时长：{self.config.frame_duration_ms}ms "
                f"仅支持：{self.SUPPORTED_FRAME_DURATIONS}"
            )

        # 初始化 WebRTC VAD
        self.vad = webrtcvad.Vad(self.config.mode.value)

        # 状态管理
        self.state = VADState.SILENCE
        self._frame_buffer: collections.deque = collections.deque(
            maxlen=self.config.window_duration_ms // self.config.frame_duration_ms
        )
        self._speech_frames = 0
        self._silence_frames = 0
        self._consecutive_speech = 0
        self._consecutive_silence = 0

        # 计时
        self._speech_start_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None

        # 回调
        self._state_callbacks: List[Callable[[VADState], None]] = []

        # 控制
        self._lock = threading.Lock()

    def process_frame(self, audio_frame: bytes) -> VADState:
        """
        处理一帧音频数据

        Args:
            audio_frame: PCM 音频帧 (16kHz 16bit)

        Returns:
            当前 VAD 状态
        """
        if len(audio_frame) < 160:  # 至少 10ms @ 16kHz
            logger.warning(f"音频帧太短：{len(audio_frame)} 字节")
            return self.state

        with self._lock:
            # 运行 VAD 检测
            is_speech = self._is_speech(audio_frame)

            # 更新缓冲区
            self._frame_buffer.append(is_speech)

            # 更新计数器
            if is_speech:
                self._speech_frames += 1
                self._consecutive_speech += 1
                self._consecutive_silence = 0
                self._last_speech_time = time.time()
            else:
                self._silence_frames += 1
                self._consecutive_silence += 1
                self._consecutive_speech = 0

            # 状态转换
            old_state = self.state
            self._update_state(is_speech)

            # 触发状态变化回调
            if old_state != self.state:
                self._trigger_callbacks(self.state)

            return self.state

    def _is_speech(self, audio_frame: bytes) -> bool:
        """检测单帧是否为语音"""
        try:
            return self.vad.is_speech(audio_frame, self.config.sample_rate)
        except Exception as e:
            logger.warning(f"VAD 检测失败：{e}")
            return False

    def _update_state(self, is_speech: bool):
        """更新 VAD 状态"""
        current_time = time.time()

        if self.state == VADState.SILENCE:
            # 静音 → 语音检测
            if self._consecutive_speech >= self.config.speech_threshold:
                self.state = VADState.SPEECH_START
                self._speech_start_time = current_time
                logger.debug("检测到语音开始")

        elif self.state == VADState.SPEECH_START:
            # 语音开始 → 语音中
            self.state = VADState.SPEECH
            logger.debug("进入语音状态")

        elif self.state == VADState.SPEECH:
            # 语音 → 静音检测
            if self._consecutive_silence >= self.config.silence_threshold:
                # 检查语音时长是否满足最小要求
                speech_duration = current_time - self._speech_start_time
                if speech_duration >= self.config.min_speech_duration_ms / 1000:
                    self.state = VADState.SPEECH_END
                    logger.debug(f"检测到语音结束，时长：{speech_duration*1000:.0f}ms")
                else:
                    # 语音时长太短，忽略
                    self.state = VADState.SILENCE
                    logger.debug("语音太短，忽略")

            # 检查最大语音时长
            if self._speech_start_time:
                speech_duration = current_time - self._speech_start_time
                max_duration = self.config.max_silence_duration_ms / 1000
                if speech_duration > max_duration:
                    self.state = VADState.SPEECH_END
                    logger.debug(f"语音时长超限：{speech_duration:.1f}s")

    def reset(self):
        """重置 VAD 状态"""
        with self._lock:
            self.state = VADState.SILENCE
            self._frame_buffer.clear()
            self._speech_frames = 0
            self._silence_frames = 0
            self._consecutive_speech = 0
            self._consecutive_silence = 0
            self._speech_start_time = None
            self._last_speech_time = None

    def is_speaking(self) -> bool:
        """当前是否在说话"""
        return self.state in [VADState.SPEECH, VADState.SPEECH_START]

    def is_silence(self) -> bool:
        """当前是否静音"""
        return self.state == VADState.SILENCE

    def get_speech_duration(self) -> float:
        """获取当前语音时长（秒）"""
        if self._speech_start_time and self.state in [VADState.SPEECH, VADState.SPEECH_START]:
            return time.time() - self._speech_start_time
        return 0.0

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "state": self.state.value,
            "speech_frames": self._speech_frames,
            "silence_frames": self._silence_frames,
            "consecutive_speech": self._consecutive_speech,
            "consecutive_silence": self._consecutive_silence,
            "speech_duration": self.get_speech_duration(),
            "buffer_size": len(self._frame_buffer)
        }

    def add_state_callback(self, callback: Callable[[VADState], None]):
        """添加状态变化回调"""
        self._state_callbacks.append(callback)

    def _trigger_callbacks(self, state: VADState):
        """触发状态变化回调"""
        for callback in self._state_callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"VAD 回调失败：{e}")


class VADAudioProcessor:
    """
    VAD 音频处理器

    结合音频流和 VAD 检测，提供语音片段回调
    """

    def __init__(
        self,
        vad_config: Optional[VADConfig] = None,
        on_speech_start: Optional[Callable] = None,
        on_speech_end: Optional[Callable[[bytes], None]] = None,
        on_silence: Optional[Callable] = None
    ):
        self.vad = VoiceActivityDetector(vad_config)
        self.config = self.vad.config

        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.on_silence = on_silence

        self._speech_buffer = bytearray()
        self._is_recording = False

        # 注册 VAD 状态回调
        self.vad.add_state_callback(self._on_vad_state_change)

    def process_audio(self, audio_frame: bytes) -> Optional[bytes]:
        """
        处理音频帧

        Args:
            audio_frame: PCM 音频帧

        Returns:
            如果是语音结束，返回完整的语音片段；否则返回 None
        """
        state = self.vad.process_frame(audio_frame)

        if state == VADState.SPEECH_START:
            self._is_recording = True
            self._speech_buffer = bytearray(audio_frame)
            if self.on_speech_start:
                self.on_speech_start()

        elif state == VADState.SPEECH:
            if self._is_recording:
                self._speech_buffer.extend(audio_frame)

        elif state == VADState.SPEECH_END:
            if self._is_recording:
                self._is_recording = False
                speech_data = bytes(self._speech_buffer)
                self._speech_buffer = bytearray()

                if self.on_speech_end:
                    self.on_speech_end(speech_data)

                return speech_data

        elif state == VADState.SILENCE:
            if self.on_silence:
                self.on_silence()

        return None

    def reset(self):
        """重置处理器"""
        self.vad.reset()
        self._speech_buffer = bytearray()
        self._is_recording = False

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = self.vad.get_stats()
        stats["is_recording"] = self._is_recording
        stats["buffer_size"] = len(self._speech_buffer)
        return stats


# 测试代码
if __name__ == "__main__":
    import sys
    import wave

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 检查依赖
    if webrtcvad is None:
        print("错误：webrtcvad 未安装")
        print("运行：pip install webrtcvad")
        sys.exit(1)

    # 创建 VAD
    config = VADConfig(
        mode=VADMode.AGGRESSIVE,
        frame_duration_ms=30,
        speech_threshold=3,
        silence_threshold=5
    )
    vad = VoiceActivityDetector(config)

    print("VAD 语音活动检测测试")
    print("=" * 50)
    print(f"检测模式：{config.mode.name}")
    print(f"帧时长：{config.frame_duration_ms}ms")
    print(f"语音阈值：{config.speech_threshold} 帧")
    print(f"静音阈值：{config.silence_threshold} 帧")
    print("=" * 50)

    # 读取测试音频
    test_file = sys.argv[1] if len(sys.argv) > 1 else "test_asr.wav"

    try:
        with wave.open(test_file, 'rb') as wav:
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()

            print(f"音频文件：{test_file}")
            print(f"格式：{sample_rate}Hz, {channels}ch, {sample_width*8}bit")

            # 每帧 30ms
            frame_size = int(sample_rate * sample_width * channels * 0.03)

            states = []
            speech_count = 0
            silence_count = 0

            while True:
                frame = wav.readframes(frame_size)
                if not frame:
                    break

                if len(frame) < frame_size:
                    # 填充最后一帧
                    frame = frame + bytes(frame_size - len(frame))

                state = vad.process_frame(frame)

                if state == VADState.SPEECH_START:
                    speech_count += 1
                    print(f"\n[语音开始] 第 {speech_count} 段")
                elif state == VADState.SPEECH_END:
                    print(f"[语音结束] 时长：{vad.get_speech_duration():.2f}s")

                states.append(state)

            print("\n" + "=" * 50)
            print(f"检测完成")
            print(f"语音段数：{speech_count}")
            print(f"总帧数：{len(states)}")
            print(f"语音占比：{sum(1 for s in states if s in [VADState.SPEECH, VADState.SPEECH_START]) / len(states) * 100:.1f}%")

    except FileNotFoundError:
        print(f"文件不存在：{test_file}")
        print("用法：python vad_detector.py [音频文件.wav]")
    except Exception as e:
        print(f"测试失败：{e}")

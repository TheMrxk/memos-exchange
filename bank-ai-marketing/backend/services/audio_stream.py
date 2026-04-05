#!/usr/bin/env python3
"""
音频流捕获模块

支持多种音频源:
1. FreeSWITCH RTP 流 (通过 mod_callcenter 或 mod_rayo)
2. HTTP 音频流 (通过 WebSocket 或 HTTP POST)
3. 本地音频文件 (用于测试)

输出：16kHz 16bit 单声道 PCM 数据
"""

import threading
import queue
import logging
import time
import wave
import io
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AudioSourceType(Enum):
    """音频源类型"""
    RTP = "rtp"  # FreeSWITCH RTP 流
    HTTP = "http"  # HTTP 音频流
    FILE = "file"  # 本地文件
    MICROPHONE = "microphone"  # 麦克风 (用于测试)


@dataclass
class AudioConfig:
    """音频配置"""
    sample_rate: int = 16000  # 采样率
    bits_per_sample: int = 16  # 每样本位数
    channels: int = 1  # 声道数
    frame_duration_ms: int = 20  # 帧时长 (毫秒)

    @property
    def bytes_per_frame(self) -> int:
        """每帧字节数"""
        return int(self.sample_rate * self.bits_per_sample / 8 * self.channels * self.frame_duration_ms / 1000)

    @property
    def frames_per_second(self) -> int:
        """每秒帧数"""
        return int(1000 / self.frame_duration_ms)


class AudioStream:
    """
    音频流基类

    负责从音频源接收音频数据并放入队列
    """

    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.audio_queue: queue.Queue = queue.Queue(maxsize=100)  # 最多缓冲 100 帧
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 统计信息
        self.frames_received = 0
        self.bytes_received = 0
        self.last_frame_time = 0.0

    def start(self) -> bool:
        """启动音频流"""
        if self.is_running:
            logger.warning("音频流已在运行")
            return False

        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("音频流已启动")
        return True

    def stop(self):
        """停止音频流"""
        if not self.is_running:
            return

        self._stop_event.set()
        self.is_running = False

        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        logger.info("音频流已停止")

    def _run(self):
        """音频流主循环 (由子类实现)"""
        raise NotImplementedError

    def get_audio_frame(self, timeout: float = 0.1) -> Optional[bytes]:
        """
        获取一帧音频数据

        Args:
            timeout: 等待超时时间 (秒)

        Returns:
            音频数据 bytes，超时或无数据返回 None
        """
        try:
            frame = self.audio_queue.get(timeout=timeout)
            self.frames_received += 1
            self.bytes_received += len(frame)
            self.last_frame_time = time.time()
            return frame
        except queue.Empty:
            return None

    def get_queue_size(self) -> int:
        """获取队列中的帧数"""
        return self.audio_queue.qsize()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "is_running": self.is_running,
            "frames_received": self.frames_received,
            "bytes_received": self.bytes_received,
            "queue_size": self.get_queue_size(),
            "last_frame_time": self.last_frame_time
        }


class FileAudioStream(AudioStream):
    """
    文件音频流

    从本地音频文件读取数据，用于测试
    """

    def __init__(self, file_path: str, config: Optional[AudioConfig] = None):
        super().__init__(config)
        self.file_path = file_path
        self.audio_data: Optional[bytes] = None
        self.playback_speed = 1.0  # 播放速度

    def _run(self):
        """从文件读取并发送音频帧"""
        try:
            # 读取 WAV 文件
            with wave.open(self.file_path, 'rb') as wav_file:
                # 验证格式
                file_sample_rate = wav_file.getframerate()
                file_channels = wav_file.getnchannels()
                file_sample_width = wav_file.getsampwidth()

                logger.info(f"音频文件信息：{file_sample_rate}Hz, {file_channels}ch, {file_sample_width*8}bit")

                # 读取所有数据
                self.audio_data = wav_file.readframes(wav_file.getnframes())

            if not self.audio_data:
                logger.error("音频文件为空")
                return

            # 计算帧大小
            bytes_per_frame = self.config.bytes_per_frame
            frame_delay = self.frame_duration_ms / 1000 / self.playback_speed

            # 按帧发送
            offset = 0
            while not self._stop_event.is_set() and offset < len(self.audio_data):
                frame = self.audio_data[offset:offset + bytes_per_frame]

                if len(frame) == bytes_per_frame:
                    try:
                        self.audio_queue.put(frame, timeout=0.1)
                    except queue.Full:
                        logger.warning("音频队列已满，丢弃帧")

                    offset += bytes_per_frame
                else:
                    # 最后一帧不足，填充
                    frame = frame + bytes(bytes_per_frame - len(frame))
                    try:
                        self.audio_queue.put(frame, timeout=0.1)
                    except queue.Full:
                        pass
                    break

                # 模拟实时播放延迟
                time.sleep(frame_delay)

            logger.info("文件播放完成")

        except Exception as e:
            logger.error(f"文件播放失败：{e}")


class RTPAudioStream(AudioStream):
    """
    RTP 音频流

    从 FreeSWITCH 接收 RTP 流
    需要使用 mod_callcenter 或自定义模块将 RTP 流转储到本地端口
    """

    def __init__(
        self,
        bind_host: str = "0.0.0.0",
        bind_port: int = 10000,
        config: Optional[AudioConfig] = None
    ):
        super().__init__(config)
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.socket = None
        self.rtp_sequence = 0
        self.expected_sequence = 0

    def _run(self):
        """接收 RTP 包并提取音频数据"""
        import socket

        try:
            # 创建 UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.bind_host, self.bind_port))
            self.socket.settimeout(1.0)

            logger.info(f"RTP 音频流监听中：{self.bind_host}:{self.bind_port}")

            while not self._stop_event.is_set():
                try:
                    data, addr = self.socket.recvfrom(2048)

                    # 解析 RTP 包 (RFC 3550)
                    # RTP 头：12 字节
                    # - version/padding/extension/CSRC count (1 byte)
                    # - marker/payload type (1 byte)
                    # - sequence number (2 bytes)
                    # - timestamp (4 bytes)
                    # - SSRC (4 bytes)

                    if len(data) < 12:
                        logger.warning(f"RTP 包太短：{len(data)}")
                        continue

                    # 解析 RTP 头
                    header = data[0:12]
                    version = (header[0] >> 6) & 0x03
                    payload_type = header[1] & 0x7F
                    sequence = (header[2] << 8) | header[3]

                    if version != 2:
                        logger.warning(f"非 RTP 2.0 包：version={version}")
                        continue

                    # G.711 PCMA (payload type 8) 或 PCMU (payload type 0)
                    if payload_type not in [0, 8]:
                        logger.debug(f"未知 payload type: {payload_type}")
                        continue

                    # 提取音频数据 (RTP 头之后)
                    audio_data = data[12:]

                    # G.711 转 PCM (如果需要)
                    if payload_type == 8:  # PCMA
                        audio_data = self._pcma_to_pcm(audio_data)
                    elif payload_type == 0:  # PCMU
                        audio_data = self._pcmu_to_pcm(audio_data)

                    # 放入队列
                    try:
                        self.audio_queue.put(audio_data, timeout=0.1)
                    except queue.Full:
                        logger.warning("音频队列已满，丢弃帧")

                    self.rtp_sequence = sequence

                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"RTP 接收失败：{e}")
                    break

        except Exception as e:
            logger.error(f"RTP 音频流启动失败：{e}")
        finally:
            if self.socket:
                self.socket.close()
                self.socket = None

    def _pcma_to_pcm(self, pcma_data: bytes) -> bytes:
        """G.711 PCMA 转 PCM 16bit"""
        pcm_data = bytearray()
        for byte in pcma_data:
            pcm = self._alaw2linear(byte)
            pcm_data.extend(pcm.to_bytes(2, byteorder='little', signed=True))
        return bytes(pcm_data)

    def _pcmu_to_pcm(self, pcmu_data: bytes) -> bytes:
        """G.711 PCMU 转 PCM 16bit"""
        pcm_data = bytearray()
        for byte in pcmu_data:
            pcm = self._ulaw2linear(byte)
            pcm_data.extend(pcm.to_bytes(2, byteorder='little', signed=True))
        return bytes(pcm_data)

    @staticmethod
    def _alaw2linear(alaw_byte: int) -> int:
        """G.711 A-law 转线性 PCM"""
        ALAW_MASK = 0x55
        t = alaw_byte ^ ALAW_MASK

        sign = 1 if (t & 0x80) else -1
        exponent = (t >> 4) & 0x07
        mantissa = t & 0x0F

        sample = (mantissa << 4) + 0x108
        sample <<= exponent - 1

        return sign * sample if exponent > 0 else sign * (mantissa << 3)

    @staticmethod
    def _ulaw2linear(ulaw_byte: int) -> int:
        """G.711 μ-law 转线性 PCM"""
        ULAW_BIAS = 0x84
        t = ~ulaw_byte & 0xFF

        sign = 1 if (t & 0x80) else -1
        exponent = (t >> 4) & 0x07
        mantissa = t & 0x0F

        sample = (mantissa << 4) + ULAW_BIAS
        sample <<= exponent

        return sign * (sample - ULAW_BIAS)


class AudioStreamManager:
    """
    音频流管理器

    管理多个音频流，支持热切换
    """

    def __init__(self):
        self.current_stream: Optional[AudioStream] = None
        self._lock = threading.Lock()
        self._audio_callbacks: List[Callable[[bytes], None]] = []

    def create_stream(
        self,
        source_type: AudioSourceType,
        **kwargs
    ) -> AudioStream:
        """创建音频流"""
        with self._lock:
            if self.current_stream and self.current_stream.is_running:
                self.current_stream.stop()

            config = kwargs.pop('config', None)

            if source_type == AudioSourceType.FILE:
                file_path = kwargs.get('file_path')
                self.current_stream = FileAudioStream(file_path, config)

            elif source_type == AudioSourceType.RTP:
                bind_host = kwargs.get('bind_host', '0.0.0.0')
                bind_port = kwargs.get('bind_port', 10000)
                self.current_stream = RTPAudioStream(bind_host, bind_port, config)

            else:
                raise ValueError(f"不支持的音频源类型：{source_type}")

            return self.current_stream

    def add_audio_callback(self, callback: Callable[[bytes], None]):
        """添加音频数据回调"""
        self._audio_callbacks.append(callback)

    def start(self) -> bool:
        """启动当前音频流"""
        if not self.current_stream:
            logger.error("未创建音频流")
            return False

        return self.current_stream.start()

    def stop(self):
        """停止当前音频流"""
        if self.current_stream:
            self.current_stream.stop()

    def get_audio_frame(self, timeout: float = 0.1) -> Optional[bytes]:
        """获取一帧音频数据"""
        if not self.current_stream:
            return None

        frame = self.current_stream.get_audio_frame(timeout)

        if frame:
            # 触发回调
            for callback in self._audio_callbacks:
                try:
                    callback(frame)
                except Exception as e:
                    logger.error(f"音频回调失败：{e}")

        return frame

    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self.current_stream:
            return {}
        return self.current_stream.get_stats()


# 全局管理器实例
_audio_stream_manager: Optional[AudioStreamManager] = None


def get_audio_stream_manager() -> Optional[AudioStreamManager]:
    """获取音频流管理器单例"""
    global _audio_stream_manager
    if _audio_stream_manager is None:
        _audio_stream_manager = AudioStreamManager()
    return _audio_stream_manager


def init_audio_stream_manager() -> AudioStreamManager:
    """初始化音频流管理器"""
    global _audio_stream_manager
    _audio_stream_manager = AudioStreamManager()
    return _audio_stream_manager


# 测试代码
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 创建文件音频流
    manager = init_audio_stream_manager()

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "test_asr.wav"

    print(f"播放音频文件：{file_path}")

    stream = manager.create_stream(AudioSourceType.FILE, file_path=file_path)
    manager.start()

    try:
        frames = 0
        while stream.is_running:
            frame = manager.get_audio_frame(timeout=0.5)
            if frame:
                frames += 1
                if frames % 50 == 0:
                    stats = manager.get_stats()
                    print(f"已接收 {frames} 帧，队列大小：{stats.get('queue_size', 0)}")
            else:
                if not stream.is_running:
                    break

        print(f"播放完成，共 {frames} 帧")

    except KeyboardInterrupt:
        print("\n中断播放")
    finally:
        manager.stop()

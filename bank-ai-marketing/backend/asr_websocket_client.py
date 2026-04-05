#!/usr/bin/env python3
"""
火山引擎豆包 ASR WebSocket 客户端
双向流式语音识别模型 2.0

WebSocket URL: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async
"""

import asyncio
import aiohttp
import json
import struct
import gzip
import uuid
import logging
import os
from typing import Optional, List, Dict, Any, AsyncGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 常量定义
DEFAULT_SAMPLE_RATE = 16000

# 火山引擎豆包 ASR WebSocket URL
WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"

# 凭证配置
APPID = "2058216235"
ACCESS_TOKEN = "HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W"
RESOURCE_ID = "volc.seedasr.sauc.duration"  # 小时版


class ProtocolVersion:
    V1 = 0b0001


class MessageType:
    CLIENT_FULL_REQUEST = 0b0001
    CLIENT_AUDIO_ONLY_REQUEST = 0b0010
    SERVER_FULL_RESPONSE = 0b1001
    SERVER_ERROR_RESPONSE = 0b1111


class MessageTypeSpecificFlags:
    NO_SEQUENCE = 0b0000
    POS_SEQUENCE = 0b0001
    NEG_SEQUENCE = 0b0010
    NEG_WITH_SEQUENCE = 0b0011


class SerializationType:
    NO_SERIALIZATION = 0b0000
    JSON = 0b0001


class CompressionType:
    NO_COMPRESSION = 0b0000
    GZIP = 0b0001


class AsrRequestHeader:
    """ASR 请求头"""

    def __init__(self):
        self.message_type = MessageType.CLIENT_FULL_REQUEST
        self.message_type_specific_flags = MessageTypeSpecificFlags.POS_SEQUENCE
        self.serialization_type = SerializationType.JSON
        self.compression_type = CompressionType.GZIP
        self.reserved_data = bytes([0x00])

    def to_bytes(self, seq: int = 0) -> bytes:
        header = bytearray()
        header.append((ProtocolVersion.V1 << 4) | 1)
        header.append((self.message_type << 4) | self.message_type_specific_flags)
        header.append((self.serialization_type << 4) | self.compression_type)
        header.extend(self.reserved_data)
        return bytes(header)


class RequestBuilder:
    """请求构建器"""

    @staticmethod
    def new_auth_headers() -> Dict[str, str]:
        reqid = str(uuid.uuid4())
        return {
            "X-Api-Resource-Id": RESOURCE_ID,
            "X-Api-Request-Id": reqid,
            "X-Api-Access-Key": ACCESS_TOKEN,
            "X-Api-App-Key": APPID,
            "X-Api-Connect-Id": str(uuid.uuid4())
        }

    @staticmethod
    def new_full_client_request(seq: int) -> bytes:
        """构建 Full Client Request (首包配置)"""
        header = AsrRequestHeader()
        header.message_type = MessageType.CLIENT_FULL_REQUEST
        header.message_type_specific_flags = MessageTypeSpecificFlags.POS_SEQUENCE

        payload = {
            "user": {
                "uid": "bank_ai_user"
            },
            "audio": {
                "format": "wav",
                "codec": "raw",
                "rate": 16000,
                "bits": 16,
                "channel": 1
            },
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": True,
                "show_utterances": True,
                "enable_nonstream": False
            }
        }

        payload_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        compressed_payload = gzip.compress(payload_bytes)
        payload_size = len(compressed_payload)

        request = bytearray()
        request.extend(header.to_bytes())
        request.extend(struct.pack('>i', seq))
        request.extend(struct.pack('>I', payload_size))
        request.extend(compressed_payload)

        return bytes(request)

    @staticmethod
    def new_audio_only_request(seq: int, segment: bytes, is_last: bool = False) -> bytes:
        """构建 Audio Only Request (音频流)"""
        header = AsrRequestHeader()
        header.message_type = MessageType.CLIENT_AUDIO_ONLY_REQUEST

        if is_last:
            header.message_type_specific_flags = MessageTypeSpecificFlags.NEG_WITH_SEQUENCE
            seq = -seq
        else:
            header.message_type_specific_flags = MessageTypeSpecificFlags.POS_SEQUENCE

        request = bytearray()
        request.extend(header.to_bytes())
        request.extend(struct.pack('>i', seq))

        compressed_segment = gzip.compress(segment)
        request.extend(struct.pack('>I', len(compressed_segment)))
        request.extend(compressed_segment)

        return bytes(request)


class ResponseParser:
    """响应解析器"""

    @staticmethod
    def parse_response(msg: bytes) -> Dict[str, Any]:
        """解析服务器响应"""
        if len(msg) < 4:
            return {"error": "Message too short"}

        header_size = msg[0] & 0x0f
        message_type = msg[1] >> 4
        message_type_specific_flags = msg[1] & 0x0f
        serialization_method = msg[2] >> 4
        message_compression = msg[2] & 0x0f

        payload = msg[header_size * 4:]
        result = {
            "message_type": message_type,
            "flags": message_type_specific_flags,
            "is_last_package": bool(message_type_specific_flags & 0x02),
            "sequence": None,
            "event": None,
            "payload": None
        }

        # 解析 sequence
        if message_type_specific_flags & 0x01:
            result["sequence"] = struct.unpack('>i', payload[:4])[0]
            payload = payload[4:]

        # 解析 event
        if message_type_specific_flags & 0x04:
            result["event"] = struct.unpack('>i', payload[:4])[0]
            payload = payload[4:]

        # 解析 payload
        if message_type == MessageType.SERVER_FULL_RESPONSE:
            payload_size = struct.unpack('>I', payload[:4])[0]
            payload = payload[4:]
        elif message_type == MessageType.SERVER_ERROR_RESPONSE:
            error_code = struct.unpack('>i', payload[:4])[0]
            payload_size = struct.unpack('>I', payload[4:8])[0]
            result["error_code"] = error_code
            payload = payload[8:]

        # 解压缩
        if message_compression == CompressionType.GZIP and payload:
            try:
                payload = gzip.decompress(payload)
            except Exception as e:
                logger.error(f"Decompression failed: {e}")
                return result

        # 解析 JSON
        if serialization_method == SerializationType.JSON and payload:
            try:
                result["payload"] = json.loads(payload.decode('utf-8'))
            except Exception as e:
                logger.error(f"JSON parse failed: {e}")

        return result


class AsrWsClient:
    """ASR WebSocket 客户端"""

    def __init__(self, url: str = WS_URL, segment_duration: int = 200):
        self.seq = 1
        self.url = url
        self.segment_duration = segment_duration
        self.conn = None
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.conn and not self.conn.closed:
            await self.conn.close()
        if self.session and not self.session.closed:
            await self.session.close()

    async def read_audio_data(self, file_path: str) -> bytes:
        """读取音频文件并转换为 16kHz PCM"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            # 检查是否需要转换
            if not self._is_valid_wav(content):
                logger.info("Converting audio to 16kHz PCM WAV format...")
                content = self._convert_wav(file_path)

            return content
        except Exception as e:
            logger.error(f"Failed to read audio data: {e}")
            raise

    def _is_valid_wav(self, data: bytes) -> bool:
        """检查是否为有效的 WAV 文件"""
        if len(data) < 44:
            return False
        return data[:4] == b'RIFF' and data[8:12] == b'WAVE'

    def _convert_wav(self, file_path: str) -> bytes:
        """使用 ffmpeg 转换音频为 16kHz PCM"""
        try:
            import subprocess
            cmd = [
                "ffmpeg", "-v", "quiet", "-y", "-i", file_path,
                "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
                "-f", "wav", "-"
            ]
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.stdout
        except Exception as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            # 如果 ffmpeg 失败，返回原始数据
            with open(file_path, 'rb') as f:
                return f.read()

    def get_segment_size(self, content: bytes) -> int:
        """计算分段大小"""
        try:
            # PCM 16kHz 16bit 单声道：16000 * 2 * 1 = 32000 bytes/sec
            size_per_sec = 16000 * 2 * 1
            segment_size = size_per_sec * self.segment_duration // 1000
            return segment_size
        except Exception as e:
            logger.error(f"Failed to calculate segment size: {e}")
            return 3200  # 默认 200ms

    async def create_connection(self) -> None:
        """创建 WebSocket 连接"""
        headers = RequestBuilder.new_auth_headers()
        try:
            self.conn = await self.session.ws_connect(
                self.url,
                headers=headers
            )
            logger.info(f"Connected to {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise

    async def send_full_client_request(self) -> None:
        """发送 Full Client Request (首包配置)"""
        request = RequestBuilder.new_full_client_request(self.seq)
        self.seq += 1

        try:
            await self.conn.send_bytes(request)
            logger.info(f"Sent full client request with seq: {self.seq - 1}")

            # 接收服务器响应
            msg = await self.conn.receive()
            if msg.type == aiohttp.WSMsgType.BINARY:
                response = ResponseParser.parse_response(msg.data)
                logger.info(f"Received response: {response}")
            else:
                logger.error(f"Unexpected message type: {msg.type}")
        except Exception as e:
            logger.error(f"Failed to send full client request: {e}")
            raise

    async def send_audio_stream(self, segment_size: int, content: bytes) -> AsyncGenerator[None, None]:
        """发送音频流"""
        total_segments = (len(content) + segment_size - 1) // segment_size

        for i in range(0, len(content), segment_size):
            end = min(i + segment_size, len(content))
            segment = content[i:end]
            is_last = (end >= len(content))

            request = RequestBuilder.new_audio_only_request(
                self.seq,
                segment,
                is_last=is_last
            )

            await self.conn.send_bytes(request)
            logger.debug(f"Sent audio segment {i // segment_size + 1}/{total_segments}, seq: {self.seq}, last: {is_last}")

            if not is_last:
                self.seq += 1

            # 模拟实时流发送间隔
            await asyncio.sleep(self.segment_duration / 1000)
            yield

    async def receive_responses(self) -> AsyncGenerator[Dict, None]:
        """接收识别结果"""
        try:
            async for msg in self.conn:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    response = ResponseParser.parse_response(msg.data)
                    yield response

                    if response.get("is_last_package") or response.get("error_code"):
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {msg.data}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket connection closed")
                    break
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            raise

    async def recognize(self, file_path: str) -> AsyncGenerator[Dict, None]:
        """执行语音识别"""
        try:
            # 1. 读取音频文件
            content = await self.read_audio_data(file_path)
            logger.info(f"Audio loaded: {len(content)} bytes")

            # 2. 计算分段大小
            segment_size = self.get_segment_size(content)
            logger.info(f"Segment size: {segment_size} bytes ({self.segment_duration}ms)")

            # 3. 创建 WebSocket 连接
            await self.create_connection()

            # 4. 发送首包配置
            await self.send_full_client_request()

            # 5. 启动发送和接收任务
            async def sender():
                async for _ in self.send_audio_stream(segment_size, content):
                    pass

            sender_task = asyncio.create_task(sender())

            try:
                async for response in self.receive_responses():
                    yield response
            finally:
                sender_task.cancel()
                try:
                    await sender_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error(f"Error in ASR recognition: {e}")
            raise
        finally:
            if self.conn:
                await self.conn.close()


async def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="火山引擎豆包 ASR WebSocket 客户端")
    parser.add_argument("--file", type=str, required=True, help="音频文件路径")
    parser.add_argument("--url", type=str, default=WS_URL, help=f"WebSocket URL (默认：{WS_URL})")
    parser.add_argument("--seg-duration", type=int, default=200, help="音频分包时长 (ms)，默认：200")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        logger.error(f"音频文件不存在：{args.file}")
        sys.exit(1)

    print("=" * 60)
    print("火山引擎豆包 ASR WebSocket 语音识别")
    print("=" * 60)
    print(f"音频文件：{args.file}")
    print(f"WebSocket URL: {args.url}")
    print(f"分包时长：{args.seg_duration}ms")
    print()

    async with AsrWsClient(args.url, args.seg_duration) as client:
        full_text = []
        try:
            async for response in client.recognize(args.file):
                payload = response.get("payload", {})
                if payload:
                    result = payload.get("result", {})
                    text = result.get("text", "")
                    if text:
                        logger.info(f"识别结果：{text}")
                        full_text.append(text)

                    # 打印分句信息
                    utterances = result.get("utterances", [])
                    for utt in utterances:
                        utt_text = utt.get("text", "")
                        definite = utt.get("definite", False)
                        if utt_text:
                            print(f"  [{'确定' if definite else '临时'}] {utt_text}")
        except Exception as e:
            logger.error(f"识别失败：{e}")
            sys.exit(1)

    print()
    print("=" * 60)
    print("识别完成")
    print("=" * 60)
    if full_text:
        print(f"完整文本：{''.join(full_text)}")


if __name__ == "__main__":
    asyncio.run(main())

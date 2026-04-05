"""
豆包实时语音大模型客户端 (Doubao Realtime Voice Model)
使用火山引擎豆包实时语音交互 API
文档：https://www.volcengine.com/docs/6561/2277844

备选方案：火山引擎语音合成 HTTP API
文档：https://www.volcengine.com/docs/6561/79817
"""

import websocket
import json
import logging
import threading
import queue
import struct
import requests
import hashlib
import hmac
import base64
import gzip
from typing import Optional, Callable
from datetime import datetime, timezone
import time

logger = logging.getLogger(__name__)


def generate_volcengine_signature(access_key: str, secret_key: str, method: str = "POST",
                                   path: str = "/api/v1/tts", body: str = "") -> dict:
    """
    生成火山引擎 API 签名
    文档：https://www.volcengine.com/docs/6369/67269

    Args:
        access_key: Access Key (AK)
        secret_key: Secret Key (SK)
        method: HTTP 方法
        path: 请求路径
        body: 请求体

    Returns:
        包含鉴权头的字典
    """
    # 生成时间戳
    now = datetime.now(timezone.utc)
    date = now.strftime("%Y%m%dT%H%M%SZ")

    # 生成 credential scope
    scope = f"{date[:8]}/cn-north-1/volc/request"
    credential = f"{access_key}/{scope}"

    # 生成 canonical request
    # 1. HTTP 方法
    # 2. Canonical URI
    # 3. Canonical query string (无查询参数，为空)
    # 4. Canonical headers
    # 5. Signed headers
    # 6. Hashed payload

    # Canonical headers (按字母顺序排序)
    canonical_headers = f"content-type:application/json\nhost:openspeech.bytedance.com\nx-date:{date}\n"
    signed_headers = "content-type;host;x-date"

    # Hashed payload
    hashed_body = hashlib.sha256(body.encode('utf-8')).hexdigest()

    canonical_request = f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{hashed_body}"

    # 生成 string to sign
    algorithm = "HMAC-SHA256"
    string_to_sign = f"{algorithm}\n{date}\n{scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    # 生成签名
    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    k_date = sign(secret_key.encode('utf-8'), date[:8])
    k_region = sign(k_date, "cn-north-1")
    k_service = sign(k_region, "volc")
    k_credentials = sign(k_service, "request")

    signature = hmac.new(k_credentials, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # 生成 Authorization header
    authorization = f"{algorithm} Credential={credential}, SignedHeaders={signed_headers}, Signature={signature}"

    return {
        "Authorization": authorization,
        "X-Date": date,
        "X-Api-App-ID": ""  # 需要额外传入
    }


class DoubaoRealtimeClient:
    """
    豆包实时语音大模型客户端

    支持功能：
    - 实时语音对话
    - 语音合成（TTS）
    - 纯文本输入模式
    """

    # WebSocket URL
    WS_URL = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"

    # 可用音色列表（豆包语音合成模型 2.0）
    AVAILABLE_VOICES = {
        'zh_female_vv_uranus_bigtts': 'vivi 2.0 音色（通用场景，女声）',
        'zh_female_cancan_mars_bigtts': '灿灿音色（通用场景，女声）',
        'zh_male_yunfeng_mars_bigtts': '云峰音色（通用场景，男声）',
    }

    # 模型版本
    MODEL_VERSIONS = {
        'O2.0': '1.2.1.1',      # O2.0 版本
        'SC2.0': '2.2.0.0',     # SC2.0 版本
    }

    def __init__(
        self,
        appid: str = "2058216235",
        access_token: str = "HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W",
        voice: str = "zh_female_vv_uranus_bigtts",  # 默认 vivi 2.0 音色
        model_version: str = "1.2.1.1",
        secret_key: str = None
    ):
        """
        初始化豆包实时语音客户端

        Args:
            appid: 火山引擎 AppID
            access_token: API Access Token
            voice: 默认音色
            model_version: 模型版本 (1.2.1.1=O2.0, 2.2.0.0=SC2.0)
            secret_key: API Secret Key (用于 X-Api-App-Key)
        """
        self.appid = appid
        self.access_token = access_token
        self.secret_key = secret_key or access_token  # 默认使用 access_token
        self.voice = voice
        self.model_version = model_version

        # WebSocket 连接
        self.ws: Optional[websocket.WebSocket] = None
        self.ws_connected = False
        self._audio_queue = queue.Queue()
        self._ws_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._session_id: Optional[str] = None
        self._sequence = 0
        self._start_connection_done = threading.Event()  # StartConnection 完成标志

        # 回调
        self._on_audio: Optional[Callable] = None
        self._on_text: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._server_sequence: int = 0  # 服务器分配的 sequence
        self._connection_started = threading.Event()  # StartConnection 响应完成标志
        self._dialog_id: Optional[str] = None  # 服务器返回的 dialog_id
        self._session_started = threading.Event()  # SessionStarted 响应完成标志

    def _build_binary_frame(
        self,
        message_type: int,
        event_id: int,
        session_id: str = None,  # 可选
        payload: str = "",
        sequence: int = None,
        include_sequence: bool = True,
        include_session_id: bool = True,
        use_compression: bool = False
    ) -> bytes:
        """
        构建二进制协议帧

        根据火山引擎官方文档和实践经验：
        - flags = 0x07 表示有 sequence + event + session_id
        - flags = 0x06 表示有 event + session_id (无 sequence)
        - flags = 0x03 表示有 sequence + event (无 session_id)
        - flags = 0x02 表示只有 event

        注意：Header byte2 和 byte3 可能包含版本号或其他信息
        """
        # Header (4 字节)
        # Byte 0: 0x11 = Protocol v1, 4-byte header

        # flags 设置
        # bit0 (0x01) = sequence
        # bit1 (0x02) = event
        # bit2 (0x04) = session_id
        flags = 0x02  # 默认只有 event
        if include_sequence:
            flags |= 0x01
        if include_session_id and session_id:
            flags |= 0x04

        # Byte 1: msg_type (high 4 bits) | flags (low 4 bits)
        header_byte1 = ((message_type & 0x0F) << 4) | flags

        # Byte 2 and 3: version/compression flag and reserved
        # 服务器响应使用 0x10，可能表示 V1 协议
        # 0x00 = V0/no compression
        # 0x01 = gzip compression
        # 0x10 = V1 protocol
        # 尝试使用 0x11 = V1 + gzip compression
        version_flag = 0x10  # V1 protocol
        if use_compression:
            version_flag |= 0x01  # Add compression flag
        header = struct.pack('BBBB', 0x11, header_byte1, version_flag, 0x00)

        # Optional 字段 - 严格按照 flags 位顺序
        optional = b''

        # sequence (flags bit0)
        if include_sequence:
            if sequence is None:
                sequence = 0xffffffff  # StartSession 使用 sequence=-1（服务器期望的初始值）
            sequence_bytes = struct.pack('>I', sequence)
            optional += sequence_bytes

        # event_id (flags bit1)
        event_bytes = struct.pack('>I', event_id)
        optional += event_bytes

        # session_id size + session_id (flags bit2)
        if include_session_id and session_id:
            session_id_bytes = session_id.encode('utf-8')
            session_id_size_bytes = struct.pack('>I', len(session_id_bytes))
            optional += session_id_size_bytes + session_id_bytes

        # payload - 可选压缩
        payload_bytes = payload.encode('utf-8')
        if use_compression:
            payload_bytes = gzip.compress(payload_bytes)
        payload_size_bytes = struct.pack('>I', len(payload_bytes))

        # 完整帧：header + optional + payload_size + payload
        frame = header + optional + payload_size_bytes + payload_bytes
        logger.debug(f"构建帧 (flags=0x{flags:02x}, compress={use_compression}, seq={sequence if include_sequence else 'N/A'}, session={session_id if include_session_id else 'N/A'}): msg_type={message_type}, event={event_id}, payload_size={len(payload_bytes)}")
        logger.debug(f"帧 hex: {frame[:80].hex()}...")
        return frame

    def connect(
        self,
        on_audio: Callable[[bytes], None] = None,
        on_text: Callable[[str], None] = None,
        on_complete: Callable = None,
        on_error: Callable = None
    ) -> bool:
        """
        连接到 WebSocket 服务

        Args:
            on_audio: 接收音频数据的回调
            on_text: 接收文本的回调
            on_complete: 完成回调
            on_error: 错误回调

        Returns:
            是否成功连接
        """
        self._on_audio = on_audio
        self._on_text = on_text
        self._on_complete = on_complete
        self._on_error = on_error

        # 重置会话状态
        self._session_started.clear()
        self._dialog_id = None
        self._server_sequence = 0

        # 构建 WebSocket URL 和 Headers
        # 鉴权格式：火山引擎实时语音模型需要特定的头格式
        # 参考：https://www.volcengine.com/docs/6561/107789
        # X-Api-App-Key 需要使用正确的 API Key 格式
        headers = [
            f"X-Api-App-ID: {self.appid}",
            f"X-Api-Access-Key: {self.access_token}",
            f"X-Api-App-Key: {self.secret_key}",  # 使用 Secret Key 作为 App Key
            f"X-Api-Resource-Id: volc.speech.dialog",
            "Content-Type: application/json"
        ]

        try:
            self.ws = websocket.WebSocketApp(
                self.WS_URL,
                header=headers,
                on_open=self._on_ws_open,
                on_message=self._on_ws_message,
                on_error=self._on_ws_error,
                on_close=self._on_ws_close
            )

            self._ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            self._ws_thread.start()

            # 等待连接
            for _ in range(50):  # 最多等待 5 秒
                if self.ws_connected:
                    return True
                time.sleep(0.1)

            logger.error("WebSocket 连接超时")
            return False

        except Exception as e:
            logger.error(f"连接失败：{e}")
            if on_error:
                on_error(e)
            return False

    def _on_ws_open(self, ws):
        """WebSocket 连接打开"""
        logger.info("WebSocket 连接已建立")
        self.ws_connected = True

        # 不发送 StartConnection，直接认为连接成功
        # 许多 WebSocket API 不需要显式的 StartConnection
        self._start_connection_done.set()
        self._connection_started.set()
        logger.debug("WebSocket 已连接，准备发送 StartSession")

    def _send_start_connection(self):
        """
        StartConnection - 使用 sequence=1

        帧结构：Header + Optional(sequence) + Payload Size + Payload
        """
        # Header: 0x11, flags=0x01 (只有 sequence)
        header = struct.pack('BBBB', 0x11, 0x11, 0x00, 0x00)

        # Optional: 只有 sequence (4 bytes), 使用 sequence=1
        sequence_bytes = struct.pack('>I', 1)
        optional = sequence_bytes

        # Payload
        payload = b'{}'
        payload_size = struct.pack('>I', len(payload))

        frame = header + optional + payload_size + payload
        self.ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
        logger.debug(f"已发送 StartConnection 帧：{frame.hex()}")

    def start_session(self, system_prompt: str = None) -> bool:
        """
        启动会话

        Args:
            system_prompt: 系统提示词/人设

        Returns:
            是否成功
        """
        # 生成 session ID
        self._session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 构建 StartSession payload
        payload = {
            "tts": {
                "audio_config": {
                    "speech_rate": 0,
                    "loudness_rate": 0
                }
            },
            "asr": {
                "extra": {
                    "end_smooth_window_ms": 1500,
                    "enable_custom_vad": False,
                    "enable_asr_twopass": False
                }
            },
            "dialog": {
                "bot_name": "银行 AI 客服",
                "system_role": system_prompt or "你是一个专业的银行客服代表，请友好地回答客户的问题。",
                "speaking_style": "专业、友好、简洁",
                "extra": {
                    "input_mod": "audio",  # 音频输入模式（语音到语音）
                    "model": self.model_version
                }
            }
        }

        # 发送 StartSession 事件 (event_id = 100)
        # StartSession 必须使用 sequence=-1 (0xffffffff) - 服务器期望的初始值
        # 尝试使用 gzip 压缩 payload
        frame = self._build_binary_frame(
            message_type=0b0001,
            event_id=100,
            session_id=self._session_id,
            payload=json.dumps(payload),
            sequence=0xffffffff,  # -1 as unsigned
            use_compression=True  # 启用 gzip 压缩
        )
        self.ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
        logger.info("已发送 StartSession 事件 (seq=-1, compressed)")

        # 等待 SessionStarted 响应（最多 5 秒）
        if not self._session_started.wait(timeout=5.0):
            logger.error("等待 SessionStarted 响应超时")
            return False

        # 服务器响应后，下一个请求使用 sequence=1
        self._server_sequence = 1

        # StartSession 后，发送一个空的 AudioLast 包来结束 seq=-1 的状态
        # 这告诉服务器上一个包已完成，可以接收下一个请求
        logger.info("发送 AudioLast 确认包...")
        finish_frame = self._build_binary_frame(
            message_type=0b0001,
            event_id=303,  # AudioLast
            session_id=self._dialog_id or self._session_id,
            payload=json.dumps({"end_reason": "normal"}),
            sequence=1,
            include_sequence=True,
            include_session_id=True,
            use_compression=True
        )
        self.ws.send(finish_frame, opcode=websocket.ABNF.OPCODE_BINARY)
        time.sleep(0.2)

        # 等待服务器准备好接收下一个请求
        time.sleep(0.5)

        return True

    def send_text(self, text: str) -> bool:
        """
        发送文本进行对话

        Args:
            text: 要发送的文本

        Returns:
            是否成功
        """
        if not self.ws_connected:
            logger.error("未连接")
            return False

        # 优先使用 dialog_id（服务器返回的），如果没有则使用 session_id
        session_id = self._dialog_id or self._session_id
        if not session_id:
            logger.error("未连接或会话未启动")
            return False

        # 使用 ChatTextQuery 事件 (event_id = 501)
        payload = {"content": text}

        # 尝试不使用 sequence (flags=0x06 = event + session_id only)
        # 这样可以避免 sequence 不匹配的问题
        frame = self._build_binary_frame(
            message_type=0b0001,
            event_id=501,
            session_id=session_id,
            payload=json.dumps(payload),
            sequence=0,
            include_sequence=False,  # 不包含 sequence
            include_session_id=True,
            use_compression=True
        )
        self.ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
        logger.info(f"已发送文本：{text} (session={session_id}, no seq)")
        return True

    def send_audio(self, audio_data: bytes, is_last: bool = False) -> bool:
        """
        发送音频数据

        Args:
            audio_data: PCM 音频数据（16kHz, 16bit, 单声道）
            is_last: 是否是最后一个音频帧

        Returns:
            是否成功
        """
        if not self.ws_connected:
            logger.error("未连接")
            return False

        session_id = self._dialog_id or self._session_id
        if not session_id:
            logger.error("未连接或会话未启动")
            return False

        # 使用 AudioData 事件 (event_id = 301)
        # payload 是二进制音频数据
        frame = self._build_binary_frame(
            message_type=0b0001,
            event_id=301,  # AudioData
            session_id=session_id,
            payload=audio_data.decode('latin-1') if isinstance(audio_data, bytes) else audio_data,
            sequence=self._server_sequence,
            include_sequence=True,
            include_session_id=True,
            use_compression=False  # 音频数据不压缩
        )
        self._server_sequence += 1
        self.ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
        logger.debug(f"已发送音频数据：{len(audio_data)} 字节 (seq={self._server_sequence - 1})")
        return True

    def finish_audio(self) -> bool:
        """
        结束音频输入，触发模型响应

        Returns:
            是否成功
        """
        if not self.ws_connected:
            logger.error("未连接")
            return False

        session_id = self._dialog_id or self._session_id
        if not session_id:
            logger.error("未连接或会话未启动")
            return False

        # 使用 AudioLast 事件 (event_id = 303)
        payload = {"end_reason": "normal"}
        frame = self._build_binary_frame(
            message_type=0b0001,
            event_id=303,  # AudioLast
            session_id=session_id,
            payload=json.dumps(payload),
            sequence=self._server_sequence,
            include_sequence=True,
            include_session_id=True,
            use_compression=True
        )
        self._server_sequence += 1
        self.ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
        logger.info(f"已发送音频结束信号 (seq={self._server_sequence - 1})")
        return True

    def _on_ws_message(self, ws, message):
        """处理 WebSocket 消息"""
        try:
            if isinstance(message, bytes):
                # 二进制帧解析
                logger.debug(f"收到二进制消息：{message.hex()}")
                self._parse_binary_frame(message)
            else:
                logger.info(f"收到文本消息：{message}")

        except Exception as e:
            logger.error(f"处理消息失败：{e}")
            if self._on_error:
                self._on_error(e)

    def _parse_binary_frame(self, data: bytes):
        """
        解析二进制帧

        服务器响应格式：
        - Header (4 bytes): 0x11, msg_type/flags, version, reserved
        - Payload Size (4 bytes): 总 payload 大小
        - Session ID Size (4 bytes): session_id 长度
        - Session ID (variable): session_id 字符串
        - JSON Payload Size (4 bytes): JSON payload 长度
        - JSON Payload (variable): JSON 数据
        """
        if len(data) < 4:
            return

        # 解析 header
        header_byte0 = data[0]
        header_byte1 = data[1]
        message_type = (header_byte1 >> 4) & 0x0F
        flags = header_byte1 & 0x0F
        version_byte = data[2]

        logger.debug(f"解析帧：msg_type={message_type}, flags={flags:#x}, version={version_byte:#x}, data_hex={data[:20].hex()}...")

        # 检查是否是错误响应 (message_type 0b1111 = 15)
        if message_type == 0b1111:
            try:
                # 服务器错误格式：Header(4) + payload_size(4) + session_size(4) + session + json_size(4) + json
                offset = 4
                payload_size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                session_size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4 + session_size
                json_size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                json_payload = data[offset:offset+json_size]

                error_response = json.loads(json_payload.decode('utf-8'))
                logger.error(f"服务器错误：{error_response}")
                if self._on_error:
                    self._on_error(Exception(f"服务器错误：{error_response}"))
            except Exception as e:
                logger.error(f"解析错误响应失败：{e}, data_hex={data[:80].hex()}")
            return

        # 解析服务器响应（标准格式）
        offset = 4

        # Total payload size
        if offset + 4 <= len(data):
            total_payload_size = struct.unpack('>I', data[offset:offset+4])[0]
            offset += 4

            # Session ID size
            if offset + 4 <= len(data):
                session_id_size = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4

                # Session ID
                if offset + session_id_size <= len(data):
                    session_id = data[offset:offset+session_id_size].decode('utf-8')
                    offset += session_id_size
                    logger.debug(f"  session_id={session_id}")

                    # JSON payload size
                    if offset + 4 <= len(data):
                        json_payload_size = struct.unpack('>I', data[offset:offset+4])[0]
                        offset += 4

                        # JSON payload
                        if offset + json_payload_size <= len(data):
                            json_payload = data[offset:offset+json_payload_size]

                            # 解压缩
                            if version_byte & 0x01:
                                try:
                                    json_payload = gzip.decompress(json_payload)
                                except:
                                    pass

                            try:
                                response = json.loads(json_payload.decode('utf-8'))
                                logger.debug(f"  response={response}")

                                # 检查 dialog_id (SessionStarted)
                                if 'dialog_id' in response:
                                    dialog_id = response.get('dialog_id')
                                    logger.info(f"会话已启动：{dialog_id}")
                                    self._dialog_id = dialog_id

                                    # 检查服务器是否返回了 sequence
                                    if 'sequence' in response:
                                        self._server_sequence = response['sequence']
                                        logger.info(f"服务器分配的 sequence: {self._server_sequence}")
                                    else:
                                        # 服务器未返回 sequence，使用 seq=1 作为下一个请求的序列号
                                        # StartSession 使用 seq=-1，服务器期望下一个包使用 seq=1
                                        self._server_sequence = 1
                                        logger.info("使用默认 sequence=1")

                                    self._session_started.set()

                                # 检查 TTS 相关事件
                                if response.get('event') == 359 or 'tts_end' in response:  # TTSEnd
                                    if self._on_complete:
                                        self._on_complete()
                                    logger.info("TTS 完成")

                                # 检查 ChatResponse
                                if response.get('event') == 550 or 'content' in response:
                                    content = response.get('content', '')
                                    if self._on_text:
                                        self._on_text(content)
                                    logger.info(f"收到文本回复：{content}")

                            except Exception as e:
                                logger.error(f"解析 JSON 失败：{e}, data={json_payload[:100]}")

    def _on_ws_error(self, ws, error):
        """WebSocket 错误"""
        logger.error(f"WebSocket 错误：{error}")
        self.ws_connected = False
        if self._on_error:
            self._on_error(error)

    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket 关闭"""
        logger.info(f"WebSocket 连接已关闭：{close_status_code} - {close_msg}")
        self.ws_connected = False

    def finish_session(self):
        """结束会话"""
        if self.ws and self._session_id and self.ws_connected:
            try:
                frame = self._build_binary_frame(
                    message_type=0b0001,
                    event_id=102,  # FinishSession
                    session_id=self._session_id,
                    payload='{}'
                )
                self.ws.send(frame, opcode=websocket.ABNF.OPCODE_BINARY)
                logger.info("已发送 FinishSession 事件")
            except Exception as e:
                logger.debug(f"FinishSession 失败（可能连接已关闭）: {e}")

    def close(self):
        """关闭连接"""
        self._stop_event.set()
        self.finish_session()
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                logger.debug(f"关闭 WebSocket 失败：{e}")
        self.ws_connected = False

    def get_audio_result(self, timeout: float = 10.0) -> bytes:
        """获取音频结果"""
        audio_chunks = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                chunk = self._audio_queue.get(timeout=0.5)
                audio_chunks.append(chunk)
            except queue.Empty:
                break

        return b''.join(audio_chunks) if audio_chunks else b''

    def synthesize_http(self, text: str, output_file: str = None) -> Optional[bytes]:
        """
        语音合成（HTTP API 方式）
        使用火山引擎豆包语音合成模型 2.0
        文档：https://www.volcengine.com/docs/6561/79817

        Args:
            text: 要合成的文本
            output_file: 输出文件路径

        Returns:
            音频数据
        """
        # 火山引擎语音合成 API 端点 - V3 单向流式
        api_url = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

        # 请求参数 - V3 HTTP 单向流式格式
        params = {
            "user": {
                "uid": "bank-ai-user"
            },
            "req_params": {
                "text": text,
                "speaker": self.voice,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": 24000
                }
            }
        }

        # 使用 Token 鉴权方式
        headers = {
            "X-Api-App-Key": str(self.appid),
            "X-Api-Access-Key": self.access_token,  # 注意：使用 X-Api-Access-Key header
            "X-Api-Resource-Id": "seed-tts-2.0",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                api_url,
                headers=headers,
                json=params,
                stream=True,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"HTTP 错误：{response.status_code}, {response.text[:200]}")
                return None

            audio_data = bytearray()

            for chunk in response.iter_lines(decode_unicode=True):
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk)
                    code = data.get("code", 0)

                    if code == 0 and data.get("data"):
                        audio = base64.b64decode(data["data"])
                        audio_data.extend(audio)
                    elif code == 20000000:
                        break
                    elif code > 0:
                        logger.error(f"语音合成错误：{data.get('message', '')}")
                        return None
                except json.JSONDecodeError:
                    pass

            if audio_data:
                logger.info(f"语音合成成功，音频大小：{len(audio_data)} 字节")

                if output_file:
                    with open(output_file, 'wb') as f:
                        f.write(audio_data)
                    logger.info(f"音频已保存到：{output_file}")

                return bytes(audio_data)
            else:
                logger.error("未收到音频数据")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败：{e}")
            return None

    def synthesize(self, text: str, output_file: str = None) -> Optional[bytes]:
        """
        语音合成（封装方法）- 优先使用 HTTP API，失败后尝试 WebSocket

        Args:
            text: 要合成的文本
            output_file: 输出文件路径

        Returns:
            音频数据
        """
        # 首先尝试 HTTP API
        logger.info("尝试使用 HTTP API 进行语音合成")
        audio_data = self.synthesize_http(text, output_file)
        if audio_data:
            return audio_data

        # HTTP API 失败后，尝试 WebSocket 方式
        logger.info("HTTP API 失败，尝试使用 WebSocket 方式")
        audio_result = []

        def on_audio(data):
            audio_result.append(data)

        def on_complete():
            logger.info("合成完成")

        # 重置 StartConnection 标志
        self._start_connection_done.clear()
        self._connection_started.clear()

        # 连接
        if not self.connect(on_audio=on_audio, on_complete=on_complete):
            return None

        # 等待 StartConnection 响应（最多等待 5 秒）
        if not self._connection_started.wait(timeout=5.0):
            logger.error("等待 StartConnection 响应超时")
            self.close()
            return None

        # StartConnection 成功后，等待一小段时间让服务器准备好
        time.sleep(0.5)

        # 启动会话
        if not self.start_session():
            self.close()
            return None

        time.sleep(0.5)

        # 发送文本
        self.send_text(text)

        # 等待完成
        time.sleep(3)

        # 获取音频
        audio = self.get_audio_result(timeout=5)

        # 保存文件
        if output_file and audio:
            with open(output_file, 'wb') as f:
                f.write(audio)
            logger.info(f"音频已保存到：{output_file}")

        self.close()
        return audio if audio else None


# 全局客户端实例
_tts_client: Optional[DoubaoRealtimeClient] = None


def get_tts_client() -> Optional[DoubaoRealtimeClient]:
    """获取 TTS 客户端单例"""
    global _tts_client
    return _tts_client


def init_tts_client(
    provider: str = 'doubao',
    appid: str = "2058216235",
    access_token: str = "HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W",
    scene: str = None,  # 兼容旧参数
    voice: str = "zh_female_vv_uranus_bigtts",
    secret_key: str = None
) -> DoubaoRealtimeClient:
    """初始化 TTS 客户端"""
    global _tts_client

    _tts_client = DoubaoRealtimeClient(
        appid=appid,
        access_token=access_token,
        voice=voice,
        secret_key=secret_key
    )

    logger.info(f"TTS 客户端已初始化，提供商：{provider}, AppID: {appid}")
    return _tts_client


def create_tts_client(appid: str, access_token: str) -> DoubaoRealtimeClient:
    """创建 TTS 客户端"""
    return DoubaoRealtimeClient(appid, access_token)

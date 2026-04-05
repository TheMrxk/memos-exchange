"""
ASR 语音识别客户端
支持阿里云智能语音交互、FunASR 和火山引擎豆包 ASR
"""

import requests
import json
import logging
from typing import Optional, Dict, Any, Generator
import hashlib
import time
import hmac
import base64
import struct
import gzip
import uuid
from urllib.parse import quote
import websocket
from threading import Thread, Event

logger = logging.getLogger(__name__)

# 火山引擎豆包 ASR WebSocket URL
VOLCENGINE_ASR_WS_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"


class ASRClient:
    """
    语音识别客户端

    支持多种 ASR 服务：
    - aliyun: 阿里云智能语音交互
    - funasr: FunASR 本地/远程服务
    - volcengine_doubao: 火山引擎豆包语音识别模型 2.0
    - azure: Azure Speech Service
    """

    # 支持的提供商
    PROVIDERS = {
        'aliyun': {
            'host': 'nls-gateway.cn-shanghai.aliyuncs.com',
            'api_version': '2019-02-28',
            'app_key_required': True
        },
        'funasr': {
            'host': 'localhost',
            'port': 10095,
            'api_version': 'v1',
            'app_key_required': False
        },
        'volcengine_doubao': {
            'host': 'openspeech.bytedance.com',
            'api_version': 'v3',
            'app_key_required': False
        }
    }

    def __init__(
        self,
        provider: str = 'volcengine_doubao',
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        app_key: Optional[str] = None,
        server_url: Optional[str] = None,
        # 火山引擎豆包 ASR 参数
        doubao_appid: Optional[str] = None,
        doubao_access_token: Optional[str] = None,
        doubao_resource_id: Optional[str] = None
    ):
        """
        初始化 ASR 客户端

        Args:
            provider: 服务提供商 (aliyun/funasr/volcengine_doubao)
            access_key_id: 阿里云 AccessKey ID
            access_key_secret: 阿里云 AccessKey Secret
            app_key: 阿里云语音项目 AppKey
            server_url: FunASR 服务器 URL（可选）
            doubao_appid: 火山引擎 APPID
            doubao_access_token: 火山引擎 Access Token
            doubao_resource_id: 火山引擎 Resource ID (如 seed-asr-2.0)
        """
        self.provider = provider
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.app_key = app_key

        # FunASR 服务器地址
        if server_url:
            self.funasr_url = server_url
        else:
            self.funasr_url = "http://localhost:10095"

        # 火山引擎豆包 ASR 参数
        self.doubao_appid = doubao_appid or "2058216235"
        self.doubao_access_token = doubao_access_token or "HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W"
        self.doubao_resource_id = doubao_resource_id or "seed-asr-2.0"

        # WebSocket 连接（用于实时识别）
        self.ws = None
        self.task_id: Optional[str] = None

    # ==================== 阿里云语音识别 ====================

    def _get_aliyun_token(self) -> str:
        """
        获取阿里云访问令牌

        使用 Pop 方式获取令牌，有效期 3600 秒

        Returns:
            str: 访问令牌
        """
        # 构建请求参数
        params = {
            'Format': 'JSON',
            'Version': '2019-02-28',
            'AccessKeyId': self.access_key_id,
            'Action': 'CreateToken',
            'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'SignatureMethod': 'HMAC-SHA1',
            'SignatureVersion': '1.0',
            'SignatureNonce': str(time.time())
        }

        # 构建待签名字符串
        sorted_params = sorted(params.items())
        query_string = '&'.join(f"{k}={quote(str(v), safe='')}" for k, v in sorted_params)
        string_to_sign = f"GET&%2F&{quote(query_string, safe='')}"

        # 计算签名
        key = f"{self.access_key_secret}&"
        signature = base64.b64encode(
            hmac.new(key.encode(), string_to_sign.encode(), hashlib.sha1).digest()
        ).decode()

        # 构建请求 URL
        url = f"https://nls-meta.cn-shanghai.aliyuncs.com/?{query_string}&Signature={quote(signature)}"

        try:
            response = requests.get(url, timeout=10)
            result = response.json()

            if 'Token' in result:
                token = result['Token']
                logger.info(f"阿里云令牌获取成功，ID: {token.get('Id')}")
                return token.get('Id')
            else:
                logger.error(f"阿里云令牌获取失败：{result}")
                raise Exception(f"阿里云令牌获取失败：{result}")

        except Exception as e:
            logger.error(f"获取阿里云令牌异常：{e}")
            raise

    def aliyun_rest_api_recognize(
        self,
        audio_url: str,
        format: str = 'wav',
        sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        阿里云 REST API 语音识别（适合录音文件识别）

        Args:
            audio_url: 音频文件 URL 或本地路径
            format: 音频格式
            sample_rate: 采样率

        Returns:
            dict: 识别结果
        """
        token = self._get_aliyun_token()

        # 创建任务
        create_url = "https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/transcriptions"
        headers = {
            "Content-Type": "application/json",
            "X-NLS-Token": token
        }

        payload = {
            "taskName": "bank_ai_call",
            "audioUrl": audio_url,
            "format": format,
            "sampleRate": sample_rate,
            "enableIntermediateResult": True,
            "enablePunctuationPrediction": True,
            "enableInverseTextNormalization": True
        }

        try:
            # 创建任务
            response = requests.post(create_url, json=payload, headers=headers, timeout=10)
            create_result = response.json()

            if create_result.get('status') != 20000000:
                logger.error(f"创建识别任务失败：{create_result}")
                raise Exception(f"创建任务失败：{create_result.get('message')}")

            task_id = create_result.get('taskId')
            logger.info(f"识别任务创建成功：{task_id}")

            # 轮询任务状态
            query_url = f"https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/transcriptions/{task_id}"

            max_wait = 300  # 最多等待 5 分钟
            start_time = time.time()

            while time.time() - start_time < max_wait:
                response = requests.get(query_url, headers=headers, timeout=10)
                result = response.json()

                status = result.get('status', {}).get('status', '')

                if status == 'SUCCEEDED':
                    logger.info(f"识别任务完成：{task_id}")
                    return self._parse_aliyun_result(result)
                elif status in ['FAILED', 'CANCELLED']:
                    logger.error(f"识别任务失败：{result}")
                    raise Exception(f"识别失败：{result.get('message')}")

                time.sleep(2)

            raise Exception("识别任务超时")

        except Exception as e:
            logger.error(f"阿里云识别异常：{e}")
            raise

    def _parse_aliyun_result(self, result: Dict) -> Dict[str, Any]:
        """解析阿里云识别结果"""
        sentences = result.get('result', {}).get('sentences', [])

        full_text = ' '.join(s.get('text', '') for s in sentences)

        return {
            'success': True,
            'text': full_text,
            'sentences': sentences,
            'provider': 'aliyun'
        }

    # ==================== 火山引擎豆包 ASR ====================

    def volcengine_doubao_recognize(
        self,
        audio_data: bytes,
        format: str = 'pcm',
        sample_rate: int = 24000,
        language: str = 'zh'
    ) -> Dict[str, Any]:
        """
        火山引擎豆包 ASR 语音识别

        文档：https://www.volcengine.com/docs/6561/1598827

        Args:
            audio_data: 音频二进制数据 (PCM 16bit 单声道)
            format: 音频格式 (pcm/wav/mp3)
            sample_rate: 采样率 (16000/24000/44100)
            language: 语言 (zh 中文/en 英文)

        Returns:
            dict: 识别结果 {'success': bool, 'text': str}
        """
        # 豆包 ASR V3 HTTP API
        url = "https://openspeech.bytedance.com/api/v3/asr/stream"

        headers = {
            "X-Api-App-Key": self.doubao_appid,
            "X-Api-Access-Key": self.doubao_access_token,
            "X-Api-Resource-Id": self.doubao_resource_id,
            "Content-Type": "application/octet-stream"
        }

        # 构建请求参数
        params = {
            "format": format,
            "sample_rate": sample_rate,
            "language": language,
            "use_itn": True  # 是否进行逆文本标准化
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                data=audio_data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return self._parse_volcengine_asr_result(result)
            else:
                logger.error(f"火山引擎 ASR 请求失败：{response.status_code} - {response.text[:200]}")
                return {'success': False, 'error': f'HTTP {response.status_code}', 'text': ''}

        except Exception as e:
            logger.error(f"火山引擎 ASR 识别异常：{e}")
            return {'success': False, 'error': str(e), 'text': ''}

    def _parse_volcengine_asr_result(self, result: Dict) -> Dict[str, Any]:
        """解析火山引擎 ASR 识别结果"""
        # 豆包 ASR 返回格式
        # {"code": 0, "message": "Success", "data": {"text": "识别结果"}}

        if result.get("code") == 0:
            text = result.get("data", {}).get("text", "")
            return {
                'success': True,
                'text': text,
                'provider': 'volcengine_doubao'
            }
        else:
            logger.warning(f"火山引擎 ASR 返回错误：{result}")
            return {
                'success': False,
                'error': result.get('message', 'Unknown error'),
                'text': ''
            }

    # ==================== FunASR 语音识别 ====================

    def funasr_online_recognize(
        self,
        audio_data: bytes,
        format: str = 'wav',
        sample_rate: int = 16000
    ) -> Dict[str, Any]:
        """
        FunASR 在线识别（HTTP 方式）

        Args:
            audio_data: 音频二进制数据
            format: 音频格式
            sample_rate: 采样率

        Returns:
            dict: 识别结果
        """
        import io

        url = f"{self.funasr_url}/"

        # 构建 multipart 请求
        files = {
            'audio': ('audio.wav', io.BytesIO(audio_data), 'audio/wav')
        }

        data = {
            'format': format,
            'sample_rate': str(sample_rate),
            'language': 'zh'
        }

        try:
            response = requests.post(url, files=files, data=data, timeout=30)
            result = response.json()

            return self._parse_funasr_result(result)

        except Exception as e:
            logger.error(f"FunASR 识别异常：{e}")
            return {'success': False, 'error': str(e), 'text': ''}

    def _parse_funasr_result(self, result: Dict) -> Dict[str, Any]:
        """解析 FunASR 识别结果"""
        # FunASR 返回格式可能不同，这里处理常见格式
        if 'text' in result:
            return {
                'success': True,
                'text': result['text'],
                'provider': 'funasr'
            }
        elif 'result' in result:
            return {
                'success': True,
                'text': result.get('result', ''),
                'provider': 'funasr'
            }
        else:
            logger.warning(f"FunASR 返回格式未知：{result}")
            return {
                'success': True,
                'text': str(result),
                'provider': 'funasr'
            }

    # ==================== 实时语音识别（WebSocket） ====================

    def start_realtime_recognition(self) -> bool:
        """
        启动实时语音识别会话

        使用 WebSocket 连接到 ASR 服务，用于流式识别

        Returns:
            bool: 是否成功启动
        """
        try:
            import websocket

            if self.provider == 'funasr':
                ws_url = f"ws://{self.funasr_url}/ws"
            else:
                # 阿里云实时识别需要更复杂的协议
                logger.error("阿里云实时识别暂未实现")
                return False

            self.ws = websocket.create_connection(ws_url)

            # 发送初始化配置
            init_msg = json.dumps({
                'type': 'config',
                'format': 'pcm',
                'sample_rate': 16000,
                'encoding': 'raw'
            })
            self.ws.send(init_msg)

            logger.info("实时识别会话已启动")
            return True

        except Exception as e:
            logger.error(f"启动实时识别失败：{e}")
            return False

    def send_audio_chunk(self, audio_chunk: bytes) -> Optional[str]:
        """
        发送音频片段进行识别

        Args:
            audio_chunk: PCM 音频数据

        Returns:
            str: 识别结果（如果有）
        """
        if not self.ws:
            logger.error("实时识别会话未启动")
            return None

        try:
            # 发送音频数据
            self.ws.send(audio_chunk, opcode=websocket.ABNF.OPCODE_BINARY)

            # 尝试接收结果（非阻塞）
            self.ws.settimeout(0.1)
            try:
                result = self.ws.recv()
                result_data = json.loads(result)

                if result_data.get('type') == 'result':
                    return result_data.get('text', '')

            except:
                # 超时，无识别结果
                pass

            return None

        except Exception as e:
            logger.error(f"发送音频片段失败：{e}")
            return None

    def stop_realtime_recognition(self) -> Optional[str]:
        """
        停止实时识别会话

        Returns:
            str: 最终识别结果
        """
        if not self.ws:
            return None

        try:
            # 发送结束消息
            end_msg = json.dumps({'type': 'end'})
            self.ws.send(end_msg)

            # 接收最终结果
            self.ws.settimeout(1)
            result = self.ws.recv()
            result_data = json.loads(result)

            self.ws.close()
            self.ws = None

            return result_data.get('text', '')

        except Exception as e:
            logger.error(f"停止实时识别失败：{e}")
            self.ws = None
            return None

    # ==================== 统一接口 ====================

    def recognize(
        self,
        audio_data: bytes,
        format: str = 'pcm',
        sample_rate: int = 24000
    ) -> Dict[str, Any]:
        """
        统一识别接口

        Args:
            audio_data: 音频数据
            format: 音频格式
            sample_rate: 采样率

        Returns:
            dict: 识别结果 {'success': bool, 'text': str}
        """
        if self.provider == 'volcengine_doubao':
            return self.volcengine_doubao_recognize(audio_data, format, sample_rate)

        elif self.provider == 'funasr':
            return self.funasr_online_recognize(audio_data, format, sample_rate)

        elif self.provider == 'aliyun':
            # 阿里云需要先将音频上传到 OSS，这里简化处理
            logger.warning("阿里云识别需要音频 URL，请使用 aliyun_rest_api_recognize")
            return {'success': False, 'error': '需要提供音频 URL'}

        else:
            logger.error(f"未知的 ASR 提供商：{self.provider}")
            return {'success': False, 'error': '未知的 ASR 提供商'}


# 全局客户端实例
_asr_client: Optional[ASRClient] = None


def get_asr_client() -> Optional[ASRClient]:
    """获取 ASR 客户端单例"""
    global _asr_client
    return _asr_client


def init_asr_client(
    provider: str = 'volcengine_doubao',
    access_key_id: Optional[str] = None,
    access_key_secret: Optional[str] = None,
    app_key: Optional[str] = None,
    server_url: Optional[str] = None,
    # 火山引擎豆包 ASR 参数
    doubao_appid: Optional[str] = None,
    doubao_access_token: Optional[str] = None,
    doubao_resource_id: Optional[str] = None
) -> ASRClient:
    """初始化 ASR 客户端"""
    global _asr_client
    _asr_client = ASRClient(
        provider=provider,
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        app_key=app_key,
        server_url=server_url,
        doubao_appid=doubao_appid,
        doubao_access_token=doubao_access_token,
        doubao_resource_id=doubao_resource_id
    )
    logger.info(f"ASR 客户端已初始化，提供商：{provider}")
    return _asr_client

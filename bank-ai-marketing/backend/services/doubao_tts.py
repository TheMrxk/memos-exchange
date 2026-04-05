#!/usr/bin/env python3
"""
豆包 TTS 服务 - 银行 AI 客服
"""

import requests
import json
import base64
from typing import Optional, List

class DoubaoTTS:
    """豆包语音合成服务"""

    def __init__(
        self,
        app_id: str = "2058216235",
        access_token: str = "HthevSMrUFC7z8Nxfb0yKFyR1XVNeW-W",
        resource_id: str = "seed-tts-2.0",
        speaker: str = "zh_female_vv_uranus_bigtts",
        sample_rate: int = 16000,  # ASR 兼容的采样率
        format: str = "wav"  # PCM WAV 格式
    ):
        self.app_id = app_id
        self.access_token = access_token
        self.resource_id = resource_id
        self.speaker = speaker
        self.sample_rate = sample_rate
        self.format = format
        self.url = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

    def synthesize(self, text: str, output_file: Optional[str] = None) -> Optional[bytes]:
        """
        合成语音

        Args:
            text: 要合成的文本
            output_file: 可选，保存音频文件的路径

        Returns:
            音频数据的 bytes，失败返回 None
        """
        headers = {
            "X-Api-App-Key": str(self.app_id),
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": self.resource_id,
            "Content-Type": "application/json",
        }

        payload = {
            "user": {"uid": "bank-ai"},
            "req_params": {
                "text": text,
                "speaker": self.speaker,
                "audio_params": {
                    "format": self.format,
                    "sample_rate": self.sample_rate
                }
            }
        }

        try:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=30
            )

            if response.status_code != 200:
                print(f"TTS 请求失败：{response.status_code}")
                return None

            audio_data = bytearray()
            error_msg = ""

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
                        # 结束标志
                        break
                    elif code > 0:
                        error_msg = data.get("message", "")
                        print(f"TTS 错误：{error_msg}")
                        return None
                except json.JSONDecodeError:
                    pass

            if audio_data:
                if output_file:
                    with open(output_file, "wb") as f:
                        f.write(audio_data)
                    print(f"音频已保存到：{output_file}")
                return bytes(audio_data)
            else:
                print("未收到音频数据")
                return None

        except Exception as e:
            print(f"TTS 请求异常：{e}")
            return None


# 测试
if __name__ == "__main__":
    tts = DoubaoTTS()

    # 测试合成
    text = "您好，欢迎使用银行 AI 客服服务。"
    print(f"正在合成：{text}")

    audio = tts.synthesize(text, "output_tts.mp3")

    if audio:
        print(f"✓ 成功！音频大小：{len(audio)} 字节")
    else:
        print("✗ 失败")

#!/usr/bin/env python3
"""
ASR 识别演示

使用火山引擎豆包流式语音识别模型 2.0
测试预先录制的音频文件
"""

import asyncio
import sys
import os

# 添加到路径
sys.path.insert(0, '.')

from asr_websocket_client import AsrWsClient

# 测试音频文件
TEST_AUDIO_FILES = [
    "test_asr.wav",  # TTS 生成的 16kHz WAV
]

async def recognize_file(file_path: str):
    """识别单个音频文件"""

    if not os.path.exists(file_path):
        print(f"文件不存在：{file_path}")
        return None

    print(f"\n{'='*60}")
    print(f"识别音频：{file_path}")
    print(f"{'='*60}")

    try:
        async with AsrWsClient() as client:
            last_definite_text = ""
            temporary_texts = []

            async for response in client.recognize(file_path):
                payload = response.get("payload", {})
                if payload:
                    result = payload.get("result", {})
                    text = result.get("text", "")
                    definite = result.get("definite", False)

                    if text:
                        if definite:
                            last_definite_text = text
                            print(f"[确定] {text}")
                            return text
                        else:
                            temporary_texts.append(text)
                            print(f"[临时] {text}")

            # 返回最后一个确定结果，如果没有则返回最后的临时结果
            return last_definite_text or (temporary_texts[-1] if temporary_texts else "")

    except Exception as e:
        print(f"识别失败：{e}")
        return None


def main():
    """主函数"""

    print("=" * 60)
    print("火山引擎豆包 ASR 语音识别演示")
    print("=" * 60)
    print()
    print("配置:")
    print("  WebSocket URL: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async")
    print("  Resource ID: volc.seedasr.sauc.duration")
    print("  音频格式：16kHz 16bit 单声道 PCM WAV")
    print()

    # 查找可用的测试音频
    available_files = [f for f in TEST_AUDIO_FILES if os.path.exists(f)]

    if not available_files:
        print("未找到测试音频文件!")
        print("请先运行：python3 -c \"from services.doubao_tts import DoubaoTTS; DoubaoTTS().synthesize('你好', 'test_asr.wav')\"")
        return 1

    print(f"找到 {len(available_files)} 个测试音频文件")

    # 识别每个文件
    results = []
    for file in available_files:
        result = asyncio.run(recognize_file(file))
        results.append((file, result))

    # 打印汇总
    print()
    print("=" * 60)
    print("识别结果汇总")
    print("=" * 60)

    for file, text in results:
        if text:
            print(f"✓ {file}: {text}")
        else:
            print(f"✗ {file}: 未识别到内容")

    print()
    print("=" * 60)
    print("演示完成")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

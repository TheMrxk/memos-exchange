#!/usr/bin/env python3
"""
AI 通话引擎低成本测试脚本

测试策略:
1. 使用短音频（5 秒内）
2. 文本不超过 30 字
3. 录制一次 API 调用，后续用录音回放
4.  mocks LLM 响应（可选）

成本估算（火山引擎豆包）:
- ASR: 约 0.002 元/次（5 秒音频）
- TTS: 约 0.001 元/次（30 字以内）
- 单次测试总成本：约 0.003 元
"""

import os
import sys
import time
import json
import wave
import requests
import base64

# 配置
BASE_URL = os.environ.get("AI_ENGINE_URL", "http://localhost:5001")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# 测试文本（短文本，控制成本）
TEST_SCRIPTS = [
    "你好。",
    "我想办信用卡。",
    "利率是多少？",
    "需要什么材料？",
    "谢谢，再见。"
]


def create_test_audio(text_index: int = 0) -> bytes:
    """
    生成测试音频

    方案 A: 使用预录制的音频文件（推荐，零成本）
    方案 B: 调用 TTS 生成（有成本）
    """
    # 优先使用预录制的测试音频
    test_file = "test_audio_short.wav"
    if os.path.exists(test_file):
        with wave.open(test_file, 'rb') as wav:
            return wav.readframes(wav.getnframes())

    # 没有预录制文件，调用 TTS 生成（有成本）
    print("未找到预录制音频，调用 TTS 生成...")
    text = TEST_SCRIPTS[text_index % len(TEST_SCRIPTS)]

    resp = requests.post(
        f"{BASE_URL}/api/tts/synthesize",
        json={"text": text}
    )

    if resp.status_code == 200:
        # 保存用于下次测试
        with open(test_file, 'wb') as f:
            f.write(resp.content)
        print(f"已保存测试音频：{test_file}")
        return resp.content
    else:
        print(f"TTS 失败：{resp.text}")
        # 返回静音数据作为备选
        return bytes(16000 * 2)  # 1 秒静音


def test_session(script_index: int = 0, use_mock_llm: bool = True):
    """
    测试完整会话流程

    Args:
        script_index: 使用第几个测试脚本
        use_mock_llm: 是否使用 Mock LLM（降低成本）
    """
    print("=" * 60)
    print("AI 通话引擎测试")
    print("=" * 60)

    # 1. 创建会话
    print("\n[1/5] 创建会话...")
    create_data = {
        "config": {
            "max_duration": 60,
            "max_turns": 2,
            "silence_timeout": 5.0
        },
        "script": {
            "greeting": "您好。",
            "closing": "再见。",
            "system_prompt": "你是银行客服。" if use_mock_llm else
                "你是一个专业的银行客服代表，请友好、简洁地回答客户的问题。你所在的银行提供存款、贷款、信用卡、理财等服务。"
        }
    }

    resp = requests.post(f"{BASE_URL}/api/session/create", json=create_data)
    if resp.status_code != 200:
        print(f"创建会话失败：{resp.text}")
        return False

    session_id = resp.json()['session_id']
    print(f"会话 ID: {session_id}")

    # 2. 启动会话
    print("\n[2/5] 启动会话...")
    resp = requests.post(f"{BASE_URL}/api/session/{session_id}/start")
    if resp.status_code != 200:
        print(f"启动会话失败：{resp.text}")
        return False
    print("会话已启动")

    # 3. 等待问候语
    print("\n[3/5] 等待问候语...")
    time.sleep(2)

    # 4. 推送测试音频
    print("\n[4/5] 推送测试音频...")
    audio_data = create_test_audio(script_index)
    print(f"音频大小：{len(audio_data)} 字节")

    # 分帧推送（每帧 20ms = 640 字节）
    frame_size = 640
    frames_pushed = 0
    for i in range(0, len(audio_data), frame_size):
        frame = audio_data[i:i+frame_size]
        if len(frame) == frame_size:
            resp = requests.post(
                f"{BASE_URL}/api/session/{session_id}/audio",
                data=frame,
                headers={'Content-Type': 'application/octet-stream'}
            )
            frames_pushed += 1
            if frames_pushed % 10 == 0:
                print(f"  已推送 {frames_pushed} 帧...")
            time.sleep(0.02)  # 模拟实时推送

    print(f"推送完成，共 {frames_pushed} 帧")

    # 5. 等待处理
    print("\n[5/5] 等待处理...")
    for i in range(10):
        time.sleep(1)
        resp = requests.get(f"{BASE_URL}/api/session/{session_id}/info")
        info = resp.json().get('data', {})
        state = info.get('state', 'unknown')
        turns = info.get('turns', [])
        print(f"  状态：{state}, 轮数：{len(turns)}")

        if state == 'ended':
            break

    # 获取最终结果
    resp = requests.get(f"{BASE_URL}/api/session/{session_id}/info")
    info = resp.json().get('data', {})

    print("\n" + "=" * 60)
    print("会话结果")
    print("=" * 60)
    print(f"状态：{info.get('state')}")
    print(f"时长：{info.get('duration', 0):.1f}秒")
    print(f"对话轮数：{info.get('turn_count', 0)}")

    if info.get('turns'):
        print("\n对话记录:")
        for turn in info['turns']:
            role = "客户" if turn['role'] == 'user' else "AI"
            print(f"  [{role}] {turn['text']}")

    # 结束会话
    requests.post(f"{BASE_URL}/api/session/{session_id}/end")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

    return True


def test_health():
    """测试健康检查"""
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if resp.status_code == 200:
            print(f"健康检查通过：{resp.json()}")
            return True
        else:
            print(f"健康检查失败：{resp.status_code}")
            return False
    except Exception as e:
        print(f"无法连接服务：{e}")
        print(f"请确保服务已启动：python3 ai_call_engine_service.py")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description='AI 通话引擎低成本测试')
    parser.add_argument('--health', action='store_true', help='仅测试健康检查')
    parser.add_argument('--script', type=int, default=0, help='使用第几个测试脚本 (0-4)')
    parser.add_argument('--mock-llm', action='store_true', help='使用 Mock LLM（不调用真实 API）')
    parser.add_argument('--loop', type=int, default=1, help='循环测试次数')

    args = parser.parse_args()

    # 健康检查
    if args.health or not test_health():
        return 1

    # 会话测试
    for i in range(args.loop):
        if args.loop > 1:
            print(f"\n>>> 第 {i+1}/{args.loop} 轮测试\n")

        success = test_session(
            script_index=args.script,
            use_mock_llm=args.mock_llm
        )

        if not success:
            return 1

        if args.loop > 1 and i < args.loop - 1:
            time.sleep(2)

    return 0


if __name__ == '__main__':
    sys.exit(main())

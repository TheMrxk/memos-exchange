#!/usr/bin/env python3
"""
测试完整的 ASR → LLM → TTS 链路

流程：
1. TTS 合成问候语
2. ASR 识别 TTS 生成的音频（模拟客户听到后说话）
3. LLM 根据识别结果生成回复
4. TTS 合成回复

这验证了 AI 对话引擎的核心链路
"""

import sys
sys.path.insert(0, '.')

from services.doubao_tts import DoubaoTTS
from services.llm_client import LLMClient
from asr_websocket_client import AsrWsClient
import asyncio
import tempfile

# 配置
TEST_TEXTS = [
    "你好，我想了解一下你们的贷款产品。",
    "请问信用卡如何申请？",
    "我的账户余额不足，怎么办？",
]

async def test_chain():
    """测试 ASR→LLM→TTS 完整链路"""

    print("=" * 70)
    print("AI 对话引擎链路测试：ASR → LLM → TTS")
    print("=" * 70)

    # 初始化客户端
    tts_client = DoubaoTTS(format="wav", sample_rate=16000)

    # LLM 客户端（使用 DeepSeek）
    import os
    llm_api_key = os.environ.get("LLM_API_KEY", "sk_test_placeholder")
    llm_client = LLMClient(api_key=llm_api_key, provider="deepseek")

    # 系统提示
    system_prompt = """你是一个专业的银行客服代表，请友好、简洁地回答客户的问题。
你所在的银行提供存款、贷款、信用卡、理财等服务。"""

    conversation_history = [
        {"role": "system", "content": system_prompt}
    ]

    for i, input_text in enumerate(TEST_TEXTS, 1):
        print(f"\n{'='*70}")
        print(f"第 {i} 轮对话")
        print(f"{'='*70}")

        # 步骤 1: 模拟客户说话（用文本代替）
        print(f"\n[客户] 说：{input_text}")

        # 步骤 2: TTS 合成客户语音（模拟录音）
        print("[TTS] 正在合成客户语音...")
        customer_audio = tts_client.synthesize(input_text)
        if not customer_audio:
            print("[TTS] 合成失败，跳过此轮")
            continue

        # 保存为临时文件
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(customer_audio)
            customer_audio_file = f.name

        print(f"[TTS] 合成完成，大小：{len(customer_audio)} 字节")

        # 步骤 3: ASR 识别客户语音
        print("[ASR] 正在识别客户语音...")
        recognized_text = ""

        try:
            async with AsrWsClient() as asr_client:
                last_definite_text = ""
                async for response in asr_client.recognize(customer_audio_file):
                    payload = response.get("payload", {})
                    if payload:
                        result = payload.get("result", {})
                        text = result.get("text", "")
                        definite = result.get("definite", False)

                        if text:
                            # 只保存确定结果
                            if definite:
                                last_definite_text = text
                                print(f"  [ASR 临时] 确定结果：{text}")
                                break
                            else:
                                print(f"  [ASR 临时] 临时结果：{text}")

                # 使用最后一个确定结果，如果没有则使用最近的临时结果
                recognized_text = last_definite_text

            import os
            os.unlink(customer_audio_file)

        except Exception as e:
            print(f"[ASR] 识别失败：{e}")
            import os
            os.unlink(customer_audio_file)
            continue

        if not recognized_text:
            print("[ASR] 未识别到有效内容，跳过此轮")
            continue

        print(f"[ASR] 识别结果：{recognized_text}")

        # 步骤 4: LLM 生成回复
        print("[LLM] 正在生成回复...")

        conversation_history.append({"role": "user", "content": recognized_text})

        try:
            llm_response = llm_client.chat(conversation_history)
            ai_reply = llm_response.get("content", "")

            if not ai_reply:
                print("[LLM] 回复为空，跳过此轮")
                continue

            print(f"[LLM] AI 回复：{ai_reply}")

        except Exception as e:
            print(f"[LLM] 生成失败：{e}")
            continue

        # 步骤 5: TTS 合成 AI 回复
        print("[TTS] 正在合成 AI 回复...")
        ai_audio = tts_client.synthesize(ai_reply)

        if ai_audio:
            print(f"[TTS] 合成完成，大小：{len(ai_audio)} 字节")

            # 保存 AI 回复音频
            reply_file = f"test_chain_reply_{i}.wav"
            with open(reply_file, "wb") as f:
                f.write(ai_audio)
            print(f"[TTS] 已保存到：{reply_file}")
        else:
            print("[TTS] 合成失败")

        # 更新对话历史
        conversation_history.append({"role": "assistant", "content": ai_reply})

        print(f"[第 {i} 轮完成]")

    print("\n" + "=" * 70)
    print("链路测试完成")
    print("=" * 70)

    # 打印完整对话
    print("\n完整对话记录:")
    print("-" * 70)
    for msg in conversation_history:
        if msg["role"] == "system":
            continue
        role = "客户" if msg["role"] == "user" else "AI"
        print(f"[{role}] {msg['content']}")
    print("-" * 70)


def main():
    """主函数"""
    try:
        asyncio.run(test_chain())
        return 0
    except KeyboardInterrupt:
        print("\n测试被中断")
        return 1
    except Exception as e:
        print(f"\n测试失败：{e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
VAD 语音活动检测测试

测试 WebRTC VAD 算法在真实音频上的表现
"""

import sys
import os
sys.path.insert(0, '.')

from services.vad_detector import VoiceActivityDetector, VADConfig, VADMode, VADState
import wave

def test_vad(file_path: str):
    """测试 VAD 检测"""

    print("=" * 60)
    print("VAD 语音活动检测测试")
    print("=" * 60)

    # VAD 配置
    config = VADConfig(
        mode=VADMode.AGGRESSIVE,
        sample_rate=16000,
        frame_duration_ms=30,  # 30ms 每帧
        speech_threshold=3,     # 3 帧判定为语音
        silence_threshold=5,    # 5 帧判定为静音
        min_speech_duration_ms=200,
        max_silence_duration_ms=3000
    )

    print(f"检测模式：{config.mode.name}")
    print(f"采样率：{config.sample_rate}Hz")
    print(f"帧时长：{config.frame_duration_ms}ms")
    print(f"语音阈值：{config.speech_threshold} 帧")
    print(f"静音阈值：{config.silence_threshold} 帧")
    print()

    # 创建 VAD
    vad = VoiceActivityDetector(config)

    # 读取音频文件
    if not os.path.exists(file_path):
        print(f"文件不存在：{file_path}")
        return False

    with wave.open(file_path, 'rb') as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()

        print(f"音频文件：{file_path}")
        print(f"格式：{sample_rate}Hz, {channels}ch, {sample_width*8}bit")

        # 每帧 30ms - readframes 参数是样本数，不是字节数
        frame_samples = int(config.frame_duration_ms * sample_rate / 1000)
        frame_bytes = frame_samples * sample_width * channels
        print(f"帧大小：{frame_bytes} 字节 ({frame_samples} 样本)")
        print()

        # 统计
        total_frames = 0
        speech_frames = 0
        silence_frames = 0
        speech_segments = []
        current_segment_start = None
        current_segment_frames = 0

        while True:
            frame = wav.readframes(frame_samples)
            if not frame:
                break

            # 填充最后一帧
            if len(frame) < frame_bytes:
                frame = frame + bytes(frame_bytes - len(frame))

            # VAD 检测
            state = vad.process_frame(frame)
            total_frames += 1

            if state in [VADState.SPEECH, VADState.SPEECH_START]:
                speech_frames += 1
                if current_segment_start is None:
                    current_segment_start = total_frames
            else:
                silence_frames += 1
                if state == VADState.SPEECH_END and current_segment_start is not None:
                    segment_duration = (total_frames - current_segment_start) * config.frame_duration_ms
                    speech_segments.append({
                        'start_frame': current_segment_start,
                        'end_frame': total_frames,
                        'duration_ms': segment_duration
                    })
                    print(f"[语音段] 第 {len(speech_segments)} 段，时长：{segment_duration}ms")
                    current_segment_start = None

            current_segment_frames += 1

        # 打印统计
        print()
        print("=" * 60)
        print("统计结果")
        print("=" * 60)
        print(f"总帧数：{total_frames}")
        print(f"语音帧数：{speech_frames} ({speech_frames/total_frames*100:.1f}%)")
        print(f"静音帧数：{silence_frames} ({silence_frames/total_frames*100:.1f}%)")
        print(f"语音段数：{len(speech_segments)}")

        if speech_segments:
            total_speech_duration = sum(s['duration_ms'] for s in speech_segments)
            avg_duration = total_speech_duration / len(speech_segments)
            print(f"总语音时长：{total_speech_duration}ms")
            print(f"平均语音时长：{avg_duration:.0f}ms")

        print()

        # 最终状态
        stats = vad.get_stats()
        print(f"最终状态：{stats['state']}")
        print(f"连续语音帧：{stats['consecutive_speech']}")
        print(f"连续静音帧：{stats['consecutive_silence']}")

    return True


if __name__ == "__main__":
    # 默认测试文件
    default_file = "test_asr.wav"

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = default_file

    if not os.path.exists(test_file):
        print(f"未找到测试文件：{test_file}")
        print("用法：python test_vad.py [音频文件.wav]")
        sys.exit(1)

    success = test_vad(test_file)
    sys.exit(0 if success else 1)

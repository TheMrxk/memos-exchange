#!/usr/bin/env python3
"""
LLM 记忆摘要生成器

支持的服务商：
- OpenAI (GPT-3.5/4)
- Anthropic (Claude)
- DeepSeek
- 其他兼容 OpenAI 格式的 API

配置方式：
1. 环境变量
2. 配置文件 ~/.openclaw/workspace/llm_config.json
"""

import os
import json
from typing import Optional, Dict
from pathlib import Path


class LLMSummarizer:
    """大模型摘要生成器"""

    # 支持的提供商
    PROVIDERS = {
        'openai': {
            'api_url': 'https://api.openai.com/v1/chat/completions',
            'model_param': 'model',
            'auth_header': 'Authorization',
            'auth_prefix': 'Bearer '
        },
        'anthropic': {
            'api_url': 'https://api.anthropic.com/v1/messages',
            'model_param': 'model',
            'auth_header': 'x-api-key',
            'auth_prefix': ''
        },
        'deepseek': {
            'api_url': 'https://api.deepseek.com/chat/completions',
            'model_param': 'model',
            'auth_header': 'Authorization',
            'auth_prefix': 'Bearer '
        },
        'dashscope': {
            'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
            'model_param': 'model',
            'auth_header': 'Authorization',
            'auth_prefix': 'Bearer '
        },
        'dashscope_coding': {
            'api_url': 'https://coding.dashscope.aliyuncs.com/v1/chat/completions',
            'model_param': 'model',
            'auth_header': 'Authorization',
            'auth_prefix': 'Bearer '
        },
        'custom': {
            'api_url': '',  # 用户自定义
            'model_param': 'model',
            'auth_header': 'Authorization',
            'auth_prefix': 'Bearer '
        }
    }

    # 摘要提示词模板（综合版：类型分类 + 置信度 + 上下文感知）
    SUMMARIZE_PROMPT = """你是一个专业的用户记忆提取助手。请从对话中识别并提取值得长期保存的用户信息。

【对话内容】
用户：{user_content}
助手：{assistant_content}

【记忆类型】
请识别以下类型的信息：
- 偏好 (preference)：喜欢/不喜欢的事物、习惯、倾向、口味
- 技能 (skill)：掌握的能力、技术、语言、专业领域
- 事实 (fact)：个人信息（职业、地点、关系、身份等）
- 经历 (experience)：完成的事情、成就、重要事件、去过的地方

【信号词识别】
- 偏好信号：喜欢、讨厌、习惯、总是、经常、偏爱、爱...
- 技能信号：会、擅长、做过、负责、开发过、熟悉...
- 事实信号：我是、我在、我有、从事、住、住在...
- 经历信号：完成了、参与了、去过、学过、考过...

【过滤规则】
请忽略以下内容：
- 临时情绪（今天好累、心情不好）
- 一次性事件（明天开会、等一下）
- 假设性陈述（如果我有时间、改天）
- 对助手的评价（你很聪明、谢谢）
- 上下文依赖的临时请求（帮我写这个、查一下）

【置信度评估】
为每条记忆评估置信度：
- 0.9-1.0：用户明确陈述的个人事实
- 0.7-0.9：用户多次提及或强烈表达的观点
- 0.5-0.7：从上下文中合理推断的信息
- <0.5：不确定的推断，应忽略

【输出格式】
请返回 JSON 格式：
{{
  "memories": [
    {{"content": "用户...", "type": "preference|skill|fact|experience", "confidence": 0.8}}
  ]
}}

如果没有有效信息，返回 {{"memories": []}}

【提取结果】"""

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化摘要生成器

        Args:
            config: 配置字典，包含：
                - provider: 服务商名称 (openai/anthropic/deepseek/custom)
                - api_key: API 密钥
                - model: 模型名称
                - api_url: 自定义 API 地址（可选）
        """
        self.config = config or self._load_config()
        self.enabled = self.config.get('enabled', False)

    def _load_config(self) -> Dict:
        """从配置文件加载配置"""
        config_path = Path.home() / '.openclaw' / 'workspace' / 'llm_config.json'

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载 LLM 配置文件失败：{e}")

        # 尝试从环境变量获取配置
        return {
            'enabled': os.environ.get('LLM_SUMMARIZER_ENABLED', 'false').lower() == 'true',
            'provider': os.environ.get('LLM_PROVIDER', 'custom'),
            'api_key': os.environ.get('LLM_API_KEY', ''),
            'model': os.environ.get('LLM_MODEL', ''),
            'api_url': os.environ.get('LLM_API_URL', '')
        }

    def summarize(self, user_content: str, assistant_content: str = None) -> Optional[str]:
        """
        使用大模型生成记忆摘要

        Args:
            user_content: 用户消息内容
            assistant_content: 助手回复内容（可选）

        Returns:
            摘要文本（JSON 格式字符串），失败返回 None
        """
        if not self.enabled:
            return None

        if not self.config.get('api_key'):
            print("[LLM Summarizer] API Key 未配置，跳过摘要")
            return None

        prompt = self.SUMMARIZE_PROMPT.format(
            user_content=user_content[:1000],  # 限制长度
            assistant_content=(assistant_content or '')[:1000]
        )

        provider = self.config.get('provider', 'custom')

        try:
            if provider == 'anthropic':
                result = self._call_anthropic(prompt)
            else:
                result = self._call_openai_format(prompt)

            # 解析 JSON 结果并格式化输出
            if result:
                return self._parse_llm_result(result)
            return None
        except Exception as e:
            print(f"[LLM Summarizer] 调用失败：{e}")
            return None

    def _parse_llm_result(self, result: str) -> Optional[str]:
        """
        解析 LLM 返回的 JSON 结果，格式化为可读文本

        Args:
            result: LLM 返回的 JSON 字符串

        Returns:
            格式化后的记忆文本
        """
        try:
            # 尝试清理可能的 markdown 标记
            result = result.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.endswith('```'):
                result = result[:-3]
            result = result.strip()

            data = json.loads(result)

            if 'memories' not in data or not data['memories']:
                return None

            # 过滤低置信度记忆
            valid_memories = [
                m for m in data['memories']
                if m.get('confidence', 0) >= 0.5 and m.get('content')
            ]

            if not valid_memories:
                return None

            # 格式化输出：每条记忆一行
            formatted = []
            for mem in valid_memories:
                content = mem.get('content', '')
                mem_type = mem.get('type', 'fact')
                confidence = mem.get('confidence', 0.5)
                formatted.append(f"[{mem_type}] {content} (置信度：{confidence})")

            return '\n'.join(formatted)

        except json.JSONDecodeError as e:
            print(f"[LLM Summarizer] JSON 解析失败：{e}，原始结果：{result[:200]}")
            # 如果 JSON 解析失败，返回原始结果
            return result if result.strip() else None
        except Exception as e:
            print(f"[LLM Summarizer] 结果处理失败：{e}")
            return None

    def _call_openai_format(self, prompt: str) -> Optional[str]:
        """调用 OpenAI 格式的 API（OpenAI/DeepSeek/自定义）"""
        import urllib.request
        import urllib.error

        api_url = self.config.get('api_url') or self.PROVIDERS.get(
            self.config.get('provider', 'custom'), {}
        ).get('api_url', '')

        if not api_url:
            raise ValueError("API URL 未配置")

        data = {
            "model": self.config.get('model', 'gpt-3.5-turbo'),
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000  # 增加输出长度限制，支持多条记忆
        }

        req = urllib.request.Request(
            api_url,
            data=json.dumps(data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                self.PROVIDERS['custom']['auth_header']:
                    self.PROVIDERS['custom']['auth_prefix'] + self.config.get('api_key', '')
            },
            method='POST'
        )

        # 增加超时时间到 60 秒
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            return content if content else None

    def _call_anthropic(self, prompt: str) -> Optional[str]:
        """调用 Anthropic Claude API"""
        import urllib.request
        import urllib.error

        data = {
            "model": self.config.get('model', 'claude-sonnet-4-20250514'),
            "max_tokens": 1000,  # 增加输出长度限制，支持多条记忆
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        req = urllib.request.Request(
            self.PROVIDERS['anthropic']['api_url'],
            data=json.dumps(data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'x-api-key': self.config.get('api_key', ''),
                'anthropic-version': '2023-06-01'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            content = result.get('content', [{}])[0].get('text', '').strip()
            return content if content else None


# 便捷函数
def summarize_with_llm(user_content: str, assistant_content: str = None,
                       config: Dict = None) -> Optional[str]:
    """
    使用大模型生成记忆摘要的便捷函数

    Args:
        user_content: 用户消息内容
        assistant_content: 助手回复内容
        config: 可选的自定义配置

    Returns:
        摘要文本
    """
    summarizer = LLMSummarizer(config)
    return summarizer.summarize(user_content, assistant_content)


if __name__ == '__main__':
    # 测试
    test_user = "唉最近心情不好，总想吃甜食，还会找个地方喝一杯美式"
    test_assistant = "嗯嗯，吃甜食和喝咖啡确实能帮助缓解情绪..."

    result = summarize_with_llm(test_user, test_assistant)
    if result:
        print(f"摘要：{result}")
    else:
        print("未生成摘要（可能未配置 API）")

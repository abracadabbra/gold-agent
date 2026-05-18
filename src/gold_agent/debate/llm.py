"""LLM 调用封装 — OpenAI 兼容端点"""

import json

from openai import AsyncOpenAI
import logging
logger = logging.getLogger(__name__)

from gold_agent.config import settings


def get_llm_client(model: str = "gpt-4.1") -> AsyncOpenAI:
    """获取 OpenAI 兼容客户端"""
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


async def chat_completion(
    messages: list[dict],
    model: str = "gpt-4.1",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    response_format: dict | None = None,
) -> str:
    """
    调用 LLM 聊天补全

    Args:
        messages: [{"role": "system/user/assistant", "content": "..."}]
        model: 模型名
        temperature: 温度
        max_tokens: 最大输出 token
        response_format: JSON 模式等

    Returns:
        LLM 输出文本
    """
    client = get_llm_client(model)

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    try:
        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        logger.info(f"LLM 调用完成: model={model}, tokens={tokens_used}, 长度={len(content)}")
        return content
    except Exception as e:
        logger.error(f"LLM 调用失败: model={model}, error={e}")
        raise


async def chat_completion_json(
    messages: list[dict],
    model: str = "gpt-4.1",
    temperature: float = 0.3,
) -> dict:
    """调用 LLM 并返回 JSON 解析结果"""
    text = await chat_completion(
        messages=messages,
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试从 markdown 代码块提取 JSON
        import re
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"LLM 输出不是有效 JSON: {text[:200]}")

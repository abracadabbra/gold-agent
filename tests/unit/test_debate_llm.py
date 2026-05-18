"""LLM 调用封装单元测试 — llm.py"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gold_agent.debate.llm import (
    chat_completion,
    chat_completion_json,
    get_llm_client,
)


def _make_fake_response(content: str):
    """创建模拟 OpenAI 响应"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.usage.total_tokens = 50
    return mock_response


# ============================================================
# get_llm_client
# ============================================================


class TestGetLlmClient:
    """测试 get_llm_client"""

    def test_creates_client_with_settings(self):
        """使用 settings 中的 api_key 和 base_url 创建客户端"""
        from gold_agent.config import settings

        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            get_llm_client(model="gpt-4.1")

            mock_client_cls.assert_called_once_with(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )


# ============================================================
# chat_completion
# ============================================================


class TestChatCompletion:
    """测试 chat_completion"""

    @pytest.mark.asyncio
    async def test_success(self):
        """正常返回 LLM 输出文本"""
        fake = _make_fake_response("test output")
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=fake)

            result = await chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                model="gpt-4.1",
            )
            assert result == "test output"

    @pytest.mark.asyncio
    async def test_openai_exception_propagated(self):
        """OpenAI 异常应向上传播"""
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API Error"),
            )

            with pytest.raises(Exception, match="API Error"):
                await chat_completion(
                    messages=[{"role": "user", "content": "hello"}],
                    model="gpt-4.1",
                )

    @pytest.mark.asyncio
    async def test_passes_kwargs_to_openai(self):
        """参数正确传递给 OpenAI 客户端"""
        fake = _make_fake_response("ok")
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=fake)

            await chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4.1",
                temperature=0.5,
                max_tokens=1000,
            )

            mock_client.chat.completions.create.assert_called_once_with(
                model="gpt-4.1",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.5,
                max_tokens=1000,
            )

    @pytest.mark.asyncio
    async def test_passes_response_format(self):
        """response_format 参数正确传递"""
        fake = _make_fake_response('{"key": "value"}')
        fmt = {"type": "json_object"}
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=fake)

            await chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4.1",
                response_format=fmt,
            )

            _, kwargs = mock_client.chat.completions.create.call_args
            assert kwargs["response_format"] == fmt


# ============================================================
# chat_completion_json
# ============================================================


class TestChatCompletionJson:
    """测试 chat_completion_json"""

    @pytest.mark.asyncio
    async def test_normal_json(self):
        """正常 JSON 响应被正确解析"""
        expected = {"key": "value", "number": 42}
        fake = _make_fake_response(json.dumps(expected))
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=fake)

            result = await chat_completion_json(
                messages=[{"role": "user", "content": "json please"}],
                model="gpt-4.1",
            )
            assert result == expected

    @pytest.mark.asyncio
    async def test_markdown_code_block_json(self):
        """从 ```json ... ``` 代码块中提取 JSON"""
        expected = {"key": "value"}
        markdown_text = 'Some text\n```json\n{"key": "value"}\n```\nmore text'
        fake = _make_fake_response(markdown_text)
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=fake)

            result = await chat_completion_json(
                messages=[{"role": "user", "content": "json please"}],
                model="gpt-4.1",
            )
            assert result == expected

    @pytest.mark.asyncio
    async def test_markdown_code_block_no_lang(self):
        """从 ``` (无语言标记) 代码块中提取 JSON"""
        expected = {"key": "value"}
        markdown_text = 'Some text\n```\n{"key": "value"}\n```'
        fake = _make_fake_response(markdown_text)
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=fake)

            result = await chat_completion_json(
                messages=[{"role": "user", "content": "json please"}],
                model="gpt-4.1",
            )
            assert result == expected

    @pytest.mark.asyncio
    async def test_invalid_json_raises_value_error(self):
        """无效 JSON 响应抛出 ValueError"""
        fake = _make_fake_response("not valid json at all")
        with patch("gold_agent.debate.llm.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(return_value=fake)

            with pytest.raises(ValueError, match="不是有效 JSON"):
                await chat_completion_json(
                    messages=[{"role": "user", "content": "json"}],
                    model="gpt-4.1",
                )

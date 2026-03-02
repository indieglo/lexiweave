"""Tests for the LLM client wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lexiweave.utils.cache import ResponseCache
from lexiweave.utils.llm import LLMClient, LLMError, LLMResponse


class TestLLMClientInit:
    def test_missing_api_key_raises(self) -> None:
        with pytest.raises(LLMError, match="API key is required"):
            LLMClient(api_key="")

    def test_creates_with_valid_key(self) -> None:
        with patch("lexiweave.utils.llm.anthropic.Anthropic"):
            client = LLMClient(api_key="test-key")
            assert client.model == "claude-sonnet-4-5-20250929"


class TestLLMGenerate:
    def _make_client(self, cache: ResponseCache | None = None) -> LLMClient:
        with patch("lexiweave.utils.llm.anthropic.Anthropic"):
            return LLMClient(api_key="test-key", cache=cache)

    def _mock_response(self, client: LLMClient, text: str, tokens: int = 100) -> None:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=text)]
        mock_msg.usage = MagicMock(input_tokens=tokens // 2, output_tokens=tokens // 2)
        client._client.messages.create = MagicMock(return_value=mock_msg)

    def test_generate_returns_response(self) -> None:
        client = self._make_client()
        self._mock_response(client, "Hello world")

        result = client.generate("Say hello")

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello world"
        assert result.cached is False
        assert result.tokens_used == 100

    def test_generate_with_system_prompt(self) -> None:
        client = self._make_client()
        self._mock_response(client, "Hola")

        client.generate("Say hello", system_prompt="You speak Spanish")

        call_kwargs = client._client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You speak Spanish"

    def test_generate_uses_cache(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        client = self._make_client(cache=cache)
        self._mock_response(client, "API response")

        # First call hits API
        result1 = client.generate("test prompt")
        assert result1.cached is False

        # Second call uses cache
        result2 = client.generate("test prompt")
        assert result2.cached is True
        assert result2.content == "API response"

        # API was only called once
        assert client._client.messages.create.call_count == 1

    def test_generate_without_cache(self) -> None:
        client = self._make_client(cache=None)
        self._mock_response(client, "response")

        result = client.generate("prompt")
        assert result.content == "response"
        assert result.cached is False


class TestLLMGenerateJSON:
    def _make_client(self) -> LLMClient:
        with patch("lexiweave.utils.llm.anthropic.Anthropic"):
            return LLMClient(api_key="test-key")

    def _mock_response(self, client: LLMClient, text: str) -> None:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=text)]
        mock_msg.usage = MagicMock(input_tokens=50, output_tokens=50)
        client._client.messages.create = MagicMock(return_value=mock_msg)

    def test_parse_json_array(self) -> None:
        client = self._make_client()
        self._mock_response(client, '[{"word": "comer", "definition": "to eat"}]')

        result = client.generate_json("define words")
        assert isinstance(result, list)
        assert result[0]["word"] == "comer"

    def test_parse_json_object(self) -> None:
        client = self._make_client()
        self._mock_response(client, '{"word": "comer", "pos": "verb"}')

        result = client.generate_json("define word")
        assert isinstance(result, dict)
        assert result["word"] == "comer"

    def test_parse_json_in_code_block(self) -> None:
        client = self._make_client()
        self._mock_response(client, '```json\n[{"word": "comer"}]\n```')

        result = client.generate_json("define words")
        assert isinstance(result, list)
        assert result[0]["word"] == "comer"

    def test_invalid_json_raises(self) -> None:
        client = self._make_client()
        self._mock_response(client, "This is not JSON")

        with pytest.raises(LLMError, match="Failed to parse"):
            client.generate_json("test")


class TestLLMRetry:
    def test_retries_on_rate_limit(self) -> None:
        import anthropic as anthropic_module

        with patch("lexiweave.utils.llm.anthropic.Anthropic"):
            client = LLMClient(api_key="test-key")

        # First call rate limited, second succeeds
        mock_success = MagicMock()
        mock_success.content = [MagicMock(text="ok")]
        mock_success.usage = MagicMock(input_tokens=10, output_tokens=10)

        rate_limit_error = anthropic_module.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )

        client._client.messages.create = MagicMock(
            side_effect=[rate_limit_error, mock_success]
        )

        with patch("lexiweave.utils.llm.time.sleep"):
            result = client.generate("test")

        assert result.content == "ok"
        assert client._client.messages.create.call_count == 2

    def test_raises_on_client_error(self) -> None:
        import anthropic as anthropic_module

        with patch("lexiweave.utils.llm.anthropic.Anthropic"):
            client = LLMClient(api_key="test-key")

        client_error = anthropic_module.APIStatusError(
            message="bad request",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )

        client._client.messages.create = MagicMock(side_effect=client_error)

        with pytest.raises(LLMError):
            client.generate("test")

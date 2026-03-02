"""Anthropic API wrapper with caching and retry logic.

Thin wrapper around the anthropic Python SDK that integrates
with the file-based response cache.
"""

from __future__ import annotations

import json
import logging
import time

import anthropic
from pydantic import BaseModel

from lexiweave.utils.cache import ResponseCache

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


class LLMResponse(BaseModel):
    """Result of an LLM call."""

    content: str
    model: str
    tokens_used: int = 0
    cached: bool = False


class LLMError(Exception):
    """Raised when the LLM call fails after retries."""


class LLMClient:
    """Wrapper around the Anthropic API with caching."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        cache: ResponseCache | None = None,
        max_tokens: int = 4096,
    ):
        if not api_key:
            msg = (
                "Anthropic API key is required. "
                "Set it in config/global.json or run `lexiweave setup`."
            )
            raise LLMError(msg)

        self.model = model
        self.cache = cache
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> LLMResponse:
        """Generate a completion. Checks cache first, retries on failure."""
        # Check cache
        if self.cache is not None:
            cache_key = ResponseCache.make_key(prompt, self.model, system_prompt)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return LLMResponse(
                    content=cached,
                    model=self.model,
                    cached=True,
                )

        # Build messages
        messages = [{"role": "user", "content": prompt}]

        # Call API with retries
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                kwargs: dict = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "messages": messages,
                }
                if system_prompt:
                    kwargs["system"] = system_prompt

                response = self._client.messages.create(**kwargs)
                content = response.content[0].text
                tokens = response.usage.input_tokens + response.usage.output_tokens

                # Store in cache
                if self.cache is not None:
                    self.cache.put(
                        cache_key,
                        content,
                        model=self.model,
                        prompt_summary=prompt[:200],
                    )

                return LLMResponse(
                    content=content,
                    model=self.model,
                    tokens_used=tokens,
                    cached=False,
                )

            except anthropic.RateLimitError as e:
                last_error = e
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning("Rate limited, retrying in %.1fs (attempt %d)", delay, attempt + 1)
                time.sleep(delay)

            except anthropic.APIStatusError as e:
                last_error = e
                if e.status_code >= 500:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "API error %d, retrying in %.1fs (attempt %d)",
                        e.status_code,
                        delay,
                        attempt + 1,
                    )
                    time.sleep(delay)
                else:
                    raise LLMError(str(e)) from e

        raise LLMError(f"Failed after {MAX_RETRIES} retries: {last_error}") from last_error

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> dict | list:
        """Generate a completion and parse the response as JSON."""
        response = self.generate(prompt, system_prompt)

        # Try to extract JSON from the response
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (``` markers)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse LLM response as JSON: {e}\n{content[:500]}") from e

        return parsed

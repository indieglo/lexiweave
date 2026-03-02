# utils/

Shared utilities for LLM integration and caching.

## Module: cache.py

File-based response cache stored in `data/cache/`.

### Key Operations
- `ResponseCache(cache_dir)` — cache backed by JSON files
- `get(key) -> str | None` — retrieve cached response
- `put(key, response, metadata)` — store response with metadata
- `clear(older_than_days=None)` — purge stale entries

### Cache Key
SHA-256 hash of (prompt + model + system_prompt). Files stored as `data/cache/{hash}.json`.

## Module: llm.py

Thin wrapper around the Anthropic Python SDK.

### Key Operations
- `LLMClient(api_key, model, cache)` — create client
- `generate(prompt, system_prompt) -> LLMResponse` — single completion
- `generate_json(prompt, system_prompt) -> dict|list` — completion with JSON parsing

### Dependencies
- `anthropic` SDK
- `utils.cache` for response caching
- `config` for API key and model settings
- No other lexiweave modules

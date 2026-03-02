"""Tests for the file-based response cache."""

from __future__ import annotations

import json
from pathlib import Path

from lexiweave.utils.cache import ResponseCache


class TestCacheKey:
    def test_deterministic(self) -> None:
        key1 = ResponseCache.make_key("hello", "model-a", "system")
        key2 = ResponseCache.make_key("hello", "model-a", "system")
        assert key1 == key2

    def test_different_prompts_different_keys(self) -> None:
        key1 = ResponseCache.make_key("hello", "model-a")
        key2 = ResponseCache.make_key("world", "model-a")
        assert key1 != key2

    def test_different_models_different_keys(self) -> None:
        key1 = ResponseCache.make_key("hello", "model-a")
        key2 = ResponseCache.make_key("hello", "model-b")
        assert key1 != key2


class TestCachePutGet:
    def test_put_and_get(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("test_key", "test response", model="m1")
        assert cache.get("test_key") == "test response"

    def test_get_missing(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        assert cache.get("nonexistent") is None

    def test_get_missing_no_dir(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "does_not_exist")
        assert cache.get("anything") is None

    def test_put_creates_directory(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        cache = ResponseCache(cache_dir)
        cache.put("key", "value")
        assert cache_dir.exists()

    def test_put_overwrites(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("key", "first")
        cache.put("key", "second")
        assert cache.get("key") == "second"

    def test_stores_metadata(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("key", "response", model="claude-test", prompt_summary="test prompt")

        path = tmp_path / "cache" / "key.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["model"] == "claude-test"
        assert data["prompt_summary"] == "test prompt"
        assert data["created_at"] != ""

    def test_no_tmp_file_after_put(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("key", "value")
        tmp_file = (tmp_path / "cache" / "key.json.tmp")
        assert not tmp_file.exists()

    def test_unicode_content(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("key", "Pretérito vs Imperfecto: comíamos")
        assert cache.get("key") == "Pretérito vs Imperfecto: comíamos"


class TestCacheClear:
    def test_clear_all(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("a", "1")
        cache.put("b", "2")
        removed = cache.clear()
        assert removed == 2
        assert cache.size() == 0

    def test_clear_empty(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        assert cache.clear() == 0

    def test_clear_no_dir(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "nonexistent")
        assert cache.clear() == 0


class TestCacheSize:
    def test_size_empty(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        assert cache.size() == 0

    def test_size_with_entries(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("a", "1")
        cache.put("b", "2")
        assert cache.size() == 2

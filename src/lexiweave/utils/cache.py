"""File-based response cache for LLM calls.

Stores responses in data/cache/ as JSON files keyed by content hash.
Avoids redundant API calls during development and re-runs.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class CacheEntry(BaseModel):
    """A cached LLM response with metadata."""

    response: str
    model: str = ""
    prompt_summary: str = ""
    created_at: str = ""


class ResponseCache:
    """File-based cache for LLM responses."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    @staticmethod
    def make_key(prompt: str, model: str = "", system_prompt: str = "") -> str:
        """Generate a cache key from prompt + model + system_prompt."""
        content = f"{prompt}|{model}|{system_prompt}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _entry_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> str | None:
        """Retrieve a cached response by key. Returns None if not found."""
        path = self._entry_path(key)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        entry = CacheEntry(**data)
        return entry.response

    def put(
        self,
        key: str,
        response: str,
        model: str = "",
        prompt_summary: str = "",
    ) -> None:
        """Store a response in the cache."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        entry = CacheEntry(
            response=response,
            model=model,
            prompt_summary=prompt_summary[:200],
            created_at=datetime.now(UTC).isoformat(),
        )

        tmp_path = self._entry_path(key).with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(entry.model_dump(), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self._entry_path(key))

    def clear(self, older_than_days: int | None = None) -> int:
        """Remove cache entries. Returns count of entries removed.

        If older_than_days is None, removes all entries.
        """
        if not self.cache_dir.exists():
            return 0

        removed = 0
        now = datetime.now(UTC)

        for path in self.cache_dir.glob("*.json"):
            if older_than_days is not None:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                entry = CacheEntry(**data)
                if entry.created_at:
                    created = datetime.fromisoformat(entry.created_at)
                    age_days = (now - created).days
                    if age_days < older_than_days:
                        continue

            path.unlink()
            removed += 1

        return removed

    def size(self) -> int:
        """Return the number of cached entries."""
        if not self.cache_dir.exists():
            return 0
        return len(list(self.cache_dir.glob("*.json")))

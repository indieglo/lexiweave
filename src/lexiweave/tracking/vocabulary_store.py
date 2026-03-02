"""Vocabulary data store.

CRUD operations on vocabulary.json for a single language.
All other modules use this to read/write vocabulary entries
rather than touching the JSON directly.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

# --- Data Models ---


class StrengthData(BaseModel):
    score: float = 0.0
    last_reviewed: str | None = None
    review_count: int = 0
    anki_interval_days: int = 0


class DefinitionData(BaseModel):
    monolingual: str = ""
    generated_by: str = ""
    generated_at: str = ""


class SentenceData(BaseModel):
    text: str
    type: str = "cloze"
    cefr_level: str = ""
    source: str = "generated"


class AudioData(BaseModel):
    forvo_url: str = ""
    local_file: str = ""
    provider: str = ""


class ImageData(BaseModel):
    search_query: str = ""
    selected_file: str | None = None
    status: str = "pending_selection"


class CognateLink(BaseModel):
    word_id: str
    word: str
    similarity: str = ""
    notes: str = ""


class VocabularyEntry(BaseModel):
    id: str
    word: str
    lang: str
    pos: str = ""
    cefr_level: str | None = None
    source: str = ""
    date_added: str = ""
    strength: StrengthData = Field(default_factory=StrengthData)
    definitions: DefinitionData = Field(default_factory=DefinitionData)
    sentences: list[SentenceData] = Field(default_factory=list)
    audio: AudioData = Field(default_factory=AudioData)
    image: ImageData = Field(default_factory=ImageData)
    cognates: dict[str, CognateLink] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    anki_note_id: str | None = None


class VocabularyMetadata(BaseModel):
    language: str
    last_updated: str = ""
    total_entries: int = 0


class VocabularyFile(BaseModel):
    metadata: VocabularyMetadata
    entries: list[VocabularyEntry] = Field(default_factory=list)


class VocabularyStats(BaseModel):
    language: str
    total_entries: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_cefr_level: dict[str, int] = Field(default_factory=dict)
    by_pos: dict[str, int] = Field(default_factory=dict)
    with_definitions: int = 0
    with_sentences: int = 0
    with_audio: int = 0


# --- Store ---


def _normalize_word(word: str) -> str:
    """Normalize a word for use in IDs: lowercase, spaces to underscores."""
    normalized = word.lower().strip()
    normalized = re.sub(r"\s+", "_", normalized)
    # Remove characters that aren't letters, digits, or underscores
    normalized = re.sub(r"[^\w]", "", normalized, flags=re.UNICODE)
    return normalized


class VocabularyStore:
    """CRUD operations on vocabulary.json for a single language."""

    def __init__(self, data_dir: Path, lang: str):
        self.lang = lang
        self.lang_dir = data_dir / "languages" / lang
        self.vocab_path = self.lang_dir / "vocabulary.json"

    def load(self) -> VocabularyFile:
        """Load vocabulary.json; return empty VocabularyFile if not found."""
        if not self.vocab_path.exists():
            return VocabularyFile(
                metadata=VocabularyMetadata(language=self.lang),
            )
        with open(self.vocab_path, encoding="utf-8") as f:
            data = json.load(f)
        return VocabularyFile(**data)

    def save(self, data: VocabularyFile) -> None:
        """Atomic write: write to .tmp then os.replace()."""
        self.lang_dir.mkdir(parents=True, exist_ok=True)
        data.metadata.last_updated = datetime.now(UTC).isoformat()
        data.metadata.total_entries = len(data.entries)

        tmp_path = self.vocab_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.vocab_path)

    def _generate_id(self, word: str, existing_ids: set[str] | None = None) -> str:
        """Generate ID like 'es_comer_001'. Handles collisions."""
        base = f"{self.lang}_{_normalize_word(word)}"
        if existing_ids is None:
            vocab = self.load()
            existing_ids = {e.id for e in vocab.entries}

        counter = 1
        while True:
            candidate = f"{base}_{counter:03d}"
            if candidate not in existing_ids:
                return candidate
            counter += 1

    def add_entry(self, entry: VocabularyEntry) -> VocabularyEntry:
        """Add entry, skipping if word already exists. Returns the entry."""
        vocab = self.load()
        existing_words = {e.word.lower() for e in vocab.entries}
        if entry.word.lower() in existing_words:
            return entry

        existing_ids = {e.id for e in vocab.entries}
        if not entry.id or entry.id in existing_ids:
            entry.id = self._generate_id(entry.word, existing_ids)
        if not entry.date_added:
            entry.date_added = datetime.now(UTC).isoformat()

        vocab.entries.append(entry)
        self.save(vocab)
        return entry

    def add_entries(self, entries: list[VocabularyEntry]) -> int:
        """Bulk add. Returns count of new entries added (skips duplicates)."""
        vocab = self.load()
        existing_words = {e.word.lower() for e in vocab.entries}
        existing_ids = {e.id for e in vocab.entries}
        added = 0

        for entry in entries:
            if entry.word.lower() in existing_words:
                continue

            if not entry.id or entry.id in existing_ids:
                entry.id = self._generate_id(entry.word, existing_ids)
            if not entry.date_added:
                entry.date_added = datetime.now(UTC).isoformat()

            vocab.entries.append(entry)
            existing_words.add(entry.word.lower())
            existing_ids.add(entry.id)
            added += 1

        if added > 0:
            self.save(vocab)
        return added

    def get_entry(self, word_id: str) -> VocabularyEntry | None:
        """Retrieve entry by its ID."""
        vocab = self.load()
        for entry in vocab.entries:
            if entry.id == word_id:
                return entry
        return None

    def find_by_word(self, word: str) -> VocabularyEntry | None:
        """Find first entry matching exact word text (case-insensitive)."""
        vocab = self.load()
        word_lower = word.lower()
        for entry in vocab.entries:
            if entry.word.lower() == word_lower:
                return entry
        return None

    def update_entry(self, word_id: str, updates: dict) -> VocabularyEntry | None:
        """Partial update of an entry. Returns updated entry or None."""
        vocab = self.load()
        for i, entry in enumerate(vocab.entries):
            if entry.id == word_id:
                entry_data = entry.model_dump()
                entry_data.update(updates)
                vocab.entries[i] = VocabularyEntry(**entry_data)
                self.save(vocab)
                return vocab.entries[i]
        return None

    def search(self, query: str) -> list[VocabularyEntry]:
        """Case-insensitive substring search across word field."""
        vocab = self.load()
        query_lower = query.lower()
        return [e for e in vocab.entries if query_lower in e.word.lower()]

    def filter_entries(
        self,
        cefr_level: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
    ) -> list[VocabularyEntry]:
        """Filter entries by criteria. All filters are AND-ed."""
        vocab = self.load()
        results = vocab.entries

        if cefr_level is not None:
            results = [e for e in results if e.cefr_level == cefr_level]
        if source is not None:
            results = [e for e in results if e.source == source]
        if tags:
            tag_set = set(tags)
            results = [e for e in results if tag_set.issubset(set(e.tags))]

        return results

    def get_stats(self) -> VocabularyStats:
        """Compute stats: total, by source, by cefr_level, by pos."""
        vocab = self.load()
        stats = VocabularyStats(language=self.lang, total_entries=len(vocab.entries))

        for entry in vocab.entries:
            # By source
            src = entry.source or "unknown"
            stats.by_source[src] = stats.by_source.get(src, 0) + 1

            # By CEFR level
            level = entry.cefr_level or "unassigned"
            stats.by_cefr_level[level] = stats.by_cefr_level.get(level, 0) + 1

            # By part of speech
            pos = entry.pos or "unknown"
            stats.by_pos[pos] = stats.by_pos.get(pos, 0) + 1

            # Content counts
            if entry.definitions.monolingual:
                stats.with_definitions += 1
            if entry.sentences:
                stats.with_sentences += 1
            if entry.audio.local_file or entry.audio.forvo_url:
                stats.with_audio += 1

        return stats

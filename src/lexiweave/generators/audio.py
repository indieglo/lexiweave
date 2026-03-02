"""Audio generator.

Batch generates pronunciation audio for vocabulary entries
using the configured TTS provider.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from lexiweave.config import LanguageConfig
from lexiweave.tracking.vocabulary_store import AudioData, VocabularyEntry, VocabularyStore
from lexiweave.utils.audio import AudioResult, EdgeTTSProvider


class GenerationSummary(BaseModel):
    """Summary of an audio generation run."""

    words_processed: int = 0
    audio_generated: int = 0
    skipped_existing: int = 0
    errors: list[str] = Field(default_factory=list)


def _needs_audio(entry: VocabularyEntry) -> bool:
    """Check if an entry is missing audio."""
    return not entry.audio.local_file


def get_words_needing_audio(vocab_store: VocabularyStore) -> list[VocabularyEntry]:
    """Return vocabulary entries that don't have audio yet."""
    vocab = vocab_store.load()
    return [e for e in vocab.entries if _needs_audio(e)]


def make_audio_provider(lang_config: LanguageConfig) -> EdgeTTSProvider:
    """Create an audio provider from language config."""
    return EdgeTTSProvider(
        voice=lang_config.tts_voice,
        lang=lang_config.language_code,
    )


def generate_audio(
    entries: list[VocabularyEntry],
    audio_dir: Path,
    provider: EdgeTTSProvider,
) -> list[AudioResult]:
    """Generate audio for a list of vocabulary entries."""
    results: list[AudioResult] = []

    for entry in entries:
        result = provider.generate(entry.word, audio_dir)
        results.append(result)

    return results


def apply_audio(
    results: list[AudioResult],
    vocab_store: VocabularyStore,
) -> int:
    """Apply audio results to vocabulary entries. Returns count of updates."""
    applied = 0

    for result in results:
        if not result.success or not result.file_path:
            continue

        entry = vocab_store.find_by_word(result.word)
        if entry is None:
            continue

        vocab_store.update_entry(
            entry.id,
            {
                "audio": AudioData(
                    local_file=result.file_path,
                    provider=result.provider,
                ).model_dump(),
            },
        )
        applied += 1

    return applied

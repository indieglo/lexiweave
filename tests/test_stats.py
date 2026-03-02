"""Tests for pipeline stats."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from lexiweave.tracking.stats import (
    format_stats,
    get_cross_language_stats,
    get_pipeline_stats,
)
from lexiweave.tracking.vocabulary_store import (
    VocabularyEntry,
    VocabularyStore,
)


def _make_entry(word: str, **kwargs) -> VocabularyEntry:
    return VocabularyEntry(id=f"es_{word}_001", word=word, lang="es", source="test", **kwargs)


def _populate(store: VocabularyStore) -> None:
    """Add entries with varying content completeness."""
    entries = [
        _make_entry("comer"),  # bare entry
        _make_entry("beber"),  # will get definition
        _make_entry("gato"),   # will get definition + sentences + audio
    ]
    store.add_entries(entries)

    # Add definition to beber
    store.update_entry("es_beber_001", {
        "definitions": {
            "monolingual": "Tomar líquidos",
            "generated_by": "test",
            "generated_at": "",
        },
    })

    # Add full content to gato
    store.update_entry("es_gato_001", {
        "definitions": {"monolingual": "Animal felino", "generated_by": "test", "generated_at": ""},
        "sentences": [{"text": "El {{c1::gato}} duerme.", "cefr_level": "A1"}],
        "audio": {"local_file": "/audio/gato.mp3", "provider": "edge_tts", "forvo_url": ""},
    })


class TestGetPipelineStats:
    def test_counts_total(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)

        stats = get_pipeline_stats(store)
        assert stats.total == 3

    def test_counts_definitions(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)

        stats = get_pipeline_stats(store)
        assert stats.with_definitions == 2  # beber + gato

    def test_counts_sentences(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)

        stats = get_pipeline_stats(store)
        assert stats.with_sentences == 1  # gato only

    def test_counts_audio(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)

        stats = get_pipeline_stats(store)
        assert stats.with_audio == 1  # gato only

    def test_ready_to_export(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)

        stats = get_pipeline_stats(store)
        assert stats.ready_to_export == 1  # gato has def + sentences + audio

    def test_exported_count(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)
        store.update_entry("es_gato_001", {"anki_note_id": "123"})

        stats = get_pipeline_stats(store)
        assert stats.exported == 1

    def test_strength_tiers_default_new(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)

        stats = get_pipeline_stats(store)
        assert stats.strength_tiers["new"] == 3

    def test_strength_tiers_with_scores(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)

        store.update_entry("es_comer_001", {
            "strength": {"score": 0.5, "review_count": 10, "anki_interval_days": 30},
        })
        store.update_entry("es_beber_001", {
            "strength": {"score": 0.95, "review_count": 20, "anki_interval_days": 180},
        })

        stats = get_pipeline_stats(store)
        assert stats.strength_tiers["young"] == 1    # comer 0.5
        assert stats.strength_tiers["mastered"] == 1  # beber 0.95
        assert stats.strength_tiers["new"] == 1       # gato 0.0

    def test_cognates_counted(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)
        store.update_entry("es_gato_001", {
            "cognates": {"ca": {"word_id": "ca_gat_001", "word": "gat", "similarity": "high"}},
        })

        stats = get_pipeline_stats(store)
        assert stats.with_cognates == 1

    def test_empty_store(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        stats = get_pipeline_stats(store)
        assert stats.total == 0
        assert stats.ready_to_export == 0


class TestGetCrossLanguageStats:
    def test_returns_stats_for_populated_languages(self, tmp_data_dir: Path) -> None:
        es_store = VocabularyStore(tmp_data_dir, "es")
        _populate(es_store)

        ca_store = VocabularyStore(tmp_data_dir, "ca")
        ca_store.add_entry(_make_entry("gat"))

        results = get_cross_language_stats(tmp_data_dir, ["es", "ca"])
        assert len(results) == 2

    def test_skips_empty_languages(self, tmp_data_dir: Path) -> None:
        es_store = VocabularyStore(tmp_data_dir, "es")
        _populate(es_store)

        results = get_cross_language_stats(tmp_data_dir, ["es", "ca"])
        assert len(results) == 1
        assert results[0].language == "es"


class TestFormatStats:
    def test_does_not_error(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate(store)
        stats = get_pipeline_stats(store)

        console = Console(file=None, force_terminal=False)
        format_stats(stats, console)  # Should not raise

    def test_empty_stats_does_not_error(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        stats = get_pipeline_stats(store)

        console = Console(file=None, force_terminal=False)
        format_stats(stats, console)  # Should not raise

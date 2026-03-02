"""Tests for vocabulary_store CRUD operations."""

from __future__ import annotations

from pathlib import Path

from lexiweave.tracking.vocabulary_store import (
    VocabularyEntry,
    VocabularyStore,
)


def _make_entry(word: str, lang: str = "es", **kwargs) -> VocabularyEntry:
    """Helper to create a test entry."""
    return VocabularyEntry(id="", word=word, lang=lang, **kwargs)


class TestVocabularyStoreLoad:
    def test_load_empty(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        vocab = store.load()
        assert vocab.metadata.language == "es"
        assert len(vocab.entries) == 0

    def test_load_existing(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = _make_entry("comer")
        store.add_entry(entry)

        vocab = store.load()
        assert len(vocab.entries) == 1
        assert vocab.entries[0].word == "comer"


class TestVocabularyStoreAdd:
    def test_add_single_entry(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = store.add_entry(_make_entry("comer"))
        assert entry.id.startswith("es_comer_")
        assert store.vocab_path.exists()

    def test_add_duplicate_word_skipped(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(_make_entry("comer"))
        store.add_entry(_make_entry("comer"))
        vocab = store.load()
        assert len(vocab.entries) == 1

    def test_add_entries_bulk(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entries = [_make_entry("comer"), _make_entry("beber"), _make_entry("comer")]
        added = store.add_entries(entries)
        assert added == 2
        vocab = store.load()
        assert len(vocab.entries) == 2

    def test_id_generation(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = store.add_entry(_make_entry("comer"))
        assert entry.id == "es_comer_001"

    def test_id_handles_multi_word_phrases(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = store.add_entry(_make_entry("se come"))
        assert entry.id == "es_se_come_001"

    def test_date_added_set_automatically(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = store.add_entry(_make_entry("comer"))
        assert entry.date_added != ""


class TestVocabularyStoreQuery:
    def test_get_entry_by_id(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        added = store.add_entry(_make_entry("comer"))
        found = store.get_entry(added.id)
        assert found is not None
        assert found.word == "comer"

    def test_get_entry_missing(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        assert store.get_entry("nonexistent") is None

    def test_find_by_word(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(_make_entry("comer"))
        found = store.find_by_word("comer")
        assert found is not None
        assert found.word == "comer"

    def test_find_by_word_case_insensitive(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(_make_entry("Comer"))
        found = store.find_by_word("comer")
        assert found is not None

    def test_search_substring(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entries([_make_entry("comer"), _make_entry("beber"), _make_entry("correr")])
        results = store.search("er")
        assert len(results) == 3  # all contain "er"

    def test_search_partial(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entries([_make_entry("comer"), _make_entry("beber"), _make_entry("correr")])
        results = store.search("com")
        assert len(results) == 1
        assert results[0].word == "comer"

    def test_filter_by_source(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entries([
            _make_entry("comer", source="duolingo_import"),
            _make_entry("beber", source="manual"),
        ])
        results = store.filter_entries(source="duolingo_import")
        assert len(results) == 1
        assert results[0].word == "comer"

    def test_filter_by_cefr_level(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entries([
            _make_entry("comer", cefr_level="A1"),
            _make_entry("beber", cefr_level="B1"),
            _make_entry("correr"),  # None
        ])
        results = store.filter_entries(cefr_level="A1")
        assert len(results) == 1
        assert results[0].word == "comer"

    def test_filter_by_tags(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entries([
            _make_entry("comer", tags=["food", "daily"]),
            _make_entry("beber", tags=["food"]),
            _make_entry("correr", tags=["sport"]),
        ])
        results = store.filter_entries(tags=["food", "daily"])
        assert len(results) == 1
        assert results[0].word == "comer"


class TestVocabularyStoreUpdate:
    def test_update_entry(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        added = store.add_entry(_make_entry("comer"))
        updated = store.update_entry(added.id, {"pos": "verb", "cefr_level": "A1"})
        assert updated is not None
        assert updated.pos == "verb"
        assert updated.cefr_level == "A1"

        # Verify persistence
        reloaded = store.get_entry(added.id)
        assert reloaded is not None
        assert reloaded.pos == "verb"

    def test_update_nonexistent_returns_none(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        result = store.update_entry("nonexistent", {"pos": "verb"})
        assert result is None


class TestVocabularyStoreStats:
    def test_stats_empty(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        stats = store.get_stats()
        assert stats.total_entries == 0
        assert stats.with_definitions == 0

    def test_stats_counts(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entries([
            _make_entry("comer", source="duolingo_import", cefr_level="A1"),
            _make_entry("beber", source="duolingo_import", cefr_level="A1"),
            _make_entry("correr", source="manual"),
        ])
        stats = store.get_stats()
        assert stats.total_entries == 3
        assert stats.by_source["duolingo_import"] == 2
        assert stats.by_source["manual"] == 1
        assert stats.by_cefr_level["A1"] == 2


class TestAtomicWrite:
    def test_save_creates_directories(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "fresh" / "data"
        store = VocabularyStore(data_dir, "fr")
        store.add_entry(_make_entry("manger", lang="fr"))
        assert store.vocab_path.exists()

    def test_no_tmp_file_after_save(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(_make_entry("comer"))
        tmp_file = store.vocab_path.with_suffix(".json.tmp")
        assert not tmp_file.exists()

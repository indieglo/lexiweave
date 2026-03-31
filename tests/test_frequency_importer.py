"""Tests for the frequency list importer."""

from __future__ import annotations

from pathlib import Path

from lexiweave.importers.frequency import (
    FrequencyImportResult,
    import_frequency_list,
    parse_frequency_file,
)
from lexiweave.tracking.vocabulary_store import VocabularyStore


def _write_freq_file(tmp_path: Path, lines: list[str]) -> Path:
    """Write a frequency list file and return its path."""
    p = tmp_path / "freq.txt"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# --- parse_frequency_file ---


class TestParseFrequencyFile:
    def test_basic_parse_returns_words(self, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["gat 500", "casa 400", "taula 300"])
        words = parse_frequency_file(p, limit=10, filter_stopwords=False)
        assert words == ["gat", "casa", "taula"]

    def test_limit_is_respected(self, tmp_path: Path) -> None:
        lines = [f"word{i} {1000 - i}" for i in range(100)]
        p = _write_freq_file(tmp_path, lines)
        words = parse_frequency_file(p, limit=10, filter_stopwords=False)
        assert len(words) == 10

    def test_skip_top_skips_entries(self, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["que 9000", "no 8000", "gat 500"])
        words = parse_frequency_file(
            p, limit=10, skip_top=2, filter_stopwords=False
        )
        assert words == ["gat"]

    def test_filters_stopwords(self, tmp_path: Path) -> None:
        # "que" and "no" are in the stopword list
        p = _write_freq_file(tmp_path, ["que 9000", "no 8000", "gat 500"])
        words = parse_frequency_file(p, limit=10, filter_stopwords=True)
        assert "que" not in words
        assert "no" not in words
        assert "gat" in words

    def test_filters_proper_nouns(self, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["Barcelona 5000", "gat 500"])
        words = parse_frequency_file(p, filter_proper_nouns=True, filter_stopwords=False)
        assert "Barcelona" not in words
        assert "gat" in words

    def test_keeps_proper_nouns_when_disabled(self, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["Barcelona 5000", "gat 500"])
        words = parse_frequency_file(
            p, filter_proper_nouns=False, filter_stopwords=False
        )
        assert "Barcelona" in words

    def test_filters_non_word_tokens(self, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["l'home 200", "can't 100", "gat 500"])
        words = parse_frequency_file(p, filter_stopwords=False, filter_proper_nouns=False)
        # Apostrophes and contractions should be filtered
        assert "l'home" not in words
        assert "can't" not in words
        assert "gat" in words

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["gat 500", "", "casa 400"])
        words = parse_frequency_file(p, filter_stopwords=False)
        assert words == ["gat", "casa"]

    def test_unicode_words_preserved(self, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["càlid 300", "préstec 200"])
        words = parse_frequency_file(p, filter_stopwords=False)
        assert "càlid" in words
        assert "préstec" in words


# --- import_frequency_list ---


class TestImportFrequencyList:
    def test_adds_entries_to_store(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["gat 500", "casa 400", "taula 300"])
        store = VocabularyStore(tmp_data_dir, "ca")

        result = import_frequency_list(p, "ca", store, limit=10, filter_stopwords=False)

        assert result.imported == 3
        assert result.duplicates_skipped == 0
        vocab = store.load()
        words = {e.word for e in vocab.entries}
        assert {"gat", "casa", "taula"}.issubset(words)

    def test_entries_have_correct_source(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["gat 500"])
        store = VocabularyStore(tmp_data_dir, "ca")
        import_frequency_list(p, "ca", store, filter_stopwords=False)
        entry = store.find_by_word("gat")
        assert entry is not None
        assert entry.source == "frequency_list"
        assert entry.lang == "ca"

    def test_deduplicates_against_existing(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["gat 500", "casa 400"])
        store = VocabularyStore(tmp_data_dir, "ca")
        # Import once
        import_frequency_list(p, "ca", store, filter_stopwords=False)
        # Import again — should all be duplicates
        result = import_frequency_list(p, "ca", store, filter_stopwords=False)
        assert result.imported == 0
        assert result.duplicates_skipped == 2

    def test_limit_restricts_import(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        lines = [f"word{i} {1000 - i}" for i in range(50)]
        p = _write_freq_file(tmp_path, lines)
        store = VocabularyStore(tmp_data_dir, "ca")
        result = import_frequency_list(
            p, "ca", store, limit=10, filter_stopwords=False
        )
        assert result.imported == 10

    def test_total_in_file_is_counted(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        p = _write_freq_file(tmp_path, ["gat 500", "casa 400", "taula 300"])
        store = VocabularyStore(tmp_data_dir, "ca")
        result = import_frequency_list(
            p, "ca", store, limit=10, filter_stopwords=False
        )
        assert result.total_in_file == 3

    def test_returns_frequency_import_result(
        self, tmp_data_dir: Path, tmp_path: Path
    ) -> None:
        p = _write_freq_file(tmp_path, ["gat 500"])
        store = VocabularyStore(tmp_data_dir, "ca")
        result = import_frequency_list(p, "ca", store, filter_stopwords=False)
        assert isinstance(result, FrequencyImportResult)

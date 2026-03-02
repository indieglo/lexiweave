"""Tests for the Duolingo importer."""

from __future__ import annotations

from pathlib import Path

from lexiweave.importers.duolingo import (
    import_duolingo,
    parse_languages_csv,
    parse_leaderboards_csv,
    parse_vocabulary_csv,
)
from lexiweave.tracking.vocabulary_store import VocabularyStore


class TestParseVocabularyCsv:
    def test_basic_parsing(self, sample_vocab_csv: Path) -> None:
        words = parse_vocabulary_csv(sample_vocab_csv)
        assert "animado" in words
        assert "carnaval" in words

    def test_deduplication(self, sample_vocab_csv: Path) -> None:
        words = parse_vocabulary_csv(sample_vocab_csv)
        # "se come" appears twice in fixture, should be deduplicated
        assert words.count("se come") == 1

    def test_unique_count(self, sample_vocab_csv: Path) -> None:
        words = parse_vocabulary_csv(sample_vocab_csv)
        assert len(words) == 4  # 5 lines, 1 duplicate

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "vocab.csv"
        csv_path.write_text("  hello  \n  world  \n", encoding="utf-8")
        words = parse_vocabulary_csv(csv_path)
        assert words == ["hello", "world"]

    def test_skips_empty_lines(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "vocab.csv"
        csv_path.write_text("hello\n\n\nworld\n", encoding="utf-8")
        words = parse_vocabulary_csv(csv_path)
        assert len(words) == 2

    def test_multi_word_phrases(self, sample_vocab_csv: Path) -> None:
        words = parse_vocabulary_csv(sample_vocab_csv)
        assert "se come" in words


class TestParseLanguagesCsv:
    def test_parses_all_rows(self, sample_gdpr_dir: Path) -> None:
        stats = parse_languages_csv(sample_gdpr_dir / "languages.csv")
        assert len(stats) == 2

    def test_numeric_fields(self, sample_gdpr_dir: Path) -> None:
        stats = parse_languages_csv(sample_gdpr_dir / "languages.csv")
        es = next(s for s in stats if s.learning_language == "es")
        assert es.points == 124072
        assert es.total_lessons == 1209
        assert es.days_active == 364

    def test_handles_empty_fields(self, sample_gdpr_dir: Path) -> None:
        stats = parse_languages_csv(sample_gdpr_dir / "languages.csv")
        es = next(s for s in stats if s.learning_language == "es")
        assert es.prior_proficiency == ""


class TestParseLeaderboardsCsv:
    def test_parses_entries(self, sample_gdpr_dir: Path) -> None:
        entries = parse_leaderboards_csv(sample_gdpr_dir / "leaderboards.csv")
        assert len(entries) == 2

    def test_tier_as_int(self, sample_gdpr_dir: Path) -> None:
        entries = parse_leaderboards_csv(sample_gdpr_dir / "leaderboards.csv")
        assert entries[0].tier == 0
        assert entries[1].tier == 1


class TestImportDuolingo:
    def test_full_import(
        self, sample_vocab_csv: Path, sample_gdpr_dir: Path, tmp_data_dir: Path
    ) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        result = import_duolingo(sample_vocab_csv, sample_gdpr_dir, "es", store)

        assert result.unique_words == 4
        assert result.new_entries_added == 4
        assert result.language_stats is not None
        assert result.language_stats.points == 124072
        assert result.leaderboard_weeks == 2

    def test_import_without_gdpr(
        self, sample_vocab_csv: Path, tmp_data_dir: Path
    ) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        result = import_duolingo(sample_vocab_csv, None, "es", store)

        assert result.new_entries_added == 4
        assert result.language_stats is None
        assert result.leaderboard_weeks == 0

    def test_entries_have_correct_source(
        self, sample_vocab_csv: Path, tmp_data_dir: Path
    ) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        import_duolingo(sample_vocab_csv, None, "es", store)

        vocab = store.load()
        for entry in vocab.entries:
            assert entry.source == "duolingo_import"

    def test_entries_have_no_cefr_level(
        self, sample_vocab_csv: Path, tmp_data_dir: Path
    ) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        import_duolingo(sample_vocab_csv, None, "es", store)

        vocab = store.load()
        for entry in vocab.entries:
            assert entry.cefr_level is None

    def test_sensitive_file_warnings(
        self, sample_vocab_csv: Path, sample_gdpr_dir: Path, tmp_data_dir: Path
    ) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        result = import_duolingo(sample_vocab_csv, sample_gdpr_dir, "es", store)

        warning_text = " ".join(result.warnings)
        assert "profile.csv" in warning_text
        assert "auth_data.csv" in warning_text

    def test_import_idempotent(
        self, sample_vocab_csv: Path, tmp_data_dir: Path
    ) -> None:
        store = VocabularyStore(tmp_data_dir, "es")

        result1 = import_duolingo(sample_vocab_csv, None, "es", store)
        assert result1.new_entries_added == 4

        result2 = import_duolingo(sample_vocab_csv, None, "es", store)
        assert result2.new_entries_added == 0
        assert result2.duplicates_skipped == 4

        vocab = store.load()
        assert len(vocab.entries) == 4

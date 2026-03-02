"""Tests for Anki sync and strength tracking."""

from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

from lexiweave.tracking.strength import (
    categorize_strength,
    compute_strength,
    sync_anki,
)
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore


def _make_apkg(path: Path, cards: list[dict]) -> Path:
    """Create a minimal .apkg file with card data for testing.

    Each card dict has: word, note_id, interval, ease_factor, reps, lapses, last_review_ts.
    """
    path.mkdir(parents=True, exist_ok=True)
    db_path = path / "collection.anki2"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            flds TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY,
            nid INTEGER,
            ivl INTEGER,
            factor INTEGER,
            reps INTEGER,
            lapses INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE revlog (
            id INTEGER,
            cid INTEGER
        )
    """)

    for i, card in enumerate(cards):
        note_id = card.get("note_id", i + 1)
        cursor.execute(
            "INSERT INTO notes (id, flds) VALUES (?, ?)",
            (note_id, card["word"]),
        )
        card_id = i + 100
        cursor.execute(
            "INSERT INTO cards (id, nid, ivl, factor, reps, lapses) VALUES (?, ?, ?, ?, ?, ?)",
            (
                card_id,
                note_id,
                card.get("interval", 30),
                card.get("ease_factor", 2500),
                card.get("reps", 5),
                card.get("lapses", 0),
            ),
        )
        if card.get("last_review_ts"):
            cursor.execute(
                "INSERT INTO revlog (id, cid) VALUES (?, ?)",
                (card["last_review_ts"], card_id),
            )

    conn.commit()
    conn.close()

    apkg_path = path / "test.apkg"
    with zipfile.ZipFile(apkg_path, "w") as zf:
        zf.write(db_path, "collection.anki2")

    return apkg_path


def _add_words(store: VocabularyStore, words: list[str]) -> None:
    for word in words:
        store.add_entry(VocabularyEntry(id="", word=word, lang="es", source="test"))


class TestComputeStrength:
    def test_zero_reps_returns_zero(self) -> None:
        result = compute_strength(0, 2500, 0, 0, 0.0)
        assert result.score == 0.0
        assert result.review_count == 0

    def test_short_interval_low_score(self) -> None:
        result = compute_strength(7, 2500, 5, 0, 0.0)
        assert 0.0 < result.score < 0.3

    def test_long_interval_high_score(self) -> None:
        result = compute_strength(300, 2500, 20, 0, 0.0)
        assert result.score > 0.7

    def test_max_interval_near_one(self) -> None:
        result = compute_strength(365, 2500, 30, 0, 0.0)
        assert result.score >= 0.95

    def test_lapses_reduce_score(self) -> None:
        without_lapses = compute_strength(100, 2500, 10, 0, 0.0)
        with_lapses = compute_strength(100, 2500, 10, 3, 0.0)
        assert with_lapses.score < without_lapses.score

    def test_overdue_decays_score(self) -> None:
        on_time = compute_strength(30, 2500, 10, 0, 30.0)
        overdue = compute_strength(30, 2500, 10, 0, 90.0)
        assert overdue.score < on_time.score

    def test_score_clamped_to_zero_one(self) -> None:
        result = compute_strength(1000, 5000, 50, 0, 0.0)
        assert 0.0 <= result.score <= 1.0

        result2 = compute_strength(1, 100, 1, 10, 1000.0)
        assert 0.0 <= result2.score <= 1.0

    def test_stores_interval_and_reps(self) -> None:
        result = compute_strength(45, 2500, 8, 1, 5.0)
        assert result.anki_interval_days == 45
        assert result.review_count == 8


class TestCategorizeStrength:
    def test_new(self) -> None:
        assert categorize_strength(0.0) == "new"

    def test_learning(self) -> None:
        assert categorize_strength(0.15) == "learning"
        assert categorize_strength(0.29) == "learning"

    def test_young(self) -> None:
        assert categorize_strength(0.3) == "young"
        assert categorize_strength(0.59) == "young"

    def test_mature(self) -> None:
        assert categorize_strength(0.6) == "mature"
        assert categorize_strength(0.89) == "mature"

    def test_mastered(self) -> None:
        assert categorize_strength(0.9) == "mastered"
        assert categorize_strength(1.0) == "mastered"


class TestSyncAnki:
    def test_matches_by_word(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        apkg = _make_apkg(tmp_path, [
            {"word": "comer", "interval": 30, "reps": 5},
            {"word": "beber", "interval": 15, "reps": 3},
        ])

        result = sync_anki(apkg, store)

        assert result.entries_matched == 2
        assert result.entries_updated == 2
        assert result.entries_not_found == 0

    def test_updates_strength_data(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        apkg = _make_apkg(tmp_path, [
            {"word": "comer", "interval": 60, "ease_factor": 2500, "reps": 10, "lapses": 1},
        ])

        sync_anki(apkg, store)

        entry = store.find_by_word("comer")
        assert entry is not None
        assert entry.strength.score > 0
        assert entry.strength.review_count == 10
        assert entry.strength.anki_interval_days == 60

    def test_sets_anki_note_id(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        apkg = _make_apkg(tmp_path, [
            {"word": "comer", "note_id": 12345, "reps": 5, "interval": 30},
        ])

        sync_anki(apkg, store)

        entry = store.find_by_word("comer")
        assert entry is not None
        assert entry.anki_note_id == "12345"

    def test_matches_by_anki_note_id(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        # First sync to set note_id
        apkg1 = _make_apkg(tmp_path / "first", [
            {"word": "comer", "note_id": 999, "reps": 5, "interval": 30},
        ])
        sync_anki(apkg1, store)

        # Second sync with different word text but same note_id
        apkg2 = _make_apkg(tmp_path / "second", [
            {"word": "different_text", "note_id": 999, "reps": 10, "interval": 60},
        ])
        result = sync_anki(apkg2, store)

        assert result.entries_matched == 1
        entry = store.find_by_word("comer")
        assert entry is not None
        assert entry.strength.review_count == 10

    def test_unmatched_entries_counted(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        apkg = _make_apkg(tmp_path, [
            {"word": "comer", "reps": 5, "interval": 30},
            {"word": "unknown_word", "reps": 3, "interval": 10},
        ])

        result = sync_anki(apkg, store)

        assert result.entries_matched == 1
        assert result.entries_not_found == 1

    def test_invalid_apkg_returns_error(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        fake_file = tmp_path / "bad.apkg"
        fake_file.write_bytes(b"not a zip file")

        result = sync_anki(fake_file, store)

        assert len(result.errors) > 0

    def test_empty_apkg(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        apkg = _make_apkg(tmp_path, [])
        result = sync_anki(apkg, store)

        assert result.entries_matched == 0
        assert result.entries_updated == 0

    def test_review_timestamp_sets_last_reviewed(
        self, tmp_data_dir: Path, tmp_path: Path
    ) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        # Timestamp in ms: 2026-01-15 12:00:00 UTC
        ts_ms = 1768478400000
        apkg = _make_apkg(tmp_path, [
            {"word": "comer", "reps": 5, "interval": 30, "last_review_ts": ts_ms},
        ])

        sync_anki(apkg, store)

        entry = store.find_by_word("comer")
        assert entry is not None
        assert entry.strength.last_reviewed is not None
        assert "2026-01-15" in entry.strength.last_reviewed

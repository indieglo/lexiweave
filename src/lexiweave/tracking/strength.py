"""Anki sync and vocabulary strength tracking.

Reads Anki .apkg exports to extract review history and compute
strength scores for vocabulary entries.
"""

from __future__ import annotations

import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from lexiweave.tracking.vocabulary_store import StrengthData, VocabularyStore


class SyncResult(BaseModel):
    """Result of syncing Anki review data."""

    entries_matched: int = 0
    entries_updated: int = 0
    entries_not_found: int = 0
    errors: list[str] = Field(default_factory=list)


def compute_strength(
    interval: int,
    ease_factor: int,
    reps: int,
    lapses: int,
    days_since_review: float,
) -> StrengthData:
    """Compute vocabulary strength from Anki SM-2 scheduling data.

    Args:
        interval: Anki card interval in days.
        ease_factor: Anki ease factor (typically 1300-3500, default 2500).
        reps: Number of reviews completed.
        lapses: Number of times the card was forgotten.
        days_since_review: Days since last review.

    Returns:
        StrengthData with computed score (0.0-1.0).
    """
    if reps == 0:
        return StrengthData(score=0.0, review_count=0, anki_interval_days=0)

    # Base score from interval (0-365 days mapped to 0-0.95)
    base = min(interval / 365.0, 1.0) * 0.95

    # Ease factor bonus (2500 is default; higher = easier = slight boost)
    ease_norm = (ease_factor / 2500.0) if ease_factor > 0 else 1.0
    ease_bonus = min(ease_norm * 0.05, 0.05)

    # Lapse penalty: each lapse reduces score
    lapse_penalty = min(lapses * 0.05, 0.3)

    raw_score = base + ease_bonus - lapse_penalty

    # Time decay: score decays as time since review exceeds interval
    if interval > 0 and days_since_review > interval:
        overdue_ratio = (days_since_review - interval) / interval
        decay = 1.0 / (1.0 + overdue_ratio)
        raw_score *= decay

    score = max(0.0, min(1.0, raw_score))

    return StrengthData(
        score=round(score, 3),
        review_count=reps,
        anki_interval_days=interval,
    )


def categorize_strength(score: float) -> str:
    """Categorize a strength score into a tier.

    Returns one of: new, learning, young, mature, mastered.
    """
    if score == 0.0:
        return "new"
    if score < 0.3:
        return "learning"
    if score < 0.6:
        return "young"
    if score < 0.9:
        return "mature"
    return "mastered"


def _extract_anki_db(apkg_path: Path, tmp_dir: Path) -> Path:
    """Extract the SQLite database from an .apkg file."""
    with zipfile.ZipFile(apkg_path, "r") as zf:
        # Anki 2.1+ uses collection.anki21 or collection.anki2
        for name in ("collection.anki21", "collection.anki2"):
            if name in zf.namelist():
                zf.extract(name, tmp_dir)
                return tmp_dir / name

    msg = f"No Anki database found in {apkg_path}"
    raise ValueError(msg)


def _read_anki_data(db_path: Path) -> list[dict]:
    """Read card scheduling data from Anki SQLite database.

    Returns list of dicts with: word, note_id, interval, ease_factor,
    reps, lapses, last_review_ts.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        # Get card data joined with notes
        # notes.flds contains fields separated by \x1f — first field is the word
        cursor.execute("""
            SELECT
                n.id as note_id,
                n.flds as fields,
                c.ivl as interval,
                c.factor as ease_factor,
                c.reps as reps,
                c.lapses as lapses
            FROM cards c
            JOIN notes n ON c.nid = n.id
        """)

        cards = []
        for row in cursor.fetchall():
            note_id, fields, interval, ease_factor, reps, lapses = row
            # First field is typically the word/front of card
            word = fields.split("\x1f")[0].strip()

            # Get last review timestamp from revlog
            cursor.execute(
                "SELECT MAX(id) FROM revlog WHERE cid IN "
                "(SELECT id FROM cards WHERE nid = ?)",
                (note_id,),
            )
            revlog_row = cursor.fetchone()
            last_review_ts = revlog_row[0] if revlog_row and revlog_row[0] else None

            cards.append({
                "word": word,
                "note_id": str(note_id),
                "interval": interval,
                "ease_factor": ease_factor,
                "reps": reps,
                "lapses": lapses,
                "last_review_ts": last_review_ts,
            })

        return cards
    finally:
        conn.close()


def sync_anki(apkg_path: Path, vocab_store: VocabularyStore) -> SyncResult:
    """Sync Anki review data into vocabulary entries.

    Reads an exported .apkg file, matches cards to vocabulary entries
    by word text or existing anki_note_id, and updates strength scores.
    """
    result = SyncResult()

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            db_path = _extract_anki_db(apkg_path, Path(tmp_dir))
        except (ValueError, zipfile.BadZipFile) as e:
            result.errors.append(str(e))
            return result

        try:
            anki_cards = _read_anki_data(db_path)
        except sqlite3.Error as e:
            result.errors.append(f"Database error: {e}")
            return result

    vocab = vocab_store.load()

    # Build lookup maps
    word_to_entry = {}
    noteid_to_entry = {}
    for entry in vocab.entries:
        word_to_entry[entry.word.lower()] = entry
        if entry.anki_note_id:
            noteid_to_entry[entry.anki_note_id] = entry

    now = datetime.now(UTC)

    for card in anki_cards:
        # Match by anki_note_id first, then by word text
        entry = noteid_to_entry.get(card["note_id"])
        if entry is None:
            entry = word_to_entry.get(card["word"].lower())

        if entry is None:
            result.entries_not_found += 1
            continue

        result.entries_matched += 1

        # Compute days since last review
        days_since = 0.0
        last_reviewed = None
        if card["last_review_ts"]:
            # Anki revlog IDs are millisecond timestamps
            last_review_dt = datetime.fromtimestamp(
                card["last_review_ts"] / 1000, tz=UTC,
            )
            days_since = (now - last_review_dt).total_seconds() / 86400
            last_reviewed = last_review_dt.isoformat()

        strength = compute_strength(
            interval=card["interval"],
            ease_factor=card["ease_factor"],
            reps=card["reps"],
            lapses=card["lapses"],
            days_since_review=days_since,
        )
        strength.last_reviewed = last_reviewed

        vocab_store.update_entry(
            entry.id,
            {
                "strength": strength.model_dump(),
                "anki_note_id": card["note_id"],
            },
        )
        result.entries_updated += 1

    return result

"""Duolingo data importer.

Parses:
- Vocabulary CSV (one word/phrase per line, no headers)
- GDPR export: languages.csv, leaderboards.csv
- Skips: profile.csv, auth_data.csv (personal data)
- Skips: user-tree-backend.csv (binary protobuf, not parseable)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore

SENSITIVE_FILES = {"profile.csv", "auth_data.csv", "duolingo-notify-data.csv"}


@dataclass
class DuolingoLanguageStats:
    learning_language: str
    from_language: str
    points: int
    skills_learned: int
    total_lessons: int
    days_active: int
    last_active: str | None
    prior_proficiency: str
    subscribed: str


@dataclass
class LeaderboardEntry:
    leaderboard: str
    timestamp: str
    tier: int
    score: int


@dataclass
class ImportResult:
    total_words_in_csv: int = 0
    unique_words: int = 0
    new_entries_added: int = 0
    duplicates_skipped: int = 0
    language_stats: DuolingoLanguageStats | None = None
    leaderboard_weeks: int = 0
    warnings: list[str] = field(default_factory=list)


def parse_vocabulary_csv(path: Path) -> list[str]:
    """Parse the vocabulary CSV. One word/phrase per line, no headers.

    Returns deduplicated list preserving first-occurrence order.
    """
    words: list[str] = []
    seen: set[str] = set()

    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if not word:
                continue
            word_lower = word.lower()
            if word_lower not in seen:
                words.append(word)
                seen.add(word_lower)

    return words


def parse_languages_csv(path: Path) -> list[DuolingoLanguageStats]:
    """Parse languages.csv from GDPR export."""
    results: list[DuolingoLanguageStats] = []

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(
                DuolingoLanguageStats(
                    learning_language=row.get("learning_language", ""),
                    from_language=row.get("from_language", ""),
                    points=int(row.get("points", 0) or 0),
                    skills_learned=int(row.get("skills_learned", 0) or 0),
                    total_lessons=int(row.get("total_lessons", 0) or 0),
                    days_active=int(row.get("days_active", 0) or 0),
                    last_active=row.get("last_active") or None,
                    prior_proficiency=row.get("prior_proficiency", ""),
                    subscribed=row.get("subscribed", ""),
                )
            )

    return results


def parse_leaderboards_csv(path: Path) -> list[LeaderboardEntry]:
    """Parse leaderboards.csv from GDPR export."""
    results: list[LeaderboardEntry] = []

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(
                LeaderboardEntry(
                    leaderboard=row.get("leaderboard", ""),
                    timestamp=row.get("timestamp", ""),
                    tier=int(row.get("tier", 0) or 0),
                    score=int(row.get("score", 0) or 0),
                )
            )

    return results


def _check_sensitive_files(gdpr_dir: Path) -> list[str]:
    """Return warnings for any sensitive files found in GDPR dir."""
    warnings: list[str] = []
    for filename in SENSITIVE_FILES:
        if (gdpr_dir / filename).exists():
            warnings.append(
                f"Skipping {filename} (contains personal data). "
                f"This file is not imported."
            )
    return warnings


def _words_to_entries(words: list[str], lang: str) -> list[VocabularyEntry]:
    """Convert raw word strings to VocabularyEntry objects."""
    now = datetime.now(UTC).isoformat()
    return [
        VocabularyEntry(
            id="",  # Store will assign real IDs
            word=word,
            lang=lang,
            source="duolingo_import",
            date_added=now,
        )
        for word in words
    ]


def import_duolingo(
    vocab_csv_path: Path,
    gdpr_dir: Path | None,
    lang: str,
    store: VocabularyStore,
) -> ImportResult:
    """Import Duolingo data into vocabulary store.

    1. Parse vocabulary CSV, deduplicate
    2. If gdpr_dir provided, parse languages.csv and leaderboards.csv
    3. Warn about sensitive/skipped files
    4. Convert words to VocabularyEntry objects
    5. Bulk add via store (store handles dedup against existing data)
    6. Return ImportResult summary
    """
    result = ImportResult()

    # Parse vocabulary
    all_words = parse_vocabulary_csv(vocab_csv_path)
    result.total_words_in_csv = len(all_words)

    # Deduplicate (already done in parse, but count for reporting)
    # Re-read raw to get total line count for comparison
    with open(vocab_csv_path, encoding="utf-8") as f:
        raw_lines = [line.strip() for line in f if line.strip()]
    result.total_words_in_csv = len(raw_lines)
    result.unique_words = len(all_words)

    # Parse GDPR data if available
    if gdpr_dir and gdpr_dir.exists():
        result.warnings.extend(_check_sensitive_files(gdpr_dir))

        languages_path = gdpr_dir / "languages.csv"
        if languages_path.exists():
            lang_stats = parse_languages_csv(languages_path)
            for stats in lang_stats:
                if stats.learning_language == lang:
                    result.language_stats = stats
                    break

        leaderboards_path = gdpr_dir / "leaderboards.csv"
        if leaderboards_path.exists():
            entries = parse_leaderboards_csv(leaderboards_path)
            result.leaderboard_weeks = len(entries)

    # Convert to entries and add to store
    vocab_entries = _words_to_entries(all_words, lang)
    added = store.add_entries(vocab_entries)
    result.new_entries_added = added
    result.duplicates_skipped = result.unique_words - added

    return result

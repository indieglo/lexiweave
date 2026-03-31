"""Frequency list importer.

Imports vocabulary from a word frequency list file (e.g. OpenSubtitles/FrequencyWords).

Expected format (FrequencyWords / OpenSubtitles):
    word count
    word count
    ...

One entry per line, space-separated. No header. UTF-8 encoded.
Lines are pre-sorted by frequency descending.

Source: https://github.com/hermitdave/FrequencyWords
License: CC BY-SA 4.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore

# Words to always skip regardless of position (common function words / noise)
_STOPWORDS: set[str] = {
    # Catalan / Romance stopwords
    "que", "no", "de", "la", "el", "i", "és", "en", "a", "un", "una", "les",
    "els", "per", "amb", "es", "li", "ho", "hi", "em", "et", "ens", "us",
    "me", "te", "se", "si", "he", "has", "ha", "hem", "heu", "han",
    "del", "al", "dels", "als", "uns", "unes",
    # Common across Romance languages
    "y", "o", "e", "da", "di", "il",
}

# Regex: only allow words made of Unicode letters (no digits, punctuation, etc.)
_WORD_RE = re.compile(r"^\w+$", re.UNICODE)


@dataclass
class FrequencyImportResult:
    total_in_file: int = 0
    imported: int = 0
    skipped_filter: int = 0
    duplicates_skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def parse_frequency_file(
    path: Path,
    limit: int = 1000,
    skip_top: int = 0,
    filter_stopwords: bool = True,
    filter_proper_nouns: bool = True,
    min_length: int = 2,
) -> list[str]:
    """Parse a FrequencyWords-format file and return a filtered word list.

    Args:
        path: Path to the frequency list file.
        limit: Maximum number of words to return.
        skip_top: Skip this many entries from the top of the list
                  (useful to skip stopwords by rank instead of a blocklist).
        filter_stopwords: Skip words in the built-in stopword list.
        filter_proper_nouns: Skip words that start with an uppercase letter.
        min_length: Minimum word length (default 2, filters clitic fragments
                    like ``l``, ``d``, ``m`` from Romance language contractions).

    Returns:
        List of words in frequency order (most common first).
    """
    words: list[str] = []
    skipped_top = 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if not parts:
                continue
            word = parts[0]

            # Skip top N by position
            if skipped_top < skip_top:
                skipped_top += 1
                continue

            # Skip short tokens (clitic fragments from contractions)
            if len(word) < min_length:
                continue

            # Skip proper nouns (uppercase first letter)
            if filter_proper_nouns and word[0].isupper():
                continue

            # Skip words with non-letter characters
            if not _WORD_RE.match(word):
                continue

            # Skip stopwords
            if filter_stopwords and word.lower() in _STOPWORDS:
                continue

            words.append(word)

            if len(words) >= limit:
                break

    return words


def import_frequency_list(
    path: Path,
    lang: str,
    store: VocabularyStore,
    limit: int = 1000,
    skip_top: int = 0,
    filter_stopwords: bool = True,
    filter_proper_nouns: bool = True,
    min_length: int = 2,
) -> FrequencyImportResult:
    """Import a frequency list into the vocabulary store.

    New entries are added; words already in the store are skipped.
    """
    result = FrequencyImportResult()

    # Count total lines for reporting
    with open(path, encoding="utf-8") as f:
        result.total_in_file = sum(1 for line in f if line.strip())

    words = parse_frequency_file(
        path,
        limit=limit,
        skip_top=skip_top,
        filter_stopwords=filter_stopwords,
        filter_proper_nouns=filter_proper_nouns,
        min_length=min_length,
    )

    result.skipped_filter = result.total_in_file - len(words) - skip_top

    now = datetime.now(UTC).isoformat()
    entries = [
        VocabularyEntry(
            id="",
            word=word,
            lang=lang,
            source="frequency_list",
            date_added=now,
        )
        for word in words
    ]

    added = store.add_entries(entries)
    result.imported = added
    result.duplicates_skipped = len(entries) - added

    return result

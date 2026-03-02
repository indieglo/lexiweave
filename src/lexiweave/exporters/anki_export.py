"""Anki deck exporter.

Generates .apkg files using genanki, or CSV for manual import.
Supports cloze deletion and vocabulary card types.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import genanki
from pydantic import BaseModel, Field

from lexiweave.config import LanguageConfig
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore

# --- Anki Note Models ---
# Model IDs must be stable (genanki uses them to identify note types).
# Generated from hash of model name to avoid collisions.


def _stable_id(name: str) -> int:
    """Generate a stable integer ID from a string."""
    h = hashlib.md5(name.encode()).hexdigest()  # noqa: S324
    return int(h[:8], 16)


CLOZE_MODEL = genanki.Model(
    _stable_id("lexiweave_cloze_v1"),
    "Lexiweave Cloze",
    fields=[
        {"name": "Text"},
        {"name": "Extra"},
        {"name": "Audio"},
    ],
    templates=[
        {
            "name": "Cloze Card",
            "qfmt": "{{cloze:Text}}<br>{{Audio}}",
            "afmt": "{{cloze:Text}}<br>{{Extra}}<br>{{Audio}}",
        },
    ],
    model_type=genanki.Model.CLOZE,
)

VOCAB_MODEL = genanki.Model(
    _stable_id("lexiweave_vocab_v1"),
    "Lexiweave Vocabulary",
    fields=[
        {"name": "Word"},
        {"name": "Definition"},
        {"name": "Sentences"},
        {"name": "Audio"},
        {"name": "Extra"},
    ],
    templates=[
        {
            "name": "Word → Definition",
            "qfmt": '<div style="font-size: 24px;">{{Word}}</div><br>{{Audio}}',
            "afmt": (
                '<div style="font-size: 24px;">{{Word}}</div><br>'
                "<hr>"
                '<div style="font-size: 18px;">{{Definition}}</div><br>'
                "{{Sentences}}<br>{{Audio}}"
            ),
        },
    ],
)


# --- Export Models ---


class ExportResult(BaseModel):
    """Result of an export operation."""

    cards_exported: int = 0
    file_path: str = ""
    format: str = ""
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


# --- Helpers ---


def _build_tags(entry: VocabularyEntry) -> list[str]:
    """Build Anki tags from entry metadata."""
    tags = list(entry.tags)
    if entry.source:
        tags.append(entry.source)
    if entry.cefr_level:
        tags.append(f"cefr::{entry.cefr_level}")
    return tags


def _audio_field(entry: VocabularyEntry) -> str:
    """Build the audio field reference for Anki."""
    if entry.audio.local_file:
        filename = Path(entry.audio.local_file).name
        return f"[sound:{filename}]"
    return ""


def _sentences_html(entry: VocabularyEntry) -> str:
    """Format sentences as HTML for the card back."""
    if not entry.sentences:
        return ""
    parts = []
    for s in entry.sentences:
        level_tag = f" ({s.cefr_level})" if s.cefr_level else ""
        parts.append(f"<div>{s.text}{level_tag}</div>")
    return "".join(parts)


def get_exportable_entries(
    vocab_store: VocabularyStore,
    incremental: bool = False,
) -> list[VocabularyEntry]:
    """Get entries ready for export.

    If incremental, only return entries without an anki_note_id.
    """
    vocab = vocab_store.load()
    entries = vocab.entries

    if incremental:
        entries = [e for e in entries if e.anki_note_id is None]

    return entries


# --- APKG Export ---


def export_apkg(
    entries: list[VocabularyEntry],
    lang_config: LanguageConfig,
    output_dir: Path,
) -> ExportResult:
    """Export vocabulary entries as an Anki .apkg file."""
    deck_name = lang_config.anki_deck_name or f"{lang_config.language_name}::Vocabulary"
    deck_id = _stable_id(deck_name)
    deck = genanki.Deck(deck_id, deck_name)

    media_files: list[str] = []
    cards_exported = 0
    skipped = 0
    errors: list[str] = []

    for entry in entries:
        tags = _build_tags(entry)
        audio = _audio_field(entry)

        # Collect audio media file
        if entry.audio.local_file and Path(entry.audio.local_file).exists():
            media_files.append(entry.audio.local_file)

        has_cloze = any(
            "{{c1::" in s.text for s in entry.sentences
        )

        if has_cloze:
            # Create cloze cards from sentences
            for sentence in entry.sentences:
                if "{{c1::" not in sentence.text:
                    continue

                extra_parts = []
                if entry.definitions.monolingual:
                    extra_parts.append(entry.definitions.monolingual)
                if entry.pos:
                    extra_parts.append(f"({entry.pos})")
                extra = " ".join(extra_parts)

                note = genanki.Note(
                    model=CLOZE_MODEL,
                    fields=[sentence.text, extra, audio],
                    tags=tags,
                )
                deck.add_note(note)
                cards_exported += 1

        elif entry.definitions.monolingual:
            # Create vocabulary card
            note = genanki.Note(
                model=VOCAB_MODEL,
                fields=[
                    entry.word,
                    entry.definitions.monolingual,
                    _sentences_html(entry),
                    audio,
                    entry.pos,
                ],
                tags=tags,
            )
            deck.add_note(note)
            cards_exported += 1
        else:
            skipped += 1

    if cards_exported == 0:
        return ExportResult(
            cards_exported=0,
            format="apkg",
            skipped=skipped,
            errors=["No cards to export. Generate definitions or sentences first."],
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"{lang_config.language_code}_{timestamp}.apkg"
    output_path = output_dir / filename

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(str(output_path))

    return ExportResult(
        cards_exported=cards_exported,
        file_path=str(output_path),
        format="apkg",
        skipped=skipped,
        errors=errors,
    )


# --- CSV Export ---


def export_csv(
    entries: list[VocabularyEntry],
    lang_config: LanguageConfig,
    output_dir: Path,
) -> ExportResult:
    """Export vocabulary entries as a CSV file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{lang_config.language_code}_vocabulary.csv"
    output_path = output_dir / filename

    cards_exported = 0
    skipped = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "word", "pos", "definition", "sentence_1", "sentence_2",
            "audio_file", "cefr_level", "source", "tags",
        ])

        for entry in entries:
            if not entry.definitions.monolingual and not entry.sentences:
                skipped += 1
                continue

            sentence_1 = entry.sentences[0].text if len(entry.sentences) > 0 else ""
            sentence_2 = entry.sentences[1].text if len(entry.sentences) > 1 else ""
            audio_file = Path(entry.audio.local_file).name if entry.audio.local_file else ""

            writer.writerow([
                entry.word,
                entry.pos,
                entry.definitions.monolingual,
                sentence_1,
                sentence_2,
                audio_file,
                entry.cefr_level or "",
                entry.source,
                ";".join(entry.tags),
            ])
            cards_exported += 1

    return ExportResult(
        cards_exported=cards_exported,
        file_path=str(output_path),
        format="csv",
        skipped=skipped,
    )

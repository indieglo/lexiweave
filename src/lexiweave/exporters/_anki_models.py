"""Shared Anki note type definitions and field-building helpers.

Used by both anki_export.py (genanki/.apkg path) and ankiconnect.py
(AnkiConnect direct sync path) to keep card templates in sync.
"""

from __future__ import annotations

from pathlib import Path

from lexiweave.tracking.vocabulary_store import VocabularyEntry

# --- Model names (must match between both export paths) ---

CLOZE_MODEL_NAME = "Lexiweave Cloze"
VOCAB_MODEL_NAME = "Lexiweave Vocabulary"

# --- Field definitions ---

CLOZE_FIELDS = ["Text", "Extra", "Audio", "Cognate"]
VOCAB_FIELDS = ["Word", "Definition", "Sentences", "Audio", "Extra"]

# --- Templates ---
# Keys match AnkiConnect createModel format: "Front" and "Back".
# anki_export.py maps these to genanki's "qfmt"/"afmt".

CLOZE_TEMPLATES = [
    {
        "name": "Cloze Card",
        "Front": "{{cloze:Text}}",
        "Back": (
            "{{cloze:Text}}"
            "<hr>"
            '<div class="definition">{{Extra}}</div>'
            '{{#Cognate}}<div class="cognate">{{Cognate}}</div>{{/Cognate}}'
            '<div class="audio">{{Audio}}</div>'
        ),
    },
]

VOCAB_TEMPLATES = [
    {
        "name": "Word → Definition",
        "Front": '<div style="font-size: 24px;">{{Word}}</div><br>{{Audio}}',
        "Back": (
            '<div style="font-size: 24px;">{{Word}}</div><br>'
            "<hr>"
            '<div style="font-size: 18px;">{{Definition}}</div><br>'
            "{{Sentences}}<br>{{Audio}}"
        ),
    },
]

# --- CSS ---

CLOZE_CSS = (
    ".card { font-family: Arial, sans-serif; font-size: 18px; "
    "text-align: left; color: #333; background: #fff; padding: 20px; }"
    ".cloze { font-weight: bold; color: #2196F3; }"
    "hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }"
    ".definition { color: #666; font-size: 15px; font-style: italic; "
    "margin-bottom: 10px; }"
    ".cognate { color: #888; font-size: 13px; margin-bottom: 12px; "
    "padding: 4px 8px; background: #f5f5f5; border-radius: 4px; "
    "display: inline-block; }"
    ".cognate .false-friend { color: #e53935; }"
    ".audio { margin-top: 8px; }"
)

VOCAB_CSS = ""

# --- Field-building helpers ---


def build_tags(entry: VocabularyEntry) -> list[str]:
    """Build Anki tags from entry metadata."""
    tags = list(entry.tags)
    if entry.source:
        tags.append(entry.source)
    if entry.cefr_level:
        tags.append(f"cefr::{entry.cefr_level}")
    return tags


def audio_field(entry: VocabularyEntry) -> str:
    """Build the Anki sound reference string for the Audio field."""
    if entry.audio.local_file:
        filename = Path(entry.audio.local_file).name
        return f"[sound:{filename}]"
    return ""


def cognate_html(entry: VocabularyEntry) -> str:
    """Format cognates as compact HTML for the Cognate field."""
    if not entry.cognates:
        return ""

    similarity_labels = {
        "high": "≈",
        "medium": "~",
        "low": "≠",
        "false_friend": "⚠",
    }

    parts = []
    for lang, link in sorted(entry.cognates.items()):
        symbol = similarity_labels.get(link.similarity, "·")
        label = lang.upper()
        if link.similarity == "false_friend":
            parts.append(
                f'{label}: <span class="false-friend">'
                f"{symbol} {link.word} (false friend)</span>"
            )
        else:
            parts.append(f"{label}: {symbol} {link.word}")

    return " &nbsp;|&nbsp; ".join(parts)


def sentences_html(entry: VocabularyEntry) -> str:
    """Format sentences as HTML for the Sentences field."""
    if not entry.sentences:
        return ""
    parts = []
    for s in entry.sentences:
        level_tag = f" ({s.cefr_level})" if s.cefr_level else ""
        parts.append(f"<div>{s.text}{level_tag}</div>")
    return "".join(parts)


def extra_html(entry: VocabularyEntry) -> str:
    """Build the Extra field: definition + styled POS label."""
    parts = []
    if entry.definitions.monolingual:
        parts.append(entry.definitions.monolingual)
    if entry.pos:
        parts.append(f'<span style="color:#999;font-size:13px;">({entry.pos})</span>')
    return "<br>".join(parts)


def has_cloze(entry: VocabularyEntry) -> bool:
    """Return True if the entry has at least one cloze sentence."""
    return any("{{c1::" in s.text for s in entry.sentences)

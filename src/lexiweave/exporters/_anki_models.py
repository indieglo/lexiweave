"""Shared Anki note type definitions and field-building helpers.

Used by both anki_export.py (genanki/.apkg path) and ankiconnect.py
(AnkiConnect direct sync path) to keep card templates in sync.

Model versioning: changing field names/count requires a new model name.
Changing only CSS or template HTML is a breaking change (AnkiConnect has
no updateModel action) — bump the version suffix in the model name.
"""

from __future__ import annotations

from pathlib import Path

from lexiweave.tracking.vocabulary_store import VocabularyEntry

# --- Model names (must match between both export paths) ---
# v2: added Image, Bilingual, IPA, Mnemonic fields

CLOZE_MODEL_NAME = "Lexiweave Cloze v2"
VOCAB_MODEL_NAME = "Lexiweave Vocabulary v2"

# --- Field definitions ---

CLOZE_FIELDS = ["Text", "Extra", "Audio", "Cognate", "Image", "Bilingual", "IPA", "Mnemonic"]
VOCAB_FIELDS = [
    "Word", "Definition", "Sentences", "Audio", "Extra",
    "Image", "Bilingual", "IPA", "Mnemonic",
]

# --- Templates ---
# Keys match AnkiConnect createModel format: "Front" and "Back".
# anki_export.py maps these to genanki's "qfmt"/"afmt".
#
# Conditional rendering: {{#Field}}...{{/Field}} shows content only when
# Field is non-empty. All new optional fields use this pattern.

CLOZE_TEMPLATES = [
    {
        "name": "Cloze Card",
        "Front": (
            "{{cloze:Text}}"
            "{{#Image}}<div class=\"image\">{{Image}}</div>{{/Image}}"
        ),
        "Back": (
            "{{cloze:Text}}"
            "{{#Image}}<div class=\"image\">{{Image}}</div>{{/Image}}"
            "<hr>"
            '{{#IPA}}<div class="ipa">{{IPA}}</div>{{/IPA}}'
            '<div class="definition">{{Extra}}</div>'
            '{{#Bilingual}}<div class="bilingual">{{Bilingual}}</div>{{/Bilingual}}'
            '{{#Cognate}}<div class="cognate">{{Cognate}}</div>{{/Cognate}}'
            '{{#Mnemonic}}<div class="mnemonic">💡 {{Mnemonic}}</div>{{/Mnemonic}}'
            '<div class="audio">{{Audio}}</div>'
        ),
    },
]

VOCAB_TEMPLATES = [
    {
        "name": "Word → Definition",
        "Front": (
            '<div class="word">{{Word}}</div>'
            "{{#Image}}<div class=\"image\">{{Image}}</div>{{/Image}}"
            "<br>{{Audio}}"
        ),
        "Back": (
            '<div class="word">{{Word}}</div>'
            "{{#Image}}<div class=\"image\">{{Image}}</div>{{/Image}}"
            "<hr>"
            '{{#IPA}}<div class="ipa">{{IPA}}</div>{{/IPA}}'
            '<div class="definition">{{Definition}}</div>'
            '{{#Bilingual}}<div class="bilingual">{{Bilingual}}</div>{{/Bilingual}}'
            "{{Sentences}}"
            '{{#Mnemonic}}<div class="mnemonic">💡 {{Mnemonic}}</div>{{/Mnemonic}}'
            "<br>{{Audio}}"
        ),
    },
]

# --- CSS ---

CLOZE_CSS = (
    ".card { font-family: Arial, sans-serif; font-size: 18px; "
    "text-align: left; color: #333; background: #fff; padding: 20px; }"
    ".cloze { font-weight: bold; color: #2196F3; }"
    "hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }"
    ".word { font-size: 24px; font-weight: bold; margin-bottom: 8px; }"
    ".ipa { color: #888; font-size: 14px; font-family: monospace; "
    "margin-bottom: 8px; }"
    ".definition { color: #444; font-size: 16px; font-style: italic; "
    "margin-bottom: 8px; }"
    ".bilingual { color: #2e7d32; font-size: 14px; margin-bottom: 8px; "
    "padding: 3px 8px; background: #e8f5e9; border-radius: 4px; "
    "display: inline-block; }"
    ".cognate { color: #888; font-size: 13px; margin-bottom: 12px; "
    "padding: 4px 8px; background: #f5f5f5; border-radius: 4px; "
    "display: inline-block; }"
    ".cognate .false-friend { color: #e53935; }"
    ".image { text-align: center; margin: 12px 0; }"
    ".image img { max-width: 300px; max-height: 200px; border-radius: 8px; }"
    ".mnemonic { color: #6a1b9a; font-size: 14px; margin-top: 12px; "
    "padding: 6px 10px; background: #f3e5f5; border-radius: 4px; }"
    ".audio { margin-top: 8px; }"
)

VOCAB_CSS = CLOZE_CSS

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


def image_field(entry: VocabularyEntry) -> str:
    """Build the Anki image tag for the Image field."""
    if entry.image.selected_file and Path(entry.image.selected_file).exists():
        filename = Path(entry.image.selected_file).name
        return f'<img src="{filename}">'
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

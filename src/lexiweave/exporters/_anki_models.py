"""Shared Anki note type definitions and field-building helpers.

Used by both anki_export.py (genanki/.apkg path) and ankiconnect.py
(AnkiConnect direct sync path) to keep card templates in sync.

Model versioning: changing field names/count requires a new model name.
Changing only CSS or template HTML is a breaking change (AnkiConnect has
no updateModel action) — bump the version suffix in the model name.
"""

from __future__ import annotations

import re
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
            '{{#Bilingual}}<div class="pill-row"><span class="bilingual">{{Bilingual}}</span></div>{{/Bilingual}}'  # noqa: E501
            '{{#Cognate}}<div class="pill-row"><span class="cognate">{{Cognate}}</span></div>{{/Cognate}}'  # noqa: E501
            '{{#Mnemonic}}<div class="pill-row"><span class="mnemonic">💡 {{Mnemonic}}</span></div>{{/Mnemonic}}'  # noqa: E501
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
            '{{#Bilingual}}<div class="pill-row"><span class="bilingual">{{Bilingual}}</span></div>{{/Bilingual}}'  # noqa: E501
            '<div class="sentences">{{Sentences}}</div>'
            '{{#Mnemonic}}<div class="pill-row"><span class="mnemonic">💡 {{Mnemonic}}</span></div>{{/Mnemonic}}'  # noqa: E501
            "<br>{{Audio}}"
        ),
    },
]

# --- CSS ---

CLOZE_CSS = (
    # Base card
    ".card { font-family: Arial, sans-serif; font-size: 18px; "
    "text-align: center; color: #1a1a1a; background: #fff; padding: 20px; }"
    ".cloze { font-weight: bold; color: #2a6a9e; }"  # Barcelona Blue light
    "hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }"
    ".word { font-size: 24px; font-weight: bold; margin-bottom: 8px; }"
    ".ipa { color: #6b6b6b; font-size: 14px; font-family: monospace; margin-bottom: 14px; }"
    ".definition { color: #444; font-size: 16px; font-style: italic; margin-bottom: 14px; }"
    # Pills — light mode (brand colors, light bg + dark text)
    ".pill-row { margin-bottom: 12px; }"
    ".bilingual { display: inline-block; font-size: 14px; padding: 3px 12px; "
    "border-radius: 4px; background: #d6f0e3; color: #1a7a4a; }"  # New Growth Green
    ".cognate { display: inline-block; font-size: 13px; padding: 4px 12px; "
    "border-radius: 4px; background: #daeaf7; color: #2a6a9e; }"  # Barcelona Blue
    ".cognate .false-friend { color: #a83232; }"  # Senyera Sunset light
    ".mnemonic { display: inline-block; font-size: 14px; padding: 6px 12px; "
    "border-radius: 4px; background: #faebd4; color: #a07830; }"  # Sagrada Gold
    # Image
    ".image { margin: 16px auto; }"
    ".image img { max-width: 300px; max-height: 200px; border-radius: 8px; }"
    ".sentences { margin-bottom: 12px; }"
    ".sentences div { margin-bottom: 6px; }"
    ".audio { margin-top: 12px; }"
    # Dark mode overrides (Anki adds .nightMode to body)
    ".nightMode .card { background: #171717; color: #e8e8e8; }"
    ".nightMode .cloze { color: #5a9fd4; }"  # Barcelona Blue dark
    ".nightMode hr { border-top-color: #333; }"
    ".nightMode .ipa { color: #888; }"
    ".nightMode .definition { color: #bbb; }"
    ".nightMode .bilingual { background: rgba(92,184,138,0.18); color: #5cb88a; }"
    ".nightMode .cognate { background: rgba(90,159,212,0.18); color: #5a9fd4; }"
    ".nightMode .cognate .false-friend { color: #d45a5a; }"
    ".nightMode .mnemonic { background: rgba(212,160,84,0.18); color: #d4a054; }"
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


_CLOZE_RE = re.compile(r"\{\{c\d+::([^}]+)\}\}")


def _strip_cloze(text: str) -> str:
    """Replace {{c1::word}} with a bold highlight of the word."""
    return _CLOZE_RE.sub(r'<b class="cloze">\1</b>', text)


def sentences_html(entry: VocabularyEntry) -> str:
    """Format sentences as HTML for the Sentences field (vocab cards).

    Cloze markers are stripped and replaced with a bold highlight so the
    sentence reads naturally on a non-cloze card type.
    """
    if not entry.sentences:
        return ""
    parts = []
    for s in entry.sentences:
        level_tag = f" ({s.cefr_level})" if s.cefr_level else ""
        parts.append(f"<div>{_strip_cloze(s.text)}{level_tag}</div>")
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

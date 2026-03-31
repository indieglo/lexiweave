"""AnkiConnect direct sync exporter.

Pushes vocabulary entries directly to a running Anki instance via the
AnkiConnect add-on (https://ankiweb.net/shared/info/2055492159).

AnkiConnect must be installed in Anki desktop and Anki must be running.
The add-on exposes a JSON-RPC API on http://localhost:8765.

Key advantage over .apkg export: existing notes are updated in-place,
preserving review history when card content changes.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from lexiweave.config import LanguageConfig
from lexiweave.exporters._anki_models import (
    CLOZE_CSS,
    CLOZE_FIELDS,
    CLOZE_MODEL_NAME,
    CLOZE_TEMPLATES,
    VOCAB_CSS,
    VOCAB_FIELDS,
    VOCAB_MODEL_NAME,
    VOCAB_TEMPLATES,
    audio_field,
    build_tags,
    cognate_html,
    extra_html,
    has_cloze,
    image_field,
    sentences_html,
)
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore

ANKICONNECT_VERSION = 6


class AnkiConnectError(Exception):
    """Raised when AnkiConnect returns an error or is unreachable."""


class SyncResult(BaseModel):
    """Result of an AnkiConnect sync operation."""

    added: int = 0
    updated: int = 0
    skipped: int = 0
    audio_uploaded: int = 0
    errors: list[str] = Field(default_factory=list)


class AnkiConnectClient:
    """HTTP client for the AnkiConnect add-on API."""

    def __init__(self, host: str = "http://localhost:8765") -> None:
        self.host = host

    def _request(self, action: str, **params: Any) -> Any:
        """POST a JSON-RPC request to AnkiConnect.

        Returns the result value on success.
        Raises AnkiConnectError on API errors or connection failures.
        """
        payload = json.dumps({
            "action": action,
            "version": ANKICONNECT_VERSION,
            "params": params,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                self.host,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                response = json.loads(resp.read())
        except OSError as e:
            msg = (
                f"Could not connect to AnkiConnect at {self.host}. "
                f"Is Anki running with the AnkiConnect add-on installed? ({e})"
            )
            raise AnkiConnectError(msg) from e

        if response.get("error"):
            raise AnkiConnectError(response["error"])

        return response["result"]

    def version(self) -> int:
        """Return the AnkiConnect API version. Use as a health check."""
        return int(self._request("version"))

    def deck_names(self) -> list[str]:
        """Return all deck names currently in Anki."""
        return list(self._request("deckNames"))

    def ensure_deck(self, deck_name: str) -> None:
        """Create the deck if it does not already exist."""
        if deck_name not in self.deck_names():
            self._request("createDeck", deck=deck_name)

    def model_names(self) -> list[str]:
        """Return all note type names currently in Anki."""
        return list(self._request("modelNames"))

    def ensure_model(
        self,
        model_name: str,
        fields: list[str],
        templates: list[dict],
        css: str = "",
        is_cloze: bool = False,
    ) -> None:
        """Create note type if it does not already exist.

        Note: AnkiConnect has no updateModel action. If the model already
        exists this is a no-op — template changes require a model version
        bump (new model name) to take effect.
        """
        if model_name in self.model_names():
            return

        anki_templates = [
            {
                "Name": t["name"],
                "Front": t["Front"],
                "Back": t["Back"],
            }
            for t in templates
        ]

        self._request(
            "createModel",
            modelName=model_name,
            inOrderFields=fields,
            css=css,
            isCloze=is_cloze,
            cardTemplates=anki_templates,
        )

    def store_audio(self, filename: str, filepath: Path) -> None:
        """Upload an audio file to Anki's media collection (base64-encoded)."""
        data = base64.b64encode(filepath.read_bytes()).decode("utf-8")
        self._request("storeMediaFile", filename=filename, data=data)

    def add_note(
        self,
        deck: str,
        model: str,
        fields: dict[str, str],
        tags: list[str],
    ) -> int:
        """Add a new note to Anki. Returns the integer note ID."""
        note_id = self._request(
            "addNote",
            note={
                "deckName": deck,
                "modelName": model,
                "fields": fields,
                "tags": tags,
                "options": {
                    "allowDuplicate": False,
                    "duplicateScope": "deck",
                },
            },
        )
        return int(note_id)

    def update_note(self, note_id: int, fields: dict[str, str]) -> None:
        """Update field values on an existing note (does not affect review history)."""
        self._request(
            "updateNoteFields",
            note={"id": note_id, "fields": fields},
        )

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        """Return info dicts for the given note IDs."""
        return list(self._request("notesInfo", notes=note_ids))

    def find_cards(self, note_id: int) -> list[int]:
        """Return card IDs for a given note ID."""
        return list(self._request("findCards", query=f"nid:{note_id}"))

    def reschedule_cards(self, card_ids: list[int], days: int) -> None:
        """Set the interval for cards to ``days`` days.

        This restores approximate scheduling after a deck reimport, without
        resetting review history. Anki will schedule the cards as if they were
        last reviewed ``days`` ago.
        """
        self._request("rescheduleCards", cards=card_ids, days=days)


# --- Sync ---


def _build_cloze_fields(entry: VocabularyEntry, sentence_text: str) -> dict[str, str]:
    return {
        "Text": sentence_text,
        "Extra": extra_html(entry),
        "Audio": audio_field(entry),
        "Cognate": cognate_html(entry),
        "Image": image_field(entry),
        "Bilingual": entry.definitions.bilingual,
        "IPA": entry.ipa,
        "Mnemonic": entry.mnemonic,
    }


def _build_vocab_fields(entry: VocabularyEntry) -> dict[str, str]:
    return {
        "Word": entry.word,
        "Definition": entry.definitions.monolingual,
        "Sentences": sentences_html(entry),
        "Audio": audio_field(entry),
        "Extra": entry.pos,
        "Image": image_field(entry),
        "Bilingual": entry.definitions.bilingual,
        "IPA": entry.ipa,
        "Mnemonic": entry.mnemonic,
    }


def sync(
    entries: list[VocabularyEntry],
    lang_config: LanguageConfig,
    vocab_store: VocabularyStore,
    incremental: bool = True,
    restore_scheduling: bool = False,
    client: AnkiConnectClient | None = None,
) -> SyncResult:
    """Push vocabulary entries to Anki via AnkiConnect.

    - New entries (no anki_note_id): added to Anki, note ID saved back.
    - Existing entries (has anki_note_id):
        - incremental=True: skipped entirely.
        - incremental=False (full sync): fields updated, review history preserved.
    - Audio uploaded for new notes only (audio doesn't change after generation).
    - restore_scheduling=True: after adding a new note, reschedule its cards
      to the interval stored in entry.strength.anki_interval_days (useful after a deck
      reimport to restore approximate scheduling from lexiweave's data).
    """
    if client is None:
        client = AnkiConnectClient()

    result = SyncResult()

    # Health check
    try:
        client.version()
    except AnkiConnectError as e:
        result.errors.append(str(e))
        return result

    deck_name = lang_config.anki_deck_name or f"{lang_config.language_name}::Vocabulary"

    # Ensure deck and note types exist
    client.ensure_deck(deck_name)
    client.ensure_model(
        CLOZE_MODEL_NAME, CLOZE_FIELDS, CLOZE_TEMPLATES, CLOZE_CSS, is_cloze=True
    )
    client.ensure_model(
        VOCAB_MODEL_NAME, VOCAB_FIELDS, VOCAB_TEMPLATES, VOCAB_CSS, is_cloze=False
    )

    for entry in entries:
        is_new = entry.anki_note_id is None

        if not is_new and incremental:
            result.skipped += 1
            continue

        # Skip entries with no content
        if not has_cloze(entry) and not entry.definitions.monolingual:
            result.skipped += 1
            continue

        tags = build_tags(entry)

        try:
            if has_cloze(entry):
                cloze_sentences = [s for s in entry.sentences if "{{c1::" in s.text]

                if is_new:
                    # Upload audio once per entry (not per sentence)
                    if entry.audio.local_file:
                        audio_path = Path(entry.audio.local_file)
                        if audio_path.exists():
                            client.store_audio(audio_path.name, audio_path)
                            result.audio_uploaded += 1

                    # Add one note per cloze sentence; store the first note ID
                    first_note_id = None
                    for sentence in cloze_sentences:
                        fields = _build_cloze_fields(entry, sentence.text)
                        note_id = client.add_note(deck_name, CLOZE_MODEL_NAME, fields, tags)
                        if first_note_id is None:
                            first_note_id = note_id

                    if first_note_id is not None:
                        vocab_store.update_entry(entry.id, {"anki_note_id": str(first_note_id)})
                        result.added += 1

                        if restore_scheduling and entry.strength.anki_interval_days > 0:
                            card_ids = client.find_cards(first_note_id)
                            if card_ids:
                                client.reschedule_cards(card_ids, entry.strength.anki_interval_days)

                else:
                    # Full sync: update fields of existing note
                    note_id = int(entry.anki_note_id)
                    fields = _build_cloze_fields(entry, cloze_sentences[0].text)
                    client.update_note(note_id, fields)
                    result.updated += 1

            else:
                # Vocabulary card
                fields = _build_vocab_fields(entry)

                if is_new:
                    if entry.audio.local_file:
                        audio_path = Path(entry.audio.local_file)
                        if audio_path.exists():
                            client.store_audio(audio_path.name, audio_path)
                            result.audio_uploaded += 1

                    note_id = client.add_note(deck_name, VOCAB_MODEL_NAME, fields, tags)
                    vocab_store.update_entry(entry.id, {"anki_note_id": str(note_id)})
                    result.added += 1

                    if restore_scheduling and entry.strength.anki_interval_days > 0:
                        card_ids = client.find_cards(note_id)
                        if card_ids:
                            client.reschedule_cards(card_ids, entry.strength.anki_interval_days)

                else:
                    client.update_note(int(entry.anki_note_id), fields)
                    result.updated += 1

        except AnkiConnectError as e:
            result.errors.append(f"{entry.word}: {e}")

    return result

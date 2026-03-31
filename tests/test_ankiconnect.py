"""Tests for AnkiConnect client and sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lexiweave.config import LanguageConfig
from lexiweave.exporters.ankiconnect import (
    AnkiConnectClient,
    AnkiConnectError,
    sync,
)
from lexiweave.tracking.vocabulary_store import (
    AudioData,
    DefinitionData,
    SentenceData,
    VocabularyEntry,
    VocabularyStore,
)

# --- Fixtures ---


def _mock_client() -> AnkiConnectClient:
    """Return a client with _request mocked."""
    client = AnkiConnectClient()
    client._request = MagicMock()
    return client


def _lang_config() -> LanguageConfig:
    return LanguageConfig(
        language_code="es",
        language_name="Spanish",
        current_cefr="B1",
        target_cefr="C1",
        anki_deck_name="Spanish::Vocabulary",
    )


def _cloze_entry(word: str = "comer", has_audio: bool = False) -> VocabularyEntry:
    audio = AudioData(local_file="/audio/comer.mp3") if has_audio else AudioData()
    return VocabularyEntry(
        id=f"es_{word}_001",
        word=word,
        lang="es",
        pos="verbo",
        source="test",
        definitions=DefinitionData(monolingual="Ingerir alimentos."),
        sentences=[
            SentenceData(text=f"Me gusta {{{{c1::{word}}}}} todos los días.", cefr_level="B1"),
        ],
        audio=audio,
    )


def _vocab_entry(word: str = "gato") -> VocabularyEntry:
    return VocabularyEntry(
        id=f"es_{word}_001",
        word=word,
        lang="es",
        source="test",
        definitions=DefinitionData(monolingual="Animal felino doméstico."),
    )


def _empty_entry(word: str = "empty") -> VocabularyEntry:
    return VocabularyEntry(id=f"es_{word}_001", word=word, lang="es", source="test")


# --- AnkiConnectClient tests ---


class TestAnkiConnectClient:
    def test_version_returns_int(self) -> None:
        client = _mock_client()
        client._request.return_value = 6
        assert client.version() == 6

    def test_version_raises_on_connection_error(self) -> None:
        client = AnkiConnectClient()
        with (
            patch("urllib.request.urlopen", side_effect=OSError("refused")),
            pytest.raises(AnkiConnectError, match="Could not connect"),
        ):
            client.version()

    def test_request_raises_on_api_error(self) -> None:
        client = AnkiConnectClient()
        response = json.dumps({"result": None, "error": "deck not found"}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            pytest.raises(AnkiConnectError, match="deck not found"),
        ):
            client.version()

    def test_ensure_deck_creates_when_missing(self) -> None:
        client = _mock_client()
        client._request.side_effect = [["Other Deck"], None]
        client.ensure_deck("Spanish::Vocabulary")
        calls = [c[0][0] for c in client._request.call_args_list]
        assert "createDeck" in calls

    def test_ensure_deck_skips_when_exists(self) -> None:
        client = _mock_client()
        client._request.return_value = ["Spanish::Vocabulary"]
        client.ensure_deck("Spanish::Vocabulary")
        calls = [c[0][0] for c in client._request.call_args_list]
        assert "createDeck" not in calls

    def test_ensure_model_creates_when_missing(self) -> None:
        client = _mock_client()
        client._request.side_effect = [["Other Model"], None]
        client.ensure_model(
            "Lexiweave Cloze",
            ["Text"],
            [{"name": "Card", "Front": "{{Text}}", "Back": "{{Text}}"}],
        )
        calls = [c[0][0] for c in client._request.call_args_list]
        assert "createModel" in calls

    def test_ensure_model_skips_when_exists(self) -> None:
        client = _mock_client()
        client._request.return_value = ["Lexiweave Cloze"]
        client.ensure_model("Lexiweave Cloze", ["Text"], [])
        calls = [c[0][0] for c in client._request.call_args_list]
        assert "createModel" not in calls

    def test_add_note_returns_id(self) -> None:
        client = _mock_client()
        client._request.return_value = 12345
        note_id = client.add_note("Spanish::Vocabulary", "Lexiweave Cloze", {"Text": "test"}, [])
        assert note_id == 12345

    def test_update_note_calls_correct_action(self) -> None:
        client = _mock_client()
        client._request.return_value = None
        client.update_note(99, {"Text": "updated"})
        action = client._request.call_args[0][0]
        assert action == "updateNoteFields"
        note_arg = client._request.call_args[1]["note"]
        assert note_arg["id"] == 99

    def test_store_audio_encodes_base64(self, tmp_path: Path) -> None:
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake mp3 data")
        client = _mock_client()
        client._request.return_value = "test.mp3"
        client.store_audio("test.mp3", audio_file)
        action = client._request.call_args[0][0]
        assert action == "storeMediaFile"
        data = client._request.call_args[1]["data"]
        import base64
        assert base64.b64decode(data) == b"fake mp3 data"


# --- Sync tests ---


class TestSync:
    def test_sync_adds_new_cloze_entry(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = _cloze_entry()
        store.add_entry(entry)

        client = _mock_client()
        # version, deckNames, createDeck, modelNames, createModel, modelNames, createModel, addNote
        client._request.side_effect = [6, ["Other"], None, ["Other"], None, ["Other"], None, 1001]

        result = sync(store.load().entries, _lang_config(), store, client=client)

        assert result.added == 1
        assert result.errors == []
        saved = store.find_by_word("comer")
        assert saved is not None
        assert saved.anki_note_id == "1001"

    def test_sync_incremental_skips_existing(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = _cloze_entry()
        store.add_entry(entry)
        store.update_entry("es_comer_001", {"anki_note_id": "999"})

        client = _mock_client()
        models = ["Lexiweave Cloze v2", "Lexiweave Vocabulary v2"]
        # version, deckNames (exists), modelNames x2 (both exist) — no creates
        client._request.side_effect = [6, ["Spanish::Vocabulary"], models, models]

        result = sync(store.load().entries, _lang_config(), store, incremental=True, client=client)

        assert result.skipped == 1
        assert result.added == 0
        # update_note and add_note should not have been called
        actions = [c[0][0] for c in client._request.call_args_list]
        assert "addNote" not in actions
        assert "updateNoteFields" not in actions

    def test_sync_full_updates_existing(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        entry = _cloze_entry()
        store.add_entry(entry)
        store.update_entry("es_comer_001", {"anki_note_id": "999"})

        client = _mock_client()
        models = ["Lexiweave Cloze v2", "Lexiweave Vocabulary v2"]
        client._request.side_effect = [6, ["Spanish::Vocabulary"], models, models, None]

        result = sync(store.load().entries, _lang_config(), store, incremental=False, client=client)

        assert result.updated == 1
        assert result.added == 0
        actions = [c[0][0] for c in client._request.call_args_list]
        assert "updateNoteFields" in actions

    def test_sync_skips_empty_entries(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(_empty_entry())

        client = _mock_client()
        models = ["Lexiweave Cloze v2", "Lexiweave Vocabulary v2"]
        client._request.side_effect = [6, ["Spanish::Vocabulary"], models, models]

        result = sync(store.load().entries, _lang_config(), store, client=client)

        assert result.skipped == 1
        assert result.added == 0

    def test_sync_unreachable_returns_error(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(_cloze_entry())

        client = AnkiConnectClient()
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            result = sync(store.load().entries, _lang_config(), store, client=client)

        assert len(result.errors) == 1
        assert result.added == 0

    def test_sync_uploads_audio_for_new_entry(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        audio_file = tmp_path / "comer.mp3"
        audio_file.write_bytes(b"mp3")
        entry = _cloze_entry(has_audio=True)
        entry.audio.local_file = str(audio_file)
        store.add_entry(entry)

        client = _mock_client()
        models = ["Lexiweave Cloze v2", "Lexiweave Vocabulary v2"]
        client._request.side_effect = [
            6, ["Spanish::Vocabulary"], models, models, "comer.mp3", 2001,
        ]

        result = sync(store.load().entries, _lang_config(), store, client=client)

        assert result.audio_uploaded == 1
        actions = [c[0][0] for c in client._request.call_args_list]
        assert "storeMediaFile" in actions

    def test_sync_skips_audio_upload_on_update(self, tmp_data_dir: Path, tmp_path: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        audio_file = tmp_path / "comer.mp3"
        audio_file.write_bytes(b"mp3")
        entry = _cloze_entry(has_audio=True)
        entry.audio.local_file = str(audio_file)
        store.add_entry(entry)
        store.update_entry("es_comer_001", {"anki_note_id": "999"})

        client = _mock_client()
        models = ["Lexiweave Cloze v2", "Lexiweave Vocabulary v2"]
        client._request.side_effect = [6, ["Spanish::Vocabulary"], models, models, None]

        result = sync(store.load().entries, _lang_config(), store, incremental=False, client=client)

        assert result.audio_uploaded == 0
        actions = [c[0][0] for c in client._request.call_args_list]
        assert "storeMediaFile" not in actions

    def test_sync_persists_note_id(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(_vocab_entry())

        client = _mock_client()
        models = ["Lexiweave Cloze v2", "Lexiweave Vocabulary v2"]
        client._request.side_effect = [6, ["Spanish::Vocabulary"], models, models, 5555]

        sync(store.load().entries, _lang_config(), store, client=client)

        saved = store.find_by_word("gato")
        assert saved is not None
        assert saved.anki_note_id == "5555"

    def test_sync_restore_scheduling(self, tmp_data_dir: Path) -> None:
        from lexiweave.tracking.vocabulary_store import StrengthData

        store = VocabularyStore(tmp_data_dir, "es")
        entry = _vocab_entry()
        store.add_entry(entry)
        # Simulate a word with known interval (30 days)
        store.update_entry("es_gato_001", {
            "strength": StrengthData(score=0.7, anki_interval_days=30).model_dump(),
        })

        client = _mock_client()
        models = ["Lexiweave Cloze v2", "Lexiweave Vocabulary v2"]
        # version, deckNames, modelNames x2, addNote, findCards, rescheduleCards
        client._request.side_effect = [
            6, ["Spanish::Vocabulary"], models, models, 7777, [11111], None,
        ]

        sync(
            store.load().entries, _lang_config(), store,
            restore_scheduling=True, client=client,
        )

        actions = [c[0][0] for c in client._request.call_args_list]
        assert "findCards" in actions
        assert "rescheduleCards" in actions
        # rescheduleCards should be called with the stored anki_interval_days
        reschedule_call = next(
            c for c in client._request.call_args_list if c[0][0] == "rescheduleCards"
        )
        assert reschedule_call[1]["days"] == 30

"""Tests for audio generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from lexiweave.config import LanguageConfig
from lexiweave.generators.audio import (
    apply_audio,
    generate_audio,
    get_words_needing_audio,
    make_audio_provider,
)
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore
from lexiweave.utils.audio import (
    AudioResult,
    EdgeTTSProvider,
    normalize_filename,
)


def _add_words(store: VocabularyStore, words: list[str]) -> None:
    for word in words:
        store.add_entry(VocabularyEntry(id="", word=word, lang="es", source="test"))


def _make_lang_config(**kwargs) -> LanguageConfig:
    defaults = {
        "language_code": "es",
        "language_name": "Spanish",
        "tts_voice": "es-ES-ElviraNeural",
    }
    defaults.update(kwargs)
    return LanguageConfig(**defaults)


class TestNormalizeFilename:
    def test_basic(self) -> None:
        assert normalize_filename("comer") == "comer"

    def test_spaces(self) -> None:
        assert normalize_filename("buenos días") == "buenos_días"

    def test_uppercase(self) -> None:
        assert normalize_filename("Comer") == "comer"

    def test_accents_preserved(self) -> None:
        assert normalize_filename("comíamos") == "comíamos"

    def test_special_chars_removed(self) -> None:
        assert normalize_filename("¿cómo?") == "cómo"

    def test_whitespace_stripped(self) -> None:
        assert normalize_filename("  comer  ") == "comer"


class TestEdgeTTSProvider:
    def test_default_voice_spanish(self) -> None:
        provider = EdgeTTSProvider(lang="es")
        assert provider.voice == "es-ES-ElviraNeural"

    def test_default_voice_catalan(self) -> None:
        provider = EdgeTTSProvider(lang="ca")
        assert provider.voice == "ca-ES-EnricNeural"

    def test_custom_voice_overrides_default(self) -> None:
        provider = EdgeTTSProvider(voice="es-MX-DaliaNeural", lang="es")
        assert provider.voice == "es-MX-DaliaNeural"

    def test_skips_existing_file(self, tmp_path: Path) -> None:
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        (audio_dir / "comer.mp3").write_bytes(b"fake audio")

        provider = EdgeTTSProvider(lang="es")
        result = provider.generate("comer", audio_dir)

        assert result.success is True
        assert result.file_path == str(audio_dir / "comer.mp3")

    @patch("lexiweave.utils.audio._generate_edge_tts", new_callable=AsyncMock)
    def test_generates_audio(self, mock_tts: AsyncMock, tmp_path: Path) -> None:
        audio_dir = tmp_path / "audio"

        # Make the mock create the file
        async def create_file(text, voice, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake audio data")

        mock_tts.side_effect = create_file

        provider = EdgeTTSProvider(lang="es")
        result = provider.generate("comer", audio_dir)

        assert result.success is True
        assert result.provider == "edge_tts"
        mock_tts.assert_called_once()

    @patch("lexiweave.utils.audio._generate_edge_tts", new_callable=AsyncMock)
    def test_handles_tts_error(self, mock_tts: AsyncMock, tmp_path: Path) -> None:
        mock_tts.side_effect = Exception("TTS failed")

        provider = EdgeTTSProvider(lang="es")
        result = provider.generate("comer", tmp_path / "audio")

        assert result.success is False
        assert "TTS failed" in result.error


class TestMakeAudioProvider:
    def test_uses_config_voice(self) -> None:
        config = _make_lang_config(tts_voice="es-MX-DaliaNeural")
        provider = make_audio_provider(config)
        assert provider.voice == "es-MX-DaliaNeural"

    def test_uses_default_when_no_voice(self) -> None:
        config = _make_lang_config(tts_voice="")
        provider = make_audio_provider(config)
        assert provider.voice == "es-ES-ElviraNeural"


class TestGenerateAudio:
    @patch("lexiweave.utils.audio._generate_edge_tts", new_callable=AsyncMock)
    def test_generates_for_entries(self, mock_tts: AsyncMock, tmp_path: Path) -> None:
        async def create_file(text, voice, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"audio")

        mock_tts.side_effect = create_file

        entries = [
            VocabularyEntry(id="es_comer_001", word="comer", lang="es"),
            VocabularyEntry(id="es_beber_001", word="beber", lang="es"),
        ]

        provider = EdgeTTSProvider(lang="es")
        results = generate_audio(entries, tmp_path / "audio", provider)

        assert len(results) == 2
        assert all(r.success for r in results)


class TestApplyAudio:
    def test_updates_vocabulary(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        results = [
            AudioResult(
                word="comer",
                file_path="/audio/comer.mp3",
                provider="edge_tts",
                success=True,
            ),
            AudioResult(
                word="beber",
                file_path="/audio/beber.mp3",
                provider="edge_tts",
                success=True,
            ),
        ]

        applied = apply_audio(results, store)

        assert applied == 2
        entry = store.find_by_word("comer")
        assert entry is not None
        assert entry.audio.local_file == "/audio/comer.mp3"
        assert entry.audio.provider == "edge_tts"

    def test_skips_failed_results(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [AudioResult(word="comer", success=False, error="failed")]
        applied = apply_audio(results, store)
        assert applied == 0

    def test_skips_unknown_words(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [
            AudioResult(
                word="unknown", file_path="/audio/unknown.mp3", provider="edge_tts", success=True
            )
        ]
        applied = apply_audio(results, store)
        assert applied == 0


class TestGetWordsNeedingAudio:
    def test_returns_entries_without_audio(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        # Add audio to one
        entry = store.find_by_word("comer")
        assert entry is not None
        store.update_entry(
            entry.id,
            {"audio": {"local_file": "/audio/comer.mp3", "provider": "edge_tts", "forvo_url": ""}},
        )

        needing = get_words_needing_audio(store)
        assert len(needing) == 1
        assert needing[0].word == "beber"

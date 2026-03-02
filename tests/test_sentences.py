"""Tests for the sentences generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from lexiweave.config import LanguageConfig
from lexiweave.generators.sentences import (
    SentenceResult,
    apply_sentences,
    build_sentence_prompt,
    generate_sentences,
    get_words_needing_sentences,
)
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore


def _make_lang_config(**kwargs) -> LanguageConfig:
    defaults = {
        "language_code": "es",
        "language_name": "Spanish",
        "current_cefr": "B1",
    }
    defaults.update(kwargs)
    return LanguageConfig(**defaults)


def _add_words(store: VocabularyStore, words: list[str]) -> None:
    for word in words:
        store.add_entry(VocabularyEntry(id="", word=word, lang="es", source="test"))


class TestBuildPrompt:
    def test_includes_language_and_cefr(self) -> None:
        config = _make_lang_config()
        prompt = build_sentence_prompt(["comer", "beber"], config)

        assert "Spanish" in prompt
        assert "B1" in prompt
        assert "B2" in prompt  # stretch level
        assert "comer" in prompt

    def test_stretch_level_progression(self) -> None:
        config = _make_lang_config(current_cefr="A2")
        prompt = build_sentence_prompt(["comer"], config)
        assert "A2" in prompt
        assert "B1" in prompt  # stretch for A2

    def test_uses_prompt_override(self) -> None:
        config = _make_lang_config(
            prompt_overrides={"sentence": "Custom: {language_name} {word_list}"}
        )
        prompt = build_sentence_prompt(["comer"], config)
        assert prompt == "Custom: Spanish comer"


class TestGenerateSentences:
    def test_parses_llm_response(self) -> None:
        mock_client = MagicMock()
        mock_client.generate_json.return_value = [
            {
                "word": "comer",
                "sentences": [
                    {
                        "text": "Me gusta {{c1::comer}} pizza.",
                        "cefr_level": "B1",
                        "type": "current",
                    },
                    {
                        "text": "Solíamos {{c1::comer}} juntos cada viernes.",
                        "cefr_level": "B2",
                        "type": "stretch",
                    },
                ],
            }
        ]

        results = generate_sentences(["comer"], _make_lang_config(), mock_client)

        assert len(results) == 1
        assert results[0].word == "comer"
        assert len(results[0].sentences) == 2
        assert "{{c1::comer}}" in results[0].sentences[0].text

    def test_batches_large_word_lists(self) -> None:
        mock_client = MagicMock()
        mock_client.generate_json.return_value = []

        words = [f"word_{i}" for i in range(45)]
        generate_sentences(words, _make_lang_config(), mock_client)

        # 45 words with batch size 20 = 3 API calls
        assert mock_client.generate_json.call_count == 3


class TestApplySentences:
    def test_updates_vocabulary(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [
            SentenceResult(
                word="comer",
                sentences=[
                    {"text": "Me gusta {{c1::comer}}.", "cefr_level": "B1", "type": "current"},
                    {"text": "Solíamos {{c1::comer}}.", "cefr_level": "B2", "type": "stretch"},
                ],
            )
        ]

        applied = apply_sentences(results, store)

        assert applied == 1
        entry = store.find_by_word("comer")
        assert entry is not None
        assert len(entry.sentences) == 2
        assert entry.sentences[0].source == "generated"

    def test_skips_empty_sentences(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [SentenceResult(word="comer", sentences=[])]
        applied = apply_sentences(results, store)
        assert applied == 0

    def test_skips_unknown_words(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [
            SentenceResult(
                word="unknown",
                sentences=[{"text": "test", "cefr_level": "B1", "type": "current"}],
            )
        ]
        applied = apply_sentences(results, store)
        assert applied == 0


class TestGetWordsNeedingSentences:
    def test_returns_entries_without_sentences(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        # Add sentences to one
        entry = store.find_by_word("comer")
        assert entry is not None
        store.update_entry(
            entry.id,
            {"sentences": [{"text": "test", "type": "cloze", "cefr_level": "B1", "source": "g"}]},
        )

        needing = get_words_needing_sentences(store)
        assert len(needing) == 1
        assert needing[0].word == "beber"

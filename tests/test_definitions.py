"""Tests for the definitions generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from lexiweave.config import LanguageConfig
from lexiweave.generators.definitions import (
    DefinitionResult,
    apply_definitions,
    build_definition_prompt,
    generate_definitions,
    get_words_needing_definitions,
)
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore


def _make_lang_config(**kwargs) -> LanguageConfig:
    defaults = {
        "language_code": "es",
        "language_name": "Spanish",
        "current_cefr": "B1",
        "definition_language": "es",
    }
    defaults.update(kwargs)
    return LanguageConfig(**defaults)


def _add_words(store: VocabularyStore, words: list[str]) -> None:
    for word in words:
        store.add_entry(VocabularyEntry(id="", word=word, lang="es", source="test"))


class TestBuildPrompt:
    def test_includes_language_and_cefr(self) -> None:
        config = _make_lang_config()
        prompt = build_definition_prompt(["comer", "beber"], config)

        assert "Spanish" in prompt
        assert "B1" in prompt
        assert "comer" in prompt
        assert "beber" in prompt

    def test_uses_prompt_override(self) -> None:
        config = _make_lang_config(
            prompt_overrides={"definition": "Custom prompt for {language_name}: {word_list}"}
        )
        prompt = build_definition_prompt(["comer"], config)

        assert prompt == "Custom prompt for Spanish: comer"


class TestGenerateDefinitions:
    def test_parses_llm_response(self) -> None:
        mock_client = MagicMock()
        mock_client.generate_json.return_value = [
            {"word": "comer", "pos": "verbo", "definition": "Tomar alimentos"},
            {"word": "beber", "pos": "verbo", "definition": "Tomar líquidos"},
        ]

        results = generate_definitions(
            ["comer", "beber"],
            _make_lang_config(),
            mock_client,
        )

        assert len(results) == 2
        assert results[0].word == "comer"
        assert results[0].definition == "Tomar alimentos"
        assert results[1].word == "beber"

    def test_batches_large_word_lists(self) -> None:
        mock_client = MagicMock()
        mock_client.generate_json.return_value = []

        words = [f"word_{i}" for i in range(65)]
        generate_definitions(words, _make_lang_config(), mock_client)

        # 65 words with batch size 30 = 3 API calls
        assert mock_client.generate_json.call_count == 3


class TestApplyDefinitions:
    def test_updates_vocabulary(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        results = [
            DefinitionResult(word="comer", pos="verbo", definition="Tomar alimentos"),
            DefinitionResult(word="beber", pos="verbo", definition="Tomar líquidos"),
        ]

        applied = apply_definitions(results, store, model_name="test-model")

        assert applied == 2
        entry = store.find_by_word("comer")
        assert entry is not None
        assert entry.definitions.monolingual == "Tomar alimentos"
        assert entry.definitions.generated_by == "test-model"
        assert entry.pos == "verbo"

    def test_skips_empty_definitions(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [DefinitionResult(word="comer", definition="")]
        applied = apply_definitions(results, store)
        assert applied == 0

    def test_skips_unknown_words(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [DefinitionResult(word="unknown_word", definition="test")]
        applied = apply_definitions(results, store)
        assert applied == 0

    def test_does_not_overwrite_existing_pos(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        store.add_entry(
            VocabularyEntry(id="", word="comer", lang="es", pos="verb", source="test")
        )

        results = [DefinitionResult(word="comer", pos="verbo", definition="Tomar alimentos")]
        apply_definitions(results, store)

        entry = store.find_by_word("comer")
        assert entry is not None
        assert entry.pos == "verb"  # Original POS preserved


class TestGetWordsNeedingDefinitions:
    def test_returns_entries_without_definitions(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        # Add a definition to one
        entry = store.find_by_word("comer")
        assert entry is not None
        store.update_entry(
            entry.id,
            {"definitions": {"monolingual": "test", "generated_by": "m", "generated_at": "t"}},
        )

        needing = get_words_needing_definitions(store)
        assert len(needing) == 1
        assert needing[0].word == "beber"

    def test_returns_empty_when_all_have_definitions(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        entry = store.find_by_word("comer")
        assert entry is not None
        store.update_entry(
            entry.id,
            {"definitions": {"monolingual": "test", "generated_by": "m", "generated_at": "t"}},
        )

        needing = get_words_needing_definitions(store)
        assert len(needing) == 0

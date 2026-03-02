"""Tests for the cognates generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from lexiweave.generators.cognates import (
    CognateResult,
    apply_cognates,
    build_cognate_prompt,
    generate_cognates,
    get_words_needing_cognates,
)
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore


def _add_words(store: VocabularyStore, words: list[str]) -> None:
    for word in words:
        store.add_entry(VocabularyEntry(id="", word=word, lang="es", source="test"))


class TestBuildPrompt:
    def test_includes_languages_and_words(self) -> None:
        prompt = build_cognate_prompt(["comer", "beber"], "Spanish", "Catalan")

        assert "Spanish" in prompt
        assert "Catalan" in prompt
        assert "comer" in prompt
        assert "beber" in prompt

    def test_includes_similarity_options(self) -> None:
        prompt = build_cognate_prompt(["comer"], "Spanish", "Catalan")
        assert "high" in prompt
        assert "false_friend" in prompt


class TestGenerateCognates:
    def test_parses_llm_response(self) -> None:
        mock_client = MagicMock()
        mock_client.generate_json.return_value = [
            {
                "source_word": "comer",
                "target_word": "menjar",
                "similarity": "low",
                "notes": "Different root: Latin comedere vs manducare",
            },
            {
                "source_word": "beber",
                "target_word": "beure",
                "similarity": "high",
                "notes": "Regular cognate from Latin bibere",
            },
        ]

        results = generate_cognates(
            ["comer", "beber"], "Spanish", "Catalan", mock_client
        )

        assert len(results) == 2
        assert results[0].source_word == "comer"
        assert results[0].target_word == "menjar"
        assert results[0].similarity == "low"
        assert results[1].source_word == "beber"
        assert results[1].target_word == "beure"

    def test_batches_large_word_lists(self) -> None:
        mock_client = MagicMock()
        mock_client.generate_json.return_value = []

        words = [f"word_{i}" for i in range(65)]
        generate_cognates(words, "Spanish", "Catalan", mock_client)

        # 65 words with batch size 30 = 3 API calls
        assert mock_client.generate_json.call_count == 3


class TestApplyCognates:
    def test_updates_vocabulary(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        results = [
            CognateResult(
                source_word="comer",
                target_word="menjar",
                similarity="low",
                notes="Different root",
            ),
            CognateResult(
                source_word="beber",
                target_word="beure",
                similarity="high",
                notes="Regular cognate",
            ),
        ]

        applied = apply_cognates(results, store, target_lang="ca")

        assert applied == 2
        entry = store.find_by_word("comer")
        assert entry is not None
        assert "ca" in entry.cognates
        assert entry.cognates["ca"].word == "menjar"
        assert entry.cognates["ca"].similarity == "low"

    def test_skips_empty_target_word(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [CognateResult(source_word="comer", target_word="")]
        applied = apply_cognates(results, store, target_lang="ca")
        assert applied == 0

    def test_skips_unknown_words(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        results = [CognateResult(source_word="unknown", target_word="desconegut")]
        applied = apply_cognates(results, store, target_lang="ca")
        assert applied == 0

    def test_preserves_existing_cognates(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        # Add a cognate for French first
        results_fr = [
            CognateResult(
                source_word="comer", target_word="manger", similarity="medium"
            )
        ]
        apply_cognates(results_fr, store, target_lang="fr")

        # Add a cognate for Catalan
        results_ca = [
            CognateResult(
                source_word="comer", target_word="menjar", similarity="low"
            )
        ]
        apply_cognates(results_ca, store, target_lang="ca")

        entry = store.find_by_word("comer")
        assert entry is not None
        assert "fr" in entry.cognates
        assert "ca" in entry.cognates
        assert entry.cognates["fr"].word == "manger"
        assert entry.cognates["ca"].word == "menjar"


class TestGetWordsNeedingCognates:
    def test_returns_entries_without_cognates(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer", "beber"])

        # Add cognate to one
        results = [
            CognateResult(source_word="comer", target_word="menjar", similarity="low")
        ]
        apply_cognates(results, store, target_lang="ca")

        needing = get_words_needing_cognates(store, target_lang="ca")
        assert len(needing) == 1
        assert needing[0].word == "beber"

    def test_different_target_lang(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _add_words(store, ["comer"])

        # Add cognate for French
        results = [
            CognateResult(source_word="comer", target_word="manger", similarity="medium")
        ]
        apply_cognates(results, store, target_lang="fr")

        # Still needs Catalan cognate
        needing = get_words_needing_cognates(store, target_lang="ca")
        assert len(needing) == 1

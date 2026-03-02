"""Tests for the gap report generator."""

from __future__ import annotations

from pathlib import Path

from lexiweave.assessment.gap_report import (
    _estimate_vocab_cefr,
    format_report_markdown,
    generate_report,
)
from lexiweave.assessment.grammar_store import (
    ErrorExample,
    GrammarConcept,
    GrammarStore,
    StrengthNote,
)
from lexiweave.tracking.vocabulary_store import VocabularyEntry, VocabularyStore


def _populate_grammar(store: GrammarStore) -> None:
    """Populate a grammar store with test data."""
    data = store.load()
    data.assessment_date = "2026-03-02T00:00:00Z"
    data.assessment_sources = ["dele_b1", "diagnostic"]
    data.assessment_notes = {"overall_cefr_estimate": "A2-B1"}
    data.concepts = [
        GrammarConcept(
            id="gram_preterite",
            name="Pretérito vs Imperfecto",
            cefr_level="A2-B1",
            status="gap",
            confidence=0.2,
            priority=1,
            notes="Biggest issue",
            error_examples=[
                ErrorExample(produced="comimos", expected="comíamos", context="Habitual"),
                ErrorExample(produced="trabajé", expected="trabajaba", context="Habitual"),
            ],
            sub_concepts=["habitual_imperfect", "completed_preterite"],
        ),
        GrammarConcept(
            id="gram_subjunctive",
            name="Present Subjunctive",
            cefr_level="B1",
            status="gap",
            confidence=0.1,
            priority=2,
            error_examples=[
                ErrorExample(produced="tiene", expected="tenga", context="After emotion"),
            ],
        ),
        GrammarConcept(
            id="gram_ser_estar",
            name="Ser vs Estar",
            cefr_level="A2-B1",
            status="weak",
            confidence=0.35,
            priority=4,
            error_examples=[
                ErrorExample(produced="es en", expected="está en", context="Location"),
            ],
        ),
        GrammarConcept(
            id="gram_conditional",
            name="Conditional Tense",
            cefr_level="B1-B2",
            status="untested",
            confidence=0.15,
            priority=8,
        ),
    ]
    data.strengths = [
        StrengthNote(id="s1", name="Vocabulary Breadth", notes="B1-level vocab size"),
        StrengthNote(id="s2", name="Present Tense", notes="Generally correct"),
    ]
    store.save(data)


def _populate_vocab(store: VocabularyStore, count: int = 50) -> None:
    """Add test vocabulary entries."""
    entries = [
        VocabularyEntry(id="", word=f"word_{i}", lang="es", source="duolingo_import")
        for i in range(count)
    ]
    store.add_entries(entries)


class TestEstimateVocabCefr:
    def test_pre_a1(self) -> None:
        assert _estimate_vocab_cefr(100) == "pre-A1"

    def test_a1(self) -> None:
        assert _estimate_vocab_cefr(500) == "A1"

    def test_a2(self) -> None:
        assert _estimate_vocab_cefr(1500) == "A2"

    def test_b1(self) -> None:
        assert _estimate_vocab_cefr(3000) == "B1"
        assert _estimate_vocab_cefr(3115) == "B1"

    def test_b2(self) -> None:
        assert _estimate_vocab_cefr(5000) == "B2"

    def test_c1(self) -> None:
        assert _estimate_vocab_cefr(8000) == "C1"


class TestGenerateReport:
    def test_report_with_data(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")
        _populate_grammar(grammar_store)
        _populate_vocab(vocab_store, count=3115)

        report = generate_report(grammar_store, vocab_store)

        assert report.language == "es"
        assert report.vocabulary_total == 3115
        assert report.vocab_estimate_cefr == "B1"
        assert report.grammar_estimate_cefr == "A2-B1"
        assert len(report.grammar_gaps) == 4
        assert len(report.strengths) == 2
        assert len(report.recommended_focus) == 3

    def test_report_empty_data(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")

        report = generate_report(grammar_store, vocab_store)

        assert report.vocabulary_total == 0
        assert report.vocab_estimate_cefr == "pre-A1"
        assert report.grammar_estimate_cefr == ""
        assert len(report.grammar_gaps) == 0
        assert len(report.recommended_focus) == 0

    def test_report_vocab_only(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")
        _populate_vocab(vocab_store, count=2000)

        report = generate_report(grammar_store, vocab_store)

        assert report.vocabulary_total == 2000
        assert report.vocab_estimate_cefr == "A2"
        assert len(report.grammar_gaps) == 0

    def test_gaps_sorted_by_priority(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")
        _populate_grammar(grammar_store)

        report = generate_report(grammar_store, vocab_store)

        priorities = [g.priority for g in report.grammar_gaps]
        assert priorities == sorted(priorities)

    def test_recommendations_top_3(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")
        _populate_grammar(grammar_store)

        report = generate_report(grammar_store, vocab_store)

        assert len(report.recommended_focus) == 3
        # Should be the top 3 gap/weak concepts by priority
        assert report.recommended_focus[0].concept_name == "Pretérito vs Imperfecto"
        assert report.recommended_focus[1].concept_name == "Present Subjunctive"
        assert report.recommended_focus[2].concept_name == "Ser vs Estar"

    def test_recommendations_skip_untested(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")
        _populate_grammar(grammar_store)

        report = generate_report(grammar_store, vocab_store)

        rec_names = [r.concept_name for r in report.recommended_focus]
        assert "Conditional Tense" not in rec_names

    def test_overall_assessment_text(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")
        _populate_grammar(grammar_store)
        _populate_vocab(vocab_store, count=3115)

        report = generate_report(grammar_store, vocab_store)

        assert "3,115 words" in report.overall_assessment
        assert "B1" in report.overall_assessment
        assert "A2-B1" in report.overall_assessment


class TestFormatMarkdown:
    def test_markdown_output(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")
        _populate_grammar(grammar_store)
        _populate_vocab(vocab_store, count=3115)

        report = generate_report(grammar_store, vocab_store)
        md = format_report_markdown(report)

        assert "# Gap Report: ES" in md
        assert "## Vocabulary Summary" in md
        assert "## Grammar Concepts" in md
        assert "## Strengths" in md
        assert "## Recommended Focus" in md
        assert "Pretérito vs Imperfecto" in md

    def test_markdown_empty_report(self, tmp_data_dir: Path) -> None:
        grammar_store = GrammarStore(tmp_data_dir, "es")
        vocab_store = VocabularyStore(tmp_data_dir, "es")

        report = generate_report(grammar_store, vocab_store)
        md = format_report_markdown(report)

        assert "# Gap Report: ES" in md
        assert "## Vocabulary Summary" in md

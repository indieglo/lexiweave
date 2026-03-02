"""Tests for grammar_store CRUD operations."""

from __future__ import annotations

from pathlib import Path

from lexiweave.assessment.grammar_store import (
    ErrorExample,
    GrammarConcept,
    GrammarStore,
    StrengthNote,
)


def _make_concept(
    concept_id: str = "gram_test", name: str = "Test Concept", **kwargs
) -> GrammarConcept:
    return GrammarConcept(id=concept_id, name=name, **kwargs)


class TestGrammarStoreLoad:
    def test_load_empty(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        data = store.load()
        assert data.language == "es"
        assert len(data.concepts) == 0

    def test_load_existing(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        store.add_concept(_make_concept())
        data = store.load()
        assert len(data.concepts) == 1

    def test_load_real_grammar_gaps(self, tmp_data_dir: Path) -> None:
        """Test loading a grammar_gaps.json with the full schema."""
        store = GrammarStore(tmp_data_dir, "es")
        concept = _make_concept(
            concept_id="gram_preterite",
            name="Pretérito vs Imperfecto",
            cefr_level="A2-B1",
            status="gap",
            confidence=0.2,
            priority=1,
            notes="Biggest issue",
            error_examples=[
                ErrorExample(
                    produced="comimos un almuerzo grande",
                    expected="comíamos un almuerzo grande",
                    context="Habitual action",
                )
            ],
            sub_concepts=["habitual_actions_imperfect", "completed_actions_preterite"],
        )
        store.add_concept(concept)

        loaded = store.get_concept("gram_preterite")
        assert loaded is not None
        assert loaded.name == "Pretérito vs Imperfecto"
        assert len(loaded.error_examples) == 1
        assert loaded.error_examples[0].produced == "comimos un almuerzo grande"
        assert len(loaded.sub_concepts) == 2


class TestGrammarStoreAdd:
    def test_add_concept(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        concept = store.add_concept(_make_concept())
        assert concept.id == "gram_test"
        assert store.gaps_path.exists()

    def test_add_duplicate_skipped(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        store.add_concept(_make_concept())
        store.add_concept(_make_concept())
        data = store.load()
        assert len(data.concepts) == 1

    def test_add_strength(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        store.add_strength(StrengthNote(id="str_vocab", name="Vocabulary Breadth", notes="Good"))
        data = store.load()
        assert len(data.strengths) == 1
        assert data.strengths[0].name == "Vocabulary Breadth"

    def test_add_strength_duplicate_skipped(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        store.add_strength(StrengthNote(id="str_vocab", name="Vocab"))
        store.add_strength(StrengthNote(id="str_vocab", name="Vocab"))
        data = store.load()
        assert len(data.strengths) == 1


class TestGrammarStoreUpdate:
    def test_update_concept(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        store.add_concept(_make_concept(confidence=0.2, status="gap"))
        updated = store.update_concept("gram_test", {"confidence": 0.6, "status": "weak"})
        assert updated is not None
        assert updated.confidence == 0.6
        assert updated.status == "weak"

        # Verify persistence
        reloaded = store.get_concept("gram_test")
        assert reloaded is not None
        assert reloaded.confidence == 0.6

    def test_update_nonexistent_returns_none(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        result = store.update_concept("nonexistent", {"status": "strong"})
        assert result is None


class TestGrammarStoreQuery:
    def test_get_concept(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        store.add_concept(_make_concept(concept_id="gram_a"))
        assert store.get_concept("gram_a") is not None
        assert store.get_concept("gram_b") is None

    def test_get_concepts_by_status(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        data = store.load()
        data.concepts = [
            _make_concept(concept_id="c1", status="gap"),
            _make_concept(concept_id="c2", status="weak"),
            _make_concept(concept_id="c3", status="gap"),
        ]
        store.save(data)

        gaps = store.get_concepts_by_status("gap")
        assert len(gaps) == 2
        weak = store.get_concepts_by_status("weak")
        assert len(weak) == 1

    def test_get_concepts_by_priority(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        data = store.load()
        data.concepts = [
            _make_concept(concept_id="c1", priority=3),
            _make_concept(concept_id="c2", priority=1),
            _make_concept(concept_id="c3", priority=2),
        ]
        store.save(data)

        ordered = store.get_concepts_by_priority()
        assert [c.id for c in ordered] == ["c2", "c3", "c1"]


class TestGrammarStoreSummary:
    def test_summary_empty(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        summary = store.get_summary()
        assert summary.total_concepts == 0
        assert summary.total_error_examples == 0

    def test_summary_counts(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        data = store.load()
        data.assessment_date = "2026-03-02T00:00:00Z"
        data.assessment_sources = ["dele_b1", "diagnostic"]
        data.concepts = [
            _make_concept(
                concept_id="c1",
                status="gap",
                cefr_level="A2-B1",
                error_examples=[
                    ErrorExample(produced="a", expected="b"),
                    ErrorExample(produced="c", expected="d"),
                ],
            ),
            _make_concept(concept_id="c2", status="weak", cefr_level="B1"),
        ]
        data.strengths = [StrengthNote(id="s1", name="Vocab")]
        store.save(data)

        summary = store.get_summary()
        assert summary.total_concepts == 2
        assert summary.by_status["gap"] == 1
        assert summary.by_status["weak"] == 1
        assert summary.total_error_examples == 2
        assert summary.total_strengths == 1
        assert summary.assessment_date == "2026-03-02T00:00:00Z"


class TestAtomicWrite:
    def test_save_creates_directories(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "fresh" / "data"
        store = GrammarStore(data_dir, "fr")
        store.add_concept(_make_concept())
        assert store.gaps_path.exists()

    def test_no_tmp_file_after_save(self, tmp_data_dir: Path) -> None:
        store = GrammarStore(tmp_data_dir, "es")
        store.add_concept(_make_concept())
        tmp_file = store.gaps_path.with_suffix(".json.tmp")
        assert not tmp_file.exists()

"""Grammar gaps data store.

CRUD operations on grammar_gaps.json for a single language.
Tracks grammar concepts, their status, and error examples
from ongoing assessments.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

# --- Data Models ---


class ErrorExample(BaseModel):
    produced: str
    expected: str
    context: str = ""


class GrammarConcept(BaseModel):
    id: str
    name: str
    cefr_level: str = ""
    status: str = "gap"  # gap, weak, untested, strong
    confidence: float = 0.0
    priority: int = 99
    notes: str = ""
    error_examples: list[ErrorExample] = Field(default_factory=list)
    sub_concepts: list[str] = Field(default_factory=list)
    cards_generated: int = 0
    cards_reviewed: int = 0
    last_practiced: str | None = None


class StrengthNote(BaseModel):
    id: str
    name: str
    notes: str = ""


class GrammarGapsFile(BaseModel):
    language: str
    assessment_date: str = ""
    assessment_sources: list[str] = Field(default_factory=list)
    assessment_notes: dict = Field(default_factory=dict)
    concepts: list[GrammarConcept] = Field(default_factory=list)
    strengths: list[StrengthNote] = Field(default_factory=list)


class GrammarSummary(BaseModel):
    language: str
    total_concepts: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_cefr_level: dict[str, int] = Field(default_factory=dict)
    total_error_examples: int = 0
    total_strengths: int = 0
    assessment_date: str = ""
    assessment_sources: list[str] = Field(default_factory=list)


# --- Store ---


class GrammarStore:
    """CRUD operations on grammar_gaps.json for a single language."""

    def __init__(self, data_dir: Path, lang: str):
        self.lang = lang
        self.lang_dir = data_dir / "languages" / lang
        self.gaps_path = self.lang_dir / "grammar_gaps.json"

    def load(self) -> GrammarGapsFile:
        """Load grammar_gaps.json; return empty file if not found."""
        if not self.gaps_path.exists():
            return GrammarGapsFile(language=self.lang)
        with open(self.gaps_path, encoding="utf-8") as f:
            data = json.load(f)
        return GrammarGapsFile(**data)

    def save(self, data: GrammarGapsFile) -> None:
        """Atomic write: write to .tmp then os.replace()."""
        self.lang_dir.mkdir(parents=True, exist_ok=True)

        tmp_path = self.gaps_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.gaps_path)

    def add_concept(self, concept: GrammarConcept) -> GrammarConcept:
        """Add a grammar concept. Skips if ID already exists."""
        data = self.load()
        existing_ids = {c.id for c in data.concepts}
        if concept.id in existing_ids:
            return concept
        data.concepts.append(concept)
        self.save(data)
        return concept

    def update_concept(self, concept_id: str, updates: dict) -> GrammarConcept | None:
        """Partial update of a concept. Returns updated concept or None."""
        data = self.load()
        for i, concept in enumerate(data.concepts):
            if concept.id == concept_id:
                concept_data = concept.model_dump()
                concept_data.update(updates)
                data.concepts[i] = GrammarConcept(**concept_data)
                self.save(data)
                return data.concepts[i]
        return None

    def get_concept(self, concept_id: str) -> GrammarConcept | None:
        """Get a concept by ID."""
        data = self.load()
        for concept in data.concepts:
            if concept.id == concept_id:
                return concept
        return None

    def get_concepts_by_status(self, status: str) -> list[GrammarConcept]:
        """Filter concepts by status (gap, weak, untested, strong)."""
        data = self.load()
        return [c for c in data.concepts if c.status == status]

    def get_concepts_by_priority(self) -> list[GrammarConcept]:
        """Return all concepts sorted by priority (lowest number = highest priority)."""
        data = self.load()
        return sorted(data.concepts, key=lambda c: c.priority)

    def add_strength(self, strength: StrengthNote) -> StrengthNote:
        """Add a strength note. Skips if ID already exists."""
        data = self.load()
        existing_ids = {s.id for s in data.strengths}
        if strength.id in existing_ids:
            return strength
        data.strengths.append(strength)
        self.save(data)
        return strength

    def get_summary(self) -> GrammarSummary:
        """Compute summary stats for grammar gaps."""
        data = self.load()
        summary = GrammarSummary(
            language=self.lang,
            total_concepts=len(data.concepts),
            total_strengths=len(data.strengths),
            assessment_date=data.assessment_date,
            assessment_sources=data.assessment_sources,
        )

        for concept in data.concepts:
            # By status
            summary.by_status[concept.status] = summary.by_status.get(concept.status, 0) + 1

            # By CEFR level
            level = concept.cefr_level or "unassigned"
            summary.by_cefr_level[level] = summary.by_cefr_level.get(level, 0) + 1

            # Error examples
            summary.total_error_examples += len(concept.error_examples)

        return summary

"""Gap report generator.

Reads grammar_gaps.json + vocabulary.json and produces a prioritized
study report showing where the learner should focus.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lexiweave.assessment.grammar_store import GrammarConcept, GrammarStore
from lexiweave.config import LanguageConfig
from lexiweave.tracking.vocabulary_store import VocabularyStore

# --- CEFR estimation from vocabulary size ---

# Rough vocabulary size thresholds per CEFR level (receptive vocabulary).
# Sources: Milton & Alexiou (2009), Nation (2006), general SLA consensus.
VOCAB_CEFR_THRESHOLDS = [
    (500, "A1"),
    (1500, "A2"),
    (3000, "B1"),
    (5000, "B2"),
    (8000, "C1"),
]


def _estimate_vocab_cefr(word_count: int) -> str:
    """Estimate CEFR level from vocabulary size."""
    level = "pre-A1"
    for threshold, cefr in VOCAB_CEFR_THRESHOLDS:
        if word_count >= threshold:
            level = cefr
        else:
            break
    return level


# --- Report Models ---


class GrammarGapSummary(BaseModel):
    id: str
    name: str
    cefr_level: str
    status: str
    confidence: float
    priority: int
    error_count: int
    sub_concept_count: int
    notes: str = ""


class RecommendedFocus(BaseModel):
    concept_name: str
    reason: str
    priority: int


class GapReport(BaseModel):
    language: str
    generated_at: str
    overall_assessment: str
    vocab_estimate_cefr: str
    grammar_estimate_cefr: str
    vocabulary_total: int
    vocabulary_with_definitions: int = 0
    vocabulary_with_sentences: int = 0
    vocabulary_with_audio: int = 0
    grammar_gaps: list[GrammarGapSummary] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommended_focus: list[RecommendedFocus] = Field(default_factory=list)


# --- Report Generation ---


def _build_overall_assessment(
    vocab_cefr: str,
    grammar_cefr: str,
    vocab_total: int,
    gap_count: int,
    weak_count: int,
) -> str:
    """Build a human-readable overall assessment string."""
    parts = [f"Vocabulary size ({vocab_total:,} words) suggests {vocab_cefr} level."]

    if grammar_cefr:
        parts.append(f"Grammar production estimated at {grammar_cefr}.")

    if vocab_cefr != grammar_cefr and grammar_cefr:
        parts.append(
            "The gap between vocabulary knowledge and grammatical accuracy "
            "is the primary bottleneck."
        )

    if gap_count > 0:
        parts.append(f"{gap_count} grammar concepts identified as gaps, {weak_count} as weak.")

    return " ".join(parts)


def _build_recommendations(concepts: list[GrammarConcept]) -> list[RecommendedFocus]:
    """Pick top 3 concepts to focus on, with reasoning."""
    recommendations: list[RecommendedFocus] = []

    # Sort by priority (lowest = most important)
    sorted_concepts = sorted(
        [c for c in concepts if c.status in ("gap", "weak")],
        key=lambda c: c.priority,
    )

    for concept in sorted_concepts[:3]:
        if concept.status == "gap":
            reason = (
                f"Identified as a gap (confidence {concept.confidence:.0%}). "
                f"{len(concept.error_examples)} error examples recorded."
            )
        else:
            reason = (
                f"Weak area (confidence {concept.confidence:.0%}). "
                f"Needs reinforcement to become reliable."
            )

        if concept.cefr_level:
            reason += f" CEFR level: {concept.cefr_level}."

        recommendations.append(
            RecommendedFocus(
                concept_name=concept.name,
                reason=reason,
                priority=concept.priority,
            )
        )

    return recommendations


def generate_report(
    grammar_store: GrammarStore,
    vocab_store: VocabularyStore,
    lang_config: LanguageConfig | None = None,
) -> GapReport:
    """Generate a gap report from grammar and vocabulary data."""
    grammar_data = grammar_store.load()
    vocab_stats = vocab_store.get_stats()

    vocab_cefr = _estimate_vocab_cefr(vocab_stats.total_entries)

    # Extract grammar CEFR from assessment notes if available
    grammar_cefr = ""
    if grammar_data.assessment_notes:
        grammar_cefr = grammar_data.assessment_notes.get("overall_cefr_estimate", "")

    gap_count = sum(1 for c in grammar_data.concepts if c.status == "gap")
    weak_count = sum(1 for c in grammar_data.concepts if c.status == "weak")

    overall = _build_overall_assessment(
        vocab_cefr, grammar_cefr, vocab_stats.total_entries, gap_count, weak_count
    )

    # Build grammar gap summaries, sorted by priority
    grammar_gaps = [
        GrammarGapSummary(
            id=c.id,
            name=c.name,
            cefr_level=c.cefr_level,
            status=c.status,
            confidence=c.confidence,
            priority=c.priority,
            error_count=len(c.error_examples),
            sub_concept_count=len(c.sub_concepts),
            notes=c.notes[:200] if c.notes else "",
        )
        for c in sorted(grammar_data.concepts, key=lambda c: c.priority)
    ]

    strengths = [f"{s.name}: {s.notes}" for s in grammar_data.strengths]

    recommendations = _build_recommendations(grammar_data.concepts)

    return GapReport(
        language=grammar_store.lang,
        generated_at=datetime.now(UTC).isoformat(),
        overall_assessment=overall,
        vocab_estimate_cefr=vocab_cefr,
        grammar_estimate_cefr=grammar_cefr,
        vocabulary_total=vocab_stats.total_entries,
        vocabulary_with_definitions=vocab_stats.with_definitions,
        vocabulary_with_sentences=vocab_stats.with_sentences,
        vocabulary_with_audio=vocab_stats.with_audio,
        grammar_gaps=grammar_gaps,
        strengths=strengths,
        recommended_focus=recommendations,
    )


# --- Formatting ---


def format_report_rich(report: GapReport, console: Console) -> None:
    """Print the gap report using Rich formatting."""
    # Overall assessment
    console.print(
        Panel(
            report.overall_assessment,
            title=f"Gap Report: {report.language.upper()}",
            border_style="blue",
        )
    )
    console.print()

    # Vocabulary summary
    table = Table(title="Vocabulary Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Total words", f"{report.vocabulary_total:,}")
    table.add_row("Estimated CEFR (vocab size)", report.vocab_estimate_cefr)
    if report.grammar_estimate_cefr:
        table.add_row("Estimated CEFR (grammar)", report.grammar_estimate_cefr)
    table.add_row("With definitions", str(report.vocabulary_with_definitions))
    table.add_row("With sentences", str(report.vocabulary_with_sentences))
    table.add_row("With audio", str(report.vocabulary_with_audio))
    console.print(table)
    console.print()

    # Grammar gaps
    if report.grammar_gaps:
        table = Table(title="Grammar Concepts")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Concept", style="bold")
        table.add_column("CEFR")
        table.add_column("Status")
        table.add_column("Confidence", justify="right")
        table.add_column("Errors", justify="right")

        status_colors = {"gap": "red", "weak": "yellow", "untested": "dim", "strong": "green"}

        for gap in report.grammar_gaps:
            color = status_colors.get(gap.status, "white")
            table.add_row(
                str(gap.priority),
                gap.name,
                gap.cefr_level,
                f"[{color}]{gap.status}[/{color}]",
                f"{gap.confidence:.0%}",
                str(gap.error_count),
            )

        console.print(table)
        console.print()

    # Strengths
    if report.strengths:
        console.print("[bold]Strengths:[/bold]")
        for strength in report.strengths:
            console.print(f"  [green]+[/green] {strength}")
        console.print()

    # Recommendations
    if report.recommended_focus:
        console.print("[bold]Recommended Focus (Top 3):[/bold]")
        for i, rec in enumerate(report.recommended_focus, 1):
            console.print(f"  {i}. [bold]{rec.concept_name}[/bold]")
            console.print(f"     {rec.reason}")
        console.print()


def format_report_markdown(report: GapReport) -> str:
    """Format the gap report as markdown."""
    lines: list[str] = []

    lines.append(f"# Gap Report: {report.language.upper()}")
    lines.append("")
    lines.append(f"*Generated: {report.generated_at}*")
    lines.append("")

    # Overall
    lines.append("## Overall Assessment")
    lines.append("")
    lines.append(report.overall_assessment)
    lines.append("")

    # Vocabulary
    lines.append("## Vocabulary Summary")
    lines.append("")
    lines.append(f"- **Total words:** {report.vocabulary_total:,}")
    lines.append(f"- **Estimated CEFR (vocab size):** {report.vocab_estimate_cefr}")
    if report.grammar_estimate_cefr:
        lines.append(f"- **Estimated CEFR (grammar):** {report.grammar_estimate_cefr}")
    lines.append(f"- **With definitions:** {report.vocabulary_with_definitions}")
    lines.append(f"- **With sentences:** {report.vocabulary_with_sentences}")
    lines.append(f"- **With audio:** {report.vocabulary_with_audio}")
    lines.append("")

    # Grammar gaps
    if report.grammar_gaps:
        lines.append("## Grammar Concepts")
        lines.append("")
        lines.append("| # | Concept | CEFR | Status | Confidence | Errors |")
        lines.append("|---|---------|------|--------|------------|--------|")
        for gap in report.grammar_gaps:
            lines.append(
                f"| {gap.priority} | {gap.name} | {gap.cefr_level} | "
                f"{gap.status} | {gap.confidence:.0%} | {gap.error_count} |"
            )
        lines.append("")

    # Strengths
    if report.strengths:
        lines.append("## Strengths")
        lines.append("")
        for strength in report.strengths:
            lines.append(f"- {strength}")
        lines.append("")

    # Recommendations
    if report.recommended_focus:
        lines.append("## Recommended Focus")
        lines.append("")
        for i, rec in enumerate(report.recommended_focus, 1):
            lines.append(f"{i}. **{rec.concept_name}** — {rec.reason}")
        lines.append("")

    return "\n".join(lines)

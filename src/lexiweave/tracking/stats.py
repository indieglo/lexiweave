"""Pipeline progress statistics.

Computes richer stats than VocabularyStore.get_stats(), including
strength tier breakdown and pipeline stage completeness.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

from lexiweave.tracking.strength import categorize_strength
from lexiweave.tracking.vocabulary_store import VocabularyStore


class PipelineStats(BaseModel):
    """Pipeline completeness stats for a single language."""

    language: str
    total: int = 0
    with_definitions: int = 0
    with_sentences: int = 0
    with_audio: int = 0
    with_cognates: int = 0
    exported: int = 0
    ready_to_export: int = 0
    strength_tiers: dict[str, int] = Field(default_factory=dict)


def get_pipeline_stats(vocab_store: VocabularyStore) -> PipelineStats:
    """Compute pipeline completeness stats for a language."""
    vocab = vocab_store.load()
    stats = PipelineStats(language=vocab_store.lang, total=len(vocab.entries))

    tier_counts: dict[str, int] = {
        "new": 0,
        "learning": 0,
        "young": 0,
        "mature": 0,
        "mastered": 0,
    }

    for entry in vocab.entries:
        has_def = bool(entry.definitions.monolingual)
        has_sent = bool(entry.sentences)
        has_audio = bool(entry.audio.local_file or entry.audio.forvo_url)
        has_cognates = bool(entry.cognates)

        if has_def:
            stats.with_definitions += 1
        if has_sent:
            stats.with_sentences += 1
        if has_audio:
            stats.with_audio += 1
        if has_cognates:
            stats.with_cognates += 1
        if entry.anki_note_id:
            stats.exported += 1
        if has_def and has_sent and has_audio:
            stats.ready_to_export += 1

        tier = categorize_strength(entry.strength.score)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    stats.strength_tiers = tier_counts
    return stats


def get_cross_language_stats(
    data_dir: Path,
    languages: list[str],
) -> list[PipelineStats]:
    """Compute pipeline stats across multiple languages."""
    results = []
    for lang in languages:
        store = VocabularyStore(data_dir, lang)
        vocab = store.load()
        if vocab.entries:
            results.append(get_pipeline_stats(store))
    return results


def format_stats(stats: PipelineStats, console: Console) -> None:
    """Display pipeline stats as a Rich table."""
    table = Table(title=f"Pipeline Stats: {stats.language.upper()}")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Coverage", justify="right")

    def pct(n: int) -> str:
        return f"{n / stats.total:.0%}" if stats.total > 0 else "—"

    table.add_row("Total entries", str(stats.total), "")
    table.add_row("", "", "")
    table.add_row("[underline]Pipeline Stages[/underline]", "", "")
    table.add_row("  With definitions", str(stats.with_definitions), pct(stats.with_definitions))
    table.add_row("  With sentences", str(stats.with_sentences), pct(stats.with_sentences))
    table.add_row("  With audio", str(stats.with_audio), pct(stats.with_audio))
    table.add_row("  With cognates", str(stats.with_cognates), pct(stats.with_cognates))
    table.add_row("  Exported to Anki", str(stats.exported), pct(stats.exported))
    table.add_row("  Ready to export", str(stats.ready_to_export), pct(stats.ready_to_export))

    if any(v > 0 for v in stats.strength_tiers.values()):
        table.add_row("", "", "")
        table.add_row("[underline]Strength Tiers[/underline]", "", "")
        tier_colors = {
            "new": "dim",
            "learning": "red",
            "young": "yellow",
            "mature": "green",
            "mastered": "bold green",
        }
        for tier in ("new", "learning", "young", "mature", "mastered"):
            count = stats.strength_tiers.get(tier, 0)
            color = tier_colors.get(tier, "white")
            table.add_row(f"  [{color}]{tier}[/{color}]", str(count), pct(count))

    console.print(table)

"""lexiweave CLI entry point."""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from lexiweave.assessment.gap_report import (
    format_report_markdown,
    format_report_rich,
    generate_report,
)
from lexiweave.assessment.grammar_store import GrammarStore
from lexiweave.config import (
    DEFAULT_CONFIG_DIR,
    get_data_dir,
    load_global_config,
    load_language_config,
)
from lexiweave.generators.cognates import (
    apply_cognates,
    generate_cognates,
    get_words_needing_cognates,
)
from lexiweave.generators.definitions import (
    apply_definitions,
    generate_definitions,
    get_words_needing_definitions,
)
from lexiweave.generators.sentences import (
    apply_sentences,
    generate_sentences,
    get_words_needing_sentences,
)
from lexiweave.importers.duolingo import import_duolingo
from lexiweave.tracking.vocabulary_store import VocabularyStore
from lexiweave.utils.cache import ResponseCache
from lexiweave.utils.llm import LLMClient, LLMError

app = typer.Typer(
    name="lexiweave",
    help="Multi-language AI-powered vocabulary tracking and card generation.",
    no_args_is_help=True,
)
assess_app = typer.Typer(help="Assessment and gap analysis commands.")
app.add_typer(assess_app, name="assess")
generate_app = typer.Typer(help="Generate content for vocabulary entries using AI.")
app.add_typer(generate_app, name="generate")
console = Console()


@app.command()
def setup(
    config_dir: Path = typer.Option(
        DEFAULT_CONFIG_DIR, "--config-dir", help="Config directory path"
    ),
) -> None:
    """Copy example config files to real config files and create data directories.

    Will NOT overwrite existing config files.
    """
    created: list[str] = []
    skipped: list[str] = []

    # Copy global config
    example = config_dir / "global.example.json"
    target = config_dir / "global.json"
    if example.exists():
        if target.exists():
            skipped.append("config/global.json (already exists)")
        else:
            shutil.copy2(example, target)
            created.append("config/global.json")

    # Copy language configs
    lang_dir = config_dir / "languages"
    if lang_dir.exists():
        for example_file in sorted(lang_dir.glob("*.example.json")):
            target_name = example_file.name.replace(".example.json", ".json")
            target_file = lang_dir / target_name
            if target_file.exists():
                skipped.append(f"config/languages/{target_name} (already exists)")
            else:
                shutil.copy2(example_file, target_file)
                created.append(f"config/languages/{target_name}")

    # Create data directories
    global_config = load_global_config(config_dir)
    data_dir = get_data_dir(global_config)
    for lang in global_config.languages:
        lang_data = data_dir / "languages" / lang / "imports"
        lang_data.mkdir(parents=True, exist_ok=True)
    (data_dir / "shared").mkdir(parents=True, exist_ok=True)
    (data_dir / "cache").mkdir(parents=True, exist_ok=True)

    # Report
    if created:
        console.print("[green]Created:[/green]")
        for item in created:
            console.print(f"  {item}")
    if skipped:
        console.print("[yellow]Skipped:[/yellow]")
        for item in skipped:
            console.print(f"  {item}")

    console.print(f"\n[green]Data directories ready at {data_dir}[/green]")
    console.print(
        "\n[dim]Edit config/global.json to add your API key, then edit "
        "language configs to set your CEFR levels.[/dim]"
    )


@app.command(name="import")
def import_cmd(
    source: str = typer.Argument(help="Import source: 'duolingo'"),
    vocab_csv: Path = typer.Option(..., "--vocab-csv", help="Path to vocabulary CSV file"),
    gdpr_dir: Path | None = typer.Option(
        None, "--gdpr-dir", help="Path to Duolingo GDPR export directory"
    ),
    lang: str = typer.Option("es", "--lang", help="Language code"),
) -> None:
    """Import vocabulary from an external source."""
    if source != "duolingo":
        console.print(f"[red]Unknown source '{source}'. Supported: duolingo[/red]")
        raise typer.Exit(1)

    if not vocab_csv.exists():
        console.print(f"[red]Vocabulary CSV not found: {vocab_csv}[/red]")
        raise typer.Exit(1)

    global_config = load_global_config()
    data_dir = get_data_dir(global_config)
    store = VocabularyStore(data_dir, lang)

    console.print(f"Importing Duolingo data for [bold]{lang}[/bold]...")

    result = import_duolingo(vocab_csv, gdpr_dir, lang, store)

    # Display warnings
    for warning in result.warnings:
        console.print(f"[yellow]  Warning: {warning}[/yellow]")

    # Display results
    console.print()
    table = Table(title="Import Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Words in CSV", str(result.total_words_in_csv))
    table.add_row("Unique words", str(result.unique_words))
    table.add_row("New entries added", str(result.new_entries_added))
    table.add_row("Duplicates skipped", str(result.duplicates_skipped))

    if result.language_stats:
        stats = result.language_stats
        table.add_row("", "")
        table.add_row("Duolingo XP", f"{stats.points:,}")
        table.add_row("Total lessons", f"{stats.total_lessons:,}")
        table.add_row("Days active", f"{stats.days_active:,}")
        if stats.last_active:
            table.add_row("Last active", stats.last_active)

    if result.leaderboard_weeks > 0:
        table.add_row("Leaderboard weeks", str(result.leaderboard_weeks))

    console.print(table)


@app.command()
def stats(
    lang: str | None = typer.Option(
        None, "--lang", help="Language code (default: all configured languages)"
    ),
) -> None:
    """Show vocabulary statistics."""
    global_config = load_global_config()
    data_dir = get_data_dir(global_config)

    languages = [lang] if lang else global_config.languages

    for language in languages:
        store = VocabularyStore(data_dir, language)
        vocab_stats = store.get_stats()

        if vocab_stats.total_entries == 0:
            console.print(
                f"[dim]{language}: No vocabulary data yet. "
                f"Run `lexiweave import` to add words.[/dim]"
            )
            continue

        table = Table(title=f"Vocabulary Stats: {language.upper()}")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("Total entries", str(vocab_stats.total_entries))

        # By source
        if vocab_stats.by_source:
            table.add_row("", "")
            table.add_row("[underline]By Source[/underline]", "")
            for src, count in sorted(vocab_stats.by_source.items()):
                table.add_row(f"  {src}", str(count))

        # By CEFR level
        if vocab_stats.by_cefr_level:
            table.add_row("", "")
            table.add_row("[underline]By CEFR Level[/underline]", "")
            for level, count in sorted(vocab_stats.by_cefr_level.items()):
                table.add_row(f"  {level}", str(count))

        # Content coverage
        table.add_row("", "")
        table.add_row("[underline]Content Coverage[/underline]", "")
        table.add_row("  With definitions", str(vocab_stats.with_definitions))
        table.add_row("  With sentences", str(vocab_stats.with_sentences))
        table.add_row("  With audio", str(vocab_stats.with_audio))

        console.print(table)
        console.print()


# --- Assess commands ---


@assess_app.command(name="report")
def assess_report(
    lang: str = typer.Option("es", "--lang", help="Language code"),
    export: bool = typer.Option(False, "--export", help="Also save report as markdown file"),
) -> None:
    """Generate a prioritized gap analysis report."""
    global_config = load_global_config()
    data_dir = get_data_dir(global_config)

    grammar_store = GrammarStore(data_dir, lang)
    vocab_store = VocabularyStore(data_dir, lang)

    lang_config = None
    with contextlib.suppress(FileNotFoundError):
        lang_config = load_language_config(lang)

    report = generate_report(grammar_store, vocab_store, lang_config)

    format_report_rich(report, console)

    if export:
        md = format_report_markdown(report)
        export_path = data_dir / "languages" / lang / "gap_report.md"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(md, encoding="utf-8")
        console.print(f"[green]Report saved to {export_path}[/green]")


@assess_app.command(name="grammar")
def assess_grammar(
    lang: str = typer.Option("es", "--lang", help="Language code"),
) -> None:
    """Show grammar assessment summary."""
    global_config = load_global_config()
    data_dir = get_data_dir(global_config)

    grammar_store = GrammarStore(data_dir, lang)
    summary = grammar_store.get_summary()

    if summary.total_concepts == 0:
        console.print(
            f"[dim]{lang}: No grammar assessment data yet. "
            f"Add a grammar_gaps.json to data/languages/{lang}/.[/dim]"
        )
        return

    table = Table(title=f"Grammar Assessment: {lang.upper()}")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Assessment date", summary.assessment_date or "unknown")
    if summary.assessment_sources:
        table.add_row("Sources", ", ".join(summary.assessment_sources))
    table.add_row("Total concepts", str(summary.total_concepts))
    table.add_row("Total error examples", str(summary.total_error_examples))
    table.add_row("Strengths noted", str(summary.total_strengths))

    if summary.by_status:
        table.add_row("", "")
        table.add_row("[underline]By Status[/underline]", "")
        status_colors = {"gap": "red", "weak": "yellow", "untested": "dim", "strong": "green"}
        for status, count in sorted(summary.by_status.items()):
            color = status_colors.get(status, "white")
            table.add_row(f"  [{color}]{status}[/{color}]", str(count))

    if summary.by_cefr_level:
        table.add_row("", "")
        table.add_row("[underline]By CEFR Level[/underline]", "")
        for level, count in sorted(summary.by_cefr_level.items()):
            table.add_row(f"  {level}", str(count))

    console.print(table)
    console.print()

    # Show concepts sorted by priority
    concepts = grammar_store.get_concepts_by_priority()
    if concepts:
        detail_table = Table(title="Concepts by Priority")
        detail_table.add_column("#", justify="right", style="dim")
        detail_table.add_column("Concept", style="bold")
        detail_table.add_column("CEFR")
        detail_table.add_column("Status")
        detail_table.add_column("Confidence", justify="right")
        detail_table.add_column("Errors", justify="right")

        status_colors = {"gap": "red", "weak": "yellow", "untested": "dim", "strong": "green"}
        for c in concepts:
            color = status_colors.get(c.status, "white")
            detail_table.add_row(
                str(c.priority),
                c.name,
                c.cefr_level,
                f"[{color}]{c.status}[/{color}]",
                f"{c.confidence:.0%}",
                str(len(c.error_examples)),
            )

        console.print(detail_table)


# --- Generate commands ---


def _make_llm_client(global_config, data_dir) -> LLMClient:
    """Create an LLM client with caching from config."""
    cache = ResponseCache(data_dir / "cache")
    return LLMClient(
        api_key=global_config.anthropic_api_key,
        model=global_config.anthropic_model,
        cache=cache,
    )


@generate_app.command(name="definitions")
def generate_definitions_cmd(
    lang: str = typer.Option("es", "--lang", help="Language code"),
    limit: int = typer.Option(50, "--limit", help="Max words to process"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated"),
) -> None:
    """Generate monolingual definitions for vocabulary entries."""
    global_config = load_global_config()
    data_dir = get_data_dir(global_config)
    vocab_store = VocabularyStore(data_dir, lang)

    try:
        lang_config = load_language_config(lang)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    entries = get_words_needing_definitions(vocab_store)[:limit]

    if not entries:
        console.print(f"[dim]{lang}: All vocabulary entries already have definitions.[/dim]")
        return

    if dry_run:
        console.print(f"[bold]Would generate definitions for {len(entries)} words:[/bold]")
        for entry in entries[:20]:
            console.print(f"  {entry.word}")
        if len(entries) > 20:
            console.print(f"  ... and {len(entries) - 20} more")
        return

    try:
        llm_client = _make_llm_client(global_config, data_dir)
    except LLMError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    words = [e.word for e in entries]
    console.print(f"Generating definitions for {len(words)} words...")

    results = generate_definitions(words, lang_config, llm_client)
    applied = apply_definitions(results, vocab_store, model_name=global_config.anthropic_model)

    console.print(f"[green]Done! {applied} definitions added.[/green]")


@generate_app.command(name="sentences")
def generate_sentences_cmd(
    lang: str = typer.Option("es", "--lang", help="Language code"),
    limit: int = typer.Option(50, "--limit", help="Max words to process"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated"),
) -> None:
    """Generate cloze-deletion sentences for vocabulary entries."""
    global_config = load_global_config()
    data_dir = get_data_dir(global_config)
    vocab_store = VocabularyStore(data_dir, lang)

    try:
        lang_config = load_language_config(lang)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    entries = get_words_needing_sentences(vocab_store)[:limit]

    if not entries:
        console.print(f"[dim]{lang}: All vocabulary entries already have sentences.[/dim]")
        return

    if dry_run:
        console.print(f"[bold]Would generate sentences for {len(entries)} words:[/bold]")
        for entry in entries[:20]:
            console.print(f"  {entry.word}")
        if len(entries) > 20:
            console.print(f"  ... and {len(entries) - 20} more")
        return

    try:
        llm_client = _make_llm_client(global_config, data_dir)
    except LLMError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    words = [e.word for e in entries]
    console.print(f"Generating sentences for {len(words)} words...")

    results = generate_sentences(words, lang_config, llm_client)
    applied = apply_sentences(results, vocab_store)

    console.print(f"[green]Done! {applied} entries updated with sentences.[/green]")


@generate_app.command(name="cognates")
def generate_cognates_cmd(
    lang: str = typer.Option("es", "--lang", help="Source language code"),
    target_lang: str = typer.Option(..., "--target-lang", help="Target language code"),
    limit: int = typer.Option(50, "--limit", help="Max words to process"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated"),
) -> None:
    """Generate cognate analysis between language pairs."""
    global_config = load_global_config()
    data_dir = get_data_dir(global_config)
    vocab_store = VocabularyStore(data_dir, lang)

    try:
        lang_config = load_language_config(lang)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    entries = get_words_needing_cognates(vocab_store, target_lang)[:limit]

    if not entries:
        console.print(
            f"[dim]{lang}: All vocabulary entries already have "
            f"{target_lang} cognates.[/dim]"
        )
        return

    if dry_run:
        console.print(
            f"[bold]Would analyze cognates for {len(entries)} words "
            f"({lang} → {target_lang}):[/bold]"
        )
        for entry in entries[:20]:
            console.print(f"  {entry.word}")
        if len(entries) > 20:
            console.print(f"  ... and {len(entries) - 20} more")
        return

    try:
        llm_client = _make_llm_client(global_config, data_dir)
    except LLMError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    words = [e.word for e in entries]
    console.print(
        f"Analyzing cognates for {len(words)} words ({lang} → {target_lang})..."
    )

    results = generate_cognates(
        words, lang_config.language_name, target_lang, llm_client
    )
    applied = apply_cognates(results, vocab_store, target_lang)

    console.print(f"[green]Done! {applied} cognate entries added.[/green]")

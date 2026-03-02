# lexiweave

A multi-language, AI-powered spaced repetition card generation and vocabulary tracking system. Designed to automate the labor-intensive parts of the [Fluent Forever](https://fluent-forever.com/) method while preserving the memory-forming activities that matter.

## What it does

- Imports vocabulary from existing sources (Duolingo, Anki exports, manual input)
- Assesses gaps against CEFR-level grammar and vocabulary checklists
- Generates rich Anki cards (monolingual definitions, cloze sentences, native audio) using AI
- Tracks vocabulary strength and coverage across multiple languages
- Links cognates across related languages (e.g., Spanish and Catalan)
- Exports Anki-compatible decks (.apkg) or CSV

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- An [Anthropic API key](https://console.anthropic.com/) (for AI-powered generation)

### Installation

```bash
git clone https://github.com/indieglo/lexiweave.git
cd lexiweave
uv sync
```

### Setup

```bash
uv run lexiweave setup
```

This copies example config files to your local configs and creates data directories. Your personal configs and data are gitignored and never committed.

After setup, edit `config/global.json` to add your Anthropic API key, and edit language configs in `config/languages/` to set your current CEFR level and targets.

## Workflow

The typical workflow follows a pipeline:

```
Import → Assess → Generate → Export → Track
```

### 1. Import vocabulary

```bash
# Import from Duolingo vocabulary CSV
uv run lexiweave import duolingo --vocab-csv path/to/vocabulary.csv --lang es

# Include GDPR export data for richer stats
uv run lexiweave import duolingo --vocab-csv path/to/vocabulary.csv --gdpr-dir path/to/duolingo_export/ --lang es
```

### 2. Check your baseline

```bash
# Quick vocabulary stats
uv run lexiweave stats --lang es

# Grammar gap assessment (requires grammar_gaps.json data)
uv run lexiweave assess grammar --lang es

# Full gap analysis report
uv run lexiweave assess report --lang es
uv run lexiweave assess report --lang es --export  # Save as markdown
```

### 3. Generate content

```bash
# Generate monolingual definitions
uv run lexiweave generate definitions --lang es --limit 50

# Generate cloze-deletion sentences
uv run lexiweave generate sentences --lang es --limit 50

# Generate cognate analysis (e.g., Spanish → Catalan)
uv run lexiweave generate cognates --lang es --target-lang ca --limit 50

# Generate pronunciation audio (Edge TTS)
uv run lexiweave generate audio --lang es --limit 50

# Run all generation stages at once
uv run lexiweave generate all --lang es --limit 50

# Preview what would be generated without making changes
uv run lexiweave generate all --lang es --dry-run
```

### 4. Export to Anki

```bash
# Export as .apkg file (recommended)
uv run lexiweave export anki --lang es

# Export as CSV for manual import
uv run lexiweave export anki --lang es --format csv

# Export only new entries (not previously exported)
uv run lexiweave export anki --lang es --incremental
```

### 5. Track progress

After studying in Anki, sync your review data back:

```bash
# Sync Anki review data to update strength scores
uv run lexiweave track sync-anki --file path/to/deck.apkg --lang es

# View detailed pipeline progress and strength tiers
uv run lexiweave track stats --lang es

# Compare progress across all languages
uv run lexiweave track stats
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `lexiweave setup` | Copy example configs and create data directories |
| `lexiweave import duolingo` | Import vocabulary from Duolingo CSV/GDPR export |
| `lexiweave stats` | Show vocabulary statistics |
| `lexiweave assess report` | Generate prioritized gap analysis report |
| `lexiweave assess grammar` | Show grammar assessment summary |
| `lexiweave generate definitions` | Generate monolingual definitions |
| `lexiweave generate sentences` | Generate cloze-deletion sentences |
| `lexiweave generate cognates` | Generate cross-language cognate analysis |
| `lexiweave generate audio` | Generate pronunciation audio (Edge TTS) |
| `lexiweave generate all` | Run all generation stages sequentially |
| `lexiweave export anki` | Export to Anki .apkg or CSV |
| `lexiweave track sync-anki` | Sync Anki review data for strength tracking |
| `lexiweave track stats` | Show pipeline progress and strength tiers |

## Project Structure

```
lexiweave/
├── src/lexiweave/           # Source code
│   ├── cli.py               # CLI entry point
│   ├── config.py            # Configuration loader
│   ├── importers/           # Data import modules (Duolingo)
│   ├── assessment/          # Grammar gaps and CEFR analysis
│   ├── generators/          # AI content generation (definitions, sentences, cognates, audio)
│   ├── exporters/           # Anki deck export (.apkg, CSV)
│   ├── tracking/            # Vocabulary store, strength tracking, stats
│   └── utils/               # LLM client, cache, audio providers
├── config/                  # Configuration files
│   ├── global.example.json
│   └── languages/           # Per-language settings
├── data/                    # Your vocabulary data (gitignored)
├── tests/                   # Test suite
└── .github/workflows/       # CI pipeline
```

## Privacy

All personal data stays local:

- `data/` — your vocabulary, imports, and cached API responses
- `config/global.json` — your API keys
- `config/languages/*.json` — your personal CEFR levels and settings

None of these are committed to git. Only example/template configs ship with the repo.

## Development

```bash
# Run tests
uv run pytest

# Run linter
uv run ruff check src/ tests/

# Auto-fix lint issues
uv run ruff check --fix src/ tests/
```

## License

MIT

# lexiweave

A multi-language, AI-powered spaced repetition card generation and vocabulary tracking system. Designed to automate the labor-intensive parts of the [Fluent Forever](https://fluent-forever.com/) method while preserving the memory-forming activities that matter.

## What it does

- Imports vocabulary from existing sources (Duolingo, Anki exports, manual input)
- Assesses gaps against CEFR-level grammar and vocabulary checklists
- Generates rich Anki cards (monolingual definitions, cloze sentences, image suggestions, native audio) using AI
- Tracks vocabulary strength and coverage across multiple languages
- Links cognates across related languages (e.g., Spanish and Catalan)
- Exports Anki-compatible decks

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/lexiweave.git
cd lexiweave
uv sync
```

### Setup

```bash
uv run lexiweave setup
```

This copies example config files to your local configs and creates data directories. Your personal configs and data are gitignored and never committed.

After setup, edit `config/global.json` to add your Anthropic API key, and edit language configs in `config/languages/` to set your current CEFR level and targets.

## Getting Started

There are several ways to start using lexiweave, depending on your situation:

### Path A: Import from Duolingo

If you have Duolingo data, you can import your vocabulary:

1. Export your vocabulary using a Duolingo vocabulary browser extension (produces a CSV)
2. Optionally, request your [Duolingo GDPR data export](https://www.duolingo.com/settings/privacy) for additional stats

```bash
# Import with just the vocabulary CSV
uv run lexiweave import duolingo --vocab-csv path/to/vocabulary.csv --lang es

# Import with GDPR export data for richer stats
uv run lexiweave import duolingo --vocab-csv path/to/vocabulary.csv --gdpr-dir path/to/duolingo_export/ --lang es
```

### Path B: Import from Anki

*(Coming soon)* If you have existing Anki decks, you can import your vocabulary and review history:

```bash
uv run lexiweave import anki --file path/to/deck.apkg --lang es
```

### Path C: Start from scratch

*(Coming soon)* Add words manually:

```bash
uv run lexiweave import manual --word "hablar" --lang es
```

### Combining sources

You can import from multiple sources into the same language. lexiweave automatically deduplicates entries, so running the same import twice is safe. For example, import from both Duolingo and Anki:

```bash
uv run lexiweave import duolingo --vocab-csv vocab.csv --lang es
uv run lexiweave import anki --file spanish_deck.apkg --lang es
```

Both sources feed into the same `vocabulary.json`, and each entry tracks where it came from.

## Checking your progress

```bash
# Stats for a specific language
uv run lexiweave stats --lang es

# Stats for all configured languages
uv run lexiweave stats
```

## Project Structure

```
lexiweave/
├── src/lexiweave/       # Source code
│   ├── cli.py           # CLI entry point
│   ├── config.py        # Configuration loader
│   ├── importers/       # Data import modules
│   ├── tracking/        # Vocabulary store and stats
│   └── utils/           # Shared utilities
├── config/              # Configuration files
│   ├── global.example.json
│   └── languages/       # Per-language settings
├── data/                # Your vocabulary data (gitignored)
├── tests/               # Test suite
└── Documents/           # Spec and reference docs
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

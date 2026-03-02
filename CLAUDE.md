# lexiweave

Multi-language AI-powered spaced repetition card generation and vocabulary tracking CLI.

## Architecture

- **CLI framework:** Typer (app defined in `src/lexiweave/cli.py`)
- **Package:** `src/lexiweave/` (src layout, installed as `lexiweave`)
- **Data models:** Pydantic v2 models in each module
- **Data storage:** JSON files in `data/languages/{lang}/`
- **Config:** JSON files in `config/` (example files ship, real ones are gitignored)

## Module Communication Rules

Modules communicate ONLY through JSON data files in `data/`.
No module imports another module except:
- Any module may import `tracking.vocabulary_store` for vocabulary CRUD
- Any module may import `config` for configuration access

## Key Commands

```bash
uv run lexiweave setup              # Copy example configs to real configs
uv run lexiweave import duolingo    # Import Duolingo data
uv run lexiweave stats              # Show vocabulary statistics
uv run pytest                       # Run tests
uv run ruff check src/ tests/       # Lint
```

## Data Flow

```
importers --> vocabulary_store (vocabulary.json) --> assessment --> generators --> exporters
```

## File Conventions

- All paths use `pathlib.Path`
- All JSON I/O uses UTF-8 encoding
- Atomic writes: write to `.tmp` file then `os.replace()`
- Timestamps are ISO 8601 UTC strings
- Word IDs follow pattern: `{lang}_{word_normalized}_{counter}`

## Public/Private Separation

- `config/*.example.json` — tracked, templates for users to copy
- `config/*.json` — gitignored, contains real API keys and personal settings
- `data/` — gitignored, all user vocabulary and cached data
- `Documents/duolingo/` — gitignored, personal GDPR export data

# importers/

Each importer reads from an external source and writes vocabulary entries
to `data/languages/{lang}/vocabulary.json` via `vocabulary_store`.

## Module: duolingo.py

### Inputs
- Vocabulary CSV: one word/phrase per line, no headers. ~3115 lines.
- GDPR export directory (optional): contains `languages.csv`, `leaderboards.csv`, and others.

### Outputs
- Adds entries to `data/languages/{lang}/vocabulary.json` with:
  - `source = "duolingo_import"`
  - `cefr_level = None` (assigned later by assessment module)
  - No definitions, sentences, audio, or cognates (generated later)

### Sensitive Files (DO NOT PARSE)
- `profile.csv` — contains username, email, full name
- `auth_data.csv` — contains email, account IDs
- `duolingo-notify-data.csv` — contains device tokens

### Key Functions
- `parse_vocabulary_csv(path) -> list[str]`
- `parse_languages_csv(path) -> list[DuolingoLanguageStats]`
- `parse_leaderboards_csv(path) -> list[LeaderboardEntry]`
- `import_duolingo(vocab_path, gdpr_dir, lang, store) -> ImportResult`

### Dependencies
- `tracking.vocabulary_store` for writing entries
- `config` for language settings
- Standard library `csv` module for parsing

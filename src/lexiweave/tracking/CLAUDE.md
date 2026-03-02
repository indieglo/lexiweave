# tracking/

Manages the vocabulary data store, strength tracking, and progress statistics.

## Module: vocabulary_store.py

### Data File
`data/languages/{lang}/vocabulary.json`

### Schema (Pydantic models)
- `VocabularyEntry` — single word/phrase with all metadata fields
- `VocabularyFile` — top-level structure with `metadata` and `entries` list
- `VocabularyStats` — computed statistics

### Key Operations
- `load() -> VocabularyFile` — returns empty file if not found
- `save(data)` — atomic write (temp file + `os.replace()`)
- `add_entry(entry)` / `add_entries(entries)` — bulk add with dedup
- `get_entry(word_id)` / `find_by_word(word)`
- `update_entry(word_id, updates)`
- `search(query)` / `filter_entries(cefr_level, source, tags)`
- `get_stats() -> VocabularyStats`

### ID Generation
Word IDs: `{lang}_{normalized_word}_{seq}` where normalized replaces
spaces with underscores and lowercases. Seq is 3-digit zero-padded.

### Atomicity
All writes go to `vocabulary.json.tmp` first, then `os.replace()`.

### Dependencies
- Pydantic for validation
- No other lexiweave modules (path is passed in at construction)

## Module: strength.py

Anki sync and vocabulary strength tracking.

### Key Functions
- `sync_anki(apkg_path, vocab_store) -> SyncResult` — reads .apkg export, matches cards to entries, updates strength scores
- `compute_strength(interval, ease_factor, reps, lapses, days_since_review) -> StrengthData` — pure strength calculation
- `categorize_strength(score) -> str` — returns tier: new, learning, young, mature, mastered

### How it works
- Extracts SQLite DB from .apkg zip file
- Reads notes, cards, and revlog tables
- Matches Anki notes to vocabulary entries by word text or `anki_note_id`
- Computes strength score (0.0-1.0) from SM-2 scheduling data with time decay

### Dependencies
- `sqlite3`, `zipfile`, `tempfile` (stdlib)
- `tracking.vocabulary_store` for reading/updating entries

## Module: stats.py

Pipeline progress statistics.

### Key Functions
- `get_pipeline_stats(vocab_store) -> PipelineStats` — per-language pipeline completeness
- `get_cross_language_stats(data_dir, languages) -> list[PipelineStats]` — compare across languages
- `format_stats(stats, console)` — Rich table output

### PipelineStats fields
- total, with_definitions, with_sentences, with_audio, with_cognates, exported, ready_to_export
- strength_tiers: dict of tier name to count (new, learning, young, mature, mastered)

### Dependencies
- `tracking.vocabulary_store` for reading entries
- `tracking.strength` for `categorize_strength()`
- `rich` for table output

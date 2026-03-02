# tracking/

Manages the vocabulary data store and statistics.

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

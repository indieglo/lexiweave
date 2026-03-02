# exporters/

Export vocabulary data to flashcard formats.

## Module: anki_export.py

Generates Anki .apkg files or CSV for manual import.

### Key Functions
- `export_apkg(entries, lang_config, output_dir) -> ExportResult` — .apkg with embedded audio
- `export_csv(entries, lang_config, output_dir) -> ExportResult` — CSV for manual import
- `get_exportable_entries(vocab_store, incremental) -> list[VocabularyEntry]`

### Card Types
- **Cloze deletion** — sentences with `{{c1::word}}` syntax
- **Vocabulary card** — front: word + audio, back: definition + sentences

### Dependencies
- `genanki` for .apkg generation
- `tracking.vocabulary_store` for reading entries
- `config.LanguageConfig` for deck name, note type
- No other lexiweave modules

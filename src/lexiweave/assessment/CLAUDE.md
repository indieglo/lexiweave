# assessment/

Modules for assessing language proficiency and identifying gaps.
Assessment is an ongoing activity — users re-assess periodically.

## Module: grammar_store.py

### Data File
`data/languages/{lang}/grammar_gaps.json`

### Schema (Pydantic models)
- `GrammarConcept` — a grammar concept with status (gap/weak/untested/strong), confidence score, priority, error examples, and sub-concepts
- `StrengthNote` — things the learner does well
- `GrammarGapsFile` — top-level with language, assessment metadata, concepts list, strengths list

### Key Operations
- `load()` / `save()` — atomic writes like vocabulary_store
- `add_concept()` / `update_concept()` / `get_concept()`
- `get_concepts_by_status()` / `get_concepts_by_priority()`
- `get_summary() -> GrammarSummary`

## Module: gap_report.py

Generates prioritized study reports from grammar_gaps.json + vocabulary.json.

### Key Functions
- `generate_report(grammar_store, vocab_store, lang_config) -> GapReport`
- `format_report_rich(report, console)` — Rich console output
- `format_report_markdown(report) -> str` — markdown for file export

### Dependencies
- `tracking.vocabulary_store` for vocabulary data
- `config` for language settings
- No other lexiweave modules

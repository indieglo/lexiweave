# generators/

LLM-powered content generators for vocabulary entries.

Each generator follows the same pattern:
1. `generate_*()` — batch-process words via LLM, return result objects
2. `apply_*()` — update vocabulary entries via VocabularyStore
3. `build_*_prompt()` — construct the prompt from word list + config

## Module: definitions.py

Generates monolingual definitions calibrated to learner's CEFR level.

### Key Functions
- `generate_definitions(words, lang_config, llm_client) -> list[DefinitionResult]`
- `apply_definitions(results, vocab_store)`

### Dependencies
- `utils.llm` for API calls
- `tracking.vocabulary_store` for updating entries
- `config.LanguageConfig` for CEFR level, definition language/style

## Module: sentences.py

Generates cloze-deletion sentences with Anki `{{c1::word}}` syntax.

### Key Functions
- `generate_sentences(words, lang_config, llm_client) -> list[SentenceResult]`
- `apply_sentences(results, vocab_store)`

## Module: cognates.py

Identifies cross-language cognates (e.g., Spanish ↔ Catalan).

### Key Functions
- `generate_cognates(words, source_lang, target_lang, llm_client) -> list[CognateResult]`
- `apply_cognates(results, vocab_store)`

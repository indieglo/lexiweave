"""Definition generator.

Generates monolingual definitions for vocabulary entries
using the Anthropic API, calibrated to the learner's CEFR level.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from lexiweave.config import LanguageConfig
from lexiweave.tracking.vocabulary_store import DefinitionData, VocabularyEntry, VocabularyStore
from lexiweave.utils.llm import LLMClient

BATCH_SIZE = 30

DEFINITION_PROMPT = """\
You are a {language_name} language teacher writing definitions for a {current_cefr} level student.

For each word below, provide:
1. A clear, simple definition in {language_name} (not English). \
Use vocabulary appropriate for {current_cefr} level.
2. The part of speech (sustantivo, verbo, adjetivo, adverbio, etc. — in {language_name}).

Words: {word_list}

Respond in JSON format only, no other text:
[
  {{"word": "...", "pos": "...", "definition": "..."}}
]"""

SYSTEM_PROMPT = (
    "You are a language education assistant. "
    "Always respond with valid JSON only, no markdown formatting or extra text."
)


class DefinitionResult(BaseModel):
    """Result of generating a definition for one word."""

    word: str
    pos: str = ""
    definition: str = ""


class GenerationSummary(BaseModel):
    """Summary of a generation run."""

    words_processed: int = 0
    definitions_added: int = 0
    cached_hits: int = 0
    errors: list[str] = Field(default_factory=list)


def _needs_definition(entry: VocabularyEntry) -> bool:
    """Check if an entry is missing a definition."""
    return not entry.definitions.monolingual


def build_definition_prompt(
    words: list[str],
    lang_config: LanguageConfig,
) -> str:
    """Build the prompt for generating definitions."""
    prompt = lang_config.prompt_overrides.get("definition", DEFINITION_PROMPT)

    return prompt.format(
        language_name=lang_config.language_name,
        current_cefr=lang_config.current_cefr,
        word_list=", ".join(words),
    )


def generate_definitions(
    words: list[str],
    lang_config: LanguageConfig,
    llm_client: LLMClient,
) -> list[DefinitionResult]:
    """Generate definitions for a list of words.

    Batches words into groups of BATCH_SIZE and calls the LLM for each batch.
    """
    results: list[DefinitionResult] = []

    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i : i + BATCH_SIZE]
        prompt = build_definition_prompt(batch, lang_config)
        raw = llm_client.generate_json(prompt, system_prompt=SYSTEM_PROMPT)

        if isinstance(raw, list):
            for item in raw:
                results.append(DefinitionResult(**item))

    return results


def apply_definitions(
    results: list[DefinitionResult],
    vocab_store: VocabularyStore,
    model_name: str = "",
) -> int:
    """Apply definition results to vocabulary entries. Returns count of updates."""
    applied = 0
    now = datetime.now(UTC).isoformat()

    for result in results:
        if not result.definition:
            continue

        entry = vocab_store.find_by_word(result.word)
        if entry is None:
            continue

        updates: dict = {
            "definitions": DefinitionData(
                monolingual=result.definition,
                generated_by=model_name,
                generated_at=now,
            ).model_dump(),
        }
        if result.pos and not entry.pos:
            updates["pos"] = result.pos

        vocab_store.update_entry(entry.id, updates)
        applied += 1

    return applied


def get_words_needing_definitions(vocab_store: VocabularyStore) -> list[VocabularyEntry]:
    """Return vocabulary entries that don't have definitions yet."""
    vocab = vocab_store.load()
    return [e for e in vocab.entries if _needs_definition(e)]

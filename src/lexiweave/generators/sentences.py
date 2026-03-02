"""Sentence generator.

Generates cloze-deletion sentences for vocabulary entries
using the Anthropic API. Two sentences per word: current level + stretch.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from lexiweave.config import LanguageConfig
from lexiweave.tracking.vocabulary_store import SentenceData, VocabularyEntry, VocabularyStore
from lexiweave.utils.llm import LLMClient

BATCH_SIZE = 20

# CEFR level progression for "stretch" sentences
CEFR_NEXT = {
    "pre-A1": "A1",
    "A1": "A2",
    "A2": "B1",
    "B1": "B2",
    "B2": "C1",
    "C1": "C2",
    "C2": "C2",
}

SENTENCE_PROMPT = """\
You are creating cloze-deletion flashcards for a {current_cefr} level {language_name} learner.

For each word, create two sentences in {language_name}:
1. A sentence at {current_cefr} level using common vocabulary
2. A "stretch" sentence at {stretch_cefr} level, introducing slightly more complex grammar \
or vocabulary

Mark the target word with double curly braces: {{{{c1::word}}}}

The sentences should:
- Sound natural (not textbook)
- Provide enough context to guess the missing word
- Exercise the word's most common usage

Words: {word_list}

Respond in JSON format only, no other text:
[
  {{
    "word": "...",
    "sentences": [
      {{"text": "...", "cefr_level": "{current_cefr}", "type": "current"}},
      {{"text": "...", "cefr_level": "{stretch_cefr}", "type": "stretch"}}
    ]
  }}
]"""

SYSTEM_PROMPT = (
    "You are a language education assistant. "
    "Always respond with valid JSON only, no markdown formatting or extra text."
)


class SentenceItem(BaseModel):
    """A single generated sentence."""

    text: str
    cefr_level: str = ""
    type: str = "current"


class SentenceResult(BaseModel):
    """Result of generating sentences for one word."""

    word: str
    sentences: list[SentenceItem] = Field(default_factory=list)


class GenerationSummary(BaseModel):
    """Summary of a generation run."""

    words_processed: int = 0
    sentences_added: int = 0
    cached_hits: int = 0
    errors: list[str] = Field(default_factory=list)


def _needs_sentences(entry: VocabularyEntry) -> bool:
    """Check if an entry is missing sentences."""
    return len(entry.sentences) == 0


def build_sentence_prompt(
    words: list[str],
    lang_config: LanguageConfig,
) -> str:
    """Build the prompt for generating sentences."""
    stretch_cefr = CEFR_NEXT.get(lang_config.current_cefr, "B2")

    prompt = lang_config.prompt_overrides.get("sentence", SENTENCE_PROMPT)

    return prompt.format(
        language_name=lang_config.language_name,
        current_cefr=lang_config.current_cefr,
        stretch_cefr=stretch_cefr,
        word_list=", ".join(words),
    )


def generate_sentences(
    words: list[str],
    lang_config: LanguageConfig,
    llm_client: LLMClient,
) -> list[SentenceResult]:
    """Generate cloze sentences for a list of words.

    Batches words into groups of BATCH_SIZE and calls the LLM for each batch.
    """
    results: list[SentenceResult] = []

    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i : i + BATCH_SIZE]
        prompt = build_sentence_prompt(batch, lang_config)
        raw = llm_client.generate_json(prompt, system_prompt=SYSTEM_PROMPT)

        if isinstance(raw, list):
            for item in raw:
                results.append(SentenceResult(**item))

    return results


def apply_sentences(
    results: list[SentenceResult],
    vocab_store: VocabularyStore,
) -> int:
    """Apply sentence results to vocabulary entries. Returns count of updates."""
    applied = 0

    for result in results:
        if not result.sentences:
            continue

        entry = vocab_store.find_by_word(result.word)
        if entry is None:
            continue

        sentence_data = [
            SentenceData(
                text=s.text,
                cefr_level=s.cefr_level,
                source="generated",
            ).model_dump()
            for s in result.sentences
            if s.text
        ]

        if sentence_data:
            vocab_store.update_entry(entry.id, {"sentences": sentence_data})
            applied += 1

    return applied


def get_words_needing_sentences(vocab_store: VocabularyStore) -> list[VocabularyEntry]:
    """Return vocabulary entries that don't have sentences yet."""
    vocab = vocab_store.load()
    return [e for e in vocab.entries if _needs_sentences(e)]

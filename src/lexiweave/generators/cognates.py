"""Cognate generator.

Identifies cross-language cognates, false friends, and related words
using the Anthropic API (e.g., Spanish ↔ Catalan).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from lexiweave.tracking.vocabulary_store import CognateLink, VocabularyEntry, VocabularyStore
from lexiweave.utils.llm import LLMClient

BATCH_SIZE = 30

COGNATE_PROMPT = """\
Given the following {source_lang} words, identify their equivalents in {target_lang}.

For each word, classify the relationship:
- high: regular cognate with predictable sound/spelling shift
- medium: related but with significant differences
- low: different root/origin
- false_friend: looks similar but different meaning

Words: {word_list}

Respond in JSON format only, no other text:
[
  {{
    "source_word": "...",
    "target_word": "...",
    "similarity": "high|medium|low|false_friend",
    "notes": "Brief explanation of the relationship"
  }}
]"""

SYSTEM_PROMPT = (
    "You are a comparative linguistics assistant. "
    "Always respond with valid JSON only, no markdown formatting or extra text."
)


class CognateResult(BaseModel):
    """Result of cognate analysis for one word."""

    source_word: str
    target_word: str
    similarity: str = ""
    notes: str = ""


class GenerationSummary(BaseModel):
    """Summary of a generation run."""

    words_processed: int = 0
    cognates_added: int = 0
    cached_hits: int = 0
    errors: list[str] = Field(default_factory=list)


def _has_cognate_for_lang(entry: VocabularyEntry, target_lang: str) -> bool:
    """Check if an entry already has a cognate for the target language."""
    return target_lang in entry.cognates


def build_cognate_prompt(
    words: list[str],
    source_lang: str,
    target_lang: str,
) -> str:
    """Build the prompt for cognate analysis."""
    return COGNATE_PROMPT.format(
        source_lang=source_lang,
        target_lang=target_lang,
        word_list=", ".join(words),
    )


def generate_cognates(
    words: list[str],
    source_lang: str,
    target_lang: str,
    llm_client: LLMClient,
) -> list[CognateResult]:
    """Generate cognate analysis for a list of words.

    Batches words into groups of BATCH_SIZE and calls the LLM for each batch.
    """
    results: list[CognateResult] = []

    for i in range(0, len(words), BATCH_SIZE):
        batch = words[i : i + BATCH_SIZE]
        prompt = build_cognate_prompt(batch, source_lang, target_lang)
        raw = llm_client.generate_json(prompt, system_prompt=SYSTEM_PROMPT)

        if isinstance(raw, list):
            for item in raw:
                results.append(CognateResult(**item))

    return results


def apply_cognates(
    results: list[CognateResult],
    vocab_store: VocabularyStore,
    target_lang: str,
) -> int:
    """Apply cognate results to vocabulary entries. Returns count of updates."""
    applied = 0

    for result in results:
        if not result.target_word:
            continue

        entry = vocab_store.find_by_word(result.source_word)
        if entry is None:
            continue

        # Build updated cognates dict (merge with existing)
        cognates = dict(entry.cognates)
        cognates[target_lang] = CognateLink(
            word_id="",
            word=result.target_word,
            similarity=result.similarity,
            notes=result.notes,
        )

        vocab_store.update_entry(
            entry.id,
            {"cognates": {k: v.model_dump() for k, v in cognates.items()}},
        )
        applied += 1

    return applied


def get_words_needing_cognates(
    vocab_store: VocabularyStore,
    target_lang: str,
) -> list[VocabularyEntry]:
    """Return vocabulary entries that don't have cognates for target_lang."""
    vocab = vocab_store.load()
    return [e for e in vocab.entries if not _has_cognate_for_lang(e, target_lang)]

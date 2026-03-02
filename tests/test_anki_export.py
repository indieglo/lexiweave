"""Tests for the Anki exporter."""

from __future__ import annotations

import csv
from pathlib import Path

from lexiweave.config import LanguageConfig
from lexiweave.exporters.anki_export import (
    export_apkg,
    export_csv,
    get_exportable_entries,
)
from lexiweave.tracking.vocabulary_store import (
    DefinitionData,
    SentenceData,
    VocabularyEntry,
    VocabularyStore,
)


def _make_lang_config(**kwargs) -> LanguageConfig:
    defaults = {
        "language_code": "es",
        "language_name": "Spanish",
        "anki_deck_name": "Spanish::Vocabulary",
    }
    defaults.update(kwargs)
    return LanguageConfig(**defaults)


def _make_entry(
    word: str,
    definition: str = "",
    sentences: list[dict] | None = None,
    audio_file: str = "",
    **kwargs,
) -> VocabularyEntry:
    entry_data = {
        "id": f"es_{word}_001",
        "word": word,
        "lang": "es",
        "source": "test",
    }
    entry_data.update(kwargs)
    entry = VocabularyEntry(**entry_data)

    if definition:
        entry.definitions = DefinitionData(
            monolingual=definition,
            generated_by="test",
            generated_at="2026-03-02",
        )

    if sentences:
        entry.sentences = [SentenceData(**s) for s in sentences]

    if audio_file:
        entry.audio.local_file = audio_file

    return entry


def _populate_store(store: VocabularyStore) -> None:
    """Add test entries with definitions and sentences."""
    entries = [
        _make_entry(
            "comer",
            definition="Tomar alimentos por la boca",
            pos="verbo",
            sentences=[
                {"text": "Me gusta {{c1::comer}} pizza.", "cefr_level": "B1"},
                {"text": "Solíamos {{c1::comer}} juntos.", "cefr_level": "B2"},
            ],
        ),
        _make_entry(
            "beber",
            definition="Tomar líquidos",
            pos="verbo",
            sentences=[
                {"text": "Necesito {{c1::beber}} agua.", "cefr_level": "B1"},
            ],
        ),
        _make_entry(
            "gato",
            definition="Animal doméstico felino",
            pos="sustantivo",
        ),
        _make_entry("empty_word"),  # No definition or sentences
    ]
    store.add_entries(entries)


class TestGetExportableEntries:
    def test_returns_all_entries(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate_store(store)

        entries = get_exportable_entries(store)
        assert len(entries) == 4

    def test_incremental_only_new(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate_store(store)

        # Mark one as already exported
        vocab = store.load()
        vocab.entries[0].anki_note_id = "existing_123"
        store.save(vocab)

        entries = get_exportable_entries(store, incremental=True)
        assert len(entries) == 3


class TestExportApkg:
    def test_creates_apkg_file(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate_store(store)
        entries = get_exportable_entries(store)
        output_dir = tmp_data_dir / "exports"

        result = export_apkg(entries, _make_lang_config(), output_dir)

        assert result.cards_exported > 0
        assert result.format == "apkg"
        assert Path(result.file_path).exists()
        assert result.file_path.endswith(".apkg")

    def test_cloze_cards_from_sentences(self, tmp_data_dir: Path) -> None:
        entries = [
            _make_entry(
                "comer",
                definition="Tomar alimentos",
                sentences=[
                    {"text": "Me gusta {{c1::comer}} pizza.", "cefr_level": "B1"},
                    {"text": "Solíamos {{c1::comer}} juntos.", "cefr_level": "B2"},
                ],
            ),
        ]
        output_dir = tmp_data_dir / "exports"

        result = export_apkg(entries, _make_lang_config(), output_dir)

        # Two sentences = two cloze cards
        assert result.cards_exported == 2

    def test_vocab_card_without_cloze(self, tmp_data_dir: Path) -> None:
        entries = [
            _make_entry("gato", definition="Animal doméstico felino"),
        ]
        output_dir = tmp_data_dir / "exports"

        result = export_apkg(entries, _make_lang_config(), output_dir)

        assert result.cards_exported == 1

    def test_skips_entries_without_content(self, tmp_data_dir: Path) -> None:
        entries = [_make_entry("empty")]
        output_dir = tmp_data_dir / "exports"

        result = export_apkg(entries, _make_lang_config(), output_dir)

        assert result.cards_exported == 0
        assert result.skipped == 1

    def test_default_deck_name(self, tmp_data_dir: Path) -> None:
        entries = [_make_entry("gato", definition="Cat")]
        output_dir = tmp_data_dir / "exports"
        config = _make_lang_config(anki_deck_name="")

        result = export_apkg(entries, config, output_dir)
        assert result.cards_exported == 1

    def test_includes_tags(self, tmp_data_dir: Path) -> None:
        entries = [
            _make_entry(
                "gato",
                definition="Cat",
                source="duolingo_import",
                cefr_level="A1",
                tags=["animals"],
            ),
        ]
        output_dir = tmp_data_dir / "exports"

        # Just verify it doesn't error — tag content is in the .apkg binary
        result = export_apkg(entries, _make_lang_config(), output_dir)
        assert result.cards_exported == 1


class TestExportCsv:
    def test_creates_csv_file(self, tmp_data_dir: Path) -> None:
        store = VocabularyStore(tmp_data_dir, "es")
        _populate_store(store)
        entries = get_exportable_entries(store)
        output_dir = tmp_data_dir / "exports"

        result = export_csv(entries, _make_lang_config(), output_dir)

        assert result.cards_exported > 0
        assert result.format == "csv"
        assert Path(result.file_path).exists()

    def test_csv_has_header(self, tmp_data_dir: Path) -> None:
        entries = [_make_entry("gato", definition="Cat")]
        output_dir = tmp_data_dir / "exports"

        result = export_csv(entries, _make_lang_config(), output_dir)

        with open(result.file_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert "word" in header
            assert "definition" in header
            assert "audio_file" in header

    def test_csv_content(self, tmp_data_dir: Path) -> None:
        entries = [
            _make_entry(
                "comer",
                definition="Tomar alimentos",
                pos="verbo",
                sentences=[
                    {"text": "Me gusta {{c1::comer}}.", "cefr_level": "B1"},
                    {"text": "Solíamos {{c1::comer}}.", "cefr_level": "B2"},
                ],
            ),
        ]
        output_dir = tmp_data_dir / "exports"

        result = export_csv(entries, _make_lang_config(), output_dir)

        with open(result.file_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)
            assert row[0] == "comer"
            assert row[1] == "verbo"
            assert row[2] == "Tomar alimentos"

    def test_csv_skips_empty_entries(self, tmp_data_dir: Path) -> None:
        entries = [
            _make_entry("empty"),
            _make_entry("gato", definition="Cat"),
        ]
        output_dir = tmp_data_dir / "exports"

        result = export_csv(entries, _make_lang_config(), output_dir)

        assert result.cards_exported == 1
        assert result.skipped == 1

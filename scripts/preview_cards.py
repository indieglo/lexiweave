"""Preview card layout with dummy data.

Creates a small Anki .apkg deck with entries covering every field combination
so you can see exactly what cards look like before running the real pipeline.

Usage:
    uv run python scripts/preview_cards.py

Imports the resulting file into Anki via File → Import.
Delete the "Lexiweave Preview" deck when done.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

# Make sure src/ is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lexiweave.exporters.anki_export import CLOZE_MODEL, VOCAB_MODEL  # noqa: E402
from lexiweave.exporters._anki_models import (  # noqa: E402
    CLOZE_MODEL_NAME,
    VOCAB_MODEL_NAME,
)

import genanki  # noqa: E402


# --- Placeholder image ---

def _make_placeholder_png(
    width: int = 300,
    height: int = 180,
    color: tuple[int, int, int] = (180, 210, 240),
    label_color: tuple[int, int, int] = (80, 120, 160),
) -> bytes:
    """Create a minimal solid-color PNG using stdlib only."""
    def pack_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return (
            struct.pack(">I", len(data))
            + c
            + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = pack_chunk(b"IHDR", ihdr_data)

    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(color) * width

    idat = pack_chunk(b"IDAT", zlib.compress(raw))
    iend = pack_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# --- Dummy entries ---
# Each tuple: (fields_list, model, tags)
# Cloze fields:  Text, Extra, Audio, Cognate, Image, Bilingual, IPA, Mnemonic
# Vocab fields:  Word, Definition, Sentences, Audio, Extra, Image, Bilingual, IPA, Mnemonic

PLACEHOLDER_IMG = '<img src="lexiweave_preview_placeholder.png">'

CLOZE_CASES = [
    {
        "label": "Cloze — minimal (text + definition only)",
        "Text": "Me gusta {{c1::comer}} todos los días.",
        "Extra": "Ingerir alimentos.<br><span style='color:#999;font-size:13px;'>(verbo)</span>",
        "Audio": "",
        "Cognate": "",
        "Image": "",
        "Bilingual": "",
        "IPA": "",
        "Mnemonic": "",
    },
    {
        "label": "Cloze — + IPA + Bilingual",
        "Text": "Ella quiere {{c1::hablar}} con su madre.",
        "Extra": "Comunicarse mediante palabras.<br><span style='color:#999;font-size:13px;'>(verbo)</span>",
        "Audio": "",
        "Cognate": "",
        "Image": "",
        "Bilingual": "to speak / to talk",
        "IPA": "/aˈblaɾ/",
        "Mnemonic": "",
    },
    {
        "label": "Cloze — + Cognate",
        "Text": "El {{c1::agua}} está fría hoy.",
        "Extra": "Líquido incoloro esencial para la vida.<br><span style='color:#999;font-size:13px;'>(sustantivo)</span>",
        "Audio": "",
        "Cognate": "CA: ≈ aigua &nbsp;|&nbsp; IT: ≈ acqua",
        "Image": "",
        "Bilingual": "water",
        "IPA": "/ˈaɣwa/",
        "Mnemonic": "",
    },
    {
        "label": "Cloze — + Mnemonic",
        "Text": "El {{c1::perro}} ladra en el jardín.",
        "Extra": "Animal doméstico, fiel compañero del ser humano.<br><span style='color:#999;font-size:13px;'>(sustantivo)</span>",
        "Audio": "",
        "Cognate": "",
        "Image": "",
        "Bilingual": "dog",
        "IPA": "/ˈpero/",
        "Mnemonic": "Sounds like 'but' (pero) — but a dog says PERO PERO PERO",
    },
    {
        "label": "Cloze — + Image (no mnemonic)",
        "Text": "La {{c1::casa}} tiene un jardín grande.",
        "Extra": "Edificio destinado a la vivienda.<br><span style='color:#999;font-size:13px;'>(sustantivo)</span>",
        "Audio": "",
        "Cognate": "CA: ≈ casa &nbsp;|&nbsp; IT: ≈ casa",
        "Image": PLACEHOLDER_IMG,
        "Bilingual": "house / home",
        "IPA": "/ˈkasa/",
        "Mnemonic": "",
    },
    {
        "label": "Cloze — ALL fields",
        "Text": "Necesito {{c1::dinero}} para comprar comida.",
        "Extra": "Medio de pago utilizado en las transacciones.<br><span style='color:#999;font-size:13px;'>(sustantivo)</span>",
        "Audio": "",
        "Cognate": "CA: ≈ diner &nbsp;|&nbsp; EN: ≠ dinner (false friend)",
        "Image": PLACEHOLDER_IMG,
        "Bilingual": "money",
        "IPA": "/diˈneɾo/",
        "Mnemonic": "Diner → you need DINERO to eat at a diner",
    },
]

VOCAB_CASES = [
    {
        "label": "Vocab — minimal",
        "Word": "gato",
        "Definition": "Animal felino doméstico, compañero del ser humano.",
        "Sentences": "<div>El gato duerme en el sofá. (A2)</div>",
        "Audio": "",
        "Extra": "sustantivo",
        "Image": "",
        "Bilingual": "",
        "IPA": "",
        "Mnemonic": "",
    },
    {
        "label": "Vocab — + IPA + Bilingual",
        "Word": "libro",
        "Definition": "Conjunto de hojas impresas encuadernadas que forman un volumen.",
        "Sentences": '<div>Leo un <b class="cloze">libro</b> cada mes. (B1)</div>',
        "Audio": "",
        "Extra": "sustantivo",
        "Image": "",
        "Bilingual": "book",
        "IPA": "/ˈliβɾo/",
        "Mnemonic": "",
    },
    {
        "label": "Vocab — + Image + ALL fields",
        "Word": "árbol",
        "Definition": "Planta leñosa con tronco sólido que puede alcanzar gran altura.",
        "Sentences": (
            '<div>El <b class="cloze">árbol</b> tiene hojas verdes. (A2)</div>'
            '<div>Plantamos un <b class="cloze">árbol</b> en el jardín. (B1)</div>'
        ),
        "Audio": "",
        "Extra": "sustantivo",
        "Image": PLACEHOLDER_IMG,
        "Bilingual": "tree",
        "IPA": "/ˈaɾβol/",
        "Mnemonic": "ARBor (Latin for tree) → ÁRBol",
    },
]


def main() -> None:
    output_dir = Path(__file__).parent.parent / "data" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "lexiweave_preview.apkg"

    # Write placeholder image to temp location for packaging
    img_path = output_dir / "lexiweave_preview_placeholder.png"
    img_path.write_bytes(_make_placeholder_png())

    deck_id = 1234567890
    deck = genanki.Deck(deck_id, "Lexiweave Preview")

    for case in CLOZE_CASES:
        note = genanki.Note(
            model=CLOZE_MODEL,
            fields=[
                case["Text"],
                case["Extra"],
                case["Audio"],
                case["Cognate"],
                case["Image"],
                case["Bilingual"],
                case["IPA"],
                case["Mnemonic"],
            ],
            tags=["preview", case["label"].replace(" ", "_").replace("—", "").replace(",", "")],
        )
        deck.add_note(note)

    for case in VOCAB_CASES:
        note = genanki.Note(
            model=VOCAB_MODEL,
            fields=[
                case["Word"],
                case["Definition"],
                case["Sentences"],
                case["Audio"],
                case["Extra"],
                case["Image"],
                case["Bilingual"],
                case["IPA"],
                case["Mnemonic"],
            ],
            tags=["preview", case["label"].replace(" ", "_").replace("—", "").replace(",", "")],
        )
        deck.add_note(note)

    package = genanki.Package(deck)
    package.media_files = [str(img_path)]
    package.write_to_file(str(output_path))

    print(f"Preview deck written to: {output_path}")
    print(f"  {len(CLOZE_CASES)} cloze cards  ({CLOZE_MODEL_NAME})")
    print(f"  {len(VOCAB_CASES)} vocab cards  ({VOCAB_MODEL_NAME})")
    print()
    print("Import into Anki: File > Import > select the .apkg file")
    print("Delete the 'Lexiweave Preview' deck when done reviewing.")


if __name__ == "__main__":
    main()

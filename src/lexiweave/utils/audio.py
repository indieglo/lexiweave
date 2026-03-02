"""Audio generation via Edge TTS.

Wraps the edge-tts async library with a sync interface.
Provider abstraction allows adding Piper TTS or Forvo later.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Default voices per language code
DEFAULT_VOICES: dict[str, str] = {
    "es": "es-ES-ElviraNeural",
    "ca": "ca-ES-EnricNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "en": "en-US-JennyNeural",
}


class AudioResult(BaseModel):
    """Result of generating audio for one word."""

    word: str
    file_path: str = ""
    provider: str = ""
    success: bool = False
    error: str = ""


def normalize_filename(word: str) -> str:
    """Normalize a word for use as a filename."""
    name = word.lower().strip()
    name = re.sub(r"\s+", "_", name)
    # Keep letters, digits, underscores, and hyphens
    name = re.sub(r"[^\w\-]", "", name, flags=re.UNICODE)
    return name


async def _generate_edge_tts(text: str, voice: str, output_path: Path) -> None:
    """Generate audio using edge-tts (async)."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


class EdgeTTSProvider:
    """Audio provider using Microsoft Edge TTS."""

    def __init__(self, voice: str = "", lang: str = "es"):
        self.voice = voice or DEFAULT_VOICES.get(lang, DEFAULT_VOICES["es"])
        self.provider_name = "edge_tts"

    def generate(self, word: str, output_dir: Path) -> AudioResult:
        """Generate audio for a single word. Returns AudioResult."""
        filename = f"{normalize_filename(word)}.mp3"
        output_path = output_dir / filename

        # Skip if file already exists
        if output_path.exists():
            return AudioResult(
                word=word,
                file_path=str(output_path),
                provider=self.provider_name,
                success=True,
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            asyncio.run(_generate_edge_tts(word, self.voice, output_path))
            return AudioResult(
                word=word,
                file_path=str(output_path),
                provider=self.provider_name,
                success=True,
            )
        except Exception as e:
            logger.warning("Failed to generate audio for '%s': %s", word, e)
            return AudioResult(
                word=word,
                provider=self.provider_name,
                success=False,
                error=str(e),
            )

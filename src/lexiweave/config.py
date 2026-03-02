"""Configuration loader for lexiweave.

Loads global.json and per-language config files from config/.
Falls back to defaults when fields are missing.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


class GlobalConfig(BaseModel):
    """Top-level configuration from config/global.json."""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    data_dir: Path = DEFAULT_DATA_DIR
    config_dir: Path = DEFAULT_CONFIG_DIR
    default_language: str = "es"
    languages: list[str] = Field(default_factory=lambda: ["es", "ca"])


class LanguageConfig(BaseModel):
    """Per-language configuration from config/languages/{lang}.json."""

    language_code: str
    language_name: str
    target_cefr: str = "B2"
    current_cefr: str = "A2"
    tts_voice: str = ""
    tts_provider: str = ""
    forvo_language_code: str = ""
    definition_language: str = ""
    definition_style: str = "monolingual_simple"
    sentence_levels: list[str] = Field(default_factory=lambda: ["current", "stretch"])
    anki_deck_name: str = ""
    anki_note_type: str = "cloze_deletion"
    prompt_overrides: dict = Field(default_factory=dict)


def load_global_config(config_dir: Path | None = None) -> GlobalConfig:
    """Load global.json, returning defaults if file missing."""
    config_dir = config_dir or DEFAULT_CONFIG_DIR
    config_path = config_dir / "global.json"
    if not config_path.exists():
        return GlobalConfig()
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    # Override config_dir to match where we loaded from
    data["config_dir"] = str(config_dir)
    return GlobalConfig(**data)


def load_language_config(lang: str, config_dir: Path | None = None) -> LanguageConfig:
    """Load config/languages/{lang}.json.

    Raises FileNotFoundError with a helpful message if the config doesn't exist.
    """
    config_dir = config_dir or DEFAULT_CONFIG_DIR
    config_path = config_dir / "languages" / f"{lang}.json"
    if not config_path.exists():
        msg = (
            f"No configuration found for language '{lang}' at {config_path}. "
            f"Run `lexiweave setup` to create config files from examples."
        )
        raise FileNotFoundError(msg)
    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    return LanguageConfig(**data)


def get_data_dir(global_config: GlobalConfig | None = None) -> Path:
    """Return the data directory, creating it if needed."""
    data_dir = (global_config or GlobalConfig()).data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_language_data_dir(lang: str, global_config: GlobalConfig | None = None) -> Path:
    """Return data/languages/{lang}/, creating it if needed."""
    data_dir = get_data_dir(global_config)
    lang_dir = data_dir / "languages" / lang
    lang_dir.mkdir(parents=True, exist_ok=True)
    return lang_dir

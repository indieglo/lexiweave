"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from lexiweave.config import (
    GlobalConfig,
    get_data_dir,
    get_language_data_dir,
    load_global_config,
    load_language_config,
)


class TestGlobalConfig:
    def test_loads_from_file(self, tmp_config_dir: Path) -> None:
        config = load_global_config(tmp_config_dir)
        assert config.default_language == "es"
        assert config.languages == ["es", "ca"]

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        config = load_global_config(tmp_path)
        assert isinstance(config, GlobalConfig)
        assert config.default_language == "es"
        assert config.anthropic_api_key == ""

    def test_partial_config_fills_defaults(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "global.json").write_text(
            '{"default_language": "ca"}', encoding="utf-8"
        )
        config = load_global_config(config_dir)
        assert config.default_language == "ca"
        assert config.anthropic_model == "claude-sonnet-4-5-20250929"


class TestLanguageConfig:
    def test_loads_language_config(self, tmp_config_dir: Path) -> None:
        config = load_language_config("es", tmp_config_dir)
        assert config.language_code == "es"
        assert config.language_name == "Spanish"
        assert config.current_cefr == "B1"

    def test_missing_language_raises(self, tmp_config_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No configuration found"):
            load_language_config("fr", tmp_config_dir)

    def test_required_fields_present(self, tmp_config_dir: Path) -> None:
        config = load_language_config("es", tmp_config_dir)
        assert config.language_code
        assert config.language_name


class TestDataDirs:
    def test_get_data_dir_creates_dir(self, tmp_path: Path) -> None:
        config = GlobalConfig(data_dir=tmp_path / "new_data")
        result = get_data_dir(config)
        assert result.exists()
        assert result == tmp_path / "new_data"

    def test_get_language_data_dir_creates_dir(self, tmp_path: Path) -> None:
        config = GlobalConfig(data_dir=tmp_path / "data")
        result = get_language_data_dir("es", config)
        assert result.exists()
        assert result.name == "es"

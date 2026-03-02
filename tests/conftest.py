"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory structure."""
    data_dir = tmp_path / "data"
    (data_dir / "languages" / "es" / "imports").mkdir(parents=True)
    (data_dir / "languages" / "ca" / "imports").mkdir(parents=True)
    (data_dir / "shared").mkdir(parents=True)
    return data_dir


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with working configs."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "languages").mkdir()

    # Write a global config
    (config_dir / "global.json").write_text(
        '{"default_language": "es", "languages": ["es", "ca"]}',
        encoding="utf-8",
    )
    # Write a Spanish language config
    (config_dir / "languages" / "es.json").write_text(
        '{"language_code": "es", "language_name": "Spanish", '
        '"current_cefr": "B1", "target_cefr": "C1"}',
        encoding="utf-8",
    )
    return config_dir


@pytest.fixture
def sample_vocab_csv(tmp_path: Path) -> Path:
    """Create a small sample vocabulary CSV with a duplicate."""
    content = "se come\nanimado\ncarnaval\ncelebración\nse come\n"
    p = tmp_path / "vocab.csv"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def sample_gdpr_dir(tmp_path: Path) -> Path:
    """Create a mock GDPR export directory."""
    gdpr = tmp_path / "duolingo"
    gdpr.mkdir()

    (gdpr / "languages.csv").write_text(
        "learning_language,from_language,points,skills_learned,total_lessons,"
        "days_active,last_active,prior_proficiency,subscribed\n"
        "es,en,124072,0,1209,364,2025-06-28 12:51:14,,\n"
        "it,en,16,0,1,1,2023-03-20 09:12:50,,\n",
        encoding="utf-8",
    )
    (gdpr / "leaderboards.csv").write_text(
        "leaderboard,timestamp,tier,score\n"
        "leagues,2023-03-20T08:44:14Z,0,1186\n"
        "leagues,2023-03-27T22:40:38Z,1,736\n",
        encoding="utf-8",
    )
    # Sensitive files (should be skipped)
    (gdpr / "profile.csv").write_text("name,value\nusername,test\n", encoding="utf-8")
    (gdpr / "auth_data.csv").write_text("Property,Value\nEmail,test@test.com\n", encoding="utf-8")

    return gdpr

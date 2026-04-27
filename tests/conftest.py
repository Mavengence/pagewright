"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from pagewright.config import BookConfig, load_book_config
from pagewright.theme import Theme, load_theme

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_BOOK_DIR = REPO_ROOT / "examples" / "sample-book"


@pytest.fixture(scope="session")
def sample_book() -> BookConfig:
    """The bundled sample book, loaded once per test session."""
    return load_book_config(SAMPLE_BOOK_DIR)


@pytest.fixture(scope="session")
def default_theme() -> Theme:
    """The bundled `default` theme."""
    return load_theme("default")


@pytest.fixture
def tmp_book(tmp_path: Path) -> Path:
    """A throwaway book directory with one chapter for save/load tests."""
    (tmp_path / "pagewright.yaml").write_text(
        "title: Tmp Book\n"
        "author: Test\n"
        "theme: default\n"
        "parts:\n"
        "  - title: Part I\n"
        "    chapters:\n"
        "      - file: 01.md\n"
        "        title: Chapter One\n",
        encoding="utf-8",
    )
    (tmp_path / "01.md").write_text("# Chapter One\n\nFirst paragraph.\n", encoding="utf-8")
    return tmp_path

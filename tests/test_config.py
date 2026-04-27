"""Book config loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pagewright.config import BookConfig, load_book_config


class TestSampleBookLoads:
    def test_total_chapters_is_four(self, sample_book: BookConfig) -> None:
        assert sample_book.total_chapters == 4

    def test_title_loaded(self, sample_book: BookConfig) -> None:
        assert "Pagewright" in sample_book.title

    def test_default_theme(self, sample_book: BookConfig) -> None:
        assert sample_book.theme == "default"

    def test_two_parts(self, sample_book: BookConfig) -> None:
        assert len(sample_book.parts) == 2

    def test_find_chapter_returns_meta(self, sample_book: BookConfig) -> None:
        result = sample_book.find_chapter("01_introduction.md")
        assert result is not None
        chapter, part_idx, chapter_num = result
        assert chapter.file == "01_introduction.md"
        assert part_idx == 0
        assert chapter_num == 1

    def test_find_chapter_returns_none_for_missing(self, sample_book: BookConfig) -> None:
        assert sample_book.find_chapter("does_not_exist.md") is None

    def test_chapter_numbering_is_global(self, sample_book: BookConfig) -> None:
        # Chapter 3 is the first chapter of Part II — should still get number 3,
        # not number 1 (per-part numbering).
        result = sample_book.find_chapter("03_callouts.md")
        assert result is not None
        _, part_idx, chapter_num = result
        assert part_idx == 1
        assert chapter_num == 3


class TestValidation:
    def test_missing_config_raises_filenotfound(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_book_config(tmp_path)

    def test_missing_title_raises_valueerror(self, tmp_path: Path) -> None:
        (tmp_path / "pagewright.yaml").write_text("parts: []")
        with pytest.raises(ValueError, match="title"):
            load_book_config(tmp_path)

    def test_missing_parts_raises_valueerror(self, tmp_path: Path) -> None:
        (tmp_path / "pagewright.yaml").write_text("title: x")
        with pytest.raises(ValueError, match="parts"):
            load_book_config(tmp_path)

    def test_alternate_config_yaml_filename_works(self, tmp_path: Path) -> None:
        # Pagewright also accepts `config.yaml` as an alternate filename.
        (tmp_path / "config.yaml").write_text(
            "title: Alt\n"
            "parts:\n"
            "  - title: P\n"
            "    chapters:\n"
            "      - file: 01.md\n"
            "        title: T\n"
        )
        (tmp_path / "01.md").write_text("# T")
        book = load_book_config(tmp_path)
        assert book.title == "Alt"

    def test_unknown_fields_pass_through_to_raw(self, tmp_book: Path) -> None:
        # Add a custom field
        (tmp_book / "pagewright.yaml").write_text(
            (tmp_book / "pagewright.yaml").read_text() + "edition: '2026.1'\n"
        )
        book = load_book_config(tmp_book)
        assert book.raw.get("edition") == "2026.1"

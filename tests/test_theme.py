"""Theme loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pagewright.theme import Theme, load_theme, render_chapter_opener


class TestBuiltinThemes:
    def test_default_theme_loads(self, default_theme: Theme) -> None:
        assert default_theme.name == "default"
        assert default_theme.css  # non-empty
        assert len(default_theme.callouts) == 8

    def test_default_has_chapter_opener(self, default_theme: Theme) -> None:
        assert default_theme.has_chapter_opener
        assert default_theme.chapter_opener_template is not None

    def test_unknown_theme_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="Built-in themes"):
            load_theme("does-not-exist")


class TestCustomThemePath:
    def test_directory_with_theme_css_resolves(self, tmp_path: Path) -> None:
        (tmp_path / "theme.css").write_text("body { font-family: serif; }")
        theme = load_theme(str(tmp_path))
        assert theme.name == tmp_path.name
        assert "font-family: serif" in theme.css

    def test_callouts_overridden_via_theme_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "theme.css").write_text("/* css */")
        (tmp_path / "theme.yaml").write_text(
            "callouts:\n"
            "  - { label: 'Astuce:', css_class: 'callout-tip', display: 'Astuce' }\n"
            "  - { label: 'Attention:', css_class: 'callout-warning', display: 'Attention' }\n"
        )
        theme = load_theme(str(tmp_path))
        assert len(theme.callouts) == 2
        assert theme.callouts[0].label == "Astuce:"
        assert theme.callouts[0].display == "Astuce"

    def test_no_chapter_opener_means_has_chapter_opener_false(self, tmp_path: Path) -> None:
        (tmp_path / "theme.css").write_text("/* css */")
        theme = load_theme(str(tmp_path))
        assert not theme.has_chapter_opener
        assert theme.chapter_opener_template is None


class TestRenderChapterOpener:
    def test_returns_empty_when_theme_has_no_template(self, tmp_path: Path) -> None:
        (tmp_path / "theme.css").write_text("/* x */")
        theme = load_theme(str(tmp_path))
        out = render_chapter_opener(
            theme,
            book={"title": "B", "author": "A", "parts": [{"title": "P"}]},
            chapter={"title": "C", "description": "d", "image": ""},
            chapter_num=1,
            total_chapters=10,
            part_index=0,
        )
        assert out == ""

    def test_placeholders_substituted(self, default_theme: Theme) -> None:
        out = render_chapter_opener(
            default_theme,
            book={"title": "My Book", "author": "Me", "parts": [{"title": "Part I"}]},
            chapter={"title": "Hello", "description": "Intro", "image": ""},
            chapter_num=3,
            total_chapters=12,
            part_index=0,
        )
        assert "Hello" in out
        assert "03" in out
        assert "12" in out
        assert "Part I" in out
        # Chapter opener template uses `data-book-title="{book_title}"`
        assert 'data-book-title="My Book"' in out

    def test_unknown_placeholder_raises_value_error(self, tmp_path: Path) -> None:
        (tmp_path / "theme.css").write_text("/* x */")
        (tmp_path / "chapter_opener.html").write_text("{not_a_placeholder}")
        theme = load_theme(str(tmp_path))
        with pytest.raises(ValueError, match="unknown placeholder"):
            render_chapter_opener(
                theme,
                book={"title": "B", "parts": []},
                chapter={"title": "C"},
                chapter_num=1,
                total_chapters=1,
                part_index=0,
            )

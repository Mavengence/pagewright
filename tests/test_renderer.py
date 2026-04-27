"""Preview renderer tests."""

from __future__ import annotations

from pagewright.config import BookConfig
from pagewright.renderer import render_chapter_html
from pagewright.theme import Theme


class TestRendererBothModes:
    def test_continuous_mode_produces_full_html_doc(
        self, sample_book: BookConfig, default_theme: Theme
    ) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme, mode="continuous")
        assert html.startswith("<!DOCTYPE html>")
        assert 'data-preview-mode="continuous"' in html
        assert "</html>" in html

    def test_paged_mode_injects_pagedjs(
        self, sample_book: BookConfig, default_theme: Theme
    ) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme, mode="paged")
        assert "paged.polyfill" in html
        assert "PagewrightPagedHandler" in html
        assert 'data-preview-mode="paged"' in html

    def test_continuous_mode_does_not_inject_pagedjs(
        self, sample_book: BookConfig, default_theme: Theme
    ) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme, mode="continuous")
        assert "paged.polyfill" not in html


class TestRendererThemeIntegration:
    def test_theme_css_is_inlined(self, sample_book: BookConfig, default_theme: Theme) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme)
        # Must inline the theme CSS so the iframe renders without an external
        # stylesheet request.
        assert "body-page" in html  # default theme defines this class
        assert "<style>" in html

    def test_chapter_opener_rendered_for_recognised_chapter(
        self, sample_book: BookConfig, default_theme: Theme
    ) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme)
        # Default theme's chapter_opener.html sets data-book-title and
        # writes "CHAPTER 01"
        assert "data-book-title=" in html
        assert "CHAPTER 01" in html

    def test_unknown_chapter_falls_back_to_simple_wrap(
        self, sample_book: BookConfig, default_theme: Theme, tmp_path: any
    ) -> None:
        # File outside the book's chapter list — should render via the
        # _wrap_simple fallback (still produces a complete HTML doc).
        stray = tmp_path / "stray.md"
        stray.write_text("# Stray\n\nNot in the book config.")
        html = render_chapter_html(stray, sample_book, default_theme)
        assert "<!DOCTYPE html>" in html
        assert "Stray" in html


class TestRendererColorScheme:
    def test_light_is_default(self, sample_book: BookConfig, default_theme: Theme) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme)
        assert 'data-color-scheme="light"' in html

    def test_dark_is_passed_to_html_attribute(
        self, sample_book: BookConfig, default_theme: Theme
    ) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme, color_scheme="dark")
        assert 'data-color-scheme="dark"' in html


class TestRendererHeadingIds:
    def test_heading_ids_present_in_output(
        self, sample_book: BookConfig, default_theme: Theme
    ) -> None:
        md_path = sample_book.directory / "01_introduction.md"
        html = render_chapter_html(md_path, sample_book, default_theme)
        assert 'id="h-1"' in html

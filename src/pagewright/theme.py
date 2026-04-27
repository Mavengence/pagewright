"""Pagewright theme system.

A theme is a directory containing:

- ``theme.css`` — the print-CSS for the rendered preview (mandatory).
- ``theme.yaml`` — metadata + callout labels (optional).
- ``chapter_opener.html`` — Python format-string template for chapter
  opener pages (optional). Available placeholders:
  ``{number}``, ``{number_padded}``, ``{title}``, ``{description}``,
  ``{part_title}``, ``{part_index_roman}``, ``{book_title}``,
  ``{book_author}``, ``{total_chapters}``.

Built-in themes ship in ``pagewright/themes/``; users can also point
``--theme`` at a custom directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .markdown import DEFAULT_CALLOUTS, CalloutSpec

PACKAGE_THEMES_DIR = Path(__file__).resolve().parent / "themes"


@dataclass(frozen=True)
class Theme:
    """A loaded theme ready for rendering."""

    name: str
    directory: Path
    css: str
    callouts: tuple[CalloutSpec, ...]
    chapter_opener_template: str | None
    has_chapter_opener: bool

    @property
    def stylesheet_url(self) -> str:
        """Local file URL for the theme's CSS (used as a debugging hint)."""
        return self.directory.joinpath("theme.css").as_uri()


def load_theme(name_or_path: str) -> Theme:
    """Resolve a theme by name (built-in) or by path (custom).

    Resolution order:
    1. If ``name_or_path`` is a directory containing ``theme.css``, use it.
    2. Otherwise, look for ``themes/<name>/theme.css`` next to the package.
    3. Otherwise, raise ``FileNotFoundError`` with a helpful message.
    """
    candidate = Path(name_or_path).expanduser()
    if candidate.is_dir() and (candidate / "theme.css").exists():
        directory = candidate
    else:
        directory = PACKAGE_THEMES_DIR / name_or_path
        if not (directory / "theme.css").exists():
            available = (
                sorted(d.name for d in PACKAGE_THEMES_DIR.iterdir() if d.is_dir())
                if PACKAGE_THEMES_DIR.exists()
                else []
            )
            raise FileNotFoundError(
                f"Theme '{name_or_path}' not found. "
                f"Built-in themes: {', '.join(available) or '(none)'}. "
                f"Or pass an absolute path to a directory containing theme.css."
            )

    css = (directory / "theme.css").read_text(encoding="utf-8")

    callouts = DEFAULT_CALLOUTS
    yaml_path = directory / "theme.yaml"
    if yaml_path.exists():
        meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        if "callouts" in meta:
            callouts = tuple(
                CalloutSpec(
                    label=c["label"],
                    css_class=c["css_class"],
                    display=c.get("display", c["label"].rstrip(":")),
                )
                for c in meta["callouts"]
            )

    opener_path = directory / "chapter_opener.html"
    has_opener = opener_path.exists()
    template = opener_path.read_text(encoding="utf-8") if has_opener else None

    return Theme(
        name=directory.name,
        directory=directory,
        css=css,
        callouts=callouts,
        chapter_opener_template=template,
        has_chapter_opener=has_opener,
    )


def render_chapter_opener(
    theme: Theme,
    book: dict,
    chapter: dict,
    chapter_num: int,
    total_chapters: int,
    part_index: int,
) -> str:
    """Format the theme's chapter opener template, or return an empty string."""
    if not theme.has_chapter_opener or theme.chapter_opener_template is None:
        return ""
    parts = book.get("parts", [])
    part_title = parts[part_index].get("title", "") if 0 <= part_index < len(parts) else ""

    placeholders = {
        "number": chapter_num,
        "number_padded": f"{chapter_num:02d}",
        "title": chapter.get("title", ""),
        "description": chapter.get("description", ""),
        "part_title": part_title,
        "part_index_roman": _roman(part_index + 1),
        "book_title": book.get("title", ""),
        "book_author": book.get("author", ""),
        "total_chapters": total_chapters,
        "total_padded": f"{total_chapters:02d}",
    }
    try:
        return theme.chapter_opener_template.format(**placeholders)
    except KeyError as exc:
        raise ValueError(
            f"chapter_opener.html in theme '{theme.name}' references "
            f"unknown placeholder {exc}. Supported: "
            f"{sorted(placeholders.keys())}"
        ) from exc


def _roman(n: int) -> str:
    table = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    return table[n] if 0 <= n < len(table) else str(n)

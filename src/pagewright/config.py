"""Book project configuration loader.

A Pagewright book lives in a directory containing ``pagewright.yaml``
plus the chapter ``.md`` files. The config schema:

```yaml
title: My Book
author: Author Name
theme: default              # built-in name OR path to custom theme dir
parts:
  - title: "Part I — Foundations"
    chapters:
      - file: 01_intro.md
        title: "Introduction"
        description: "Why we wrote this book"
      - file: 02_features.md
        title: "Features"
```

Unknown fields are passed through as ``book["..."]`` so themes that need
extra metadata (e.g. ``edition``, ``publisher``) can read them from the
chapter opener template.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_FILENAME = "pagewright.yaml"
LEGACY_CONFIG_FILENAME = "config.yaml"


@dataclass(frozen=True)
class ChapterMeta:
    file: str
    title: str
    description: str = ""
    image: str = ""


@dataclass(frozen=True)
class PartMeta:
    title: str
    chapters: tuple[ChapterMeta, ...]


@dataclass(frozen=True)
class BookConfig:
    """Validated book configuration."""

    directory: Path
    title: str
    author: str
    theme: str
    parts: tuple[PartMeta, ...]
    raw: dict  # Full YAML for theme template access

    @property
    def total_chapters(self) -> int:
        return sum(len(p.chapters) for p in self.parts)

    def find_chapter(self, filename: str) -> tuple[ChapterMeta, int, int] | None:
        """Locate a chapter by its filename. Returns (chapter, part_idx, num)."""
        counter = 0
        for part_idx, part in enumerate(self.parts):
            for ch in part.chapters:
                counter += 1
                if ch.file == filename:
                    return ch, part_idx, counter
        return None


def load_book_config(book_dir: Path) -> BookConfig:
    """Load a book's config from ``pagewright.yaml`` (or legacy ``config.yaml``).

    Raises ``FileNotFoundError`` if no config is present.
    Raises ``ValueError`` for missing required fields.
    """
    book_dir = Path(book_dir).resolve()
    config_path = book_dir / CONFIG_FILENAME
    if not config_path.exists():
        legacy = book_dir / LEGACY_CONFIG_FILENAME
        if legacy.exists():
            config_path = legacy
        else:
            raise FileNotFoundError(
                f"No {CONFIG_FILENAME} (or {LEGACY_CONFIG_FILENAME}) found in {book_dir}"
            )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    if "title" not in raw:
        raise ValueError(f"{config_path} is missing required field: title")
    if "parts" not in raw or not raw["parts"]:
        raise ValueError(f"{config_path} is missing required field: parts (at least one)")

    parts: list[PartMeta] = []
    for p in raw["parts"]:
        chapters = tuple(
            ChapterMeta(
                file=ch["file"],
                title=ch.get("title", Path(ch["file"]).stem),
                description=ch.get("description", ""),
                image=ch.get("image", ""),
            )
            for ch in p.get("chapters", [])
        )
        if chapters:
            parts.append(PartMeta(title=p.get("title", ""), chapters=chapters))

    if not parts:
        raise ValueError(f"{config_path} has no chapters")

    return BookConfig(
        directory=book_dir,
        title=raw["title"],
        author=raw.get("author", ""),
        theme=raw.get("theme", "default"),
        parts=tuple(parts),
        raw=raw,
    )

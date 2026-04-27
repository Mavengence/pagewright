# Architecture

Pagewright is a single-page Flask app that serves your book directory
as a multi-chapter editor. This page documents the request flow,
module boundaries, and the extension points where you can plug in
your own behaviour.

## Modules

```
src/pagewright/
├── cli.py         argparse entry point — parses --port, --theme, book_dir
├── server.py      Flask app — routes, atomic saves, ETag, no-cache
├── renderer.py    Markdown → standalone HTML — theme + mode aware
├── markdown.py    Self-contained Markdown converter — heading IDs, callouts
├── theme.py       Theme loader — built-in + custom paths, callout overrides
├── config.py      pagewright.yaml schema + loader
├── static/        Editor UI — index.html, app.js, style.css, icons.js
└── themes/        Built-in themes (default)
```

## Request flow

### Boot

1. `pagewright.cli.main` parses CLI args.
2. `pagewright.server.serve` calls `create_app(book_dir, theme_name)`.
3. `create_app` loads `pagewright.yaml` (`config.load_book_config`)
   and the active theme (`theme.load_theme`).
4. Both are stored on `app.config` and the routes are registered.
5. Flask binds to `127.0.0.1:5566` (or whatever `--port` was given).

### Editing loop

```
Browser                                Server
   │                                       │
   │  GET /                                │
   │ ────────────────────────────────────▶ │
   │  ◀──────────── index.html ─────────── │
   │                                       │
   │  GET /api/tree                        │
   │ ────────────────────────────────────▶ │
   │  ◀──── [book → parts → chapters] ──── │
   │                                       │
   │  click chapter "01_intro.md"          │
   │                                       │
   │  GET /api/file?path=01_intro.md       │
   │ ────────────────────────────────────▶ │
   │  ◀────── markdown source + ETag ───── │
   │                                       │
   │  GET /api/preview?path=01_intro.md    │
   │       &mode=continuous                │
   │ ────────────────────────────────────▶ │
   │  ◀──── standalone preview HTML  ───── │
   │                                       │
   │  ── user types in CodeMirror ──       │
   │       (debounce 1.5 s)                │
   │                                       │
   │  POST /api/file                       │
   │       { path, content, ifMatch }      │
   │ ────────────────────────────────────▶ │
   │       atomic write + new ETag         │
   │  ◀──────── { saved, etag } ────────── │
   │                                       │
   │  GET /api/preview (refresh)           │
   │ ────────────────────────────────────▶ │
   │  ◀──── new HTML, position-stable ──── │
```

### Save conflict

If the file changed under the editor (another tool, `git pull`):

```
   │  POST /api/file                       │
   │       { …, ifMatch: "<old etag>" }    │
   │ ────────────────────────────────────▶ │
   │       (file mtime no longer matches)  │
   │  ◀──── 409 Conflict + currentEtag ─── │
   │                                       │
   │  ── editor opens modal:               │
   │       Reload / Overwrite / Cancel ──  │
```

## Renderer pipeline

`renderer.render_chapter_html(md_path, book, theme, mode, color_scheme)`:

1. Read the markdown file from disk.
2. Convert to HTML via `markdown.md_to_html`, passing the theme's
   callout list so blockquote prefixes (`> **Tip:**`) become
   `<div class="callout callout-tip">`.
3. Look up the chapter in `book.parts` to get its number, part index,
   and total count.
4. Format the theme's `chapter_opener.html` template (if present)
   with placeholders.
5. Wrap the chapter HTML in `<html>` + `<body>` boilerplate, inline
   the theme CSS, and inject mode-specific overrides:
   - **Continuous** — kill `@page` print constraints, single floating page.
   - **Paged** — preserve `@page` rules, inject paged.js polyfill,
     inject a small `Paged.Handler` that posts page count back to the
     parent iframe.
6. Return the standalone HTML string.

The output is a complete HTML document. The editor's preview iframe
loads it directly from `/api/preview?…` and treats it as an isolated
document.

## Extension points

### Adding a theme

Create a new directory anywhere with at minimum a `theme.css`. Pass
its path via `--theme ./my-theme/` or set `theme: ./my-theme/` in
`pagewright.yaml`. See [`docs/themes.md`](themes.md).

### Custom callouts

Add a `theme.yaml` to your theme:

```yaml
callouts:
  - { label: "Note:",     css_class: "callout-note",     display: "Note" }
  - { label: "Warning:",  css_class: "callout-warning",  display: "Warning" }
```

### Calling the renderer programmatically

For PDF generation or static HTML export, import the renderer
directly:

```python
from pathlib import Path

from pagewright.config import load_book_config
from pagewright.theme import load_theme
from pagewright.renderer import render_chapter_html


book = load_book_config(Path("my-book"))
theme = load_theme(book.theme)

out_dir = Path("dist")
out_dir.mkdir(exist_ok=True)

for part in book.parts:
    for chapter in part.chapters:
        html = render_chapter_html(
            book.directory / chapter.file,
            book,
            theme,
            mode="paged",          # or "continuous"
            color_scheme="light",  # or "dark"
        )
        (out_dir / f"{chapter.file}.html").write_text(html)
```

Pipe each HTML through your favourite print-CSS engine (WeasyPrint,
paged.js-cli, Prince) to produce a PDF.

### Server endpoints

| Method | Path                        | Purpose                                    |
|--------|-----------------------------|--------------------------------------------|
| GET    | `/`                         | Editor SPA shell                           |
| GET    | `/api/health`               | Liveness probe                             |
| GET    | `/api/tree`                 | Book + chapter index                       |
| GET    | `/api/file?path=…`          | Load markdown source + ETag                |
| POST   | `/api/file`                 | Atomic save with ETag conflict detection   |
| GET    | `/api/preview?path=&mode=`  | Standalone preview HTML for one chapter    |
| GET    | `/theme-asset/<path>`       | Serve fonts/images from active theme dir   |
| GET    | `/book-asset/<path>`        | Serve files from book directory            |
| GET    | `/static/<path>`            | Editor UI bundle (HTML/CSS/JS/icons)       |

All routes set `Cache-Control: no-store` so editor changes land on
next reload without a hard-refresh.

## Performance characteristics

- **Markdown render**: O(lines), single-pass converter, ~5 ms for a
  50 KB chapter on M-series Apple Silicon.
- **Preview generation**: ~10 ms (markdown → HTML + theme CSS inline).
- **paged.js layout**: 1–3 s for a typical 4-page chapter; scales
  roughly linearly with page count.
- **Editor side effects** (word count, outline rebuild) debounce at
  200 ms so 50 KB chapters stay snappy under burst typing.

## Why Flask

Flask is the smallest sensible Python web framework. The whole server
is ~250 lines. There is no ORM, no async, no background workers, no
WebSocket — Pagewright is a single-tenant local tool, not a server
application.

If you want to extend it for multi-tenant or networked use, fork it
and replace `server.py`. The renderer and theme system are the
durable parts; the Flask layer is glue.

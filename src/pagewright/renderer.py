"""Preview renderer: a single chapter → standalone HTML for the iframe.

Two modes:

- ``continuous`` — ``@page`` print rules are stripped and the chapter
  scrolls as one tall HTML document. Fast, no external JS.
- ``paged`` — ``@page`` rules are preserved and **paged.js** lays the
  chapter into discrete A4 pages (with running headers, page numbers,
  and ``break-inside`` rules from the theme CSS). 1–3 s repagination.

The renderer is theme-agnostic: all visual styling comes from
``Theme.css``. Templates inject heading IDs (``#h-N``) so the editor's
outline + scroll-restore can target specific positions in the iframe.
"""

from __future__ import annotations

from pathlib import Path

from .config import BookConfig
from .markdown import RenderOptions, md_to_html
from .theme import Theme, render_chapter_opener

# paged.js polyfill — pinned for stable behaviour. Override via
# environment variable ``PAGEWRIGHT_PAGEDJS_URL`` if you mirror it.
PAGEDJS_URL = "https://unpkg.com/pagedjs@0.4.3/dist/paged.polyfill.js"


def render_chapter_html(
    md_path: Path,
    book: BookConfig,
    theme: Theme,
    *,
    mode: str = "continuous",
    color_scheme: str = "light",
) -> str:
    """Render one chapter to standalone HTML.

    Args:
        md_path: Absolute path to the chapter's ``.md`` file.
        book: Loaded book configuration.
        theme: Loaded theme.
        mode: ``"continuous"`` or ``"paged"``.
        color_scheme: ``"light"`` or ``"dark"``. Themes opt in to dark
            via ``data-color-scheme="dark"`` selectors in their CSS.

    Returns:
        A complete HTML document as a string.
    """
    md_text = md_path.read_text(encoding="utf-8")
    body_html = md_to_html(md_text, RenderOptions(callouts=theme.callouts))

    info = book.find_chapter(md_path.name)
    if info is None:
        return _wrap_simple(md_path, theme, mode, color_scheme)

    chapter, part_idx, chapter_num = info

    chapter_dict = {
        "title": chapter.title,
        "description": chapter.description,
        "image": chapter.image,
    }
    opener_html = render_chapter_opener(
        theme,
        book.raw,
        chapter_dict,
        chapter_num=chapter_num,
        total_chapters=book.total_chapters,
        part_index=part_idx,
    )

    body_section = (
        f'<section class="body-page" data-chapter-num="{chapter_num}">{body_html}</section>'
    )

    if mode == "paged":
        editor_overrides = _PAGED_MODE_OVERRIDES
        scripts = _paged_scripts()
    else:
        editor_overrides = _CONTINUOUS_MODE_OVERRIDES
        scripts = ""

    title = book.title
    return f"""<!DOCTYPE html>
<html lang="en" data-preview-mode="{mode}" data-color-scheme="{color_scheme}">
<head>
<meta charset="UTF-8">
<title>{_escape(title)} — preview</title>
<style>{theme.css}</style>
{editor_overrides}
{scripts}
</head>
<body>
{opener_html}
{body_section}
</body>
</html>"""


def _wrap_simple(
    md_path: Path,
    theme: Theme,
    mode: str,
    color_scheme: str,
) -> str:
    """Fallback when a md file has no entry in the book config."""
    body_html = md_to_html(
        md_path.read_text(encoding="utf-8"),
        RenderOptions(callouts=theme.callouts),
    )
    overrides = _PAGED_MODE_OVERRIDES if mode == "paged" else _CONTINUOUS_MODE_OVERRIDES
    scripts = _paged_scripts() if mode == "paged" else ""
    return f"""<!DOCTYPE html>
<html lang="en" data-preview-mode="{mode}" data-color-scheme="{color_scheme}">
<head>
<meta charset="UTF-8">
<title>{md_path.stem} — preview</title>
<style>{theme.css}</style>
{overrides}
{scripts}
</head>
<body>
<section class="body-page">{body_html}</section>
</body>
</html>"""


def _paged_scripts() -> str:
    """Inject paged.js polyfill + a tiny handler that posts page count."""
    return f"""
<script src="{PAGEDJS_URL}"></script>
<script>
  // Notify the parent editor when paged.js finishes laying the doc out.
  // The editor uses this to (a) hide its loading spinner, (b) update
  // the "N pages" badge, and (c) restore the scroll position that was
  // captured before the most recent re-render.
  (function () {{
    if (typeof Paged === "undefined" || !Paged.registerHandlers) return;
    class PagewrightPagedHandler extends Paged.Handler {{
      constructor(chunker, polisher, caller) {{ super(chunker, polisher, caller); }}
      afterRendered(pages) {{
        try {{
          window.parent.postMessage({{
            type: "paged-rendered",
            pages: pages.length,
            path: location.pathname + location.search,
          }}, "*");
        }} catch (e) {{}}
        document.documentElement.classList.add("pagedjs-ready");
      }}
    }}
    Paged.registerHandlers(PagewrightPagedHandler);
  }})();
</script>"""


def _escape(s: str) -> str:
    import html

    return html.escape(s, quote=True)


# Continuous mode: kill A4 print constraints, content scrolls as one
# long HTML document. The page-shadow keeps the "floating page" feel
# without paged.js.
_CONTINUOUS_MODE_OVERRIDES = """<style id="pw-continuous-overrides">
  @page { size: auto; margin: 0; }
  html, body {
    background: var(--pw-canvas-bg, #f3f0e9);
    transition: background-color 240ms cubic-bezier(0.32, 0.72, 0, 1);
  }
  body { padding: 24pt 0; }
  .chapter-page,
  .body-page {
    margin: 0 auto 24pt auto;
    box-shadow: 0 8px 32px rgba(11, 9, 8, 0.10), 0 2px 6px rgba(11, 9, 8, 0.04);
  }
  .body-page {
    width: 210mm;
    min-height: auto;
    padding: 64pt 56pt 60pt 56pt;
    background: var(--pw-page-bg, #ffffff);
  }
  .chapter-page {
    width: 210mm;
    height: 297mm;
  }
</style>"""


# Paged mode: keep the engine's @page rules, paged.js handles
# pagination. We only style the *paged.js wrappers* — `.pagedjs_pages`
# and `.pagedjs_page` — so each rendered page sits as a floating A4
# sheet on the canvas.
_PAGED_MODE_OVERRIDES = """<style id="pw-paged-overrides">
  /* Hide unpaginated content while paged.js works. */
  html:not(.pagedjs-ready) > body { visibility: hidden; }
  html.pagedjs-ready > body { visibility: visible; }

  /* Force zero body padding — paged.js measures every direct body
     child and any leading offset becomes a phantom blank page. */
  body {
    background: var(--pw-canvas-bg, #f3f0e9);
    padding: 0 !important;
    margin: 0 !important;
    transition: background-color 240ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .pagedjs_pages {
    margin: 0 auto;
    padding: 24pt 0 32pt 0;
  }

  .pagedjs_page {
    background: var(--pw-page-bg, #ffffff) !important;
    box-shadow: 0 8px 32px rgba(11, 9, 8, 0.10), 0 2px 6px rgba(11, 9, 8, 0.04);
    margin: 0 auto 28pt auto !important;
  }

  /* Subtle page-number caption under each rendered page. */
  .pagedjs_page::after {
    content: "Page " counter(pages-meta);
    counter-increment: pages-meta;
    display: block;
    text-align: center;
    margin: 8pt auto 0 auto;
    font-family: var(--pw-meta-font, "JetBrains Mono", monospace);
    font-size: 9pt;
    color: var(--pw-meta-fg, #9c8f85);
    letter-spacing: 0.5pt;
  }
  body { counter-reset: pages-meta; }

  /* Let .chapter-page / .body-page fill paged.js's content area. */
  .chapter-page {
    position: relative;
    width: 100%;
    height: 100%;
    margin: 0 !important;
    box-shadow: none !important;
  }
  .body-page {
    margin: 0 !important;
    box-shadow: none !important;
  }
</style>"""

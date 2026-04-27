# Changelog

All notable changes to Pagewright will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- `pagewright build my-book.pdf` — single-command full-book PDF build via WeasyPrint or paged.js-cli
- Additional themes: `academic`, `fiction-novel`, `technical-reference`
- Per-chapter image references (`![alt](image.png)` resolved against book directory)

## [0.1.0] — 2026-04-27

Initial public release.

### Added

- Two-pane editor: CodeMirror 5 (markdown source) + iframe preview
- Two preview modes: **continuous** (scrolling HTML) and **paged**
  (true A4 layout via paged.js 0.4.3)
- Multi-chapter project model via `pagewright.yaml`
- Atomic file saves (temp file + `os.replace`)
- ETag-based conflict detection (HTTP 409 + Reload / Overwrite / Cancel dialog)
- 3× exponential-backoff retry on transient save failures
- Position-stable hot reload (heading at top of viewport stays put)
- Outline-driven navigation (click heading → cursor jumps + preview scrolls)
- Eight semantic callouts with theme-overridable labels
- Pluggable theme system: `theme.css` + optional `theme.yaml` + optional `chapter_opener.html`
- Bundled `default` theme — clean modern paper-on-cream with ember accent
- Runnable example book in `examples/sample-book/` (~3,500 words across 4 chapters)
- Dark mode with system-preference detection
- Zoom + fit-to-width preview controls
- Command palette (⌘K) for jump-to-chapter
- Filterable chapter sidebar (⌘/)
- Path-traversal-safe asset serving
- `Cache-Control: no-store` on all editor surfaces
- Pip-installable with `pagewright` console script

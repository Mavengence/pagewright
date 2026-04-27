# Contributing to Pagewright

Thanks for considering a contribution. Pagewright is small enough that
one careful PR can move it forward meaningfully — and small enough that
it's easy to read end-to-end before you change anything.

## Setup

```bash
git clone https://github.com/Mavengence/pagewright
cd pagewright
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the editor against the bundled sample book:

```bash
pagewright examples/sample-book --port 5566
```

Run the test suite:

```bash
pytest tests/ -v
```

68 tests across `tests/test_markdown.py`, `test_config.py`,
`test_theme.py`, `test_renderer.py`, and `test_server.py`. They run
in well under a second and cover the markdown converter, the config
loader, the theme system, the renderer, and every Flask endpoint
(including the ETag conflict-detection path).

## What we want

- **Bug fixes** — open an issue first only if it's not obvious from
  reading the code. For obvious bugs, just open a PR with a failing
  test + the fix.
- **New themes** — we'd love a few more in `src/pagewright/themes/`.
  Academic, fiction-novel, technical-reference, RFC-style. One CSS
  file, optional `chapter_opener.html`, optional `theme.yaml` for
  callout labels.
- **Theme docs** — `docs/themes.md` is sparse; concrete walkthroughs
  with screenshots are valuable.
- **PDF rendering helper** — a `pagewright build my-book.pdf` command
  that pipes the renderer through WeasyPrint or paged.js-cli is
  explicitly on the roadmap.

## What we don't want

- **Cloud features.** Pagewright is local-first by design. No auth, no
  multi-tenant, no SaaS surface. If you want collaboration, look at
  Vivliostyle Pub or Ketty.
- **Inline markdown images.** Themes manage their own image assets via
  `theme-asset/`. Inline `![](…)` is intentionally out of scope.
- **More dependencies.** Flask + PyYAML is the entire backend. We're
  resistant to adding more.

## Code style

- Python: PEP 8, type hints everywhere, `ruff` clean.
- JS: vanilla, no build step, no framework. Read `src/pagewright/static/app.js`
  before adding anything new — almost everything you need is probably
  already in there.
- CSS: token-driven (`--bg-app`, `--text`, `--accent`, …). Don't
  introduce new hex literals outside the `:root` block.
- Comments: explain *why*, not *what*. The code says what.

## Testing

```bash
pytest tests/ -v
```

Sub-second test suite. New features need a new test; bug fixes need
a regression test. Don't ship a PR with red CI.

## License

By contributing you agree your work is licensed under the MIT License.

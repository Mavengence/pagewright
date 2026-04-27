# Configuration reference — `pagewright.yaml`

Every Pagewright book lives in a directory containing one
`pagewright.yaml` file. This page is the full schema reference.

## Minimum

```yaml
title: "My Book"
author: "Your Name"
parts:
  - title: "Part I"
    chapters:
      - file: 01_intro.md
        title: "Introduction"
```

That's enough to boot the editor against your book directory.

## Full schema

```yaml
# ── Required ────────────────────────────────────────────────────────────────
title: "My Book"               # str  — display name in topbar + theme strings
parts:                         # list — at least one part with at least one chapter
  - title: "Part I"
    chapters:
      - file: 01_intro.md
        title: "Introduction"

# ── Optional ────────────────────────────────────────────────────────────────
author:   "Your Name"          # str  — used by themes (footer, opener)
subtitle: "A short subtitle"   # str  — used by themes (cover, opener)
theme:    default              # str  — built-in name OR path to custom theme dir
                               #        Built-ins: default
                               #        CLI flag --theme overrides this.

# ── Pass-through fields ─────────────────────────────────────────────────────
# Any extra top-level keys are stored on book.raw and accessible from
# chapter_opener.html via {placeholder} format strings.
edition:        "2026.1"
publisher:      "Acme Press"
isbn:           "978-3-00-000000-0"
classification: "Public"
```

## Parts and chapters

```yaml
parts:
  - title: "Part I — Foundations"
    chapters:
      - file: 01_intro.md           # required — relative to book directory
        title: "Introduction"       # required
        description: "Why this…"    # optional — shown in TOC + chapter opener
        image: cover_01.png         # optional — passed to chapter opener as {image}

      - file: 02_history.md
        title: "A Short History"

  - title: "Part II — Practice"
    chapters:
      - file: 03_setup.md
        title: "Setup"
```

### Chapter numbering

Chapters are numbered globally (1, 2, 3, … across all parts) — not
per-part. The number is exposed to themes as `{number}` and
`{number_padded}` (zero-padded to 2 digits).

### Part numbering

Parts are exposed to themes as `{part_index_roman}` (I, II, III, IV,
…) and `{part_title}`.

## Theme resolution

When `theme:` is set in `pagewright.yaml`:

| Value                | Resolves to                                       |
|----------------------|---------------------------------------------------|
| `default`            | Built-in `src/pagewright/themes/default/`         |
| `./themes/custom/`   | Relative path from the book directory             |
| `/abs/path/`         | Absolute path                                     |
| `~/themes/foo/`      | Tilde-expanded path                               |

The CLI flag `--theme <name>` overrides the YAML value:

```bash
pagewright my-book --theme default
pagewright my-book --theme ~/work/my-house-style/
```

## File layout conventions

```
my-book/
├── pagewright.yaml
├── 01_intro.md
├── 02_history.md
├── 03_setup.md
├── 04_workflow.md
└── images/                        # optional — your theme references via /book-asset/
    └── diagram-1.png
```

The Pagewright editor sandboxes file access to the book directory.
Path-traversal attempts (`../etc/passwd`) return 404.

## Validation

The loader raises with a useful message on:

- **Missing `pagewright.yaml`** (also checks for legacy `config.yaml`)
- **Missing `title` field**
- **Missing `parts` field** (or empty)
- **Empty parts** (parts with zero chapters are silently dropped; if
  no parts have chapters, the loader raises)
- **Missing `chapters[].file`** (KeyError)

Unknown top-level fields are accepted silently and stored in
`book.raw` so themes can use them.

## Filename fallback

If `pagewright.yaml` is missing, Pagewright also checks for
`config.yaml`. Same schema, alternate name.

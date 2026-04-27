# Markdown Features for Long-Form

This chapter exercises every block-level construct Pagewright's
renderer knows about, in roughly the order you'll encounter them
when writing a book chapter. Each section pairs a small piece of
explanation with a live example, so you can see how the construct
looks in your active theme without leaving the page.

## Headings and section flow

Headings render with positional `id="h-N"` anchors so the editor's
outline can jump the preview to the exact heading you click. The
**first paragraph after an h1** is treated as a `.section-lead` and
may be styled larger or in a different weight by the theme — this
is the pattern most non-fiction books use to signal the start of a
new section.

### Third-level heading

Third-level headings are quieter than h2 — they break up a subsection
without competing with it. Use them when a single h2 needs internal
structure but doesn't warrant a fresh top-level section.

You'll rarely need h4 or deeper in a book. If you find yourself
reaching for `####`, you're probably writing a reference document or
an outline; restructure into shorter, flatter sections instead.

## Lists

Bullet lists for unordered points:

- **The first item** carries a strong concept
- The second item supports it with detail
- The third item adds nuance: this works because Markdown lets you
  write multiple sentences inside a single list item without breaking
  the visual flow
- The fourth item, kept short

Numbered lists for sequenced steps:

1. Open the chapter file in your editor of choice
2. Make changes to the markdown source
3. Watch Pagewright re-render the preview
4. Save when satisfied (`⌘S` or wait 1.5s for autosave)
5. Commit when a coherent unit of work is complete

Task lists for in-chapter checklists (GitHub-style `- [ ]` syntax):

- [x] Decide on the book's voice and tense
- [x] Sketch the table of contents
- [x] Write the introduction
- [ ] Edit the introduction relentlessly
- [ ] Show it to two trusted readers
- [ ] Cut the parts you secretly suspected were filler

## Tables

Markdown tables work for any tabular data that fits within the page
width. Pagewright's renderer preserves empty interior cells, so
comparison tables with row labels in the first column lay out
correctly:

| Format     | Editable in 50 years? | Diffs cleanly? | Versioned in git? |
|------------|------------------------|----------------|---------------------|
| **`.md`**  | Yes                    | Yes            | Yes                 |
| `.docx`    | Probably               | No             | No                  |
| `.indd`    | Unlikely               | No             | No                  |
| `.tex`     | Yes                    | Yes            | Yes                 |
| `.txt`     | Yes                    | Yes            | Yes                 |

Wide tables that don't fit on the page will overflow. For very wide
data (more than ~6 columns), consider splitting into two tables or
restructuring as a list of rows.

## Code

Inline `code()` for short snippets and fenced blocks for full
listings. Both render in the theme's monospace face — usually
JetBrains Mono.

Python:

```python
from pathlib import Path
from pagewright.renderer import render_chapter_html
from pagewright.config import load_book_config
from pagewright.theme import load_theme

book = load_book_config(Path("my-book"))
theme = load_theme(book.theme)

for part in book.parts:
    for chapter in part.chapters:
        html = render_chapter_html(
            book.directory / chapter.file,
            book,
            theme,
            mode="paged",
        )
        Path(f"out/{chapter.file}.html").write_text(html)
```

Shell:

```bash
# Start the editor against any book directory
pagewright path/to/my-book --port 5566

# Override the theme without editing pagewright.yaml
pagewright path/to/my-book --theme ./themes/custom/
```

YAML:

```yaml
title:  "My Book"
author: "Your Name"
theme:  default

parts:
  - title: "Part I — Foundations"
    chapters:
      - file: 01_introduction.md
        title: "Introduction"
        description: "Why this book exists."
```

## Links

Inline links like [paged.js](https://pagedjs.org/) keep their URLs
visible and are styled by your active theme. Email links (`[name](mailto:...)`)
render as the visible text only — addresses don't survive the
print-to-paper trip and turning them into clickable elements would
be visual noise.

## Quotes

Plain blockquotes pass through, styled by the theme as either an
indented italic or a left-bordered pull-quote depending on theme
choice:

> A book is a thing made of many parts. The page is the smallest one
> you can hold in your hand and the largest one you can change in a
> single keystroke.

Multi-paragraph quotes work too, with blank `>` lines between
paragraphs:

> Every chapter has a moment where the writer realises the structure
> is wrong and the only fix is to start over. The discipline is to
> recognise this without despair.
>
> The work is mostly recognition.

Use blockquotes sparingly. A quoted paragraph every other page reads
as a manuscript that doesn't trust its own voice; one well-placed
quote per chapter signals authority.

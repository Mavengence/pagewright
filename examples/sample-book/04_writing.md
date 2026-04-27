# Authoring Workflow

Pagewright is built around three working assumptions: you write
locally, you commit your manuscript to version control, and you want
fast feedback on how the book will print. This chapter walks through
the day-to-day loop of writing inside that environment.

## The basic loop

Open the editor:

```bash
pagewright my-book/
```

The sidebar lists every chapter in `pagewright.yaml`, grouped by
part, numbered globally. Click a chapter — the markdown loads on the
left, the preview renders on the right.

Edit a paragraph. Pagewright captures the heading at the top of your
preview viewport, autosaves your file 1.5 seconds after the last
keystroke, then re-renders the preview. The captured heading lands
back at the top — your scroll position is preserved.

That's the loop. Edit, watch, edit, watch. The 1.5-second debounce
is long enough that you don't see the preview blink on every
keystroke, short enough that you don't have to think about saving.

## Autosave + atomic writes

Saves go through a sibling `.tmp` file and `os.replace`. A killed
process — `kill -9`, system crash, dropped power — never leaves a
half-written file on disk. You either get the previous version
intact or you get the new version intact, never something in between.

The save flow:

1. **Editor** sends `POST /api/file` with the new content + an
   `ifMatch` header carrying the file's last-known ETag (the file's
   mtime in nanoseconds).
2. **Server** checks if the file's current ETag matches `ifMatch`.
3. **If yes**, the server writes the new content via temp+replace and
   returns the new ETag. The editor stores it for the next save.
4. **If no**, the server returns `409 Conflict` with the current
   ETag. The editor opens a Reload / Overwrite / Cancel dialog.

> **Tip:** Use `⌘S` to force-save immediately. Useful before a
> `git commit` so you know nothing's still in the autosave debounce.

## Conflict resolution

Conflicts happen when the file changes underneath the editor — most
commonly because you ran `git pull`, or because another editor (a
second Pagewright tab, VS Code, Vim) saved over your work.

When the editor detects a conflict, you get three choices:

- **Reload from disk** — discard your in-editor changes; reload the
  file as it now exists. Use when the on-disk version is correct
  (e.g. you forgot you edited from a second device).
- **Overwrite** — push your in-editor version to disk anyway. The
  on-disk changes are lost. Use when you're certain your in-editor
  version is correct.
- **Cancel** — keep editing without saving. The file stays in its
  modified state on screen; your unsaved changes are still there.
  Use when you need to think.

> **Warning:** "Overwrite" really overwrites — the on-disk version
> is gone unless it was committed. If in doubt, copy the on-disk
> version to a scratch file first, then overwrite, then reconcile.

## Outline-driven navigation

The left sidebar shows an outline of the open chapter, extracted from
its h1 / h2 / h3 headings. Click a heading and:

1. The CodeMirror cursor jumps to that heading's line.
2. The preview iframe scrolls to the matching `#h-N` anchor.

Both are bidirectional — moving the cursor in the editor highlights
the corresponding outline entry. If you write with the outline
visible, you can navigate a 30,000-word chapter without ever using
the scrollbar.

## Workflow shortcuts

| Shortcut             | Action                       |
|----------------------|------------------------------|
| `⌘S`                 | Save immediately             |
| `⌘B` / `⌘I`          | Bold / italic                |
| `⌘F`                 | Find in current file         |
| `⌘K`                 | Jump-to-chapter palette      |
| `⌘/`                 | Focus chapter filter         |
| `⌘\`                 | Toggle sidebar               |
| `⌘+` / `⌘−` / `⌘0`   | Zoom preview (in/out/fit)    |
| `?`                  | Show keyboard help           |
| `Esc`                | Close palette / dialog       |

## When you're done writing

Pagewright is the *editor* — it doesn't ship the PDF. To produce a
final PDF, point your favourite print-CSS engine at the same theme
CSS your preview uses:

```bash
# WeasyPrint (Python, ships with Pagewright's dev deps)
weasyprint preview.html my-book.pdf

# paged.js-cli (Node, npm install -g pagedjs-cli)
pagedjs-cli preview.html -o my-book.pdf

# Prince (commercial)
prince preview.html -o my-book.pdf
```

All three engines honour the same `@page` rules, `string-set`
running headers, and `break-inside` hints your theme defines, so
the output matches the on-screen preview.

A future `pagewright build` command will glue this together. Today,
write a 30-line Python script that imports `render_chapter_html` and
pipes the output through your engine of choice.

## A note on ergonomics

You'll do most of your writing inside the editor. But the editor is
not a moat — your manuscript is plain markdown in a directory you
control. At any moment, close Pagewright and open the same files in
Vim, VS Code, Obsidian, or Notepad. Nothing about Pagewright locks
your work in. The whole point of writing in markdown was that it
shouldn't.

That property — the ability to walk away from the tool without losing
your work — is what makes a tool worth living inside.

# Why Markdown for Books

The book you're reading was written in plain text. Every chapter is a
`.md` file in a directory; every paragraph survived a `git commit`;
every layout decision lives in a single CSS file. Nothing in this
sentence is in a proprietary format. Open the source folder with
`cat` and you'd see the same words you're seeing now.

This is unusual. The default expectation for "writing a book" is still
Word, Scrivener, InDesign — applications that hide your manuscript
inside a binary that one program owns. A 90,000-word novel becomes a
.docx that only Word can really read; a magazine layout becomes an
.indd that only InDesign can really edit. Decades of writing accrete
inside formats one company controls.

Markdown rejects that. The manuscript is text. The structure is text.
The chapter order is text. **Everything you produce belongs to you, in
a form that any tool — past, present, or future — can read.**

## The case for plain text

Three things change when your book is text:

1. **Version control works.** Every keystroke is a diff. You can see
   exactly what you changed yesterday, branch off to try a new chapter
   structure, abandon it without losing anything, merge revisions from
   a co-author, blame a single sentence to find when you wrote it.
   None of this is possible inside a .docx.
2. **Tooling composes.** `grep` works. `wc -w` works. `sed` works.
   You can write a script that counts adverbs per chapter, or one
   that ensures no paragraph exceeds 200 words, or one that flags
   every sentence beginning with "But." Your manuscript is not an
   opaque blob — it's input for any program you can write.
3. **The workflow is durable.** In ten years, Word will have moved
   on. The .docx format you used in 2015 may render slightly
   differently in 2030. A markdown file from 2015 will render
   identically in 2030, in 2050, in 2100 — because the format is the
   text itself.

> **Tip:** Set up your manuscript directory as a git repository on day
> one. Even if you never push it anywhere, the local commit history
> alone is worth more than any "track changes" feature.

## What Markdown gives up

Markdown is intentionally narrow. You get headings, paragraphs, lists,
emphasis, blockquotes, code, tables, links — and nothing else. There's
no way to pick a font for one specific paragraph. There's no way to
nudge a single line two pixels to the left. There's no way to draw an
arrow connecting two table cells.

For most book authors, this is the point. Choices about typography,
spacing, and layout don't belong inside the manuscript — they belong
inside the *theme*. The author writes structure (headings, lists,
emphasis); the typographer writes presentation (fonts, margins,
running headers). When those two roles are separated, both improve.

When you do need a layout exception — a sidebar, a callout, a pulled
figure — Markdown lets you mark it semantically (`> **Tip:**`) and
the theme decides how it looks. The author never touches CSS; the
typographer never touches the manuscript.

## What Pagewright adds

Plain-text manuscripts and print-CSS themes have existed for a
decade. The missing piece, for most writers, was the *editor*: a
place to write where you can see, in real time, how your words break
across A4 pages — without waiting for a build, without leaving the
manuscript, without trusting that your imagination of "what page 47
will look like" matches reality.

Pagewright is that editor. CodeMirror on the left, paged.js on the
right. Edit a paragraph; 1.5 seconds later, your page breaks update.
You're writing into the printed page in real time.

## How to read this sample

The four chapters of this sample exist to demonstrate every Markdown
feature Pagewright renders, including:

- **This chapter** — narrative paragraphs, emphasis, callouts, lists
- **Markdown Features** — headings, tables, code blocks, links
- **Callouts and Tone** — all eight built-in callout types with
  guidance on when to use which
- **Authoring Workflow** — the day-to-day loop of writing in
  Pagewright, including saves, conflicts, and the keyboard

Open the editor at <http://127.0.0.1:5566>. Click any chapter in the
sidebar. Toggle between **Continuous** (scroll the chapter as one
document) and **Paged** (true A4 layout via paged.js). Edit a sentence;
watch the preview update without losing your scroll position.

If at any point the right pane shows your words rendering exactly as
they will appear on the printed page, the tool is working as
intended.

# Callouts and Tone

Callouts are the editorial seasoning of a book. Used well, they break
the monotony of body text, signal importance, and give the reader
visual handholds they can scan when flipping back to find something.
Used poorly, they teach the reader to skip every coloured box on the
page.

The default theme ships eight semantic callouts. Each is an extended
blockquote prefixed with a `**Label:**` marker — the parser detects
the marker and applies a themed CSS class. This page demonstrates all
eight in roughly the order of editorial weight, from quietest to
loudest.

## Note — supporting context

Use **Note** for asides, prerequisites, or background context that
supports the main thread without interrupting it. The reader can
read or skip a note without losing the argument.

> **Note:** All examples in this chapter assume you're running the
> bundled `default` theme. A custom theme can rename the callouts
> (via `theme.yaml`) and restyle them (via `theme.css`), but the
> underlying HTML structure is identical.

## Tip — actionable advice

Use **Tip** for practical, applicable advice the reader can use right
now. Tips work best when they're short, concrete, and pay off
immediately.

> **Tip:** Bind `⌘S` muscle memory early. Pagewright autosaves 1.5
> seconds after the last keystroke, but `⌘S` forces an immediate save
> — useful before a `git commit` so you know nothing is still in the
> autosave debounce.

## Important — high-gravity point

Use **Important** for points the reader must internalise — non-
negotiable principles, decisions that cascade into many subsequent
choices. Higher gravity than a tip; lower gravity than a warning.

> **Important:** Your theme's CSS is the *single source of truth* for
> how the printed book will look. The same `theme.css` powers the
> editor preview AND the final PDF render. Never write "preview-only"
> styles — anything you put in the CSS will land in the book.

## Example — worked illustration

Use **Example** for a worked example, often pairing with a code
block or table. Examples are the bridge between abstract claim and
concrete reader experience.

> **Example:** Suppose you want every chapter to end with a "Coming
> next" pointer. Add to your `chapter_opener.html` template:
> `<div class="ch-next">Coming next: {description}</div>` — the
> placeholder pulls the next chapter's description from
> `pagewright.yaml`.

## Definition — domain term

Use **Definition** for the precise meaning of a domain term you'll
use throughout the book. The default theme renders definitions as
horizontal-rule margin notes — quieter than a coloured callout, but
more findable than a plain paragraph.

> **Definition:** A *theme*, in Pagewright, is a directory containing
> at minimum a `theme.css` file. Optionally a `theme.yaml` for callout
> labels and a `chapter_opener.html` for per-chapter front pages.

## Quote — pull quote

Use **Quote** for an inline pull-quote from another author or a
primary source. The default theme italicises the body and removes
the coloured bar so it reads as a margin voice rather than an alarm.

> **Quote:** "The first draft of anything is shit." — Hemingway
> (probably).

## Warning — real consequences

Use **Warning** sparingly. A warning is a promise: ignore this and
something concrete will go wrong. If you find yourself writing more
than one warning per chapter, you're either teaching dangerous
material or you're using warnings where tips would suffice.

> **Warning:** Two browser tabs editing the same chapter will
> conflict-detect each other on save. The second tab to save gets a
> 409 and a Reload / Overwrite / Cancel dialog. There's no last-write-
> wins fallback — by design.

## Code — annotated listing

Use **Code** when a code snippet needs prose context inside the same
visual unit. For plain code without commentary, use a fenced code
block instead.

> **Code:** `pagewright examples/sample-book --port 5566 --theme ./my-theme/`
> starts the editor against the bundled sample using a theme from a
> sibling directory. Useful when developing a new theme and you want
> rapid iteration without editing `pagewright.yaml`.

## A discipline of restraint

Eight callouts feels like a lot. In practice, most chapters need
two or three: a Note or two for context, a Tip per major idea,
maybe an Important when the chapter pivots on a single decision.

If a chapter has more than five callouts on a page, the page reads
as a slide deck, not a book. Push the content into prose and reserve
callouts for genuinely separable units.

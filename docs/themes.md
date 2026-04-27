# Writing a Pagewright theme

A theme is a directory containing one to three files:

```
my-theme/
├── theme.css                # required
├── theme.yaml               # optional — callout label overrides
└── chapter_opener.html      # optional — per-chapter front-page template
```

That's the entire theme contract. Pagewright loads the CSS and serves
it as the print-stylesheet for the chapter preview. There is no build
step, no preprocessor.

## Where themes live

Built-in themes ship under `src/pagewright/themes/`. Resolve a theme by
name (currently: `default`) or by absolute path:

```bash
# By name (built-in)
pagewright my-book --theme default

# By path (custom)
pagewright my-book --theme ~/work/my-house-theme/
```

Or set it once in `pagewright.yaml`:

```yaml
theme: ./themes/my-house-theme/
```

## theme.css

Your CSS is responsible for everything visual: typography, colour,
margins, page geometry, callout styling, table styles. Pagewright
wraps it in two small overrides depending on preview mode (continuous
vs. paged) but never edits your selectors.

The renderer emits this HTML structure for each chapter:

```html
<div class="chapter-page" data-book-title="...">
  <!-- Output of your chapter_opener.html template, if present -->
</div>

<section class="body-page" data-chapter-num="N">
  <div class="section-mark"></div>
  <h1 class="section-title" id="h-1">First H1</h1>
  <div class="section-rule"></div>
  <p class="section-lead">First paragraph after H1.</p>
  <p>Subsequent paragraphs.</p>

  <h2 class="subsection-title" id="h-2">First H2</h2>
  ...

  <h3 class="sub-subsection-title" id="h-3">...</h3>
  ...

  <ul class="body-list">
    <li>Bullet</li>
    <li class="task-item"><span class="task-box checked"></span>Task</li>
  </ul>

  <ol class="body-list-ordered">
    <li>Numbered</li>
  </ol>

  <div class="table-group">
    <table class="data-table">
      <thead><tr><th>...</th></tr></thead>
      <tbody><tr><td>...</td></tr></tbody>
    </table>
  </div>

  <pre class="code-block">...</pre>
  <code class="inline-code">inline</code>

  <div class="callout callout-tip">
    <div class="callout-title">Tip</div>
    <p>...</p>
  </div>

  <blockquote><p>plain quote</p></blockquote>
</section>
```

Style any subset of these. You don't need to handle classes you don't
use — they'll just inherit browser defaults inside the section.

## Page-level rules

For paged mode, declare your `@page` rules. Common ingredients:

```css
@page {
  size: A4;
  margin: 0;
}

@page chapter-page {
  size: A4;
  margin: 0;
  background: #ffffff;
}

@page body-page {
  size: A4;
  margin: 64pt 56pt 60pt 56pt;
  background: #ffffff;

  @top-left  { content: string(book-title); ... }
  @top-right { content: string(chapter-title); ... }
  @bottom-right { content: counter(page); ... }
}

.chapter-page { page: chapter-page; page-break-after: always; }
.body-page    { page: body-page; }
```

Use CSS-Named-Page strings to pull running header content from your
DOM:

```css
.body-page  { string-set: book-title attr(data-book-title); }
.ch-title   { string-set: chapter-title content(); }
```

## theme.yaml

Override the default callout labels. The default theme ships with
English; if you want a different language, just declare the labels:

```yaml
callouts:
  - { label: "Astuce:",     css_class: "callout-tip",        display: "Astuce" }
  - { label: "Attention:",  css_class: "callout-warning",    display: "Attention" }
  - { label: "Définition:", css_class: "callout-definition", display: "Définition" }
```

Authors then write `> **Tipp:**` in their markdown. The CSS class is
the same — you only restyle if you want to.

## chapter_opener.html

If your theme wants a dedicated front page per chapter (chapter number,
big title, image, etc.), drop a `chapter_opener.html` template into the
theme directory. It's a Python format-string with these placeholders:

| Placeholder           | Example                |
|-----------------------|------------------------|
| `{number}`            | `4`                    |
| `{number_padded}`     | `04`                   |
| `{title}`             | `Writing in Pagewright`|
| `{description}`       | `Workflow tips, …`     |
| `{part_title}`        | `Part II — Authoring`  |
| `{part_index_roman}`  | `II`                   |
| `{book_title}`        | `My Book`              |
| `{book_author}`       | `Your Name`            |
| `{total_chapters}`    | `12`                   |
| `{total_padded}`      | `12`                   |

Example template:

```html
<div class="chapter-page" data-book-title="{book_title}">
  <div class="ch-rule"></div>
  <div class="ch-meta">
    <span>Part {part_index_roman} · {part_title}</span>
    <span>Chapter {number_padded} / {total_padded}</span>
  </div>
  <div class="ch-num">CHAPTER {number_padded}</div>
  <h1 class="ch-title">{title}</h1>
  <p class="ch-desc">{description}</p>
</div>
```

Pagewright passes `data-book-title` so your `@page body-page` running
header can pick up the title from a CSS string.

## Theme assets

Need fonts, images, or any other static asset? Drop them anywhere
inside the theme directory and reference them via the `/theme-asset/`
prefix:

```css
@font-face {
  font-family: 'MyDisplay';
  src: url('/theme-asset/fonts/MyDisplay-Bold.woff2') format('woff2');
}
```

The server sandboxes asset access to your theme directory.

## Reference theme

Read the bundled `default` theme's `theme.css` and `chapter_opener.html`
end-to-end to see how a complete theme is structured. Fork it as the
starting point for your own.

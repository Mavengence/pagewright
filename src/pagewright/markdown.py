"""Markdown → HTML converter with positional heading IDs and theme callouts.

Block-level handling:

- Front-matter ``---`` blocks at the top of a file are skipped.
- ``#``, ``##``, ``###`` headings get ``id="h-N"`` (1-based positional)
  so the editor's outline can jump the preview iframe to a specific
  heading via ``#h-N`` anchor links.
- Fenced code blocks ``` are wrapped in ``<pre class="code-block">``.
- Markdown tables become ``<table class="data-table">`` with empty
  interior cells preserved (row labels in column 0 work correctly).
- Blockquote prefixes (``> **Tip:**``) become themed callouts; the
  callout label set is supplied by the active theme so a localised
  theme can ship its own marker words while keeping the same CSS
  classes (``callout-tip``, ``callout-warning``, etc.).
- Bullet (``-``/``*``) and ordered (``1.``) lists. GitHub-style task
  list items (``- [ ]`` / ``- [x]``) render with a real checkbox span.

Inline handling: bold/italic, inline code, ``[text](url)`` links, and
``[[wiki-style]]`` links (rendered as bold). HTML special characters in
prose are escaped before markdown tokens are parsed.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CalloutSpec:
    """One callout definition: marker shown in source, CSS class on output."""

    label: str  # e.g. "Tip:" — what authors write inside ``> **...**``
    css_class: str  # e.g. "callout-tip"
    display: str  # e.g. "Tip" — shown above the body (no trailing colon)


# Sensible default callouts for the default English theme. Themes can
# replace this list entirely via theme.yaml.
DEFAULT_CALLOUTS: tuple[CalloutSpec, ...] = (
    CalloutSpec("Note:", "callout-note", "Note"),
    CalloutSpec("Tip:", "callout-tip", "Tip"),
    CalloutSpec("Warning:", "callout-warning", "Warning"),
    CalloutSpec("Important:", "callout-important", "Important"),
    CalloutSpec("Example:", "callout-example", "Example"),
    CalloutSpec("Definition:", "callout-definition", "Definition"),
    CalloutSpec("Quote:", "callout-quote", "Quote"),
    CalloutSpec("Code:", "callout-code", "Code"),
)


@dataclass(frozen=True)
class RenderOptions:
    """Flags controlling markdown → HTML behavior."""

    callouts: tuple[CalloutSpec, ...] = DEFAULT_CALLOUTS
    # If True, the first paragraph after an h1 is rendered with a
    # ``.section-lead`` class so themes can style it as a lede.
    emphasize_first_paragraph: bool = True
    # If True, h1 gets a ``.section-mark`` divider above it.
    h1_section_mark: bool = True


def md_to_html(md_text: str, options: RenderOptions | None = None) -> str:
    """Convert markdown to HTML.

    Args:
        md_text: The raw markdown source.
        options: Render options. ``None`` uses ``RenderOptions()`` defaults.

    Returns:
        HTML string with positional heading IDs and themed callout markup.
    """
    opts = options or RenderOptions()
    callout_map = {c.label: c for c in opts.callouts}

    lines = md_text.split("\n")
    parts: list[str] = []
    i = 0
    first_h1_rendered = False
    lead_pending = False
    heading_idx = 0

    while i < len(lines):
        line = lines[i]

        # Strip YAML front-matter if present at the top of the file.
        if i == 0 and line.strip() == "---":
            i += 1
            while i < len(lines) and lines[i].strip() != "---":
                i += 1
            i += 1
            continue

        # Skip Obsidian image embeds — themes don't support them out of
        # the box and silently dropping is friendlier than failing.
        if re.match(r"^!\[\[.*\]\]$", line.strip()):
            i += 1
            continue

        if not line.strip():
            i += 1
            continue

        if re.match(r"^---+$", line.strip()):
            i += 1
            continue

        if line.strip().startswith("```"):
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(html.escape(lines[i]))
                i += 1
            i += 1
            parts.append(f'<pre class="code-block">{chr(10).join(code_lines)}</pre>')
            lead_pending = False
            continue

        if "|" in line and i + 1 < len(lines) and re.match(r"^[\s|:\-]+$", lines[i + 1].strip()):
            table_lines: list[str] = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            parts.append(_render_table(table_lines))
            lead_pending = False
            continue

        if line.strip().startswith(">"):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s*", "", lines[i]))
                i += 1
            parts.append(_render_quote_or_callout(quote_lines, callout_map))
            lead_pending = False
            continue

        if re.match(r"^\s*[-*]\s", line):
            items: list[str] = []
            any_task = False
            while i < len(lines) and re.match(r"^\s*[-*]\s", lines[i]):
                text = re.sub(r"^\s*[-*]\s+", "", lines[i])
                task_match = re.match(r"^\[([ xX])\]\s+(.*)$", text)
                if task_match:
                    any_task = True
                    checked = task_match.group(1).lower() == "x"
                    body = task_match.group(2)
                    box = (
                        '<span class="task-box checked"></span>'
                        if checked
                        else '<span class="task-box"></span>'
                    )
                    items.append(f'<li class="task-item">{box}{_inline(body)}</li>')
                else:
                    items.append(f"<li>{_inline(text)}</li>")
                i += 1
            list_class = "body-list body-list-task" if any_task else "body-list"
            parts.append(f'<ul class="{list_class}">{"".join(items)}</ul>')
            lead_pending = False
            continue

        if re.match(r"^\s*\d+[.)]\s", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+[.)]\s", lines[i]):
                text = re.sub(r"^\s*\d+[.)]\s+", "", lines[i])
                items.append(f"<li>{_inline(text)}</li>")
                i += 1
            parts.append(f'<ol class="body-list-ordered">{"".join(items)}</ol>')
            lead_pending = False
            continue

        if line.strip().startswith("# ") and not line.strip().startswith("## "):
            title = line.strip().lstrip("#").strip()
            heading_idx += 1
            if opts.h1_section_mark:
                if not first_h1_rendered:
                    parts.append('<div class="section-mark"></div>')
                    first_h1_rendered = True
                else:
                    parts.append('<div class="section-mark" style="margin-top: 28pt;"></div>')
            parts.append(f'<h1 class="section-title" id="h-{heading_idx}">{_inline(title)}</h1>')
            if opts.h1_section_mark:
                parts.append('<div class="section-rule"></div>')
            lead_pending = opts.emphasize_first_paragraph
            i += 1
            continue

        if line.strip().startswith("## ") and not line.strip().startswith("### "):
            title = line.strip().lstrip("#").strip()
            heading_idx += 1
            parts.append(f'<h2 class="subsection-title" id="h-{heading_idx}">{_inline(title)}</h2>')
            lead_pending = False
            i += 1
            continue

        if line.strip().startswith("### "):
            title = line.strip().lstrip("#").strip()
            heading_idx += 1
            parts.append(
                f'<h3 class="sub-subsection-title" id="h-{heading_idx}">{_inline(title)}</h3>'
            )
            lead_pending = False
            i += 1
            continue

        para_lines: list[str] = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            text = " ".join(para_lines)
            if lead_pending:
                parts.append(f'<p class="section-lead">{_inline(text)}</p>')
                lead_pending = False
            else:
                parts.append(f"<p>{_inline(text)}</p>")
            continue

        i += 1

    return "\n".join(parts)


def _is_block_start(line: str) -> bool:
    s = line.strip()
    if s.startswith("#"):
        return True
    if s.startswith("```"):
        return True
    if s.startswith(">"):
        return True
    if re.match(r"^[-*]\s", s):
        return True
    if re.match(r"^\d+[.)]\s", s):
        return True
    if re.match(r"^---+$", s):
        return True
    if re.match(r"^!\[\[", s):
        return True
    return False


def _inline(text: str) -> str:
    """Apply inline markdown to a string of escaped HTML."""
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r'<code class="inline-code">\1</code>', text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"___(.+?)___", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<em>\1</em>", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"<strong>\1</strong>", text)

    def _link_repl(m: re.Match[str]) -> str:
        link_text = m.group(1)
        url = m.group(2).strip()
        if url.startswith("mailto:"):
            return link_text
        if url.startswith(("http://", "https://")):
            return f'<a href="{url}">{link_text}</a>'
        return f'<a href="{url}">{link_text}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_repl, text)
    return text


def _split_row(line: str) -> list[str]:
    """Split a markdown table row, preserving empty interior cells."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _render_table(table_lines: list[str]) -> str:
    if len(table_lines) < 2:
        return ""
    headers = _split_row(table_lines[0])
    n_cols = len(headers)
    rows: list[list[str]] = []
    for line in table_lines[2:]:
        cells = _split_row(line)
        if not any(cells):
            continue
        if len(cells) < n_cols:
            cells = cells + [""] * (n_cols - len(cells))
        elif len(cells) > n_cols:
            cells = cells[:n_cols]
        rows.append(cells)

    out = ['<div class="table-group"><table class="data-table"><thead><tr>']
    out += [f"<th>{_inline(h)}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        out += [f"<td>{_inline(cell)}</td>" for cell in row]
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _render_quote_or_callout(quote_lines: list[str], callout_map: dict[str, CalloutSpec]) -> str:
    """Convert ``>`` lines into either a themed callout or a plain blockquote."""
    paras: list[str] = []
    buf: list[str] = []
    for q in quote_lines:
        if q.strip():
            buf.append(q)
        elif buf:
            paras.append(" ".join(buf).strip())
            buf = []
    if buf:
        paras.append(" ".join(buf).strip())
    if not paras:
        return ""

    first = paras[0]
    callout: CalloutSpec | None = None
    body_first = first
    for label, spec in callout_map.items():
        prefix = f"**{label}**"
        if first.startswith(prefix):
            callout = spec
            body_first = first[len(prefix) :].strip()
            break

    if callout:
        body_html: list[str] = []
        if body_first:
            body_html.append(f"<p>{_inline(body_first)}</p>")
        for p in paras[1:]:
            body_html.append(f"<p>{_inline(p)}</p>")
        return (
            f'<div class="callout {callout.css_class}">'
            f'<div class="callout-title">{html.escape(callout.display)}</div>'
            f"{''.join(body_html)}"
            f"</div>"
        )

    body_html_str = "".join(f"<p>{_inline(p)}</p>" for p in paras)
    return f"<blockquote>{body_html_str}</blockquote>"

"""Markdown converter tests."""

from __future__ import annotations

from pagewright.markdown import (
    DEFAULT_CALLOUTS,
    CalloutSpec,
    RenderOptions,
    md_to_html,
)


class TestHeadings:
    def test_h1_gets_section_title_class_and_id(self) -> None:
        html = md_to_html("# Hello")
        assert 'class="section-title"' in html
        assert 'id="h-1"' in html
        assert ">Hello</h1>" in html

    def test_h2_gets_subsection_title_class(self) -> None:
        html = md_to_html("## Hello")
        assert 'class="subsection-title"' in html
        assert 'id="h-1"' in html

    def test_h3_gets_sub_subsection_title_class(self) -> None:
        html = md_to_html("### Hello")
        assert 'class="sub-subsection-title"' in html

    def test_heading_ids_increment_positionally(self) -> None:
        html = md_to_html("# A\n\n## B\n\n### C\n\n# D")
        assert 'id="h-1"' in html
        assert 'id="h-2"' in html
        assert 'id="h-3"' in html
        assert 'id="h-4"' in html

    def test_first_paragraph_after_h1_is_section_lead(self) -> None:
        html = md_to_html("# Title\n\nLead paragraph.\n\nFollow-up.")
        assert '<p class="section-lead">Lead paragraph.' in html
        assert "<p>Follow-up." in html

    def test_h1_emits_section_mark_divider(self) -> None:
        html = md_to_html("# Hello")
        assert 'class="section-mark"' in html
        assert 'class="section-rule"' in html


class TestCallouts:
    def test_default_theme_ships_eight(self) -> None:
        assert len(DEFAULT_CALLOUTS) == 8
        labels = {c.label for c in DEFAULT_CALLOUTS}
        assert {"Note:", "Tip:", "Warning:", "Important:"} <= labels

    def test_tip_callout_renders(self) -> None:
        html = md_to_html("> **Tip:** Use git.")
        assert 'class="callout callout-tip"' in html
        assert ">Tip</div>" in html
        assert "Use git." in html

    def test_warning_callout_renders(self) -> None:
        html = md_to_html("> **Warning:** Read carefully.")
        assert 'class="callout callout-warning"' in html

    def test_unmarked_blockquote_is_plain_blockquote(self) -> None:
        html = md_to_html("> Just a quote.")
        assert "<blockquote>" in html
        assert "callout" not in html

    def test_custom_callout_set_overrides_default(self) -> None:
        custom = (CalloutSpec("Astuce:", "callout-tip", "Astuce"),)
        html = md_to_html(
            "> **Astuce:** Bon conseil.",
            options=RenderOptions(callouts=custom),
        )
        assert 'class="callout callout-tip"' in html
        assert ">Astuce</div>" in html


class TestLists:
    def test_bullet_list_uses_body_list_class(self) -> None:
        html = md_to_html("- one\n- two\n- three")
        assert 'class="body-list"' in html
        assert html.count("<li>") == 3

    def test_ordered_list_uses_body_list_ordered_class(self) -> None:
        html = md_to_html("1. first\n2. second")
        assert 'class="body-list-ordered"' in html

    def test_task_list_renders_checkboxes(self) -> None:
        html = md_to_html("- [ ] todo\n- [x] done")
        assert "body-list-task" in html
        assert 'class="task-box"' in html
        assert 'class="task-box checked"' in html


class TestTables:
    def test_simple_table_renders(self) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        html = md_to_html(md)
        assert 'class="data-table"' in html
        assert "<thead>" in html
        assert "<th>A</th>" in html
        assert "<td>1</td>" in html

    def test_empty_interior_cells_preserved(self) -> None:
        # The previous implementation dropped empty cells, breaking
        # comparison tables with row labels in the first column.
        md = "| | A | B |\n|---|---|---|\n| Row | x | y |"
        html = md_to_html(md)
        # Header should have 3 <th>s, including an empty first one
        assert html.count("<th>") == 3


class TestCode:
    def test_inline_code_renders(self) -> None:
        html = md_to_html("Use `git pull` regularly.")
        assert '<code class="inline-code">git pull</code>' in html

    def test_fenced_code_block_renders(self) -> None:
        md = "```\nprint('hi')\n```"
        html = md_to_html(md)
        assert '<pre class="code-block">' in html
        assert "print(&#x27;hi&#x27;)" in html  # html-escaped


class TestInline:
    def test_bold(self) -> None:
        assert "<strong>x</strong>" in md_to_html("**x**")

    def test_italic(self) -> None:
        assert "<em>x</em>" in md_to_html("*x*")

    def test_bold_italic(self) -> None:
        assert "<strong><em>x</em></strong>" in md_to_html("***x***")

    def test_link_to_url_renders_anchor(self) -> None:
        html = md_to_html("[paged.js](https://pagedjs.org)")
        assert '<a href="https://pagedjs.org">paged.js</a>' in html

    def test_html_in_prose_is_escaped(self) -> None:
        # GmbH & Co. KG, Score < 20, etc. should not break parsing.
        html = md_to_html("Score < 20 and AT&T")
        assert "&lt;" in html
        assert "&amp;" in html


class TestFrontMatter:
    def test_yaml_front_matter_is_stripped(self) -> None:
        md = "---\ntitle: Foo\n---\n\n# Real Heading"
        html = md_to_html(md)
        assert "title: Foo" not in html
        assert ">Real Heading</h1>" in html


class TestEmptyInput:
    def test_empty_string_returns_empty_html(self) -> None:
        assert md_to_html("") == ""

    def test_whitespace_only_returns_empty(self) -> None:
        assert md_to_html("   \n\n  \n") == ""

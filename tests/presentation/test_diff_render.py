# topmark:header:start
#
#   project      : TopMark
#   file         : test_diff_render.py
#   file_relpath : tests/presentation/test_diff_render.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Diff utils: rendering from text or sequences and empty inputs.

Covers `render_patch` inputs and output type guarantees.
"""

from __future__ import annotations

import textwrap

from topmark.presentation.formatters.unified_diff import format_patch_plain
from topmark.presentation.markdown.utils import render_fenced_code_block_markdown


def test_render_patch_accepts_str_and_list() -> None:
    """`render_patch` should accept both a diff string and an iterable of lines."""
    diff_text = "--- a\n+++ b\n-foo\n+bar\n"
    s1: str = format_patch_plain(
        patch=diff_text,
    )
    s2: str = format_patch_plain(
        patch=diff_text.splitlines(False),
    )

    # Both should render to non-empty strings.
    assert isinstance(s1, str) and isinstance(s2, str) and s1 and s2


def test_render_patch_empty_input_is_safe() -> None:
    """Empty diff input should not raise and should return a string."""
    s: str = format_patch_plain(
        patch="",
    )
    assert isinstance(s, str)


def test_render_fenced_code_block_markdown_uses_diff_language() -> None:
    """Markdown diff blocks should include the requested language marker."""
    patch: str = textwrap.dedent("""\
        --- a
        +++ b
        -foo
        +bar
        """)
    rendered: str = render_fenced_code_block_markdown(
        text=patch,
        language="diff",
    )

    assert rendered.startswith("```diff\n")
    assert rendered.endswith("\n```")
    assert "-foo" in rendered
    assert "+bar" in rendered


def test_render_fenced_code_block_markdown_avoids_backtick_collision() -> None:
    """Markdown fences should be longer than any backtick run in diff content."""
    patch: str = textwrap.dedent("""\
        --- README.md
        +++ README.md
        +```python
        +print("hello")
        +```
        """)
    rendered: str = render_fenced_code_block_markdown(
        text=patch,
        language="diff",
    )

    lines: list[str] = rendered.splitlines()

    assert lines[0] == "````diff"
    assert lines[-1] == "````"
    assert "+```python" in rendered
    assert "+```" in rendered


def test_render_fenced_code_block_markdown_handles_longer_backtick_runs() -> None:
    """Markdown fences should grow beyond longer nested code fences."""
    patch: str = textwrap.dedent("""\
        --- docs/example.md
        +++ docs/example.md
        +````markdown
        +```python
        +pass
        +```
        +````
        """)
    rendered: str = render_fenced_code_block_markdown(
        text=patch,
        language="diff",
    )

    lines: list[str] = rendered.splitlines()

    assert lines[0] == "`````diff"
    assert lines[-1] == "`````"
    assert "+````markdown" in rendered

# topmark:header:start
#
#   project      : TopMark
#   file         : test_help_epilog.py
#   file_relpath : tests/cli/test_help_epilog.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for Rich Click help epilog rendering helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from topmark.cli.help import HelpExample
from topmark.cli.help import render_examples_epilog

if TYPE_CHECKING:
    from rich.text import Text


def test_render_examples_epilog_renders_examples_without_notes() -> None:
    """Render examples and omit the notes section when no notes are provided."""
    epilog: Text = render_examples_epilog(
        examples=(
            HelpExample(
                summary="Run a dry-run check",
                command_line="topmark check src",
            ),
        ),
    )

    assert epilog.plain == ("Examples:\n  # Run a dry-run check\n  topmark check src\n")


def test_render_examples_epilog_renders_examples_and_notes() -> None:
    """Render examples followed by notes when both sections are provided."""
    epilog: Text = render_examples_epilog(
        examples=(
            HelpExample(
                summary="Print the installed version",
                command_line="topmark version",
            ),
        ),
        notes=(
            "Default output is human-readable.",
            "Machine-readable formats emit structured metadata.",
        ),
    )

    assert epilog.plain == (
        "Examples:\n"
        "  # Print the installed version\n"
        "  topmark version\n"
        "\n"
        "Notes:\n"
        "  • Default output is human-readable.\n"
        "  • Machine-readable formats emit structured metadata.\n"
    )


def test_render_examples_epilog_renders_notes_without_examples() -> None:
    """Render notes without an examples heading when examples are empty."""
    epilog: Text = render_examples_epilog(
        examples=(),
        notes=("Use this output for command help only.",),
    )

    assert epilog.plain == ("Notes:\n  • Use this output for command help only.\n")


def test_render_examples_epilog_renders_empty_text_for_no_content() -> None:
    """Render an empty Rich Text object when no examples or notes are provided."""
    epilog: Text = render_examples_epilog(examples=())

    assert epilog.plain == ""

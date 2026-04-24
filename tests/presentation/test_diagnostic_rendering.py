# topmark:header:start
#
#   project      : TopMark
#   file         : test_diagnostic_rendering.py
#   file_relpath : tests/presentation/test_diagnostic_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for human diagnostic presentation helpers."""

from __future__ import annotations

from topmark.presentation.markdown.diagnostic import render_human_diagnostics_markdown
from topmark.presentation.shared.diagnostic import HumanDiagnosticCounts
from topmark.presentation.shared.diagnostic import HumanDiagnosticLine
from topmark.presentation.text.diagnostic import render_human_diagnostics_text


def test_human_diagnostics_text_summary_at_default_verbosity() -> None:
    """TEXT diagnostics should render a compact summary at default verbosity."""
    output: str = render_human_diagnostics_text(
        counts=HumanDiagnosticCounts(error=1, warning=2, info=3),
        diagnostics=[
            HumanDiagnosticLine(level="error", message="Invalid config"),
            HumanDiagnosticLine(level="warning", message="Deprecated option"),
        ],
        verbosity_level=0,
    )

    assert output == (
        "Diagnostics: 1 error(s), 2 warning(s), 3 information(s) (use '-v' to view details)"
    )


def test_human_diagnostics_markdown_summary_at_default_verbosity() -> None:
    """Markdown diagnostics should render a compact summary at default verbosity."""
    output: str = render_human_diagnostics_markdown(
        title="Configuration diagnostics",
        counts=HumanDiagnosticCounts(error=1, warning=2, info=3),
        diagnostics=[
            HumanDiagnosticLine(level="error", message="Invalid config"),
            HumanDiagnosticLine(level="warning", message="Deprecated option"),
        ],
        verbosity_level=0,
    )

    assert output == (
        "> **Diagnostics:** 1 error(s), 2 warning(s), 3 information(s) (use `-v` to view details)\n"
    )


def test_human_diagnostics_text_details_at_verbose_level() -> None:
    """TEXT diagnostics should include detail lines at verbose levels."""
    output: str = render_human_diagnostics_text(
        counts=HumanDiagnosticCounts(error=1, warning=1, info=0),
        diagnostics=[
            HumanDiagnosticLine(level="error", message="Invalid config"),
            HumanDiagnosticLine(level="warning", message="Deprecated option"),
        ],
        verbosity_level=1,
    )

    assert output == "\n".join(
        [
            "Diagnostics: 1 error(s), 1 warning(s), 0 information(s)",
            "- error: Invalid config",
            "- warning: Deprecated option",
        ]
    )


def test_human_diagnostics_markdown_details_at_verbose_level() -> None:
    """Markdown diagnostics should include a section, summary, and detail lines."""
    output: str = render_human_diagnostics_markdown(
        title="Configuration diagnostics",
        counts=HumanDiagnosticCounts(error=1, warning=1, info=0),
        diagnostics=[
            HumanDiagnosticLine(level="error", message="Invalid config"),
            HumanDiagnosticLine(level="warning", message="Deprecated option"),
        ],
        verbosity_level=1,
    )

    assert (
        output
        == "\n".join(
            [
                "### Configuration diagnostics",
                "",
                "**Diagnostics:** 1 error(s), 1 warning(s), 0 information(s)",
                "- **error**: Invalid config",
                "- **warning**: Deprecated option",
            ]
        )
        + "\n"
    )


def test_human_diagnostics_render_empty_when_no_diagnostics() -> None:
    """Both renderers should return an empty string when there are no diagnostics."""
    counts = HumanDiagnosticCounts(error=0, warning=0, info=0)

    assert (
        render_human_diagnostics_text(
            counts=counts,
            diagnostics=[],
            verbosity_level=0,
        )
        == ""
    )
    assert (
        render_human_diagnostics_markdown(
            title="Configuration diagnostics",
            counts=counts,
            diagnostics=[],
            verbosity_level=1,
        )
        == ""
    )

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

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import cast

from topmark.diagnostic.model import Diagnostic
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.presentation.markdown.diagnostic import render_diagnostics_markdown
from topmark.presentation.markdown.diagnostic import render_human_diagnostics_markdown
from topmark.presentation.shared.diagnostic import HumanDiagnosticCounts
from topmark.presentation.shared.diagnostic import HumanDiagnosticLine
from topmark.presentation.shared.diagnostic import prepare_human_diagnostics
from topmark.presentation.text.diagnostic import render_diagnostics_text
from topmark.presentation.text.diagnostic import render_human_diagnostics_text

if TYPE_CHECKING:
    from collections.abc import Iterable


class CustomLevel(str, Enum):
    """Non-standard level used to exercise human diagnostic fallback handling."""

    NOTICE = "notice"


@dataclass(frozen=True, kw_only=True, slots=True)
class LooseDiagnostic:
    """Diagnostic-like object used to test shared human preparation fallbacks."""

    level: object
    message: object


def _log_with_entries(entries: list[tuple[DiagnosticLevel, str]]) -> MutableDiagnosticLog:
    """Build a mutable diagnostic log with stable insertion order."""
    log = MutableDiagnosticLog()
    for level, message in entries:
        log.add(Diagnostic(level=level, message=message))
    return log


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


def test_human_diagnostics_markdown_renders_stable_document_output() -> None:
    """Markdown diagnostics should render stable document output."""
    output: str = render_human_diagnostics_markdown(
        title="Configuration diagnostics",
        counts=HumanDiagnosticCounts(error=1, warning=2, info=3),
        diagnostics=[
            HumanDiagnosticLine(level="error", message="Invalid config"),
            HumanDiagnosticLine(level="warning", message="Deprecated option"),
        ],
    )

    assert (
        output
        == "\n".join(
            [
                "### Configuration diagnostics",
                "",
                "**Diagnostics:** 1 error(s), 2 warning(s), 3 information(s)",
                "- **error**: Invalid config",
                "- **warning**: Deprecated option",
            ]
        )
        + "\n"
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
        )
        == ""
    )


def test_prepare_human_diagnostics_counts_known_levels() -> None:
    """Shared diagnostic preparation should count known diagnostic levels."""
    diagnostics: list[Diagnostic] = [
        Diagnostic(level=DiagnosticLevel.ERROR, message="Broken"),
        Diagnostic(level=DiagnosticLevel.WARNING, message="Deprecated"),
        Diagnostic(level=DiagnosticLevel.INFO, message="FYI"),
    ]

    counts, lines = prepare_human_diagnostics(diagnostics)

    assert counts == HumanDiagnosticCounts(error=1, warning=1, info=1)
    assert lines == [
        HumanDiagnosticLine(level="error", message="Broken"),
        HumanDiagnosticLine(level="warning", message="Deprecated"),
        HumanDiagnosticLine(level="info", message="FYI"),
    ]


def test_prepare_human_diagnostics_treats_unknown_levels_as_info() -> None:
    """Unknown or empty levels should remain stable and count as information."""
    diagnostics: Iterable[Diagnostic] = cast(
        "Iterable[Diagnostic]",
        [
            LooseDiagnostic(level=CustomLevel.NOTICE, message=123),
            LooseDiagnostic(level="", message="empty level"),
        ],
    )

    counts, lines = prepare_human_diagnostics(diagnostics)

    assert counts == HumanDiagnosticCounts(error=0, warning=0, info=2)
    assert lines == [
        HumanDiagnosticLine(level="notice", message="123"),
        HumanDiagnosticLine(level="info", message="empty level"),
    ]


def test_render_diagnostics_text_empty_log_returns_empty_string() -> None:
    """Full TEXT diagnostics renderer should be silent for empty logs."""
    assert (
        render_diagnostics_text(
            diagnostics=MutableDiagnosticLog(),
            verbosity_level=0,
            color=False,
        )
        == ""
    )


def test_render_diagnostics_text_compact_error_warning_summary() -> None:
    """At verbosity 0, TEXT diagnostics should summarize high-severity entries only."""
    log: MutableDiagnosticLog = _log_with_entries(
        [
            (DiagnosticLevel.ERROR, "Broken config"),
            (DiagnosticLevel.WARNING, "Deprecated key"),
            (DiagnosticLevel.INFO, "Extra detail"),
        ]
    )

    output: str = render_diagnostics_text(
        diagnostics=log,
        verbosity_level=0,
        color=False,
    )

    assert output == "ℹ️  Diagnostics: 1 error, 1 warning (use '-v' to view details)"


def test_render_diagnostics_text_compact_info_only_summary() -> None:
    """At verbosity 0, TEXT diagnostics should include info when no higher severity exists."""
    log: MutableDiagnosticLog = _log_with_entries(
        [
            (DiagnosticLevel.INFO, "First detail"),
            (DiagnosticLevel.INFO, "Second detail"),
        ]
    )

    output: str = render_diagnostics_text(
        diagnostics=log,
        verbosity_level=0,
        color=False,
    )

    assert output == "ℹ️  Diagnostics: 2 infos (use '-v' to view details)"


def test_render_diagnostics_text_verbose_renders_all_entries() -> None:
    """At verbosity >= 1, TEXT diagnostics should include one line per entry."""
    log: MutableDiagnosticLog = _log_with_entries(
        [
            (DiagnosticLevel.ERROR, "Broken config"),
            (DiagnosticLevel.WARNING, "Deprecated key"),
            (DiagnosticLevel.INFO, "Extra detail"),
        ]
    )

    output: str = render_diagnostics_text(
        diagnostics=log.freeze(),
        verbosity_level=1,
        color=False,
    )

    assert output == "\n".join(
        [
            "ℹ️  Diagnostics: 1 error, 1 warning",
            "  [error] Broken config",
            "  [warning] Deprecated key",
            "  [info] Extra detail",
        ]
    )


def test_render_diagnostics_markdown_empty_log_returns_empty_string() -> None:
    """Full Markdown diagnostics renderer should be silent for empty logs."""
    assert render_diagnostics_markdown(diagnostics=MutableDiagnosticLog()) == ""


def test_render_diagnostics_markdown_renders_error_warning_summary() -> None:
    """Markdown diagnostics should render a stable triage block and entries."""
    log: MutableDiagnosticLog = _log_with_entries(
        [
            (DiagnosticLevel.ERROR, "Broken config"),
            (DiagnosticLevel.WARNING, "Deprecated key"),
            (DiagnosticLevel.INFO, "Extra detail"),
        ]
    )

    output: str = render_diagnostics_markdown(diagnostics=log.freeze())

    assert (
        output
        == "\n".join(
            [
                "> ℹ️ **Diagnostics:** 1 error, 1 warning",
                "",
                "- ❌ **[error]** Broken config",
                "- ⚠️ **[warning]** Deprecated key",
                "- ℹ️ **[info]** Extra detail",
            ]
        )
        + "\n"
    )


def test_render_diagnostics_markdown_renders_info_only_summary() -> None:
    """Markdown diagnostics should include info counts when no higher severity exists."""
    log: MutableDiagnosticLog = _log_with_entries(
        [
            (DiagnosticLevel.INFO, "First detail"),
            (DiagnosticLevel.INFO, "Second detail"),
        ]
    )

    output: str = render_diagnostics_markdown(diagnostics=log)

    assert (
        output
        == "\n".join(
            [
                "> ℹ️ **Diagnostics:** 2 infos",
                "",
                "- ℹ️ **[info]** First detail",
                "- ℹ️ **[info]** Second detail",
            ]
        )
        + "\n"
    )

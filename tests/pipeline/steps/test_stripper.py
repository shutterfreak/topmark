# topmark:header:start
#
#   project      : TopMark
#   file         : test_stripper.py
#   file_relpath : tests/pipeline/steps/test_stripper.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the `stripper` pipeline step.

These tests validate that the step removes the TopMark header using the
scanner-provided header span and that it trims exactly one leading blank
line when the header starts at the top of the file. The tests bootstrap a
minimal `ProcessingContext` without running the full pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_stripper
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import ListFileImageView
from topmark.processors.base import HeaderProcessor
from topmark.processors.types import StripDiagKind
from topmark.processors.types import StripDiagnostic

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


# --- Helper classes and context factory for stripper tests ---


class _NotFoundStripProcessor(HeaderProcessor):
    """Processor stub that reports no removable header."""

    namespace = "test"
    local_key = "not_found_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> tuple[list[str], tuple[int, int] | None, StripDiagnostic]:
        """Return a NOT_FOUND strip diagnostic without changing lines."""
        return (
            lines,
            None,
            StripDiagnostic(kind=StripDiagKind.NOT_FOUND, reason="stub not found"),
        )


class _ErrorStripProcessor(HeaderProcessor):
    """Processor stub that reports a strip analysis error."""

    namespace = "test"
    local_key = "error_strip"

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> tuple[list[str], tuple[int, int] | None, StripDiagnostic]:
        """Return an ERROR strip diagnostic without changing lines."""
        return (
            lines,
            None,
            StripDiagnostic(kind=StripDiagKind.ERROR, reason="stub strip error"),
        )


def _make_strip_context(path: Path, lines: list[str]) -> ProcessingContext:
    """Create a minimal context suitable for stripper unit tests."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.views.image = ListFileImageView(lines)
    ctx.header_processor = HeaderProcessor()
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.DETECTED
    ctx.newline_style = "\n"
    ctx.ends_with_newline = bool(lines and lines[-1].endswith("\n"))
    return ctx


def test_stripper_uses_span_and_trims_leading_blank(tmp_path: Path) -> None:
    """When span is provided, stripper should remove exactly that region and trim."""
    file: Path = tmp_path / "x.py"
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "\n",
        "code\n",
    ]

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx.views.image = ListFileImageView(lines)

    # Use the base processor; removal relies on span and generic bounds logic.
    ctx.header_processor = HeaderProcessor()

    ctx.views.header = HeaderView(
        range=(0, 2),  # as provided by scanner
        lines=None,
        block=None,
        mapping=None,
    )

    # Simulate resolver result so stripper proceeds
    ctx.status.resolve = ResolveStatus.RESOLVED

    # Simulate reader result so stripper proceeds
    ctx.status.content = ContentStatus.OK

    # Simulate scanner result so stripper proceeds
    ctx.status.header = HeaderStatus.DETECTED

    ctx = run_stripper(ctx)
    updated_lines: list[str] = materialize_updated_lines(ctx)
    # After stripping, only the code line should remain; statuses updated accordingly.
    assert updated_lines == ["code\n"]
    assert ctx.status.strip is StripStatus.READY
    assert ctx.status.header is HeaderStatus.DETECTED


# --- Additional stripper behavior tests ---


def test_stripper_preserves_shebang_before_header(tmp_path: Path) -> None:
    """Removing a header after a shebang should preserve the shebang and body."""
    lines: list[str] = [
        "#!/usr/bin/env python\n",
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "print('body')\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "script.py", lines)
    ctx.views.header = HeaderView(
        range=(1, 3),
        lines=lines[1:4],
        block="".join(lines[1:4]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == [
        "#!/usr/bin/env python\n",
        "print('body')\n",
    ]


def test_stripper_removing_whole_file_header_keeps_final_newline_placeholder(
    tmp_path: Path,
) -> None:
    """A header-only file with a final newline should strip to one newline placeholder."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "header_only.py", lines)
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines,
        block="".join(lines),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\n"]


def test_stripper_missing_header_is_not_needed(tmp_path: Path) -> None:
    """Missing headers should not produce an updated image."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "missing.py",
        ["print('body')\n"],
    )
    ctx.status.header = HeaderStatus.MISSING
    ctx.views.header = None

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.halt_state is None


def test_stripper_rejects_malformed_header_status(tmp_path: Path) -> None:
    """Malformed scanner status should fail and halt before processor removal."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "malformed.py",
        ["# broken\n", "body\n"],
    )
    ctx.status.header = HeaderStatus.MALFORMED_SOME_FIELDS

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.FAILED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None


def test_stripper_not_found_diagnostic_is_not_needed(tmp_path: Path) -> None:
    """Processor NOT_FOUND diagnostics should leave stripping as not needed."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "not_found.py",
        ["# not a topmark header\n", "body\n"],
    )
    ctx.header_processor = _NotFoundStripProcessor()
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# not a topmark header\n"],
        block="# not a topmark header\n",
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.halt_state is None


def test_stripper_error_diagnostic_halts_without_updated_view(tmp_path: Path) -> None:
    """Processor ERROR diagnostics should halt and avoid producing updated lines."""
    ctx: ProcessingContext = _make_strip_context(
        tmp_path / "error.py",
        ["# broken\n", "body\n"],
    )
    ctx.header_processor = _ErrorStripProcessor()
    ctx.views.header = HeaderView(
        range=(0, 0),
        lines=["# broken\n"],
        block="# broken\n",
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.NOT_NEEDED
    assert ctx.views.updated is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "stub strip error"


def test_stripper_preserves_crlf_newline_style_for_empty_placeholder(
    tmp_path: Path,
) -> None:
    """Header-only CRLF input should preserve CRLF in the logical-empty placeholder."""
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\r\n",
        "# h\r\n",
        f"# {TOPMARK_END_MARKER}\r\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "crlf.py", lines)
    ctx.newline_style = "\r\n"
    ctx.ends_with_newline = True
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines,
        block="".join(lines),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\r\n"]


def test_stripper_preserves_leading_bom_on_remaining_body(tmp_path: Path) -> None:
    """If the original image had a BOM, stripped output should retain it."""
    lines: list[str] = [
        f"\ufeff# {TOPMARK_START_MARKER}\n",
        "# h\n",
        f"# {TOPMARK_END_MARKER}\n",
        "body\n",
    ]
    ctx: ProcessingContext = _make_strip_context(tmp_path / "bom.py", lines)
    ctx.leading_bom = True
    ctx.views.header = HeaderView(
        range=(0, 2),
        lines=lines[:3],
        block="".join(lines[:3]),
        mapping={},
    )

    ctx = run_stripper(ctx)

    assert ctx.status.strip is StripStatus.READY
    assert materialize_updated_lines(ctx) == ["\ufeffbody\n"]

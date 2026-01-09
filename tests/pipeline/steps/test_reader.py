# topmark:header:start
#
#   project      : TopMark
#   file         : test_reader.py
#   file_relpath : tests/pipeline/steps/test_reader.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the `reader` pipeline step.

This module verifies the strict policy for mixed line endings introduced in the
reader step. The reader splits files into `keepends=True` lines, computes a
histogram of line terminators (LF, CRLF, CR), and sets the file status to
`SKIPPED_MIXED_LINE_ENDINGS` when more than one style is present. The test
constructs a file that intentionally mixes CRLF and LF to assert this behavior.

Test outline:
  1. Create a temporary file with mixed line endings and a minimal TopMark-like block.
  2. Run the resolver to ensure a file type/processor is selected.
  3. Run the reader and assert that it flags the file as skipped due to mixed endings.

Additional tests cover consistent newline style, single-line files without newline,
and BOM-before-shebang policy.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.conftest import parametrize
from tests.pipeline.conftest import (
    make_pipeline_context,
    materialize_image_lines,
    run_reader,
    run_resolver,
    run_sniffer,
)
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.status import (
    ContentStatus,
    FsStatus,
    ResolveStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.core.diagnostics import Diagnostic
    from topmark.pipeline.context.model import ProcessingContext


def test_read_sets_skip_on_mixed_newlines_strict(tmp_path: Path) -> None:
    """Reader must set SKIPPED_MIXED_LINE_ENDINGS when a file mixes CRLF and LF."""
    # Mix CRLF (\r\n) and LF (\n) deliberately: header lines alternate CRLF/LF, then body uses LF.
    content: str = f"# {TOPMARK_START_MARKER}\r\n# h\n# {TOPMARK_END_MARKER}\r\nprint('Hi!')\n"
    file: Path = tmp_path / "x.py"
    # Use newline="" so Python preserves the exact line endings we provide.
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # First resolve the file type
    ctx = run_resolver(ctx)

    # The resolver must identify a processor; otherwise the reader step would be ill-defined.
    assert ctx.file_type is not None

    # Now sniff (which enforces strict mixed-newlines policy) and assert early skip
    ctx = run_sniffer(ctx)

    # Now read the file (sniffer set status.fs to FsStatus.MIXED_LINE_ENDINGS)
    ctx = run_reader(ctx)

    assert ctx.status.content == ContentStatus.SKIPPED_MIXED_LINE_ENDINGS
    # Reader will no-op when status != RESOLVED; no file_lines are loaded in this case
    return


@parametrize("line_end", ["\r\n", "\n", "\r", ""])
def test_read_detects_trailing_newline_presence_param(tmp_path: Path, line_end: str) -> None:
    """Reader must record whether the file ends with a newline (parametrized)."""
    # Compose content with (or without) a trailing newline based on the parameter.
    content: str = f'print("Hi There"){line_end}'
    suf: str = line_end.replace("\r", "CR").replace("\n", "LF") or "none"
    file: Path = tmp_path / f"x_ends_with_{suf}.py"
    # Use newline="" so Python preserves the exact line endings we provide.
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # First resolve the file type
    ctx = run_resolver(ctx)

    # The resolver must identify a processor; otherwise the reader step would be ill-defined.
    assert ctx.file_type is not None

    # Now read the file
    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    # Strict policy: mixed line endings must cause the reader to skip processing.
    expected: bool = len(line_end) > 0

    assert ctx.ends_with_newline == expected


@parametrize("line_end, expected", [("\n", "\n"), ("\r\n", "\r\n")])
def test_read_detects_consistent_newline_style(
    tmp_path: Path, line_end: str, expected: str
) -> None:
    """Reader must set ctx.newline_style to the actual line terminator in the file."""
    lines: list[str] = [f"print({i}){line_end}" for i in range(3)]
    content: str = "".join(lines)
    file: Path = tmp_path / ("lf.py" if line_end == "\n" else "crlf.py")
    # Use newline="" so Python preserves the exact line endings we provide.
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.newline_style == expected
    assert ctx.mixed_newlines is False
    # Histogram should have exactly one non-zero bucket
    assert set(ctx.newline_hist.keys()) == {expected}


def test_read_defaults_to_lf_when_no_newline_observed(tmp_path: Path) -> None:
    """Reader should default to LF when the file has no newline terminator at all."""
    content: str = "print('one-line')"  # no trailing newline
    file: Path = tmp_path / "single_line_no_nl.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.newline_style == "\n"  # default
    assert ctx.ends_with_newline is False
    assert ctx.newline_hist == {}  # no line terminators observed


def test_read_detects_cr_only_newlines(tmp_path: Path) -> None:
    """Reader must support classic-Mac CR-only files without marking them mixed."""
    lines: list[str] = [f"print({i})\r" for i in range(3)]
    content: str = "".join(lines)
    file: Path = tmp_path / "mac_cr.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.newline_style == "\r"
    assert ctx.mixed_newlines is False
    assert set(ctx.newline_hist.keys()) == {"\r"}


@parametrize("line_end, expected", [("\n", "\n"), ("\r\n", "\r\n")])
def test_read_histogram_dominance_for_consistent_files(
    tmp_path: Path, line_end: str, expected: str
) -> None:
    """Reader should report dominance_ratio == 1.0 for homogeneous files."""
    lines: list[str] = [f"print({i}){line_end}" for i in range(100)]
    content: str = "".join(lines)
    file: Path = tmp_path / ("many_lf.py" if line_end == "\n" else "many_crlf.py")
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.dominant_newline == expected
    assert ctx.dominance_ratio == 1.0
    assert ctx.mixed_newlines is False


def test_read_leading_bom_without_shebang(tmp_path: Path) -> None:
    """Reader should strip a leading UTF-8 BOM when there is no shebang, and proceed."""
    content: str = "\ufeffprint('hello')\n"
    file: Path = tmp_path / "bom_no_shebang.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.leading_bom is True
    assert ctx.views.image is not None
    lines: list[str] = materialize_image_lines(ctx)
    assert lines is not None
    assert not lines[0].startswith("\ufeff"), "BOM must be stripped from in-memory text"


def test_read_accepts_unicode_rich_text(tmp_path: Path) -> None:
    """Reader must accept valid Unicode content as text."""
    content = "π = 3.14159\nprice = '€5'\nrocket = '🚀'\n"
    file: Path = tmp_path / "unicode_ok.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.newline_style == "\n"  # we wrote LF explicitly
    assert set(ctx.newline_hist.keys()) == {"\n"}


def test_read_bom_only_file_contract(tmp_path: Path) -> None:
    """Define/verify behavior when the file is only a BOM."""
    file: Path = tmp_path / "bom_only.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\ufeff")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    # RESOLVED with leading_bom:
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.status.fs == FsStatus.EMPTY
    assert ctx.leading_bom is True
    assert ctx.ends_with_newline is False

    lines: list[str] = materialize_image_lines(ctx)

    assert lines == []  # BOM-only file is treated as empty


def test_read_mixed_newlines_even_if_dominant(tmp_path: Path) -> None:
    """Even with strong dominance, strict policy must skip mixed endings."""
    content: str = "".join([f"print({i})\r\n" for i in range(99)]) + "print(999)\n"
    file: Path = tmp_path / "dominant_but_mixed.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.content == ContentStatus.SKIPPED_MIXED_LINE_ENDINGS
    assert ctx.dominant_newline == "\r\n"


def test_read_shebang_no_bom_is_ok(tmp_path: Path) -> None:
    """Shebang without BOM should not be skipped."""
    content: str = "#!/usr/bin/env python3\nprint('ok')\n"
    file: Path = tmp_path / "shebang_ok.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED


def test_read_non_bom_leading_char_before_shebang(tmp_path: Path) -> None:
    """A normal character before shebang must not trigger BOM/shebang skip."""
    content = " \n#!/usr/bin/env python3\nprint('ok')\n"  # leading space then newline
    file: Path = tmp_path / "space_before_shebang.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED


def test_read_dominance_ratio_none_when_no_terminators(tmp_path: Path) -> None:
    """No line terminators ⇒ dominance_ratio should be None."""
    file: Path = tmp_path / "single_line.py"
    file.write_text("print('solo')", encoding="utf-8")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.newline_hist == {}
    assert ctx.dominance_ratio is None


# TODO: If the CI environment supports it, add a test that simulates permission errors to
# trigger FileStatus.UNREADABLE (instead of SKIPPED_NOT_FOUND). On Windows this can be flaky,
# so we prefer the not-found path above for portability.

# --- Additional focused reader tests ---


@parametrize("line_end, expected", [("\n", "\n"), ("\r\n", "\r\n")])
def test_read_only_blank_lines(tmp_path: Path, line_end: str, expected: str) -> None:
    """Reader must resolve files that contain only blank lines with a consistent newline style."""
    content: str = f"{line_end}{line_end}{line_end}"  # three blank lines
    file: Path = tmp_path / ("only_blank_lf.py" if line_end == "\n" else "only_blank_crlf.py")
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.newline_style == expected
    assert ctx.ends_with_newline is True
    assert set(ctx.newline_hist.keys()) == {expected}


def test_read_cr_only_without_final_newline(tmp_path: Path) -> None:
    """Reader must support CR-only files even when the last line has no terminator."""
    content = "line1\rline2\rline3"  # last line has no CR
    file: Path = tmp_path / "cr_only_no_final.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.newline_style == "\r"
    assert ctx.ends_with_newline is False
    assert set(ctx.newline_hist.keys()) == {"\r"}


def test_read_mixed_newlines_diagnostic_contains_histogram(tmp_path: Path) -> None:
    """Reader diagnostics should include a histogram hint when mixed line endings are detected."""
    # 2x CRLF + 1x LF to create a clear histogram
    content = "a\r\nb\r\nc\n"
    file: Path = tmp_path / "diag_histogram_mixed.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.content == ContentStatus.SKIPPED_MIXED_LINE_ENDINGS
    # Histogram should reflect 2 CRLF and 1 LF
    assert ctx.newline_hist.get("\r\n", 0) == 2
    assert ctx.newline_hist.get("\n", 0) == 1

    # If diagnostics are available, ensure a helpful message is present
    diags: list[Diagnostic] = getattr(ctx, "diagnostics", [])
    if diags:
        text_blob: str = "\n".join(str(d) for d in diags)
        assert "Mixed line endings" in text_blob
        # Check that counts are mentioned (tolerant of exact phrasing)
        assert "LF=" in text_blob and "CRLF=" in text_blob
        # Note: CR may be zero and omitted; don't require it.


def test_read_handles_very_large_single_line_no_newline(tmp_path: Path) -> None:
    """Reader must handle very large single-line files without a newline terminator."""
    # Construct a ~200KB single line without a newline
    chunk: str = "x" * 1000
    content: str = chunk * 200  # ~200k chars
    file: Path = tmp_path / "very_large_single_line.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)

    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    ctx = run_reader(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.ends_with_newline is False
    assert ctx.newline_hist == {}
    assert ctx.dominance_ratio is None

    lines: list[str] = materialize_image_lines(ctx)

    assert isinstance(lines, list) and len(lines) == 1
    assert lines[0].endswith("\n") is False

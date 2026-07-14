# topmark:header:start
#
#   project      : TopMark
#   file         : test_sniffer.py
#   file_relpath : tests/pipeline/steps/test_sniffer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the `sniffer` pipeline step.

This suite verifies the lightweight pre-read behaviors that occur between
`ResolverStep` and `ReaderStep`:
- existence/permission checks and EMPTY_FILE detection
- fast binary sniff (NUL-byte heuristic)
- BOM and shebang ordering, with policy enforcement when BOM precedes shebang
- quick newline histogram and strict mixed-newlines refusal (policy #1)

The sniffer must *not* populate the reader-owned image; it only annotates the
context and can short-circuit with a terminal filesystem status.
"""

from __future__ import annotations

from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import run_resolver
from tests.helpers.pipeline import run_sniffer
from tests.helpers.registry import make_file_type
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import FsStatus
from topmark.pipeline.steps import sniffer as sniffer_module
from topmark.pipeline.steps.sniffer import SnifferStep
from topmark.pipeline.steps.sniffer import _count_newlines  # pyright: ignore[reportPrivateUsage]
from topmark.pipeline.steps.sniffer import _NLCounts  # pyright: ignore[reportPrivateUsage]
from topmark.pipeline.steps.sniffer import inspect_bom_shebang
from topmark.processors.base import HeaderProcessor
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path
    from typing import NoReturn

    from tests.conftest import EffectiveRegistries
    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint


def _resolved_context(
    file: Path,
    effective_registries: EffectiveRegistries,
    *,
    cfg: FrozenConfig | None = None,
) -> ProcessingContext:
    """Resolve a path against one explicit file type and processor."""
    file_type: FileType = make_file_type(
        local_key="sniffer",
        description="Sniffer test file",
        extensions=[".sniff"],
    )
    with effective_registries(
        {file_type.local_key: file_type},
        {file_type.local_key: HeaderProcessor()},
    ):
        ctx: ProcessingContext = make_pipeline_context(
            file,
            cfg or mutable_config_from_defaults().freeze(),
        )
        return run_resolver(ctx)


def _assert_terminal_hint(
    ctx: ProcessingContext,
    *,
    code: KnownCode,
    message: str,
) -> None:
    """Assert the common terminal filesystem-hint contract."""
    assert len(ctx.diagnostic_hints.items) == 1
    hint: Hint = ctx.diagnostic_hints.items[0]
    assert hint.axis == Axis.FS
    assert hint.code == code.value
    assert hint.cluster == Cluster.SKIPPED.value
    assert hint.message == message
    assert hint.terminal is True


def test_sniffer_healthy_path_records_bounded_facts_without_reader_image(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """A healthy sniff records filesystem facts but does not load the text image."""
    file: Path = tmp_path / "healthy.sniff"
    file.write_bytes(b"alpha\r\nbeta\r\n")
    ctx: ProcessingContext = _resolved_context(file, effective_registries)
    step = SnifferStep()

    ctx = step(ctx)

    assert step.primary_axis == Axis.FS
    assert step.axes_written == (Axis.FS,)
    assert ctx.status.fs == FsStatus.OK
    assert ctx.timestamp is not None
    assert ctx.timestamp.tzinfo == timezone.utc
    assert ctx.newline_hist == {"\r\n": 2}
    assert ctx.dominant_newline == "\r\n"
    assert ctx.dominance_ratio == 1.0
    assert ctx.newline_style == "\r\n"
    assert ctx.mixed_newlines is False
    assert ctx.ends_with_newline is None
    assert ctx.views.image is None
    assert ctx.halt_state is None
    assert ctx.diagnostics.items == []
    assert ctx.diagnostic_hints.items == []


def test_sniffer_gate_requires_resolved_unhalted_context(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Only a normal resolver outcome without an earlier halt enters the sniffer."""
    file: Path = tmp_path / "gated.sniff"
    file.write_text("content\n", encoding="utf-8")
    step = SnifferStep()
    unresolved: ProcessingContext = make_pipeline_context(
        file,
        mutable_config_from_defaults().freeze(),
    )
    resolved: ProcessingContext = _resolved_context(file, effective_registries)

    assert step.may_proceed(unresolved) is False
    assert step.may_proceed(resolved) is True

    resolved.request_halt(reason="earlier halt", at_step=step)
    assert step.may_proceed(resolved) is False


def test_count_newlines_preserves_crlf_pairing_across_chunks() -> None:
    """A carried CR pairs once with a leading LF and leaves later styles distinct."""
    first, carry_cr = _count_newlines(b"alpha\r", carry_cr=False)
    second, carry_cr = _count_newlines(b"\nbeta\rgamma\n", carry_cr=carry_cr)

    assert first == _NLCounts()
    assert second == _NLCounts(lf=1, crlf=1, cr=1)
    assert carry_cr is False


@pytest.mark.parametrize(
    ("follow_up", "expected"),
    [
        (b"", _NLCounts(cr=1)),
        (b"content", _NLCounts(cr=1)),
    ],
)
def test_count_newlines_commits_unpaired_carried_cr(
    follow_up: bytes,
    expected: _NLCounts,
) -> None:
    """A carried CR becomes one standalone terminator when no LF follows."""
    counts, carry_cr = _count_newlines(follow_up, carry_cr=True)

    assert counts == expected
    assert carry_cr is False


def test_sniffer_commits_trailing_cr_at_end_of_stream(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """A physical CR at the end of the inspected stream is counted exactly once."""
    file: Path = tmp_path / "trailing-cr.sniff"
    file.write_bytes(b"alpha\r")
    ctx: ProcessingContext = run_sniffer(_resolved_context(file, effective_registries))

    assert ctx.status.fs == FsStatus.OK
    assert ctx.newline_hist == {"\r": 1}
    assert ctx.dominant_newline == "\r"
    assert ctx.dominance_ratio == 1.0
    assert ctx.newline_style == "\r"
    assert ctx.mixed_newlines is False


def test_sniffer_detects_incomplete_utf8_at_end_of_file(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Flushing the bounded decoder rejects an incomplete final UTF-8 sequence."""
    file: Path = tmp_path / "incomplete.sniff"
    file.write_bytes(b"valid text\n\xe2\x82")
    ctx: ProcessingContext = run_sniffer(_resolved_context(file, effective_registries))

    assert ctx.status.fs == FsStatus.UNICODE_DECODE_ERROR
    assert ctx.newline_hist == {}
    assert ctx.mixed_newlines is None
    assert ctx.views.image is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "SnifferStep"
    assert ctx.halt_state.reason_code == FsStatus.UNICODE_DECODE_ERROR.value
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (
            DiagnosticLevel.ERROR,
            "Invalid UTF-8 sequence at end-of-file; treating as non-text file.",
        )
    ]
    _assert_terminal_hint(
        ctx,
        code=KnownCode.CONTENT_ENCODING_ERROR,
        message="Unicode decode error",
    )


def test_sniffer_apply_mode_rejects_unwritable_path_at_access_boundary(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apply mode maps a deterministic failed write check to a terminal FS outcome."""
    file: Path = tmp_path / "unwritable.sniff"
    file.write_text("content\n", encoding="utf-8")
    ctx: ProcessingContext = _resolved_context(file, effective_registries)
    ctx.run_options = RunOptions(pipeline_kind="check", apply_changes=True)

    def _deny_access(path: Path, mode: int) -> bool:
        del path, mode
        return False

    monkeypatch.setattr(sniffer_module.os, "access", _deny_access)
    ctx = run_sniffer(ctx)

    assert ctx.status.fs == FsStatus.NO_WRITE_PERMISSION
    assert ctx.timestamp is not None
    assert ctx.views.image is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "SnifferStep"
    assert ctx.halt_state.reason_code == "Permission denied: cannot write to file"
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.ERROR, "Permission denied: cannot write to file")
    ]
    _assert_terminal_hint(
        ctx,
        code=KnownCode.FS_UNWRITABLE,
        message="no write permission",
    )


def test_sniffer_allowed_empty_file_records_info_and_policy_hint(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """An allowed zero-byte file remains a reader/policy handoff, not a halt."""
    file: Path = tmp_path / "empty.sniff"
    file.touch()
    mutable_cfg: MutableConfig = mutable_config_from_defaults()
    mutable_cfg.policy.allow_header_in_empty_files = True
    ctx: ProcessingContext = run_sniffer(
        _resolved_context(file, effective_registries, cfg=mutable_cfg.freeze())
    )

    assert ctx.status.fs == FsStatus.EMPTY
    assert ctx.timestamp is not None
    assert ctx.views.image is None
    assert ctx.halt_state is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, "File is empty.")
    ]
    assert len(ctx.diagnostic_hints.items) == 1
    hint = ctx.diagnostic_hints.items[0]
    assert hint.axis == Axis.FS
    assert hint.code == KnownCode.CONTENT_EMPTY_FILE.value
    assert hint.cluster == Cluster.BLOCKED_POLICY.value
    assert hint.message == "empty file"
    assert hint.terminal is False


def test_sniffer_maps_initial_stat_permission_failure(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An initial stat denial is a terminal unreadable filesystem outcome."""
    file: Path = tmp_path / "denied.sniff"
    file.write_text("content\n", encoding="utf-8")
    ctx: ProcessingContext = _resolved_context(file, effective_registries)

    def _deny_stat(path: Path, *, follow_symlinks: bool = True) -> NoReturn:
        del path, follow_symlinks
        raise PermissionError("denied by test boundary")

    monkeypatch.setattr(type(file), "stat", _deny_stat)
    ctx = run_sniffer(ctx)

    assert ctx.status.fs == FsStatus.NO_READ_PERMISSION
    assert ctx.timestamp is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "SnifferStep"
    assert "denied by test boundary" in ctx.halt_state.reason_code
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level == DiagnosticLevel.ERROR
    assert "Permission denied:" in ctx.diagnostics.items[0].message
    _assert_terminal_hint(
        ctx,
        code=KnownCode.FS_UNREADABLE,
        message="permission denied",
    )


@pytest.mark.parametrize(
    ("error", "expected_status", "hint_code", "hint_message", "reason_fragment"),
    [
        (
            FileNotFoundError(),
            FsStatus.NOT_FOUND,
            KnownCode.FS_NOT_FOUND,
            "file not found",
            "File not found:",
        ),
        (
            PermissionError("read denied at test boundary"),
            FsStatus.NO_READ_PERMISSION,
            KnownCode.FS_UNREADABLE,
            "permission denied",
            "Permission denied: read denied at test boundary",
        ),
        (
            OSError("read failed at test boundary"),
            FsStatus.UNREADABLE,
            KnownCode.FS_UNREADABLE,
            "read error",
            "Error while sniffing: read failed at test boundary",
        ),
    ],
)
def test_sniffer_maps_failures_after_successful_stat(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
    monkeypatch: pytest.MonkeyPatch,
    error: OSError,
    expected_status: FsStatus,
    hint_code: KnownCode,
    hint_message: str,
    reason_fragment: str,
) -> None:
    """A stat/open race and representative read failure preserve coherent FS state."""
    file: Path = tmp_path / "race.sniff"
    file.write_text("content\n", encoding="utf-8")
    ctx: ProcessingContext = _resolved_context(file, effective_registries)

    def _fail_after_stat(context: ProcessingContext) -> FsStatus | None:
        del context
        raise error

    monkeypatch.setattr(sniffer_module, "_sniff_stream", _fail_after_stat)
    ctx = run_sniffer(ctx)

    assert ctx.status.fs == expected_status
    assert ctx.timestamp is not None
    assert ctx.views.image is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "SnifferStep"
    assert reason_fragment in ctx.halt_state.reason_code
    assert len(ctx.diagnostics.items) == 1
    assert ctx.diagnostics.items[0].level == DiagnosticLevel.ERROR
    assert reason_fragment in ctx.diagnostics.items[0].message
    _assert_terminal_hint(ctx, code=hint_code, message=hint_message)


def test_sniff_skips_on_nul_byte_non_text(tmp_path: Path) -> None:
    """Sniffer must set SKIPPED_NOT_TEXT_FILE when a NUL byte is present."""
    # Include a NUL byte to trigger non-text detection.
    content: str = 'print("Hi There\0")'
    file: Path = tmp_path / "x.py"
    # Use newline="" so Python preserves the exact line endings we provide.
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # First resolve the file type
    ctx = run_resolver(ctx)

    # The resolver must identify a processor; otherwise the reader step would be ill-defined.
    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.BINARY
    assert ctx.views.image is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "SnifferStep"
    assert ctx.halt_state.reason_code == FsStatus.BINARY.value
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.ERROR, "NUL byte detected; treating this as a binary file.")
    ]
    _assert_terminal_hint(
        ctx,
        code=KnownCode.CONTENT_NOT_SUPPORTED,
        message="binary file",
    )


def test_sniff_skips_when_bom_precedes_shebang(tmp_path: Path) -> None:
    """Sniffer must skip when a UTF-8 BOM appears before a shebang."""
    content: str = "\ufeff#!/usr/bin/env python3\nprint('hello')\n"
    file: Path = tmp_path / "bom_shebang.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG


def test_sniff_marks_empty_file(tmp_path: Path) -> None:
    """Sniffer must mark truly empty files as EMPTY_FILE and avoid further processing."""
    file: Path = tmp_path / "empty.py"
    # Create an empty file
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write("")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.EMPTY


def test_sniff_marks_not_found_when_disappears(tmp_path: Path) -> None:
    """Sniffer should mark SKIPPED_NOT_FOUND when the file disappears before read()."""
    file: Path = tmp_path / "vanishing.py"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write("print('hi')\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    # Simulate a race: remove the file before reader executes
    file.unlink()
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.NOT_FOUND


def test_sniff_skips_on_invalid_utf8(tmp_path: Path) -> None:
    """Sniffer must mark non-text when decoding fails (invalid UTF-8)."""
    file: Path = tmp_path / "bad_utf8.py"
    bad = b"print('x')\n" + b"\xc3\x28"  # invalid 2-byte sequence
    with file.open("wb") as fh:
        fh.write(bad)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.UNICODE_DECODE_ERROR


def test_sniff_strict_mixed_newlines(tmp_path: Path) -> None:
    """Sniffer must report mixed line endings."""
    file: Path = tmp_path / "bad_utf8.py"
    mixed = "# A test file\r\n# with mixed\r# line endings\r\nprint('x')\n"  # mixed line endings
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(mixed)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None
    ctx = run_sniffer(ctx)
    assert ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS


# --- Exotic Unicode separator tests ---


@pytest.mark.parametrize(
    "separator, label",
    [
        ("\x85", "nel"),
        ("\u2028", "line_separator"),
        ("\u2029", "paragraph_separator"),
    ],
)
def test_sniff_treats_exotic_separators_as_content_not_newlines(
    tmp_path: Path, separator: str, label: str
) -> None:
    """Sniffer must not recognize NEL/LS/PS as physical newline styles."""
    file: Path = tmp_path / f"exotic_separator_{label}.py"
    content: str = f"alpha{separator}beta{separator}gamma"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)

    assert ctx.status.fs == FsStatus.OK
    assert ctx.newline_style == "\n"
    assert ctx.newline_hist == {}
    assert ctx.dominant_newline is None
    assert ctx.dominance_ratio is None
    assert ctx.mixed_newlines is False
    assert ctx.ends_with_newline is None


def test_sniff_does_not_count_exotic_separators_as_mixed_newlines(tmp_path: Path) -> None:
    """NEL/LS/PS near LF text must not create a mixed-newline skip."""
    file: Path = tmp_path / "lf_with_exotic_separators.py"
    content: str = "alpha\u2028beta\ncharlie\x85delta\necho\u2029foxtrot\n"
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    assert ctx.file_type is not None

    ctx = run_sniffer(ctx)

    assert ctx.status.fs == FsStatus.OK
    assert ctx.newline_style == "\n"
    assert ctx.newline_hist == {"\n": 3}
    assert ctx.dominant_newline == "\n"
    assert ctx.dominance_ratio == 1.0
    assert ctx.mixed_newlines is False
    assert ctx.ends_with_newline is None


# --- Unit test for _inspect_bom_shebang ---
@pytest.mark.parametrize(
    "payload, expected",
    [
        # Shebang at byte 0, no BOM
        (b"#!/usr/bin/env python\n", (False, True, False)),
        # UTF-8 BOM followed by shebang at offset 3
        (b"\xef\xbb\xbf#!/usr/bin/env python\n", (True, True, True)),
        # BOM present but no shebang
        (b"\xef\xbb\xbfprint('x')\n", (True, False, False)),
        # Shebang not at byte 0 or directly after BOM → not treated as shebang
        (b"  #!/usr/bin/env python\n", (False, False, False)),
    ],
)
def test_inspect_bom_shebang_variants(
    payload: bytes,
    expected: tuple[bool, bool, bool],
) -> None:
    """_inspect_bom_shebang should classify BOM and shebang ordering correctly.

    This focuses on the low-level bytes → flags behavior, independent of any
    `ProcessingContext` mutation or policy decisions in `SnifferStep`.
    """
    assert inspect_bom_shebang(payload) == expected

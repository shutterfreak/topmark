# topmark:header:start
#
#   project      : TopMark
#   file         : test_scanner.py
#   file_relpath : tests/pipeline/steps/test_scanner.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Direct contracts for the scanner pipeline step."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.registry import make_file_type
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps import scanner as scanner_module
from topmark.pipeline.steps.scanner import ScannerStep
from topmark.pipeline.views import ListFileImageView
from topmark.processors.base import HeaderProcessor
from topmark.processors.types import BoundsKind
from topmark.processors.types import HeaderBounds
from topmark.processors.types import HeaderParseResult

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint
    from topmark.pipeline.views import HeaderView
    from topmark.processors.base import ProcessingContextLike


class _ScannerProcessor(HeaderProcessor):
    """Deterministic processor double for scanner-owned result mapping."""

    namespace = "test"
    local_key = "scanner"

    def __init__(self, *, bounds: HeaderBounds, parse_result: HeaderParseResult) -> None:
        super().__init__()
        self.bounds: HeaderBounds = bounds
        self.parse_result: HeaderParseResult = parse_result
        self.bounds_lines: list[str] | None = None
        self.bounds_newline_style: str | None = None
        self.view_seen_during_parse: HeaderView | None = None

    def get_header_bounds(
        self,
        *,
        lines: Iterable[str],
        newline_style: str,
    ) -> HeaderBounds:
        """Return configured bounds while recording the reader-image handoff."""
        self.bounds_lines = list(lines)
        self.bounds_newline_style = newline_style
        return self.bounds

    def parse_fields(self, context: ProcessingContextLike) -> HeaderParseResult:
        """Return configured fields while recording that the view already exists."""
        self.view_seen_during_parse = context.views.header
        return self.parse_result


def _scanner_context(
    path: Path,
    config: FrozenConfig,
    *,
    processor: _ScannerProcessor,
    lines: list[str],
    fs_status: FsStatus = FsStatus.OK,
    newline_style: str = "\n",
) -> ProcessingContext:
    """Create a coherent resolved, post-reader context for direct scanner tests."""
    ctx: ProcessingContext = make_pipeline_context(path, config)
    file_type: FileType = make_file_type(
        local_key="scanner",
        description="Scanner contract fixture",
        extensions=[".scan"],
    )
    processor.file_type = file_type
    ctx.file_type = file_type
    ctx.header_processor = processor
    ctx.views.image = ListFileImageView(lines)
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.fs = fs_status
    ctx.status.content = ContentStatus.OK
    ctx.newline_style = newline_style
    ctx.ends_with_newline = bool(lines and lines[-1].endswith(("\n", "\r")))
    return ctx


def _only_hint(ctx: ProcessingContext) -> Hint:
    """Return the context's sole hint."""
    assert len(ctx.diagnostic_hints.items) == 1
    return ctx.diagnostic_hints.items[0]


def _policy_refuses(ctx: ProcessingContext) -> bool:
    """Return a deterministic scanner-stage policy refusal."""
    _: ProcessingContext = ctx
    return False


def test_missing_header_maps_none_without_creating_a_view(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """BoundsKind.NONE maps to a non-terminal missing-header outcome."""
    lines: list[str] = ["preamble\n", "body\n"]
    processor = _ScannerProcessor(
        bounds=HeaderBounds(kind=BoundsKind.NONE),
        parse_result=HeaderParseResult(),
    )
    ctx: ProcessingContext = _scanner_context(
        tmp_path / "missing.scan",
        default_frozen_config,
        processor=processor,
        lines=lines,
    )

    ScannerStep()(ctx)

    assert processor.bounds_lines == lines
    assert processor.bounds_newline_style == "\n"
    assert processor.view_seen_during_parse is None
    assert ctx.status.header == HeaderStatus.MISSING
    assert ctx.views.header is None
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    hint: Hint = _only_hint(ctx)
    assert (hint.axis, hint.code, hint.cluster, hint.message, hint.terminal) == (
        Axis.HEADER,
        KnownCode.HEADER_MISSING.value,
        Cluster.PENDING.value,
        "no TopMark header detected",
        False,
    )


@pytest.mark.parametrize(
    ("parse_result", "expected_status", "warning_fragment", "hint_message"),
    [
        (
            HeaderParseResult(fields={"project": "TopMark"}, success_count=1),
            HeaderStatus.DETECTED,
            None,
            "TopMark header detected",
        ),
        (
            HeaderParseResult(),
            HeaderStatus.EMPTY,
            "but no fields",
            "empty TopMark header",
        ),
        (
            HeaderParseResult(error_count=2),
            HeaderStatus.MALFORMED_ALL_FIELDS,
            "contains no valid header lines",
            "all header fields malformed",
        ),
        (
            HeaderParseResult(fields={"project": "TopMark"}, success_count=1, error_count=1),
            HeaderStatus.MALFORMED_SOME_FIELDS,
            "contains valid and invalid header lines",
            "some header fields malformed",
        ),
    ],
)
def test_span_builds_exact_view_and_maps_parse_result(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    parse_result: HeaderParseResult,
    expected_status: HeaderStatus,
    warning_fragment: str | None,
    hint_message: str,
) -> None:
    """A valid span preserves the image slice and maps processor parse counts."""
    lines: list[str] = ["preamble\r\n", "<start>\r\n", "field\r\n", "<end>\r\n", "body"]
    processor = _ScannerProcessor(
        bounds=HeaderBounds(kind=BoundsKind.SPAN, start=1, end=4),
        parse_result=parse_result,
    )
    ctx: ProcessingContext = _scanner_context(
        tmp_path / "span.scan",
        default_frozen_config,
        processor=processor,
        lines=lines,
        newline_style="\r\n",
    )

    ScannerStep()(ctx)

    header: HeaderView | None = ctx.views.header
    assert header is not None
    assert processor.view_seen_during_parse is header
    assert header.range == (1, 3)
    assert header.lines == lines[1:4]
    assert header.block == "".join(lines[1:4])
    assert header.mapping == parse_result.fields
    assert header.success_count == parse_result.success_count
    assert header.error_count == parse_result.error_count
    assert ctx.status.header == expected_status
    assert ctx.halt_state is None
    if warning_fragment is None:
        assert ctx.diagnostics.items == []
    else:
        assert len(ctx.diagnostics.items) == 1
        assert ctx.diagnostics.items[0].level == DiagnosticLevel.WARNING
        assert warning_fragment in ctx.diagnostics.items[0].message
    hint: Hint = _only_hint(ctx)
    assert hint.message == hint_message
    assert hint.terminal is False


@pytest.mark.parametrize(
    ("bounds", "expected_range", "expected_lines", "expected_reason"),
    [
        (
            HeaderBounds(
                kind=BoundsKind.MALFORMED,
                start=1,
                end=3,
                reason="duplicate header markers",
            ),
            (1, 2),
            ["<start>\n", "<start>\n"],
            "duplicate header markers",
        ),
        (
            HeaderBounds(kind=BoundsKind.MALFORMED),
            None,
            None,
            "Malformed header markers",
        ),
    ],
)
def test_structural_malformation_halts_with_only_a_usable_best_effort_view(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    bounds: HeaderBounds,
    expected_range: tuple[int, int] | None,
    expected_lines: list[str] | None,
    expected_reason: str,
) -> None:
    """Malformed bounds halt and materialize a view only for a usable span."""
    lines: list[str] = ["preamble\n", "<start>\n", "<start>\n", "body\n"]
    processor = _ScannerProcessor(bounds=bounds, parse_result=HeaderParseResult())
    ctx: ProcessingContext = _scanner_context(
        tmp_path / "malformed.scan",
        default_frozen_config,
        processor=processor,
        lines=lines,
    )

    ScannerStep()(ctx)

    assert processor.view_seen_during_parse is None
    assert ctx.status.header == HeaderStatus.MALFORMED
    if expected_range is None:
        assert ctx.views.header is None
    else:
        header: HeaderView | None = ctx.views.header
        assert header is not None
        assert header.range == expected_range
        assert header.lines == expected_lines
        assert header.block == "".join(expected_lines or [])
        assert header.mapping is None
        assert header.success_count == 0
        assert header.error_count == 0
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.WARNING, expected_reason)
    ]
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "ScannerStep"
    assert ctx.halt_state.reason_code == f"scanner: {expected_reason}"
    assert [
        (hint.code, hint.cluster, hint.message, hint.terminal)
        for hint in ctx.diagnostic_hints.items
    ] == [
        (
            KnownCode.HEADER_MALFORMED.value,
            Cluster.ERROR.value,
            expected_reason,
            True,
        ),
        (
            KnownCode.HEADER_MALFORMED.value,
            Cluster.SKIPPED.value,
            "malformed TopMark header",
            True,
        ),
    ]


def test_true_empty_reader_image_maps_to_missing_without_calling_processor(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """A reader-reconciled zero-byte image is a normal missing-header outcome."""
    processor = _ScannerProcessor(
        bounds=HeaderBounds(kind=BoundsKind.SPAN, start=0, end=1),
        parse_result=HeaderParseResult(fields={"unexpected": "field"}, success_count=1),
    )
    ctx: ProcessingContext = _scanner_context(
        tmp_path / "empty.scan",
        default_frozen_config,
        processor=processor,
        lines=[],
        fs_status=FsStatus.EMPTY,
    )

    ScannerStep()(ctx)

    assert processor.bounds_lines is None
    assert processor.view_seen_during_parse is None
    assert ctx.status.header == HeaderStatus.MISSING
    assert ctx.views.header is None
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    assert _only_hint(ctx).code == KnownCode.HEADER_MISSING.value


def test_missing_header_hands_policy_refusal_to_scanner_halt(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scanner owns the halt when scanner-stage policy refuses an outcome."""
    processor = _ScannerProcessor(
        bounds=HeaderBounds(kind=BoundsKind.NONE),
        parse_result=HeaderParseResult(),
    )
    ctx: ProcessingContext = _scanner_context(
        tmp_path / "blocked.scan",
        default_frozen_config,
        processor=processor,
        lines=["body\n"],
    )
    monkeypatch.setattr(scanner_module, "check_permitted_by_policy", _policy_refuses)

    ScannerStep()(ctx)

    assert ctx.status.header == HeaderStatus.MISSING
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "ScannerStep"
    assert ctx.halt_state.reason_code == "stopped by policy"
    assert _only_hint(ctx).terminal is False

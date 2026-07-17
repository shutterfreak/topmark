# topmark:header:start
#
#   project      : TopMark
#   file         : test_base_contracts.py
#   file_relpath : tests/processors/test_base_contracts.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Focused contracts for the processor base class."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.filetypes.policy import FileTypeHeaderPolicy
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import Views
from topmark.processors.base import NO_LINE_ANCHOR
from topmark.processors.base import HeaderProcessor
from topmark.processors.types import BoundsKind
from topmark.processors.types import StripDiagKind

if TYPE_CHECKING:
    from topmark.processors.types import HeaderBounds
    from topmark.processors.types import HeaderParseResult
    from topmark.processors.types import StripHeaderResult


class ExampleHeaderProcessor(HeaderProcessor):
    """Processor with visible affixes for base-contract tests."""

    namespace = "pytest"
    local_key = "example"
    description = "Example processor"
    block_prefix = "<block>"
    block_suffix = "</block>"
    line_prefix = "//"
    line_suffix = "!"
    line_indent = "  "
    header_indent = ""


class _CharOffsetProcessor(ExampleHeaderProcessor):
    local_key = "char-offset"

    def get_header_insertion_index(
        self,
        file_lines: list[str],
    ) -> int:
        return NO_LINE_ANCHOR

    def get_header_insertion_char_offset(
        self,
        original_text: str,
    ) -> int | None:
        return len("preamble\n")


class _MissingCharOffsetProcessor(_CharOffsetProcessor):
    local_key = "missing-char-offset"

    def get_header_insertion_char_offset(
        self,
        original_text: str,
    ) -> int | None:
        return None


@dataclass
class _Context:
    views: Views
    diagnostics: MutableDiagnosticLog


@dataclass(frozen=True)
class _Config:
    header_fields: tuple[str, ...]
    align_fields: bool


def _context(
    *,
    lines: list[str] | None,
    header_range: tuple[int, int] | None = (0, 0),
) -> _Context:
    header = HeaderView(
        range=header_range,
        lines=lines,
        block=None if lines is None else "".join(lines),
        mapping=None,
    )
    return _Context(views=Views(header=header), diagnostics=MutableDiagnosticLog())


def test_processor_identity_and_constructor_overrides_are_instance_owned() -> None:
    """Construction preserves class metadata while keeping instances unbound."""
    default = ExampleHeaderProcessor()
    overridden = ExampleHeaderProcessor(
        block_prefix="BEGIN",
        block_suffix="END",
        line_prefix="#",
        line_suffix="",
        line_indent=" ",
        header_indent="    ",
    )

    assert default.qualified_key == "pytest:example"
    assert default.file_type is None
    assert overridden.file_type is None
    assert (overridden.block_prefix, overridden.block_suffix) == ("BEGIN", "END")
    assert (overridden.line_prefix, overridden.line_suffix) == ("#", "")
    assert (overridden.line_indent, overridden.header_indent) == (" ", "    ")
    assert ExampleHeaderProcessor.block_prefix == "<block>"
    assert ExampleHeaderProcessor.line_prefix == "//"
    assert default.block_prefix == "<block>"
    assert default.line_prefix == "//"


def test_external_subclass_cannot_claim_reserved_topmark_namespace() -> None:
    """The built-in namespace remains restricted to TopMark processor modules."""
    with pytest.raises(TypeError, match="reserved"):

        class _ExternalBuiltin(HeaderProcessor):  # pyright: ignore[reportUnusedClass]
            namespace = "topmark"
            local_key = "external"


@pytest.mark.parametrize(
    ("header_range", "lines"),
    [
        (None, [f"// {TOPMARK_START_MARKER} !\n"]),
        ((0, 0), None),
        ((0, 0), []),
    ],
)
def test_parse_fields_missing_or_empty_views_are_stable_empty_results(
    header_range: tuple[int, int] | None,
    lines: list[str] | None,
) -> None:
    """Missing view components and empty slices parse without diagnostics."""
    processor = ExampleHeaderProcessor()
    context: _Context = _context(lines=lines, header_range=header_range)

    result: HeaderParseResult = processor.parse_fields(context)

    assert result.fields == {}
    assert result.success_count == result.error_count == 0
    assert context.diagnostics.items == []


def test_parse_fields_adjacent_markers_are_a_valid_empty_payload() -> None:
    """An empty marker-delimited payload parses successfully without fields."""
    lines: list[str] = [
        f"// {TOPMARK_START_MARKER} !\n",
        f"// {TOPMARK_END_MARKER} !\n",
    ]
    context: _Context = _context(
        lines=lines,
        header_range=(0, 1),
    )

    result: HeaderParseResult = ExampleHeaderProcessor().parse_fields(context)

    assert result.fields == {}
    assert result.success_count == result.error_count == 0
    assert context.diagnostics.items == []


@pytest.mark.parametrize(
    "lines",
    [
        [f"// {TOPMARK_START_MARKER} !\n"],
        [f"// {TOPMARK_END_MARKER} !\n"],
        [f"// {TOPMARK_END_MARKER} !\n", f"// {TOPMARK_START_MARKER} !\n"],
    ],
)
def test_parse_fields_invalid_inner_marker_pairs_report_one_stable_error(
    lines: list[str],
) -> None:
    """Invalid marker pairs return no fields and one ordered diagnostic."""
    processor = ExampleHeaderProcessor()
    context: _Context = _context(
        lines=lines,
        header_range=(4, 4 + len(lines) - 1),
    )

    result: HeaderParseResult = processor.parse_fields(context)

    assert result.fields == {}
    assert result.success_count == result.error_count == 0
    assert [item.message for item in context.diagnostics.items] == [
        "parse_fields(): could not locate a valid START/END marker pair."
    ]


def test_parse_fields_normalizes_affixes_and_preserves_field_semantics() -> None:
    """Parsing ignores blanks, splits once, and reports malformed lines in order."""
    processor = ExampleHeaderProcessor()
    lines: list[str] = [
        f"  // {TOPMARK_START_MARKER} !\r\n",
        "  // alpha: one:two !\r\n",
        "// !\r\n",
        "// empty: !\r\n",
        "// missing-colon !\r\n",
        "// : missing-name !\r\n",
        f"// {TOPMARK_END_MARKER} !\r\n",
    ]
    context: _Context = _context(
        lines=lines,
        header_range=(9, 15),
    )

    result: HeaderParseResult = processor.parse_fields(context)

    assert result.fields == {
        "alpha": "one:two",
        "empty": "",
    }
    assert result.success_count == 2
    assert result.error_count == 2
    assert [item.message for item in context.diagnostics.items] == [
        "Malformed header at line 14 (no colon found): '// missing-colon !\\r\\n'",
        "Malformed header at line 15 (empty text before colon): '// : missing-name !\\r\\n'",
    ]


@pytest.mark.parametrize("align_fields", [False, True])
def test_render_header_lines_is_ordered_round_trippable_and_non_mutating(
    align_fields: bool,
) -> None:
    """Rendering respects field order, indentation roles, affixes, and CRLF."""
    processor = ExampleHeaderProcessor()
    values: dict[str, str] = {
        "longer": "two",
        "a": "one",
        "unused": "keep",
    }
    original: dict[str, str] = dict(values)
    config = _Config(
        header_fields=("a", "longer"),
        align_fields=align_fields,
    )

    rendered: list[str] = processor.render_header_lines(
        header_values=values,
        config=config,
        newline_style="\r\n",
        header_indent_override="    ",
        line_indent_override=" ",
    )

    assert values == original
    assert all(line.endswith("\r\n") for line in rendered)
    assert rendered[0] == "    <block>\r\n"
    assert rendered[-1] == "</block>\r\n"
    assert rendered.index(next(line for line in rendered if "one" in line)) < rendered.index(
        next(line for line in rendered if "two" in line)
    )
    parsed_context: _Context = _context(
        lines=rendered,
        header_range=(0, len(rendered) - 1),
    )
    parsed: HeaderParseResult = processor.parse_fields(parsed_context)
    assert parsed.fields == {
        "a": "one",
        "longer": "two",
    }
    assert parsed.success_count == 2
    assert parsed.error_count == 0


@pytest.mark.parametrize(
    ("lines", "kind", "start", "end", "reason"),
    [
        ([], BoundsKind.NONE, None, None, None),
        (["body\n"], BoundsKind.NONE, None, None, None),
        (
            [f"// {TOPMARK_END_MARKER} !\n"],
            BoundsKind.MALFORMED,
            None,
            1,
            "end marker without preceding start",
        ),
        (
            [f"// {TOPMARK_START_MARKER} !\n"],
            BoundsKind.MALFORMED,
            0,
            None,
            "start marker without matching end",
        ),
        (
            [f"// {TOPMARK_END_MARKER} !\n", f"// {TOPMARK_START_MARKER} !\n"],
            BoundsKind.MALFORMED,
            0,
            2,
            "end marker before start marker",
        ),
        (
            [f"// {TOPMARK_START_MARKER} {TOPMARK_END_MARKER} !\n"],
            BoundsKind.MALFORMED,
            0,
            1,
            "start and end marker on the same line",
        ),
    ],
)
def test_header_bounds_classify_absent_and_malformed_markers(
    lines: list[str],
    kind: BoundsKind,
    start: int | None,
    end: int | None,
    reason: str | None,
) -> None:
    """Bounds use exclusive ends and stable malformed classifications."""
    bounds: HeaderBounds = ExampleHeaderProcessor().get_header_bounds(
        lines=iter(lines),
        newline_style="\n",
    )

    assert (bounds.kind, bounds.start, bounds.end, bounds.reason) == (kind, start, end, reason)


def test_header_bounds_reject_valid_markers_outside_location_window() -> None:
    """A complete header far from its insertion anchor is not selected."""
    lines: list[str] = ["body\n"] * 4 + [
        "<block>\n",
        f"// {TOPMARK_START_MARKER} !\n",
        f"// {TOPMARK_END_MARKER} !\n",
        "</block>\n",
    ]

    bounds: HeaderBounds = ExampleHeaderProcessor().get_header_bounds(
        lines=lines,
        newline_style="\n",
    )

    assert bounds.kind is BoundsKind.NONE


@pytest.mark.parametrize(
    ("lines", "start", "end", "reason"),
    [
        (
            [
                f"// {TOPMARK_START_MARKER} !\n",
                f"// {TOPMARK_END_MARKER} !\n",
                "body\n",
                f"// {TOPMARK_START_MARKER} !\n",
            ],
            3,
            None,
            "start marker without matching end",
        ),
        (
            [
                f"// {TOPMARK_START_MARKER} !\n",
                f"// {TOPMARK_END_MARKER} !\n",
                f"// {TOPMARK_END_MARKER} !\n",
            ],
            None,
            3,
            "end marker without preceding start",
        ),
        (
            [
                f"// {TOPMARK_START_MARKER} !\n",
                f"// {TOPMARK_START_MARKER} !\n",
                f"// {TOPMARK_END_MARKER} !\n",
            ],
            0,
            2,
            "start marker before previous header ended",
        ),
    ],
)
def test_header_bounds_classify_mixed_complete_and_dangling_marker_shapes(
    lines: list[str],
    start: int | None,
    end: int | None,
    reason: str,
) -> None:
    """A valid first pair does not hide later dangling or nested markers."""
    bounds: HeaderBounds = ExampleHeaderProcessor().get_header_bounds(
        lines=lines,
        newline_style="\n",
    )

    assert (bounds.kind, bounds.start, bounds.end, bounds.reason) == (
        BoundsKind.MALFORMED,
        start,
        end,
        reason,
    )


def test_header_bounds_select_first_of_multiple_complete_headers_deterministically() -> None:
    """Separate complete headers remain valid and the first one wins."""
    lines: list[str] = [
        f"// {TOPMARK_START_MARKER} !\n",
        f"// {TOPMARK_END_MARKER} !\n",
        f"// {TOPMARK_START_MARKER} !\n",
        f"// {TOPMARK_END_MARKER} !\n",
    ]

    bounds: HeaderBounds = ExampleHeaderProcessor().get_header_bounds(
        lines=iter(lines),
        newline_style="\n",
    )

    assert (bounds.kind, bounds.start, bounds.end) == (BoundsKind.SPAN, 0, 2)


@pytest.mark.parametrize(
    ("processor", "lines", "expected"),
    [
        (
            _CharOffsetProcessor(),
            [
                "preamble\n",
                "<block>\n",
                f"// {TOPMARK_START_MARKER} !\n",
                f"// {TOPMARK_END_MARKER} !\n",
                "</block>\n",
            ],
            (1, 5),
        ),
        (
            _MissingCharOffsetProcessor(),
            [
                "<block>\n",
                f"// {TOPMARK_START_MARKER} !\n",
                f"// {TOPMARK_END_MARKER} !\n",
                "</block>\n",
            ],
            (0, 4),
        ),
    ],
)
def test_header_bounds_honor_character_offset_plugin_seam(
    processor: HeaderProcessor,
    lines: list[str],
    expected: tuple[int, int],
) -> None:
    """NO_LINE_ANCHOR delegates to character offsets and safely defaults when absent."""
    bounds: HeaderBounds = processor.get_header_bounds(
        lines=lines,
        newline_style="\n",
    )

    assert (bounds.kind, bounds.start, bounds.end) == (BoundsKind.SPAN, *expected)


def test_line_has_directive_requires_the_complete_configured_suffix() -> None:
    """Marker text alone does not bypass a configured line suffix."""
    processor = ExampleHeaderProcessor()

    assert processor.line_has_directive(
        f"// {TOPMARK_START_MARKER} !\n",
        TOPMARK_START_MARKER,
    )
    assert not processor.line_has_directive(
        f"// {TOPMARK_START_MARKER}\n",
        TOPMARK_START_MARKER,
    )


def test_strip_refuses_malformed_markers_without_mutating_input() -> None:
    """Auto-detected malformed headers are conservatively refused."""
    processor = ExampleHeaderProcessor()
    lines: list[str] = [f"// {TOPMARK_START_MARKER} !\n", "body\n"]
    original: list[str] = list(lines)

    result: StripHeaderResult = processor.strip_header_block(lines=lines)

    assert result.lines is lines
    assert lines == original
    assert result.removed_span is None
    assert result.diagnostic.kind is StripDiagKind.MALFORMED_REFUSED
    assert result.diagnostic.reason == "start marker without matching end"


def test_strip_permissively_removes_a_complete_legacy_substring_pair() -> None:
    """The documented fallback removes old marker wrappers outside the scan window."""
    processor = ExampleHeaderProcessor()
    lines: list[str] = [
        "body\n",
        "body\n",
        "body\n",
        "body\n",
        f"legacy wrapper {TOPMARK_START_MARKER}\n",
        "legacy payload\n",
        f"legacy wrapper {TOPMARK_END_MARKER}\n",
        "tail\n",
    ]
    original: list[str] = list(lines)

    result: StripHeaderResult = processor.strip_header_block(lines=lines)

    assert lines == original
    assert result.lines == [*lines[:4], "tail\n"]
    assert result.removed_span == (4, 6)
    assert result.diagnostic.kind is StripDiagKind.REMOVED


@pytest.mark.parametrize(
    "span",
    [
        pytest.param((-1, 0), id="negative"),
        pytest.param((1, 0), id="reversed"),
        pytest.param((0, 2), id="out-of-range"),
    ],
)
def test_strip_rejects_invalid_explicit_spans_without_mutation(
    span: tuple[int, int],
) -> None:
    """Negative, reversed, and out-of-range inclusive spans are no-ops."""
    processor = ExampleHeaderProcessor()
    lines: list[str] = ["body\n", "tail"]
    original: list[str] = list(lines)

    result: StripHeaderResult = processor.strip_header_block(
        lines=lines,
        span=span,
    )

    assert result.lines is lines
    assert lines == original
    assert result.removed_span is None
    assert result.diagnostic.kind is StripDiagKind.NOT_FOUND


def test_invalid_encoding_regex_falls_back_to_shebang_anchor() -> None:
    """A bad plugin policy regex does not block safe insertion after a shebang."""
    processor = ExampleHeaderProcessor()
    processor.file_type = make_file_type(
        local_key="script",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex="[",
        ),
    )

    lines: list[str] = ["#!/usr/bin/env example\n", "# coding: utf-8\n", "body\n"]
    assert processor.get_header_insertion_index(lines) == 1
    assert processor.get_header_insertion_index(lines) == 1


def test_default_result_collections_are_independent() -> None:
    """Processor-facing result collection defaults are never shared."""
    first: HeaderParseResult = ExampleHeaderProcessor().parse_fields(
        _Context(Views(), MutableDiagnosticLog()),
    )
    second: HeaderParseResult = ExampleHeaderProcessor().parse_fields(
        _Context(Views(), MutableDiagnosticLog()),
    )

    first.fields["owned"] = "first"
    assert second.fields == {}

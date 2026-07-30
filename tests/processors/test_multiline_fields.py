# topmark:header:start
#
#   project      : TopMark
#   file         : test_multiline_fields.py
#   file_relpath : tests/processors/test_multiline_fields.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Literal multiline header field serialization contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import Views
from topmark.processors.base import HeaderProcessor
from topmark.processors.builtins.cblock import CBlockHeaderProcessor
from topmark.processors.builtins.markdown import MarkdownHeaderProcessor
from topmark.processors.builtins.pound import PoundHeaderProcessor
from topmark.processors.builtins.slash import SlashHeaderProcessor
from topmark.processors.builtins.xml import XmlHeaderProcessor

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.processors.types import HeaderFieldValidationIssue
    from topmark.processors.types import HeaderParseResult


@dataclass(frozen=True, kw_only=True)
class _Config:
    header_fields: tuple[str, ...]
    align_fields: bool
    max_header_line_length: int | None = None
    wrap_fields: tuple[str, ...] = ()


@dataclass(kw_only=True)
class _Context:
    views: Views
    diagnostics: MutableDiagnosticLog


class _RejectingProcessor(PoundHeaderProcessor):
    """Processor whose semantic hook rejects empty values and a sentinel."""

    namespace = "tests"
    local_key = "multiline-rejecting"

    def validate_processor_field(
        self,
        *,
        field_index: int,
        field_name: str,
        field_value: str,
    ) -> tuple[HeaderFieldValidationIssue, ...]:
        """Reject values used to exercise parse-time validation."""
        if field_value and "stop" not in field_value:
            return ()
        return (
            self._field_validation_issue(
                field_index=field_index,
                field_name=field_name,
                target="value",
                rule="processor:test-rejected",
            ),
        )


def _parse(
    processor: HeaderProcessor,
    lines: list[str],
) -> tuple[HeaderParseResult, _Context]:
    context = _Context(
        views=Views(
            header=HeaderView(
                range=(0, len(lines) - 1),
                lines=lines,
                block="".join(lines),
                mapping=None,
            )
        ),
        diagnostics=MutableDiagnosticLog(),
    )
    return processor.parse_fields(context), context


def _pound_payload(
    *payload: str,
    newline: str = "\n",
) -> list[str]:
    return [
        f"# {TOPMARK_START_MARKER}{newline}",
        *(f"# {line}{newline}" for line in payload),
        f"# {TOPMARK_END_MARKER}{newline}",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "|",
        "|= value",
        ">",
        ">= value",
        "| beginning",
        "> beginning",
    ],
)
def test_ordinary_token_values_remain_ordinary(
    value: str,
) -> None:
    """Continuation-looking ordinary values retain ordinary semantics."""
    result, _ = _parse(PoundHeaderProcessor(), _pound_payload(f"field: {value}"))

    assert result.fields == {"field": value}
    assert (result.success_count, result.error_count) == (1, 0)


@pytest.mark.parametrize(
    ("value", "records"),
    [
        (
            "first\nsecond",
            [
                "| first",
                "| second",
            ],
        ),
        (
            "\nsecond",
            [
                "|",
                "| second",
            ],
        ),
        (
            "first\n\nthird",
            [
                "| first",
                "|",
                "| third",
            ],
        ),
        (
            "first\n",
            [
                "| first",
                "|",
            ],
        ),
        (
            "\n",
            [
                "|",
                "|",
            ],
        ),
        (
            "  first  \nsecond",
            [
                '|= "  first  "',
                "| second",
            ],
        ),
        (
            ' quote " and slash \\ \nplain',
            [
                '|= " quote \\" and slash \\\\ "',
                "| plain",
            ],
        ),
        (
            "colon: | >=\nsecond",
            [
                "| colon: | >=",
                "| second",
            ],
        ),
    ],
)
def test_literal_records_round_trip_with_canonical_encoding(
    value: str,
    records: list[str],
) -> None:
    """Plain, bare, and exact records reconstruct the original value."""
    processor = PoundHeaderProcessor()
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(header_fields=("notice",), align_fields=True),
        newline_style="\n",
    )

    assert "notice" in rendered[2] and ":" in rendered[2]
    assert [line.removeprefix("#     ").rstrip("\n") for line in rendered[3:-2]] == records
    parsed, context = _parse(processor, rendered)
    assert parsed.fields == {"notice": value}
    assert (parsed.success_count, parsed.error_count) == (1, 0)
    assert context.diagnostics.items == []


@pytest.mark.parametrize(
    ("records", "value"),
    [
        (("> first",), "first"),
        (('>= "   Indented"',), "   Indented"),
        (("> first", "> second"), "first second"),
        (("> first", '>= "   second"'), "first   second"),
        (('>= ""', '>= "   Indented"'), "   Indented"),
    ],
)
def test_folded_records_reconstruct_one_semantic_value(
    records: tuple[str, ...],
    value: str,
) -> None:
    """One-or-more plain and exact folded records reconstruct losslessly."""
    result, context = _parse(
        PoundHeaderProcessor(),
        _pound_payload("notice:", *records),
    )

    assert result.fields == {"notice": value}
    assert result.success_count == 1
    assert result.error_count == 0
    assert list(context.diagnostics.items) == []


def test_redundant_empty_exact_folded_record_canonicalizes_away() -> None:
    """A redundant empty exact record remains parseable but is not rendered."""
    processor = PoundHeaderProcessor()
    parsed, _context = _parse(
        processor,
        _pound_payload("notice:", '>= ""', '>= "   Indented"'),
    )

    rendered: list[str] = processor.render_header_lines(
        header_values=parsed.fields,
        config=_Config(header_fields=("notice",), align_fields=False),
        newline_style="\n",
    )

    assert '#     >= ""\n' not in rendered
    assert '#     >= "   Indented"\n' in rendered


def test_selected_overlong_field_wraps_to_complete_physical_line_width() -> None:
    """Wrapping measures pound-comment affixes and produces canonical folded records."""
    processor = PoundHeaderProcessor()
    overflow_fields: set[str] = set()
    value = "A sufficiently long notice that contains ordinary spaces and can be wrapped."
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=35,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
        soft_overflow_fields=overflow_fields,
    )

    assert "#   notice:\n" in rendered
    assert "#     > A sufficiently long notice\n" in rendered
    assert "#     > that contains ordinary\n" in rendered
    assert "#     > spaces and can be wrapped.\n" in rendered
    assert all(len(line.removesuffix("\n")) <= 35 for line in rendered[2:6])
    assert overflow_fields == set()

    parsed, _context = _parse(processor, rendered)
    assert parsed.fields == {"notice": value}


def test_wrapping_preserves_multiple_space_runs_with_exact_records() -> None:
    """Automatic boundaries preserve exceptional U+0020 runs exactly."""
    processor = PoundHeaderProcessor()
    value = "Words  separated   here"
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=30,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
    )

    assert "#     > Words  separated\n" in rendered
    assert '#     >= "   here"\n' in rendered
    parsed, _context = _parse(processor, rendered)
    assert parsed.fields == {"notice": value}


def test_width_boundary_and_allowlist_control_automatic_folding() -> None:
    """The complete ordinary line fits at equality and folds only when selected below it."""
    processor = PoundHeaderProcessor()
    value = "one two"
    ordinary_length = len("#   notice: one two")

    at_boundary: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=ordinary_length,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
    )
    below_boundary: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=ordinary_length - 1,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
    )
    unselected: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=ordinary_length - 1,
            wrap_fields=(),
        ),
        newline_style="\n",
    )

    assert "#   notice: one two\n" in at_boundary
    assert "#   notice:\n" in below_boundary
    assert "#     > one\n" in below_boundary
    assert "#     > two\n" in below_boundary
    assert "#   notice: one two\n" in unselected


def test_unicode_width_counts_code_points_and_preserves_emoji_sequences() -> None:
    """Unicode wrapping counts Python code points rather than display cells or bytes."""
    processor = PoundHeaderProcessor()
    value = "界 界 👩‍💻 界"
    rendered: list[str] = processor.render_header_lines(
        header_values={"n": value},
        config=_Config(
            header_fields=("n",),
            align_fields=False,
            max_header_line_length=14,
            wrap_fields=("n",),
        ),
        newline_style="\n",
    )

    folded_lines: list[str] = [line for line in rendered if "> " in line]
    assert folded_lines == ["#     > 界 界\n", "#     > 👩‍💻 界\n"]
    assert all(len(line.removesuffix("\n")) <= 14 for line in folded_lines)
    parsed, _context = _parse(processor, rendered)
    assert parsed.fields == {"n": value}


def test_unbreakable_selected_value_remains_ordinary_and_reports_soft_overflow() -> None:
    """The soft width never hard-splits an unbreakable value."""
    processor = PoundHeaderProcessor()
    value = "https://example.com/very/long/path"
    overflow_fields: set[str] = set()
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=10,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
        soft_overflow_fields=overflow_fields,
    )

    assert f"#   notice: {value}\n" in rendered
    assert not any("> " in line for line in rendered)
    assert overflow_fields == {"notice"}


def test_impossibly_small_width_uses_smallest_lossless_breakpoint() -> None:
    """A soft target below structural overhead still makes deterministic progress."""
    processor = PoundHeaderProcessor()
    overflow_fields: set[str] = set()
    value = "one two"
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=1,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
        soft_overflow_fields=overflow_fields,
    )

    assert "#   notice:\n" in rendered
    assert "#     > one\n" in rendered
    assert "#     > two\n" in rendered
    assert overflow_fields == {"notice"}
    parsed, _context = _parse(processor, rendered)
    assert parsed.fields == {"notice": value}


def test_folded_wrapper_enforces_semantic_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed renderer round-trip invariant is an implementation error."""
    processor = PoundHeaderProcessor()

    def decode_as_mismatch(_records: Sequence[str]) -> str:
        return "different"

    monkeypatch.setattr(
        processor,
        "_decode_folded_records",
        decode_as_mismatch,
    )

    with pytest.raises(
        RuntimeError,
        match="did not preserve the semantic value",
    ):
        processor._wrap_folded_records(  # pyright: ignore[reportPrivateUsage]
            "one two",
            max_line_length=1,
            measure_line=lambda inner, _continuation: len(inner),
        )


def test_folded_internal_decoder_rejects_non_folded_records() -> None:
    """The renderer's round-trip verifier rejects a non-folded record."""
    with pytest.raises(
        RuntimeError,
        match="invalid folded continuation record",
    ):
        HeaderProcessor._decode_folded_records(  # pyright: ignore[reportPrivateUsage]
            ["| literal"]
        )


@pytest.mark.parametrize(
    "newline_style",
    [
        "\n",
        "\r\n",
        "\r",
    ],
)
@pytest.mark.parametrize(
    "align_fields",
    [
        False,
        True,
    ],
)
@pytest.mark.parametrize(
    "processor",
    [
        PoundHeaderProcessor(),
        SlashHeaderProcessor(),
        CBlockHeaderProcessor(),
        MarkdownHeaderProcessor(),
        XmlHeaderProcessor(),
    ],
)
def test_every_builtin_family_wraps_and_round_trips_deterministically(
    processor: HeaderProcessor,
    align_fields: bool,
    newline_style: str,
) -> None:
    """Every built-in family applies affixes, width, alignment, and newline policy."""
    value = "Deterministic wrapping preserves the complete semantic value across processors."
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=align_fields,
            max_header_line_length=42,
            wrap_fields=("notice",),
        ),
        newline_style=newline_style,
        header_indent_override="  ",
    )

    folded_lines: list[str] = [line for line in rendered if "> " in line or '>= "' in line]
    assert len(folded_lines) >= 2
    assert all(len(line.removesuffix(newline_style)) <= 42 for line in folded_lines)
    assert all(line.endswith(newline_style) for line in rendered)
    parsed, _context = _parse(processor, rendered)
    assert parsed.fields == {"notice": value}


@pytest.mark.parametrize("align_fields", [False, True])
@pytest.mark.parametrize(
    "processor",
    [
        PoundHeaderProcessor(),
        SlashHeaderProcessor(),
        CBlockHeaderProcessor(),
        MarkdownHeaderProcessor(),
        XmlHeaderProcessor(),
    ],
)
def test_every_builtin_family_round_trips_multiline_with_crlf_and_indent(
    processor: HeaderProcessor,
    align_fields: bool,
) -> None:
    """Every built-in comment family affixes every CRLF physical line."""
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": "first\nsecond", "longer": "ordinary"},
        config=_Config(header_fields=("notice", "longer"), align_fields=align_fields),
        newline_style="\r\n",
        header_indent_override="\t",
    )

    assert all(line.endswith("\r\n") for line in rendered)
    assert all(line.startswith("\t") for line in rendered if line.strip())
    parsed, _ = _parse(processor, rendered)
    assert parsed.fields == {"notice": "first\nsecond", "longer": "ordinary"}
    assert (parsed.success_count, parsed.error_count) == (2, 0)


def test_layout_indentation_is_ignored_and_duplicate_last_occurrence_wins() -> None:
    """Layout whitespace is nonsemantic and duplicate values keep the last scalar."""
    lines: list[str] = _pound_payload(
        "notice:",
        "\t\t| first",
        "             | second",
        "ordinary: value",
        "notice:",
        "| replacement",
        "| final",
    )

    result, _ = _parse(PoundHeaderProcessor(), lines)

    assert result.fields == {
        "notice": "replacement\nfinal",
        "ordinary": "value",
    }
    assert (result.success_count, result.error_count) == (3, 0)


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_physical_newlines_parse_to_semantic_lf(newline: str) -> None:
    """All supported physical separators reconstruct semantic LF."""
    result, _ = _parse(
        PoundHeaderProcessor(),
        _pound_payload("notice:", "| first", "| second", newline=newline),
    )

    assert result.fields == {
        "notice": "first\nsecond",
    }


@pytest.mark.parametrize("terminator", ["\r\n", "\n", "\r", ""])
def test_affix_removal_accepts_optional_physical_line_terminator(
    terminator: str,
) -> None:
    """Affix removal handles CRLF, LF, CR, and an unterminated logical line."""
    processor = HeaderProcessor(
        line_prefix="#",
        line_suffix="!",
    )

    inner, valid = processor._remove_line_affixes(  # pyright: ignore[reportPrivateUsage]
        f"#   | content !{terminator}"
    )

    assert valid
    assert inner == "   | content"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            ("| orphan",),
            "header:orphan-continuation",
        ),
        (
            ("field: ordinary", "| after"),
            "header:continuation-after-scalar",
        ),
        (
            ("field:", "| only"),
            "header:scalar-too-short",
        ),
        (
            ("field:", ">"),
            "header:missing-continuation-body",
        ),
        (
            ("field:", "| ", "| second"),
            "header:missing-continuation-body",
        ),
        (
            ("field:", '|= "bad\\n"', "| second"),
            "header:invalid-continuation-string",
        ),
        (
            ("field:", "| trailing ", "| second"),
            "header:invalid-continuation-character",
        ),
        (
            ("field:", "| first", "> second"),
            "header:mixed-scalar-mode",
        ),
        (
            ("field:", '>= "bad\\n"', "> second"),
            "header:invalid-continuation-string",
        ),
        (
            ("> orphan",),
            "header:orphan-continuation",
        ),
        (
            ("| ",),
            "header:missing-continuation-body",
        ),
        (
            ("field:", "| first", "not-a-field"),
            "header:missing-continuation-body",
        ),
        (
            ("field:", "|=", "| second"),
            "header:missing-continuation-body",
        ),
        (
            ("field:", '|="missing separator"', "| second"),
            "header:invalid-continuation-string",
        ),
        (
            ("field:", '|= "', "| second"),
            "header:invalid-continuation-string",
        ),
        (
            ("field:", '|= "unescaped " quote"', "| second"),
            "header:invalid-continuation-string",
        ),
        (
            ("field:", "|unexpected", "| second"),
            "header:missing-continuation-body",
        ),
        (
            ("field:", "| embedded\ttab", "| second"),
            "header:invalid-continuation-character",
        ),
    ],
)
def test_malformed_continuations_have_stable_safe_diagnostics(
    payload: tuple[str, ...],
    code: str,
) -> None:
    """Malformed scalar diagnostics expose only safe positions and line numbers."""
    result, context = _parse(PoundHeaderProcessor(), _pound_payload(*payload))

    assert result.error_count == 1
    assert any(code in item.message for item in context.diagnostics.items)
    assert all("physical line" in item.message for item in context.diagnostics.items)


def test_missing_processor_affix_is_a_scalar_error() -> None:
    """A continuation without the processor prefix invalidates its scalar."""
    lines: list[str] = _pound_payload("field:")
    lines.insert(-1, "  | first\n")
    lines.insert(-1, "  | second\n")

    result, context = _parse(PoundHeaderProcessor(), lines)

    assert (result.success_count, result.error_count) == (0, 1)
    assert "header:invalid-continuation-affix" in context.diagnostics.items[0].message


@pytest.mark.parametrize(
    "suffix_separator",
    [
        " ",
        "",
    ],
)
def test_missing_processor_suffix_is_a_scalar_error(
    suffix_separator: str,
) -> None:
    """A continuation missing its required suffix invalidates the whole scalar."""
    processor = HeaderProcessor(
        line_prefix="#",
        line_suffix="!",
    )
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}{suffix_separator}!\n",
        f"# field:{suffix_separator}!\n",
        f"#   | first{suffix_separator}!\n",
        "#   | second\n",
        f"# {TOPMARK_END_MARKER}{suffix_separator}!\n",
    ]

    result, context = _parse(processor, lines)

    assert (result.success_count, result.error_count) == (0, 1)
    assert "header:invalid-continuation-affix" in context.diagnostics.items[0].message


@pytest.mark.parametrize(
    "payload",
    [
        ("field:",),
        ("field: stop",),
        ("field:", "| first", "| stop"),
    ],
)
def test_parsed_scalars_must_pass_processor_semantic_validation(
    payload: tuple[str, ...],
) -> None:
    """Empty, ordinary, and literal source scalars share the validation boundary."""
    result, context = _parse(_RejectingProcessor(), _pound_payload(*payload))

    assert result.fields == {}
    assert (result.success_count, result.error_count) == (0, 1)
    assert [item.message.split(" at ", maxsplit=1)[0] for item in context.diagnostics.items] == [
        "processor:test-rejected"
    ]


@pytest.mark.parametrize(
    "escape",
    [r"\n", r"\r", r"\t", r"\u0041", r"\U00000041"],
)
def test_exact_records_reject_every_unsupported_escape(escape: str) -> None:
    """Exact records support only escaped quote and escaped backslash."""
    result, context = _parse(
        PoundHeaderProcessor(),
        _pound_payload("field:", f'|= "bad{escape}"', "| second"),
    )

    assert result.error_count == 1
    assert "header:invalid-continuation-string" in context.diagnostics.items[0].message


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\0", "\t"])
def test_invalid_semantic_characters_never_render(separator: str) -> None:
    """Controls and Unicode separators remain invalid in multiline values."""
    result = PoundHeaderProcessor().validate_header_fields(
        field_names=("notice",),
        header_values={"notice": f"first{separator}second\nthird"},
    )

    assert not result.is_valid


def test_physical_line_wrapper_rejects_raw_line_breaks() -> None:
    """The one-line affix helper cannot receive raw semantic line breaks."""
    processor = PoundHeaderProcessor()

    with pytest.raises(ValueError, match="cannot contain CR or LF"):
        processor._wrap_line(  # pyright: ignore[reportPrivateUsage]
            "unsafe\nline",
            newline_style="\n",
        )


def test_continuation_encoder_requires_normalized_semantic_newlines() -> None:
    """Raw CR cannot cross the private physical-line encoding boundary."""
    with pytest.raises(ValueError, match="must be normalized"):
        PoundHeaderProcessor()._encode_field_lines(  # pyright: ignore[reportPrivateUsage]
            field_name="notice",
            field_value="first\rsecond",
            width=0,
        )

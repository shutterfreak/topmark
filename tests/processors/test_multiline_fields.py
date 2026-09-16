# topmark:header:start
#
#   project      : TopMark
#   file         : test_multiline_fields.py
#   file_relpath : tests/processors/test_multiline_fields.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Structural-pipe multiline header rendering contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import Views
from topmark.processors.builtins.cblock import CBlockHeaderProcessor
from topmark.processors.builtins.markdown import MarkdownHeaderProcessor
from topmark.processors.builtins.pound import PoundHeaderProcessor
from topmark.processors.builtins.slash import SlashHeaderProcessor
from topmark.processors.builtins.xml import XmlHeaderProcessor

if TYPE_CHECKING:
    from topmark.processors.base import HeaderProcessor
    from topmark.processors.types import HeaderFieldValidationResult
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


def _parse(
    processor: HeaderProcessor,
    lines: list[str],
) -> tuple[HeaderParseResult, _Context]:
    """Parse one marker-delimited header block."""
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
    """Build a pound-comment header from affix-free payload lines."""
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
    ],
)
def test_ordinary_token_values_remain_ordinary(
    value: str,
) -> None:
    """Continuation-looking text after a field colon remains ordinary content."""
    result, _ = _parse(
        PoundHeaderProcessor(),
        _pound_payload(
            f"field: {value}",
        ),
    )

    assert result.fields == {"field": value}
    assert (result.success_count, result.error_count) == (1, 0)


def test_pipe_records_parse_as_structural_multiline_content() -> None:
    """Pipes safely group content and paragraph separators below an empty opener."""
    result, context = _parse(
        PoundHeaderProcessor(),
        _pound_payload(
            "notice:",
            "| First paragraph.",
            "|",
            "| Second paragraph.",
        ),
    )

    assert result.fields == {"notice": "First paragraph.\n\nSecond paragraph."}
    assert (result.success_count, result.error_count) == (1, 0)
    assert context.diagnostics.items == []


def test_pipe_continuations_allow_colon_bearing_prose() -> None:
    """A colon in prose cannot be mistaken for a field delimiter."""
    result, _ = _parse(
        PoundHeaderProcessor(),
        _pound_payload(
            "notice:",
            "| Note: read the documentation.",
        ),
    )

    assert result.fields == {"notice": "Note: read the documentation."}


def test_empty_field_opener_parses_as_an_empty_value() -> None:
    """An opener without pipe records retains the ordinary empty-value form."""
    result, context = _parse(PoundHeaderProcessor(), _pound_payload("notice:"))

    assert result.fields == {"notice": ""}
    assert (result.success_count, result.error_count) == (1, 0)
    assert context.diagnostics.items == []


def test_unselected_multiline_value_uses_only_pipe_records() -> None:
    """Unselected multiline content retains its logical layout with pipes."""
    rendered: list[str] = PoundHeaderProcessor().render_header_lines(
        header_values={"notice": "first\n\nsecond"},
        config=_Config(header_fields=("notice",), align_fields=False),
        newline_style="\n",
    )

    assert "#   notice:\n" in rendered
    assert "#     | first\n" in rendered
    assert "#     |\n" in rendered
    assert "#     | second\n" in rendered
    assert not any(">" in line or "|=" in line for line in rendered)


@pytest.mark.parametrize(
    "value",
    [
        "One paragraph with several words.",
        "One paragraph with\nseveral words.",
        "\nOne paragraph with\nseveral words.\n",
    ],
)
def test_selected_prose_normalizes_equivalent_toml_layout(
    value: str,
) -> None:
    """Selected prose ignores incidental TOML line layout and outer blank lines."""
    rendered: list[str] = PoundHeaderProcessor().render_header_lines(
        header_values={"notice": value},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=30,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
    )

    assert rendered == [
        "# topmark:header:start\n",
        "#\n",
        "#   notice:\n",
        "#     | One paragraph with\n",
        "#     | several words.\n",
        "#\n",
        "# topmark:header:end\n",
    ]


def test_selected_prose_preserves_paragraph_boundaries() -> None:
    """Blank TOML-line runs become one bare-pipe paragraph separator."""
    rendered: list[str] = PoundHeaderProcessor().render_header_lines(
        header_values={"notice": "First\nparagraph.\n\n\nSecond paragraph."},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            max_header_line_length=40,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
    )

    assert "#     | First paragraph.\n" in rendered
    assert "#     |\n" in rendered
    assert "#     | Second paragraph.\n" in rendered


def test_selected_prose_without_width_still_uses_one_record_per_paragraph() -> None:
    """The allowlist controls prose normalization independently of the soft width."""
    rendered: list[str] = PoundHeaderProcessor().render_header_lines(
        header_values={"notice": "first\nsecond\n\nthird"},
        config=_Config(
            header_fields=("notice",),
            align_fields=False,
            wrap_fields=("notice",),
        ),
        newline_style="\n",
    )

    assert "#     | first second\n" in rendered
    assert "#     |\n" in rendered
    assert "#     | third\n" in rendered


def test_selected_unbreakable_value_remains_ordinary_and_reports_soft_overflow() -> None:
    """A soft width never hard-splits an unbreakable prose fragment."""
    value = "https://example.com/very/long/path"
    overflow_fields: set[str] = set()
    rendered: list[str] = PoundHeaderProcessor().render_header_lines(
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
    assert overflow_fields == {"notice"}


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
def test_every_builtin_family_wraps_prose_with_pipe_records(
    processor: HeaderProcessor,
    align_fields: bool,
    newline_style: str,
) -> None:
    """Every built-in processor affixes and measures structural pipe records."""
    rendered: list[str] = processor.render_header_lines(
        header_values={"notice": "Deterministic wrapping applies to prose across processors."},
        config=_Config(
            header_fields=("notice",),
            align_fields=align_fields,
            max_header_line_length=42,
            wrap_fields=("notice",),
        ),
        newline_style=newline_style,
        header_indent_override="  ",
    )

    pipe_lines: list[str] = [line for line in rendered if "| " in line]
    assert len(pipe_lines) >= 2
    assert all(len(line.removesuffix(newline_style)) <= 42 for line in pipe_lines)
    assert all(line.endswith(newline_style) for line in rendered)
    assert not any("|=" in line for line in rendered)


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
            ("field:", "|unexpected"),
            "header:missing-continuation-body",
        ),
        (
            ("field:", "|= old syntax"),
            "header:missing-continuation-body",
        ),
        (
            ("|missing separator",),
            "header:missing-continuation-body",
        ),
        (
            ("field:", "|missing separator", "| ignored"),
            "header:missing-continuation-body",
        ),
    ],
)
def test_malformed_pipe_continuations_have_safe_diagnostics(
    payload: tuple[str, ...],
    code: str,
) -> None:
    """Malformed pipes are rejected without exposing unsafe source content."""
    result, context = _parse(PoundHeaderProcessor(), _pound_payload(*payload))

    assert result.error_count == 1
    assert any(code in item.message for item in context.diagnostics.items)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (("field: contains\0nul",), "content:nul"),
        (("field:", "| contains\0nul"), "content:nul"),
        (("field\0:",), "content:nul"),
    ],
)
def test_invalid_scalar_and_pipe_values_are_rejected_during_parsing(
    payload: tuple[str, ...],
    code: str,
) -> None:
    """Field validation rejects unsafe parsed content in either structural form."""
    result, context = _parse(PoundHeaderProcessor(), _pound_payload(*payload))

    assert result.fields == {}
    assert (result.success_count, result.error_count) == (0, 1)
    assert code in context.diagnostics.items[0].message


def test_missing_processor_affix_invalidates_pipe_continuation() -> None:
    """Continuation records still require the selected processor's affixes."""
    lines: list[str] = _pound_payload("field:")
    lines.insert(-1, "  | first\n")

    result, context = _parse(PoundHeaderProcessor(), lines)

    assert (result.success_count, result.error_count) == (0, 1)
    assert "header:invalid-continuation-affix" in context.diagnostics.items[0].message


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\0", "\t"])
def test_invalid_semantic_characters_never_render(
    separator: str,
) -> None:
    """Controls and Unicode separators remain invalid in multiline values."""
    result: HeaderFieldValidationResult = PoundHeaderProcessor().validate_header_fields(
        field_names=("notice",),
        header_values={"notice": f"first{separator}second\nthird"},
    )

    assert not result.is_valid


def test_continuation_encoder_requires_normalized_semantic_newlines() -> None:
    """Raw CR cannot cross the private physical-line encoding boundary."""
    with pytest.raises(ValueError, match="must be normalized"):
        PoundHeaderProcessor()._encode_field_lines(  # pyright: ignore[reportPrivateUsage]
            field_name="notice",
            field_value="first\rsecond",
            width=0,
        )

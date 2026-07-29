# topmark:header:start
#
#   project      : TopMark
#   file         : test_field_validation.py
#   file_relpath : tests/processors/test_field_validation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contracts for validating fields before processor rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.processors.builtins.cblock import CBlockHeaderProcessor
from topmark.processors.builtins.markdown import MarkdownHeaderProcessor
from topmark.processors.builtins.pound import PoundHeaderProcessor
from topmark.processors.builtins.slash import SlashHeaderProcessor
from topmark.processors.builtins.xml import XmlHeaderProcessor

if TYPE_CHECKING:
    from topmark.processors.base import HeaderProcessor
    from topmark.processors.types import HeaderFieldValidationIssue
    from topmark.processors.types import HeaderFieldValidationResult


class ExtendingProcessor(PoundHeaderProcessor):
    """Custom processor exercising the additive validation hook."""

    namespace = "tests"
    local_key = "extending-validation"

    def validate_processor_field(
        self,
        *,
        field_index: int,
        field_name: str,
        field_value: str,
    ) -> tuple[HeaderFieldValidationIssue, ...]:
        """Reject a custom token without repeating shared validation."""
        if "custom-stop" not in field_value:
            return ()
        return (
            self._field_validation_issue(
                field_index=field_index,
                field_name=field_name,
                target="value",
                rule="processor:custom-stop",
            ),
        )


class EncodedLineExtendingProcessor(PoundHeaderProcessor):
    """Custom processor exercising the additive encoded-line hook."""

    namespace = "tests"
    local_key = "extending-encoded-line-validation"

    def validate_processor_encoded_line(
        self,
        *,
        field_index: int,
        field_name: str,
        field_value: str,
        encoded_line: str,
    ) -> tuple[HeaderFieldValidationIssue, ...]:
        """Reject a custom token after canonical continuation encoding."""
        if "encoded-stop" not in encoded_line:
            return ()
        return (
            self._field_validation_issue(
                field_index=field_index,
                field_name=field_name,
                target="value",
                rule="processor:encoded-stop",
            ),
        )


def test_semantic_newline_value_is_valid_before_cblock_rendering() -> None:
    """A semantic newline is encoded into prefixed physical continuation lines."""
    result: HeaderFieldValidationResult = CBlockHeaderProcessor().validate_header_fields(
        field_names=("project",),
        header_values={"project": "safe\nescaped"},
    )

    assert result.is_valid


def test_comment_terminator_is_rejected_before_processor_rendering() -> None:
    """Processor grammar must reject content that terminates its comment."""
    cblock: HeaderFieldValidationResult = CBlockHeaderProcessor().validate_header_fields(
        field_names=("project",),
        header_values={"project": "unsafe */ tail"},
    )
    xml: HeaderFieldValidationResult = XmlHeaderProcessor().validate_header_fields(
        field_names=("project",),
        header_values={"project": "unsafe -- tail"},
    )

    assert [(issue.target, issue.rule) for issue in cblock.issues] == [
        ("value", "processor:cblock-comment-terminator"),
    ]
    assert [(issue.target, issue.rule) for issue in xml.issues] == [
        ("value", "processor:xml-double-hyphen"),
    ]


def test_comment_terminators_are_rejected_across_multiline_boundaries() -> None:
    """Processor restrictions inspect the complete reconstructed value."""
    cblock: HeaderFieldValidationResult = CBlockHeaderProcessor().validate_header_fields(
        field_names=("notice",),
        header_values={"notice": "first\nunsafe */ tail"},
    )
    markdown: HeaderFieldValidationResult = MarkdownHeaderProcessor().validate_header_fields(
        field_names=("notice",),
        header_values={"notice": "first\nunsafe -- tail"},
    )

    assert not cblock.is_valid
    assert not markdown.is_valid


@pytest.mark.parametrize(
    ("field_name", "field_value", "target", "rule"),
    [
        ("", "value", "name", "name:empty"),
        (" project", "value", "name", "name:not-round-trippable"),
        ("project ", "value", "name", "name:not-round-trippable"),
        ("bad:key", "value", "name", "name:colon"),
        ("bad\nname", "value", "name", "content:line-break"),
        ("project", "nul\0byte", "value", "content:nul"),
        ("project", "tab\tvalue", "value", "content:control-character"),
        ("project", "escape\x1bvalue", "value", "content:control-character"),
        ("project", "delete\x7fvalue", "value", "content:control-character"),
        ("project", TOPMARK_START_MARKER, "value", "content:reserved-start-marker"),
        ("project", TOPMARK_END_MARKER, "value", "content:reserved-end-marker"),
        (TOPMARK_START_MARKER, "value", "name", "content:reserved-start-marker"),
    ],
)
def test_shared_validation_rejects_unsafe_or_ambiguous_content(
    field_name: str,
    field_value: str,
    target: str,
    rule: str,
) -> None:
    """Shared rules apply to every processor before grammar-specific rules."""
    result: HeaderFieldValidationResult = PoundHeaderProcessor().validate_header_fields(
        field_names=(field_name,),
        header_values={field_name: field_value},
    )

    assert (target, rule) in [(issue.target, issue.rule) for issue in result.issues]


@pytest.mark.parametrize(
    "processor",
    [
        CBlockHeaderProcessor(),
        XmlHeaderProcessor(),
        MarkdownHeaderProcessor(),
        PoundHeaderProcessor(),
        SlashHeaderProcessor(),
    ],
)
def test_safe_ordinary_field_is_valid_for_every_builtin_processor(
    processor: HeaderProcessor,
) -> None:
    """Ordinary printable single-line content remains valid for every family."""
    result: HeaderFieldValidationResult = processor.validate_header_fields(
        field_names=("project",),
        header_values={"project": "TopMark 1.0"},
    )

    assert result.is_valid


@pytest.mark.parametrize(
    "content",
    [
        "contains */ safely",
        "contains -- safely",
    ],
)
@pytest.mark.parametrize(
    "processor",
    [
        PoundHeaderProcessor(),
        SlashHeaderProcessor(),
    ],
)
def test_line_comment_processors_do_not_reject_other_comment_grammars(
    processor: PoundHeaderProcessor | SlashHeaderProcessor,
    content: str,
) -> None:
    """Pound and slash processors keep grammar-permitted text valid."""
    result: HeaderFieldValidationResult = processor.validate_header_fields(
        field_names=("project",),
        header_values={"project": content},
    )

    assert result.is_valid


def test_xml_and_markdown_reject_double_hyphen_in_names_and_values() -> None:
    """Both HTML-comment processor families enforce their actual grammar."""
    for processor in (XmlHeaderProcessor(), MarkdownHeaderProcessor()):
        name_result: HeaderFieldValidationResult = processor.validate_header_fields(
            field_names=("bad--name",),
            header_values={"bad--name": "value"},
        )
        value_result: HeaderFieldValidationResult = processor.validate_header_fields(
            field_names=("project",),
            header_values={"project": "bad--value"},
        )

        assert any(issue.target == "name" for issue in name_result.issues)
        assert any(issue.target == "value" for issue in value_result.issues)


def test_custom_processor_extends_without_replacing_shared_validation() -> None:
    """A custom hook adds its rule while shared checks still run automatically."""
    result: HeaderFieldValidationResult = ExtendingProcessor().validate_header_fields(
        field_names=("project",),
        header_values={"project": "custom-stop\n"},
    )

    assert [(issue.target, issue.rule) for issue in result.issues] == [
        ("value", "processor:custom-stop"),
    ]


def test_custom_processor_can_restrict_canonical_encoded_lines() -> None:
    """The shared orchestrator invokes additive encoded-line checks."""
    result: HeaderFieldValidationResult = EncodedLineExtendingProcessor().validate_header_fields(
        field_names=("notice",),
        header_values={"notice": "first\nencoded-stop"},
    )

    assert [(issue.target, issue.rule) for issue in result.issues] == [
        ("value", "processor:encoded-stop"),
    ]

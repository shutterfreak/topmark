# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_rendering.py
#   file_relpath : tests/presentation/test_registry_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for human-facing registry presentation renderers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

from tests.helpers.registry import make_file_type
from topmark.filetypes.policy import FileTypeHeaderPolicy
from topmark.presentation.markdown.registry import render_bindings_markdown
from topmark.presentation.markdown.registry import render_filetype_policy_markdown
from topmark.presentation.markdown.registry import render_filetypes_markdown
from topmark.presentation.markdown.registry import render_processors_markdown
from topmark.presentation.shared.registry import BindingHumanItem
from topmark.presentation.shared.registry import BindingsHumanReport
from topmark.presentation.shared.registry import FileTypeHumanItem
from topmark.presentation.shared.registry import FileTypePolicyHumanItem
from topmark.presentation.shared.registry import FileTypesHumanReport
from topmark.presentation.shared.registry import ProcessorHumanItem
from topmark.presentation.shared.registry import ProcessorsHumanReport
from topmark.presentation.shared.registry import UnboundFileTypeHumanItem
from topmark.presentation.shared.registry import build_bindings_human_report
from topmark.presentation.shared.registry import build_filetypes_human_report
from topmark.presentation.shared.registry import build_processors_human_report
from topmark.presentation.text.registry import render_bindings_text
from topmark.presentation.text.registry import render_filetype_policy_text
from topmark.presentation.text.registry import render_filetypes_text
from topmark.presentation.text.registry import render_processors_text
from topmark.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from tests.conftest import EffectiveRegistries
    from topmark.filetypes.model import FileType


# ---- Helpers ----


class _RegistryPresentationProcessor(HeaderProcessor):
    """Processor used for deterministic presentation registry tests."""

    local_key: ClassVar[str] = "registry-presentation"
    namespace: ClassVar[str] = "test"
    description: ClassVar[str] = "Registry presentation processor"

    line_indent: str = ""
    line_prefix: str = "#"
    line_suffix: str = ""
    block_prefix: str = ""
    block_suffix: str = ""


class _UnusedRegistryPresentationProcessor(HeaderProcessor):
    """Unused processor used for deterministic presentation registry tests."""

    local_key: ClassVar[str] = "registry-unused"
    namespace: ClassVar[str] = "test"
    description: ClassVar[str] = "Unused registry presentation processor"

    line_indent: str = ""
    line_prefix: str = "//"
    line_suffix: str = ""
    block_prefix: str = ""
    block_suffix: str = ""


def _policy_item() -> FileTypePolicyHumanItem:
    """Return a policy item with non-default-looking values for renderer checks."""
    return FileTypePolicyHumanItem(
        supports_shebang=True,
        encoding_line_regex="^# coding:",
        pre_header_blank_after_block=1,
        ensure_blank_after_header=True,
        blank_collapse_mode="strict",
        blank_collapse_extra="\\f",
    )


def _filetype_item(*, bound: bool = True) -> FileTypeHumanItem:
    """Return a deterministic file type presentation item."""
    return FileTypeHumanItem(
        local_key="python",
        namespace="test",
        qualified_key="test.python",
        description="Python source",
        bound=bound,
        extensions=(".py",),
        filenames=("SConstruct",),
        patterns=(".*\\.pyi",),
        skip_processing=False,
        has_content_matcher=True,
        has_insert_checker=True,
        policy=_policy_item(),
    )


def _processor_item(*, bound: bool = True) -> ProcessorHumanItem:
    """Return a deterministic processor presentation item."""
    return ProcessorHumanItem(
        local_key="hash",
        namespace="test",
        qualified_key="test.hash",
        description="Hash comments",
        bound=bound,
        line_indent="",
        line_prefix="#",
        line_suffix="",
        block_prefix="",
        block_suffix="",
    )


def _binding_item() -> BindingHumanItem:
    """Return a deterministic binding presentation item."""
    return BindingHumanItem(
        file_type_key="test.python",
        file_type_local_key="python",
        file_type_namespace="test",
        processor_key="test.hash",
        processor_local_key="hash",
        processor_namespace="test",
        file_type_description="Python source",
        processor_description="Hash comments",
    )


def _table_cells(row: str) -> list[str]:
    """Return stripped Markdown table cells without outer separators."""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _find_table_row(output: str, marker: str) -> list[str]:
    """Return normalized cells for the first Markdown table row containing marker."""
    row = next(
        line for line in output.splitlines() if line.lstrip().startswith("|") and marker in line
    )
    return _table_cells(row)


# ---- Text ----


def test_render_filetype_policy_text_lists_policy_pairs_without_style() -> None:
    """TEXT policy rendering should expose all shared policy fields."""
    output: str = render_filetype_policy_text(_policy_item(), styled=False)

    assert output == (
        "supports_shebang=true, encoding_line_regex='^# coding:', "
        "pre_header_blank_after_block=1, ensure_blank_after_header=true, "
        "blank_collapse_mode=strict, blank_collapse_extra='\\\\f'"
    )


def test_render_filetype_policy_markdown_emphasizes_policy_keys() -> None:
    """Markdown policy rendering should emphasize shared policy field names."""
    output: str = render_filetype_policy_markdown(_policy_item())

    assert output == (
        "**supports_shebang**=true, **encoding_line_regex**='^# coding:', "
        "**pre_header_blank_after_block**=1, **ensure_blank_after_header**=true, "
        "**blank_collapse_mode**=strict, **blank_collapse_extra**='\\\\f'"
    )


def test_render_filetypes_text_compact_lists_qualified_key_and_description() -> None:
    """Compact TEXT file-type rendering should list identity and description."""
    report = FileTypesHumanReport(
        show_details=False,
        verbosity_level=0,
        styled=False,
        items=(_filetype_item(),),
    )

    output: str = render_filetypes_text(report)

    assert output == "1. test.python Python source"


def test_render_filetypes_text_details_include_matching_and_policy_metadata() -> None:
    """Detailed TEXT file-type rendering should include matching and policy metadata."""
    report = FileTypesHumanReport(
        show_details=True,
        verbosity_level=1,
        styled=False,
        items=(_filetype_item(bound=False),),
    )

    output: str = render_filetypes_text(report)

    assert "Supported file types (canonical identities):" in output
    assert "1. test.python - Python source" in output
    assert "      local key       : python" in output
    assert "      namespace       : test" in output
    assert "      bound           : no" in output
    assert "      extensions      : .py" in output
    assert "      filenames       : SConstruct" in output
    assert "      patterns        : .*\\.pyi" in output
    assert "      content matcher : yes" in output
    assert "      insert checker  : yes" in output
    assert "      header policy   : supports_shebang=true" in output
    assert "encoding_line_regex='^# coding:'" in output
    assert "pre_header_blank_after_block=1" in output
    assert "ensure_blank_after_header=true" in output


def test_render_processors_text_compact_and_details() -> None:
    """TEXT processor rendering should support compact and detailed modes."""
    compact_report = ProcessorsHumanReport(
        show_details=False,
        verbosity_level=0,
        processors=(_processor_item(),),
        styled=False,
    )
    detail_report = ProcessorsHumanReport(
        show_details=True,
        verbosity_level=1,
        processors=(_processor_item(bound=False),),
        styled=False,
    )

    assert render_processors_text(compact_report) == "1. test.hash Hash comments"

    detail_output: str = render_processors_text(detail_report)
    assert "Registered header processors:" in detail_output
    assert "1. test.hash - Hash comments" in detail_output
    assert "      local key       : hash" in detail_output
    assert "      namespace       : test" in detail_output
    assert "      bound           : no" in detail_output
    assert "      line prefix     : #" in detail_output


def test_render_bindings_text_includes_unbound_and_unused_sections() -> None:
    """TEXT binding rendering should include binding, unbound, and unused sections."""
    report = BindingsHumanReport(
        show_details=False,
        verbosity_level=1,
        bindings=(_binding_item(),),
        unbound_filetypes=(UnboundFileTypeHumanItem(name="test.markdown", description="Markdown"),),
        unused_processors=(_processor_item(bound=False),),
        styled=False,
    )

    output: str = render_bindings_text(report)

    assert "Effective file-type-to-processor bindings:" in output
    assert "1. test.python -> test.hash" in output
    assert "Unbound file types:" in output
    assert "1. test.markdown - Markdown" in output
    assert "Unused processors:" in output
    assert "1. test.hash - Hash comments" in output


def test_render_bindings_text_details_include_identity_components() -> None:
    """Detailed TEXT binding rendering should include local keys and namespaces."""
    report = BindingsHumanReport(
        show_details=True,
        verbosity_level=0,
        bindings=(_binding_item(),),
        unbound_filetypes=(),
        unused_processors=(),
        styled=False,
    )

    output: str = render_bindings_text(report)

    assert "1. test.python -> test.hash" in output
    assert "      file type local key : python" in output
    assert "      file type namespace : test" in output
    assert "      processor local key : hash" in output
    assert "      processor namespace : test" in output
    assert "      file type desc      : Python source" in output
    assert "      processor desc      : Hash comments" in output


# ---- Markdown ----


def test_render_filetypes_markdown_compact_and_details() -> None:
    """Markdown file-type rendering should support compact and detailed tables."""
    compact_report = FileTypesHumanReport(
        show_details=False,
        verbosity_level=0,
        styled=False,
        items=(_filetype_item(),),
    )
    detail_report = FileTypesHumanReport(
        show_details=True,
        verbosity_level=0,
        styled=False,
        items=(_filetype_item(),),
    )

    compact_output: str = render_filetypes_markdown(compact_report)
    assert compact_output.startswith("# Supported File Types\n")
    assert _find_table_row(compact_output, "Qualified Key") == ["Qualified Key", "Description"]
    assert _find_table_row(compact_output, "`test.python`") == [
        "`test.python`",
        "Python source",
    ]

    detail_output: str = render_filetypes_markdown(detail_report)
    assert "## Legend" in detail_output
    assert _find_table_row(detail_output, "Qualified Key")[:4] == [
        "Qualified Key",
        "Local Key",
        "Namespace",
        "Bound",
    ]
    assert _find_table_row(detail_output, "`test.python`")[:4] == [
        "`test.python`",
        "`python`",
        "`test`",
        "**yes**",
    ]
    assert "**supports_shebang**=true" in detail_output


def test_render_processors_markdown_compact_and_details() -> None:
    """Markdown processor rendering should support compact and detailed tables."""
    compact_report = ProcessorsHumanReport(
        show_details=False,
        verbosity_level=0,
        processors=(_processor_item(),),
        styled=False,
    )
    detail_report = ProcessorsHumanReport(
        show_details=True,
        verbosity_level=0,
        processors=(_processor_item(bound=False),),
        styled=False,
    )

    compact_output: str = render_processors_markdown(compact_report)
    assert compact_output.startswith("# Supported Header Processors\n")
    assert _find_table_row(compact_output, "Qualified Key") == ["Qualified Key", "Description"]
    assert _find_table_row(compact_output, "`test.hash`") == [
        "`test.hash`",
        "Hash comments",
    ]

    detail_output: str = render_processors_markdown(detail_report)
    assert "## Legend" in detail_output
    assert _find_table_row(detail_output, "Qualified Key")[:4] == [
        "Qualified Key",
        "Local Key",
        "Namespace",
        "Bound",
    ]
    assert _find_table_row(detail_output, "`test.hash`")[:4] == [
        "`test.hash`",
        "`hash`",
        "`test`",
        "no",
    ]
    assert "Hash comments" in detail_output


def test_render_bindings_markdown_includes_unbound_and_unused_tables() -> None:
    """Markdown binding rendering should include optional unbound and unused tables."""
    report = BindingsHumanReport(
        show_details=False,
        verbosity_level=0,
        bindings=(_binding_item(),),
        unbound_filetypes=(UnboundFileTypeHumanItem(name="test.markdown", description="Markdown"),),
        unused_processors=(_processor_item(bound=False),),
        styled=False,
    )

    output: str = render_bindings_markdown(report)

    assert output.startswith("# Effective File-Type-to-Processor Bindings\n")
    assert _find_table_row(output, "File Type") == ["File Type", "Processor"]
    assert _find_table_row(output, "`test.python`") == ["`test.python`", "`test.hash`"]
    assert "## Unbound File Types" in output
    assert _find_table_row(output, "`test.markdown`") == ["`test.markdown`", "Markdown"]
    assert "## Unused Processors" in output
    assert _find_table_row(output, "`test.hash`") == ["`test.python`", "`test.hash`"]
    assert _find_table_row(output, "Hash comments") == ["`test.hash`", "Hash comments"]


def test_render_bindings_markdown_details_include_identity_components() -> None:
    """Detailed Markdown binding rendering should include identity components."""
    report = BindingsHumanReport(
        show_details=True,
        verbosity_level=0,
        bindings=(_binding_item(),),
        unbound_filetypes=(),
        unused_processors=(),
        styled=False,
    )

    output: str = render_bindings_markdown(report)

    assert _find_table_row(output, "File Type")[:6] == [
        "File Type",
        "Processor",
        "File Type Local Key",
        "File Type Namespace",
        "Processor Local Key",
        "Processor Namespace",
    ]
    assert _find_table_row(output, "`test.python`") == [
        "`test.python`",
        "`test.hash`",
        "`python`",
        "`test`",
        "`hash`",
        "`test`",
        "Python source",
        "Hash comments",
    ]


def test_build_filetypes_human_report_sorts_and_maps_policy(
    effective_registries: EffectiveRegistries,
) -> None:
    """Shared file-type report builder should sort items and map policy metadata."""
    alpha: FileType = make_file_type(
        local_key="alpha",
        namespace="test",
        description="Alpha type",
        extensions=[".a"],
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex="^# coding:",
            pre_header_blank_after_block=2,
            ensure_blank_after_header=False,
        ),
    )
    beta: FileType = make_file_type(
        local_key="beta",
        namespace="test",
        description="Beta type",
        extensions=[".b"],
    )

    with effective_registries(
        {"beta": beta, "alpha": alpha},
        {"alpha": _RegistryPresentationProcessor()},
    ):
        report: FileTypesHumanReport = build_filetypes_human_report(
            show_details=True,
            verbosity_level=2,
            styled=False,
        )

    assert [item.qualified_key for item in report.items] == ["test:alpha", "test:beta"]
    assert report.items[0].bound is True
    assert report.items[1].bound is False
    assert report.items[0].policy.supports_shebang is True
    assert report.items[0].policy.encoding_line_regex == "^# coding:"
    assert report.items[0].policy.pre_header_blank_after_block == 2
    assert report.items[0].policy.ensure_blank_after_header is False


def test_build_processors_human_report_sorts_and_marks_bound_processors(
    effective_registries: EffectiveRegistries,
) -> None:
    """Shared processor report builder should sort processors and mark bound state."""
    alpha: FileType = make_file_type(local_key="alpha", namespace="test", description="Alpha type")

    with effective_registries(
        {"alpha": alpha},
        {
            "alpha": _RegistryPresentationProcessor(),
            "unused": _UnusedRegistryPresentationProcessor(),
        },
    ):
        report: ProcessorsHumanReport = build_processors_human_report(
            show_details=True,
            verbosity_level=1,
            styled=False,
        )

    assert [item.qualified_key for item in report.processors] == [
        "test:registry-presentation",
        "test:registry-unused",
    ]
    assert report.processors[0].bound is True
    assert report.processors[1].bound is False
    assert report.processors[0].line_prefix == "#"
    assert report.processors[1].line_prefix == "//"


def test_build_bindings_human_report_lists_bindings_unbound_and_unused(
    effective_registries: EffectiveRegistries,
) -> None:
    """Shared binding report builder should expose bindings plus dangling registry state."""
    alpha: FileType = make_file_type(local_key="alpha", namespace="test", description="Alpha type")
    beta: FileType = make_file_type(local_key="beta", namespace="test", description="Beta type")

    with effective_registries(
        {"beta": beta, "alpha": alpha},
        {
            "alpha": _RegistryPresentationProcessor(),
            "unused": _UnusedRegistryPresentationProcessor(),
        },
    ):
        report: BindingsHumanReport = build_bindings_human_report(
            show_details=True,
            verbosity_level=1,
            styled=False,
        )

    assert [(item.file_type_key, item.processor_key) for item in report.bindings] == [
        ("test:alpha", "test:registry-presentation"),
    ]
    assert report.unbound_filetypes == (
        UnboundFileTypeHumanItem(name="test:beta", description="Beta type"),
    )
    assert [item.qualified_key for item in report.unused_processors] == ["test:registry-unused"]

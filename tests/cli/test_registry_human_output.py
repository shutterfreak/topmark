# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_human_output.py
#   file_relpath : tests/cli/test_registry_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI registry command human-output behavior tests.

This module verifies output-control behavior for the `topmark registry` command
family:
- compact and detailed TEXT output,
- Markdown output stability when TEXT-only verbosity is used,
- rejection of unsupported `--quiet` usage,
- deterministic rendering of filetypes, processors, and bindings.

These are output/applicability tests rather than pure exit-code contract tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

import pytest

from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_human_output_does_not_contain
from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.registry import make_file_type
from tests.helpers.registry import patched_effective_registries
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from click.testing import Result

    from topmark.filetypes.model import FileType


class BoundHumanRegistryProcessor(HeaderProcessor):
    """Processor bound to the test file type."""

    local_key: ClassVar[str] = "bound_processor"
    namespace: ClassVar[str] = "pytest"
    description: ClassVar[str] = "Processor bound to the test file type."


class UnusedHumanRegistryProcessor(HeaderProcessor):
    """Processor intentionally left unused."""

    local_key: ClassVar[str] = "unused_processor"
    namespace: ClassVar[str] = "pytest"
    description: ClassVar[str] = "Processor left intentionally unused."


pytestmark: pytest.MarkDecorator = pytest.mark.cli


@pytest.fixture
def registry_snapshot() -> Iterator[None]:
    """Patch a small deterministic registry for output rendering tests."""
    bound_filetype: FileType = make_file_type(
        local_key="bound_ft",
        namespace="pytest",
        description="Bound registry test file type.",
        extensions=[".bound"],
    )
    unbound_filetype: FileType = make_file_type(
        local_key="unbound_ft",
        namespace="pytest",
        description="Unbound registry test file type.",
        extensions=[".unbound"],
    )

    processors: dict[str, HeaderProcessor] = {
        "bound_ft": BoundHumanRegistryProcessor(
            line_prefix="# ",
            line_suffix="",
            line_indent="",
            block_prefix="",
            block_suffix="",
        ),
        "missing_ft": UnusedHumanRegistryProcessor(
            line_prefix="// ",
            line_suffix="",
            line_indent="",
            block_prefix="/*",
            block_suffix="*/",
        ),
    }

    with patched_effective_registries(
        filetypes={
            "bound_ft": bound_filetype,
            "unbound_ft": unbound_filetype,
        },
        processors=processors,
    ):
        yield


# --- TEXT output: filetypes ---


def test_registry_filetypes_text_output_is_compact_by_default(
    registry_snapshot: None,
) -> None:
    """Default TEXT filetypes output should render a compact view."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
        ]
    )

    assert_SUCCESS(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="pytest:bound_ft",
    )
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="pytest:unbound_ft",
    )
    assert_human_output_does_not_contain(
        output_format=None,
        output=result.output,
        expected="Extensions:",
    )


def test_registry_filetypes_text_verbose_shows_console_heading(
    registry_snapshot: None,
) -> None:
    """Verbose TEXT filetypes output should add a console-oriented heading."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
        ]
    )

    assert_SUCCESS(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="Supported file types (canonical identities):",
    )
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="pytest:bound_ft",
    )


def test_registry_filetypes_text_long_shows_details(
    registry_snapshot: None,
) -> None:
    """`registry filetypes --long` should add filetype details to TEXT output."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.SHOW_DETAILS,
        ]
    )

    assert_SUCCESS(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="pytest:bound_ft",
    )
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected=".bound",
    )


# --- Unsupported quiet mode ---


@pytest.mark.parametrize(
    "cmd",
    [
        CliCmd.REGISTRY_FILETYPES,
        CliCmd.REGISTRY_PROCESSORS,
        CliCmd.REGISTRY_BINDINGS,
    ],
)
def test_registry_commands_reject_quiet_option_for_text_output(
    cmd: str,
    registry_snapshot: None,
) -> None:
    """Registry subcommands should reject TEXT `--quiet` suppression."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
        ]
    )

    assert_rich_output_no_such_option(
        result,
        option_name=CliOpt.QUIET,
    )


# --- Markdown output: filetypes ---


def test_registry_filetypes_markdown_ignores_verbose(
    registry_snapshot: None,
) -> None:
    """Markdown filetypes output should ignore TEXT-only verbosity."""
    base: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )
    verbose: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_SUCCESS(base)
    assert_SUCCESS(verbose)
    assert verbose.output == base.output


def test_registry_filetypes_markdown_rejects_quiet_option(
    registry_snapshot: None,
) -> None:
    """Markdown filetypes output should reject unsupported `--quiet`."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_rich_output_no_such_option(
        result,
        option_name=CliOpt.QUIET,
    )


def test_registry_filetypes_markdown_long_shows_details(
    registry_snapshot: None,
) -> None:
    """`registry filetypes --long --output-format markdown` should show details."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            CliOpt.SHOW_DETAILS,
        ]
    )

    assert_SUCCESS(result)
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="# Supported File Types",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="pytest:bound_ft",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="Bound registry test file type.",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected=".bound",
    )


# --- Markdown output: processors and bindings ---


def test_registry_processors_markdown_ignores_verbose(
    registry_snapshot: None,
) -> None:
    """Markdown processors output should ignore TEXT-only verbosity."""
    base: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_PROCESSORS,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )
    verbose: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_PROCESSORS,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_SUCCESS(base)
    assert_SUCCESS(verbose)
    assert verbose.output == base.output


def test_registry_bindings_markdown_ignores_verbose(
    registry_snapshot: None,
) -> None:
    """Markdown bindings output should ignore TEXT-only verbosity."""
    base: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )
    verbose: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_SUCCESS(base)
    assert_SUCCESS(verbose)
    assert verbose.output == base.output


def test_registry_bindings_markdown_long_shows_binding_details(
    registry_snapshot: None,
) -> None:
    """`registry bindings --long --output-format markdown` should show details."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_BINDINGS,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
            CliOpt.SHOW_DETAILS,
        ]
    )

    assert_SUCCESS(result)
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="# Effective File-Type-to-Processor Bindings",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="pytest:bound_ft",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="pytest:bound_processor",
    )
    assert_human_output_contains(
        output_format=OutputFormat.MARKDOWN,
        output=result.output,
        expected="Bound registry test file type.",
    )

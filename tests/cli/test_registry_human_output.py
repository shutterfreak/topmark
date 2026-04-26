# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_human_output.py
#   file_relpath : tests/cli/test_registry_human_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for human-facing registry command output."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.conftest import parametrize
from tests.helpers.registry import make_file_type
from tests.helpers.registry import patched_effective_registries
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
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


pytestmark = pytest.mark.cli


@pytest.fixture
def registry_snapshot() -> Iterator[None]:
    """Patch a tiny deterministic effective registry for human-output tests."""
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


def test_registry_filetypes_text_output_is_compact_by_default(
    registry_snapshot: None,
) -> None:
    """TEXT filetypes output should render a compact default view."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
        ]
    )

    assert_SUCCESS(result)
    assert "pytest:bound_ft" in result.output
    assert "pytest:unbound_ft" in result.output
    assert "Extensions:" not in result.output


def test_registry_filetypes_text_verbose_shows_heading(
    registry_snapshot: None,
) -> None:
    """TEXT verbosity should add console-oriented headings."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
        ]
    )

    assert_SUCCESS(result)
    assert "Supported file types (canonical identities):" in result.output
    assert "pytest:bound_ft" in result.output


@parametrize(
    "cmd",
    [
        CliCmd.REGISTRY_FILETYPES,
        CliCmd.REGISTRY_PROCESSORS,
        CliCmd.REGISTRY_BINDINGS,
    ],
)
def test_registry_commands_do_not_accept_quiet(
    cmd: str,
    registry_snapshot: None,
) -> None:
    """Registry subcommands are informational and should not accept `--quiet`."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            cmd,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
        ]
    )

    assert result.exit_code != 0
    assert "No such option" in result.output
    assert CliOpt.QUIET in result.output


def test_registry_filetypes_text_long_shows_details(
    registry_snapshot: None,
) -> None:
    """`--long` should add registry detail to TEXT output."""
    result: Result = run_cli(
        [
            CliCmd.REGISTRY,
            CliCmd.REGISTRY_FILETYPES,
            CliOpt.NO_COLOR_MODE,
            CliOpt.SHOW_DETAILS,
        ]
    )

    assert_SUCCESS(result)
    assert "pytest:bound_ft" in result.output
    assert ".bound" in result.output


def test_registry_filetypes_markdown_ignores_verbose(
    registry_snapshot: None,
) -> None:
    """Markdown registry output should ignore TEXT-only verbosity."""
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


def test_registry_filetypes_markdown_does_not_accept_quiet(
    registry_snapshot: None,
) -> None:
    """Registry Markdown output should not expose `--quiet`."""
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

    assert result.exit_code != 0
    assert "No such option" in result.output
    assert CliOpt.QUIET in result.output


def test_registry_filetypes_markdown_long_shows_details(
    registry_snapshot: None,
) -> None:
    """`--long` should control Markdown filetype detail depth."""
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
    assert "# Supported File Types" in result.output
    assert "pytest:bound_ft" in result.output
    assert "Bound registry test file type." in result.output
    assert ".bound" in result.output


def test_registry_processors_markdown_ignores_verbose(
    registry_snapshot: None,
) -> None:
    """Markdown processor output should ignore TEXT-only verbosity."""
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
    """Markdown binding output should ignore TEXT-only verbosity."""
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


def test_registry_bindings_markdown_long_shows_details(
    registry_snapshot: None,
) -> None:
    """`--long` should control Markdown registry detail depth."""
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
    assert "# Effective File-Type-to-Processor Bindings" in result.output
    assert "pytest:bound_ft" in result.output
    assert "pytest:bound_processor" in result.output
    assert "Bound registry test file type." in result.output

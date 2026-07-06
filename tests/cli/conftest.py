# topmark:header:start
#
#   project      : TopMark
#   file         : conftest.py
#   file_relpath : tests/cli/conftest.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test helpers for running TopMark in a controlled working directory.

This module provides small utilities used across CLI tests. In particular,
`run_cli_in()` changes the process working directory to the given `tmp_path`
before invoking the Click CLI. This ensures that **relative** file patterns and
**globs** (e.g., "*.py") are resolved against the temporary test directory,
matching TopMark's resolver contract that disallows absolute patterns.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import IO
from typing import TYPE_CHECKING
from typing import Any
from typing import Final

import click
from click.testing import CliRunner
from click.testing import Result

from topmark.cli.main import cli
from topmark.cli.state import TopmarkCliState
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from collections.abc import Sequence


def run_cli_in(
    tmp_path: Path,
    argv: str | Sequence[str] | None,
    *,
    input_text: str | bytes | IO[Any] | None = None,
    prune_views: bool = False,
) -> Result:
    """Invoke the CLI with `tmp_path` as the working directory.

    This helper temporarily calls `os.chdir` to run the command from the
    provided temporary directory so that relative paths and glob patterns are
    evaluated against that directory. It mirrors how end users typically run the
    tool from a project root and avoids accidental reliance on absolute patterns.

    Args:
        tmp_path: Pytest-provided temporary directory used as the CWD for the
            command invocation.
        argv: CLI argument vector, e.g. `["--apply", "*.py"]`.
        input_text: Optional standard input to pass to the command.
            This can be a string, bytes, or a file-like object for `--stdin` modes.
        prune_views: If True, release consumed volatile views between pipeline steps.

    Returns:
        The `click.testing.Result` produced by `click.testing.CliRunner.invoke`.

    Example:
        ```python
        res = run_cli_in(tmp_path, ["--apply", "*.py"])  # relative glob in tmp_path
        assert res.exit_code == ExitCode.SUCCESS
        ```
    """
    runner = CliRunner()
    cwd: Path = Path.cwd()
    try:
        os.chdir(tmp_path)
        return runner.invoke(
            cli,
            argv,
            input=input_text,
            obj=TopmarkCliState(
                prune_pipeline_views=prune_views,
            ),  # inject typed CLI state into Click context (test override)
        )
    finally:
        os.chdir(cwd)


def run_cli(
    argv: str | Sequence[str] | None,
    *,
    input_text: str | bytes | IO[Any] | None = None,
    prune_views: bool = False,
) -> Result:
    """Invoke the CLI without changing the working directory.

    Use this helper when the test does **not** depend on files created in
    ``tmp_path`` (e.g., ``--help`` / ``--version``) or when all provided paths are
    absolute. For tests that pass **relative** paths or glob patterns and create
    files under ``tmp_path``, prefer `run_cli_in` so those paths resolve
    against the temporary directory.

    Args:
        argv: CLI argument vector, e.g. ``["--help"]`` or
            ``["--version"]``.
        input_text: Optional standard input to pass
            to the command. This can be a string, bytes, or a file-like object for
            ``--stdin`` modes.
        prune_views: If True, release consumed volatile views between pipeline steps.

    Returns:
        The `click.testing.Result` produced by `click.testing.CliRunner.invoke`.

    Example:
        ```python
        result = run_cli(["--help"])  # no filesystem interaction
        assert result.exit_code == ExitCode.SUCCESS
        ```
    """
    runner = CliRunner()
    return runner.invoke(
        cli,
        argv,
        input=input_text,
        obj=TopmarkCliState(
            prune_pipeline_views=prune_views,
        ),  # inject typed CLI state into Click context (test override)
    )


# --- Exit-code contract assertion helpers ---


# Tests that pin the public CLI exit-code contract should use
# pytest.mark.exit_code so they can be audited with:
# pytest -m exit_code


def assert_SUCCESS(result: Result) -> None:
    """Assert that the command exited successfully (code 0).

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.SUCCESS, result.output


def assert_FAILURE(result: Result) -> None:
    """Assert that the command exited with generic failure (code 1).

    This is a defensive fallback assertion for unexpected non-specific failures.
    Prefer a more specific helper such as `assert_CONFIG_ERROR`,
    `assert_IO_ERROR`, or `assert_FILE_NOT_FOUND` whenever the command contract
    defines a specific outcome.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.FAILURE, result.output


def assert_WOULD_CHANGE(result: Result) -> None:
    """Assert that the command exited with WOULD_CHANGE (code 3).

    `WOULD_CHANGE` is a normal dry-run outcome, not a runtime failure. TopMark
    intentionally uses code 3 so tests and scripts can distinguish this semantic
    change signal from Click parser-level usage errors, which use code 2.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    # WOULD_CHANGE is a normal TopMark outcome; Click parser usage errors use
    # raw exit code 2 and must be asserted with parser-error-specific helpers.
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output


def assert_SUCCESS_or_WOULD_CHANGE(result: Result) -> None:
    """Assert that the command exited with success or dry-run changes.

    This helper is intended for tests where both clean and would-change outcomes
    are acceptable, for example when a fixture may already be in the desired
    state.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code in [ExitCode.SUCCESS, ExitCode.WOULD_CHANGE], result.output


def assert_UNSUPPORTED_FILE_TYPE(result: Result) -> None:
    """Assert that the command exited with unsupported/unavailable input.

    Historically this maps to `ExitCode.UNSUPPORTED_FILE_TYPE`. For the CLI
    contract, this is used by commands such as `probe` when an explicitly
    requested input is unsupported, unresolved, or filtered.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.UNSUPPORTED_FILE_TYPE, result.output


def assert_USAGE_ERROR(result: Result) -> None:
    """Assert that the command exited with USAGE_ERROR (code 64).

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    # TopMark normalizes usage errors to the public USAGE_ERROR contract code.
    assert result.exit_code == ExitCode.USAGE_ERROR, result.output


def assert_CONFIG_ERROR(result: Result) -> None:
    """Assert that the command exited with a configuration error (code 78).

    This represents errors that prevent normal command execution, such as an
    unreadable, malformed, or otherwise unusable configuration file.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.CONFIG_ERROR, result.output


def assert_IO_ERROR(result: Result) -> None:
    """Assert that the command exited with an I/O error (code 74).

    This represents apply/write failures and other filesystem I/O failures that
    occur after command-line parsing and configuration loading have succeeded.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.IO_ERROR, result.output


def assert_PERMISSION_DENIED(result: Result) -> None:
    """Assert that the command exited with a permission error (code 77).

    This represents input/access permission failures detected by the pipeline,
    such as unreadable files or files/directories without required permissions.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.PERMISSION_DENIED, result.output


def assert_FILE_NOT_FOUND(result: Result) -> None:
    """Assert that the command exited with a file-not-found error (code 66).

    This represents missing input paths detected by the pipeline before normal
    processing can complete.

    Args:
        result: The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.FILE_NOT_FOUND, result.output


ANSI_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
"""ANSI control-sequence matcher used to normalize Rich-rendered test output."""


# --- Human-output assertion helpers ---


def _normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace for semantic CLI-output assertions."""
    return " ".join(text.split())


def _join_soft_wrapped_option_tokens(text: str) -> str:
    """Join Rich/Markdown soft wraps after hyphenated option-name fragments."""
    return re.sub(r"(?<=-)\s+(?=[A-Za-z0-9])", "", text)


# Rich/TEXT output ---------------------------------------------------------


def normalize_rich_cli_output(output: str) -> str:
    """Normalize Rich-rendered CLI output for semantic substring assertions.

    Rich panels and tables may wrap messages across lines, surround content with
    border glyphs, and emit ANSI control sequences depending on the terminal
    environment. Long option names may also soft-wrap after hyphens inside Rich
    table cells. These tests validate command behavior, not exact terminal
    layout, so this helper removes ANSI sequences and panel borders, collapses
    whitespace, and joins soft-wrapped hyphenated option tokens while preserving
    the rendered text content.
    """
    plain_output: str = ANSI_ESCAPE_RE.sub("", output)
    content_lines: list[str] = []
    for line in plain_output.splitlines():
        stripped: str = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("╭", "╰")):
            continue
        if stripped.startswith("│") and stripped.endswith("│"):
            stripped = stripped[1:-1].strip()
        elif stripped.startswith("│"):
            stripped = stripped[1:].strip()
        content_lines.append(stripped)

    return _join_soft_wrapped_option_tokens(_normalize_whitespace(" ".join(content_lines)))


def assert_rich_output_contains(
    output: str,
    *,
    expected: str,
) -> None:
    """Assert text appears in Rich-rendered CLI output.

    The comparison ignores Rich panel borders and line wrapping so tests remain
    focused on emitted diagnostic content.
    """
    normalized_output: str = normalize_rich_cli_output(output)
    normalized_expected: str = _normalize_whitespace(expected)
    assert normalized_expected in normalized_output


def assert_rich_output_does_not_contain(
    output: str,
    *,
    expected: str,
) -> None:
    """Assert text does not appear in Rich-rendered CLI output.

    The comparison ignores Rich panel borders and line wrapping so tests remain
    focused on emitted diagnostic content.
    """
    normalized_output: str = normalize_rich_cli_output(output)
    normalized_expected: str = _normalize_whitespace(expected)
    assert normalized_expected not in normalized_output


def assert_rich_output_contains_if(
    *,
    output: str,
    expected: str,
    expected_present: bool,
) -> None:
    """Assert conditional text visibility in Rich-rendered CLI output.

    Args:
        output: Rich-rendered CLI output to inspect.
        expected: String expected to appear or not appear in the output.
        expected_present: If True, assert that `expected` appears. If False,
            assert that `expected` does not appear.
    """
    if expected_present:
        assert_rich_output_contains(
            output=output,
            expected=expected,
        )
        return

    assert_rich_output_does_not_contain(
        output=output,
        expected=expected,
    )


# Markdown output ----------------------------------------------------------


def normalize_markdown_cli_output(output: str) -> str:
    """Normalize Markdown-rendered CLI output for semantic substring assertions.

    The comparison keeps Markdown syntax intact while ignoring layout-only line
    breaks and escaped hard line-break markers.
    """
    content_lines: list[str] = []
    for line in output.splitlines():
        stripped: str = line.strip()
        if not stripped:
            continue
        if stripped.endswith("\\"):
            stripped = stripped.rstrip("\\").rstrip()
        content_lines.append(stripped)

    return _normalize_whitespace(" ".join(content_lines))


def assert_markdown_output_contains(
    output: str,
    *,
    expected: str,
) -> None:
    """Assert text appears in Markdown-rendered CLI output."""
    normalized_output: str = normalize_markdown_cli_output(output)
    normalized_expected: str = _normalize_whitespace(expected)
    assert normalized_expected in normalized_output


def assert_markdown_output_does_not_contain(
    output: str,
    *,
    expected: str,
) -> None:
    """Assert text does not appear in Markdown-rendered CLI output."""
    normalized_output: str = normalize_markdown_cli_output(output)
    normalized_expected: str = _normalize_whitespace(expected)
    assert normalized_expected not in normalized_output


def assert_markdown_output_contains_if(
    *,
    output: str,
    expected: str,
    expected_present: bool,
) -> None:
    """Assert conditional text visibility in Markdown-rendered CLI output.

    Args:
        output: Markdown-rendered CLI output to inspect.
        expected: String expected to appear or not appear in the output.
        expected_present: If True, assert that `expected` appears. If False,
            assert that `expected` does not appear.
    """
    if expected_present:
        assert_markdown_output_contains(
            output=output,
            expected=expected,
        )
        return

    assert_markdown_output_does_not_contain(
        output=output,
        expected=expected,
    )


# Format-aware human-output facade ----------------------------------------


def assert_human_output_contains(
    *,
    output_format: OutputFormat | None,
    output: str,
    expected: str,
) -> None:
    """Assert text appears in human-readable CLI output.

    Args:
        output_format: Human output format requested by the test. `None` means
            the CLI default, currently equivalent to `OutputFormat.TEXT`.
        output: CLI output to inspect.
        expected: String expected to appear in the output.

    Raises:
        ValueError: If `output_format` is not a human-readable output format.
    """
    match output_format:
        case None | OutputFormat.TEXT:
            assert_rich_output_contains(
                output=output,
                expected=expected,
            )
        case OutputFormat.MARKDOWN:
            assert_markdown_output_contains(
                output=output,
                expected=expected,
            )
        case _:
            msg: str = f"Invalid human output format specified: {output_format!r}"
            raise ValueError(msg)


def assert_human_output_does_not_contain(
    *,
    output_format: OutputFormat | None,
    output: str,
    expected: str,
) -> None:
    """Assert text does not appear in human-readable CLI output.

    Args:
        output_format: Human output format requested by the test. `None` means
            the CLI default, currently equivalent to `OutputFormat.TEXT`.
        output: CLI output to inspect.
        expected: String expected not to appear in the output.

    Raises:
        ValueError: If `output_format` is not a human-readable output format.
    """
    match output_format:
        case None | OutputFormat.TEXT:
            assert_rich_output_does_not_contain(
                output=output,
                expected=expected,
            )
        case OutputFormat.MARKDOWN:
            assert_markdown_output_does_not_contain(
                output=output,
                expected=expected,
            )
        case _:
            msg: str = f"Invalid human output format specified: {output_format!r}"
            raise ValueError(msg)


def assert_human_format_does_not_contain(
    *,
    output_format: OutputFormat | None,
    output: str,
    expected: str,
) -> None:
    """Assert text is absent from human-readable CLI output.

    This compatibility wrapper keeps the `human_format` spelling available for
    tests that want to emphasize the selected output format. Prefer
    `assert_human_output_does_not_contain` for new assertions.
    """
    assert_human_output_does_not_contain(
        output_format=output_format,
        output=output,
        expected=expected,
    )


def assert_human_output_contains_if(
    *,
    output_format: OutputFormat | None,
    output: str,
    expected: str,
    expected_present: bool,
) -> None:
    """Assert conditional text visibility in human-readable CLI output.

    Args:
        output_format: Human output format requested by the test. `None` means
            the CLI default, currently equivalent to `OutputFormat.TEXT`.
        output: CLI output to inspect.
        expected: String expected to appear or not appear in the output.
        expected_present: If True, assert that `expected` appears. If False,
            assert that `expected` does not appear.

    Raises:
        ValueError: If `output_format` is not a human-readable output format.
    """
    if expected_present:
        assert_human_output_contains(
            output_format=output_format,
            output=output,
            expected=expected,
        )
        return

    assert_human_output_does_not_contain(
        output_format=output_format,
        output=output,
        expected=expected,
    )


# Domain-specific human-output assertions ----------------------------------


FILE_TYPE_OVERLAP_WARNING_PREFIX: Final[str] = (
    "File types specified in both include and exclude filters; exclusion wins:"
)
"""Stable prefix for strict include/exclude file-type overlap diagnostics."""


def assert_strict_file_type_overlap_warning(
    result: Result,
    *,
    output_format: OutputFormat | None,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """Assert strict file-type overlap output includes actionable diagnostics.

    This helper verifies the semantic contract for strict include/exclude
    file-type overlap handling without depending on incidental Rich or Markdown
    layout. The diagnostic prefix and each removed file type are asserted
    separately so line wrapping, panel borders, and punctuation around the
    rendered list do not make the test brittle.

    Args:
        result: CLI result returned by `run_cli` or `run_cli_in`.
        output_format: Human output format requested by the test. `None` means
            the CLI default, currently equivalent to `OutputFormat.TEXT`.
        expected_removed_file_types: File-type labels expected to be removed
            from the include filter because the exclude filter wins.
    """
    assert_CONFIG_ERROR(result)
    assert_human_output_contains(
        output_format=output_format,
        output=result.output,
        expected=FILE_TYPE_OVERLAP_WARNING_PREFIX,
    )
    for expected_removed_file_type in expected_removed_file_types:
        assert_human_output_contains(
            output_format=output_format,
            output=result.output,
            expected=expected_removed_file_type,
        )


# Parser-level Rich Click assertions ---------------------------------------


CLICK_USAGE_ERROR_EXIT_CODE: Final[int] = 2
"""Raw exit code used by Click for parser-level usage errors."""


def assert_rich_output_no_such_option(
    result: Result,
    *,
    option_name: str,
    valid_option_name: str | None = None,
) -> None:
    """Assert that Rich Click reported an unknown CLI option.

    Click parser-level usage errors (for example, unknown commands, unknown options
    options or invalid option values) may exit with code `2` before command logic runs.
    TopMark intentionally does not assign code 2 to a semantic outcome; `WOULD_CHANGE`
    uses code 3 instead. This helper therefore asserts both the Click-owned code
    and the rendered `No such option` diagnostic.

    Args:
        result: the captured result of an invoked CLI script.
        option_name: Full invalid option spelling, including its hyphen prefix.
        valid_option_name: Optional full valid option spelling, including its hyphen prefix.
    """
    # Click handles the parser error and `CliRunner` captures the resulting
    # `SystemExit(2)`, not the original `click.NoSuchOption` instance. The
    # rendered diagnostic distinguishes this parser-level failure from
    # TopMark-owned semantic outcomes such as WOULD_CHANGE (code 3).
    assert result.exit_code == CLICK_USAGE_ERROR_EXIT_CODE, result.output

    # Use the message format used by `rich-click`:
    assert_rich_output_contains(
        result.output,
        expected=f"No such option '{option_name}'.",
    )
    if valid_option_name:
        assert_rich_output_contains(
            result.output,
            expected=f"Did you mean '{valid_option_name}'?",
        )


def command_option_names(command_name: str) -> set[str]:
    """Return all option declarations exposed by a CLI subcommand.

    Rich Click may wrap long option names inside rendered help tables, so tests
    that validate option exposure should inspect the Click command model instead
    of asserting on terminal layout. The helper creates a lightweight Click
    context explicitly because no global current context exists after
    `CliRunner.invoke` has returned.
    """
    ctx = click.Context(cli, info_name="topmark")
    command: click.Command | None = cli.get_command(ctx, cmd_name=command_name)
    assert command is not None

    option_names: set[str] = set()
    for parameter in command.params:
        option_names.update(parameter.opts)
        option_names.update(parameter.secondary_opts)
    return option_names

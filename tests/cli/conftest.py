# topmark:header:start
#
#   file         : conftest.py
#   file_relpath : tests/cli/conftest.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test helpers for running TopMark in a controlled working directory.

This module provides small utilities used across CLI tests. In particular,
`run_in()` changes the process working directory to the given `tmp_path`
before invoking the Click CLI. This ensures that **relative** file patterns and
**globs** (e.g., "*.py") are resolved against the temporary test directory,
matching TopMark's resolver contract that disallows absolute patterns.
"""

import os
from pathlib import Path
from typing import IO, Any, Sequence

from click.testing import CliRunner, Result

from topmark.cli.main import cli
from topmark.cli_shared.exit_codes import ExitCode


def run_cli_in(
    tmp_path: Path,
    argv: str | Sequence[str] | None,
    *,
    input_text: str | bytes | IO[Any] | None = None,
) -> Result:
    """Invoke the CLI with `tmp_path` as the working directory.

    This helper temporarily calls `os.chdir` to run the command from the
    provided temporary directory so that relative paths and glob patterns are
    evaluated against that directory. It mirrors how end users typically run the
    tool from a project root and avoids accidental reliance on absolute patterns.

    Args:
        tmp_path (Path): Pytest-provided temporary directory used as the CWD for the
            command invocation.
        argv (str | Sequence[str] | None): CLI argument vector, e.g. `["--apply", "*.py"]`.
        input_text (str | bytes | IO[Any] | None): Optional standard input to pass to the command.
            This can be a string, bytes, or a file-like object for `--stdin` modes.

    Returns:
        Result: The `click.testing.Result` produced by
            `click.testing.CliRunner.invoke`.

    Example:
        ```python
        res = run_cli_in(tmp_path, ["--apply", "*.py"])  # relative glob in tmp_path
        assert res.exit_code == ExitCode.SUCCESS
        ```
    """
    runner = CliRunner()
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        return runner.invoke(cli, argv, input=input_text)
    finally:
        os.chdir(cwd)


def run_cli(
    argv: str | Sequence[str] | None,
    *,
    input_text: str | bytes | IO[Any] | None = None,
) -> Result:
    """Invoke the CLI without changing the working directory.

    Use this helper when the test does **not** depend on files created in
    ``tmp_path`` (e.g., ``--help`` / ``--version``) or when all provided paths are
    absolute. For tests that pass **relative** paths or glob patterns and create
    files under ``tmp_path``, prefer `run_cli_in` so those paths resolve
    against the temporary directory.

    Args:
        argv (str | Sequence[str] | None): CLI argument vector, e.g. ``["--help"]`` or
            ``["--version"]``.
        input_text (str | bytes | IO[Any] | None): Optional standard input to pass
            to the command. This can be a string, bytes, or a file-like object for
            ``--stdin`` modes.

    Returns:
        Result: The `click.testing.Result` produced by
            `click.testing.CliRunner.invoke`.

    Example:
        ```python
        result = run_cli(tmp_path, ["--help"])  # no filesystem interaction
        assert result.exit_code == ExitCode.SUCCESS
        ```
    """
    runner = CliRunner()
    return runner.invoke(cli, argv, input=input_text)


def assert_SUCCESS(result: Result) -> None:
    """Assert that the command exited successfully (code 0).

    Args:
        result (Result): The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code == ExitCode.SUCCESS, result.output


def assert_WOULD_CHANGE(result: Result) -> None:
    """Assert that the command exited with WOULD_CHANGE (code 2).

    Args:
        result (Result): The Result object returned by `run_cli` or `run_cli_in`.
    """
    # WOULD_CHANGE is a *normal* outcome; do not assert on exception.
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output


def assert_SUCCESS_or_WOULD_CHANGE(result: Result) -> None:
    """Assert that the command exited successfully (code 0).

    Args:
        result (Result): The Result object returned by `run_cli` or `run_cli_in`.
    """
    assert result.exit_code in [ExitCode.SUCCESS, ExitCode.WOULD_CHANGE], result.output


def assert_USAGE_ERROR(result: Result) -> None:
    """Assert that the command exited with USAGE_ERROR (code 64).

    Args:
        result (Result): The Result object returned by `run_cli` or `run_cli_in`.
    """
    # Your CLI returns USAGE_ERROR=64; Click’s UsageError type may be present.
    assert result.exit_code == ExitCode.USAGE_ERROR, result.output

# topmark:header:start
#
#   project      : TopMark
#   file         : test_version.py
#   file_relpath : tests/cli/test_version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI version command output and option behavior tests.

This module verifies human-facing `topmark version` behavior:
- default PEP 440 output,
- SemVer rendering with `--semver`,
- Markdown output stability,
- rejection of unsupported `--quiet` usage.

These are output/behavior tests rather than pure exit-code contract tests.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import click
import pytest
from packaging.version import InvalidVersion
from packaging.version import Version

import topmark.cli.commands.version as version_module
from tests.cli.conftest import assert_rich_output_no_such_option
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.pipeline import unsupported_output_format
from tests.helpers.version import SEMVER_RE
from topmark.cli.commands.version import version_command
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_VERSION
from topmark.utils.version import convert_pep440_to_semver

if TYPE_CHECKING:
    from click.testing import Result

    from topmark.core.formats import OutputFormat


# --- Plain TEXT output ---


def test_version_outputs_pep440_version_by_default() -> None:
    """`version` should output the PEP 440 project version by default."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,  # Disable color mode for RE pattern matching
        ]
    )

    assert_SUCCESS(result)

    out: str = result.output.strip()
    # Default TEXT output is the exact PEP 440 project version.
    assert out == TOPMARK_VERSION

    # Validate that the emitted token is valid PEP 440.
    try:
        Version(out)  # raises InvalidVersion if not PEP 440
    except InvalidVersion as exc:
        pytest.fail(f"Not a valid PEP 440 version: {out!r} ({exc})")


def test_version_text_output_skips_empty_renderer_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TEXT output should avoid printing a blank line if rendering returns nothing."""

    def _report(value: str) -> str:
        return ""

    monkeypatch.setattr(version_module, "render_version_text", _report)

    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
        ]
    )

    assert_SUCCESS(result)
    assert result.output == ""


def test_version_semver_flag_outputs_semver_version() -> None:
    """`version --semver` should output the SemVer-rendered version."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,  # Disable color mode for RE pattern matching
            CliOpt.SEMVER_VERSION,
        ]
    )

    assert_SUCCESS(result)

    out: str = result.output.strip()
    expected: str = convert_pep440_to_semver(TOPMARK_VERSION)

    # Exact mapping check: CLI output should equal the shared conversion helper.
    assert out == expected

    # Validate the rendered SemVer token against the shared relaxed SemVer pattern.
    assert re.fullmatch(SEMVER_RE, out) is not None


# --- Unsupported quiet mode ---


def test_version_rejects_quiet_option_for_text_output() -> None:
    """`version --quiet` should be rejected because version emits pure content."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
        ]
    )

    assert_rich_output_no_such_option(
        result,
        option_name=CliOpt.QUIET,
    )


def test_version_rejects_quiet_option_with_markdown_output() -> None:
    """`version --quiet --output-format markdown` should also be rejected."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
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


# --- Markdown output ---


def test_version_verbose_does_not_change_markdown_output() -> None:
    """`version -v --output-format markdown` should match non-verbose Markdown."""
    base_result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )
    verbose_result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "markdown",
        ]
    )

    assert_SUCCESS(base_result)
    assert_SUCCESS(verbose_result)
    assert verbose_result.output == base_result.output


@pytest.mark.parametrize("use_semver", [False, True])
def test_version_markdown_format_contains_expected_version(use_semver: bool) -> None:
    """Markdown output should contain the expected PEP 440 or SemVer version."""
    args: list[str] = [
        CliCmd.VERSION,
        CliOpt.NO_COLOR_MODE,
        CliOpt.OUTPUT_FORMAT,
        "markdown",
    ]
    if use_semver:
        args.append(CliOpt.SEMVER_VERSION)

    result: Result = run_cli(args)
    assert_SUCCESS(result)

    out: str = result.output.strip()
    assert out, "Markdown output must not be empty"

    assert "# TopMark Version" in out

    if use_semver:
        expected: str = convert_pep440_to_semver(TOPMARK_VERSION)
        # Do not over-specify Markdown formatting around the value.
        assert expected in out
        # Validate the version token itself, not the whole Markdown block.
        assert re.fullmatch(SEMVER_RE, expected) is not None
    else:
        assert TOPMARK_VERSION in out
        # Validate the expected version token as PEP 440 without over-specifying Markdown.
        candidate: str = TOPMARK_VERSION
        try:
            Version(candidate)
        except InvalidVersion as exc:
            pytest.fail(f"Markdown does not contain a valid PEP 440 version: {candidate!r} ({exc})")


def test_version_command_rejects_invalid_direct_output_format() -> None:
    """Direct callback use with an invalid format should fail closed consistently."""
    ctx = click.Context(version_command)
    invalid_format: OutputFormat = unsupported_output_format("fake_format")

    with ctx, pytest.raises(ValueError, match="Unsupported machine-readable output format"):
        version_command.callback(  # pyright: ignore[reportOptionalCall]
            verbosity=0,
            color_mode=None,
            no_color=True,
            semver=False,
            output_format=invalid_format,
        )

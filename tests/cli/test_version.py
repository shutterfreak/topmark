# topmark:header:start
#
#   project      : TopMark
#   file         : test_version.py
#   file_relpath : tests/cli/test_version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI tests for human-facing `topmark version` output."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from packaging.version import InvalidVersion
from packaging.version import Version

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.version import SEMVER_RE
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.constants import TOPMARK_VERSION
from topmark.utils.version import convert_pep440_to_semver

if TYPE_CHECKING:
    from click.testing import Result


def test_version_outputs_pep440_version() -> None:
    """It should output the PEP 440 version string (exact match)."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,  # Disable color mode for RE pattern matching
        ]
    )

    assert_SUCCESS(result)

    out: str = result.output.strip()
    # Contract: default 'version' prints the PEP 440 project version exactly
    assert out == TOPMARK_VERSION

    # Validate it's a valid PEP 440 version
    try:
        Version(out)  # raises InvalidVersion if not PEP 440
    except InvalidVersion as exc:
        pytest.fail(f"Not a valid PEP 440 version: {out!r} ({exc})")


def test_version_with_semver_flag_outputs_semver() -> None:
    """It should output the SemVer-rendered version string with --semver."""
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

    # 1) Exact mapping check: CLI output should equal our conversion helper
    assert out == expected

    # 2) Validate the rendered SemVer token against the shared relaxed SemVer pattern.
    assert re.fullmatch(SEMVER_RE, out) is not None


@pytest.mark.parametrize("use_semver", [False, True])
def test_version_markdown_format(use_semver: bool) -> None:
    """`version --output-format markdown` prints the correct version in human output."""
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

    out = result.output.strip()
    assert out, "Markdown output must not be empty"

    if use_semver:
        expected: str = convert_pep440_to_semver(TOPMARK_VERSION)
        assert expected in out  # don’t over-specify formatting around the value
        # Validate the version token itself (not the whole markdown block)
        assert re.fullmatch(SEMVER_RE, expected) is not None
    else:
        assert TOPMARK_VERSION in out
        # Extract the first version-like token and validate it’s PEP 440.
        # We keep this flexible in case the markdown includes code spans or prefixes.
        # Fallback: use the exact TOPMARK_VERSION we already saw in the string.
        candidate: str = TOPMARK_VERSION
        try:
            Version(candidate)
        except InvalidVersion as exc:
            pytest.fail(f"Markdown does not contain a valid PEP 440 version: {candidate!r} ({exc})")

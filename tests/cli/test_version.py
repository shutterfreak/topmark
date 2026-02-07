# topmark:header:start
#
#   project      : TopMark
#   file         : test_version.py
#   file_relpath : tests/cli/test_version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: `version` command output."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, cast

import pytest
from packaging.version import InvalidVersion, Version

from tests.cli.conftest import assert_SUCCESS, run_cli
from topmark.cli.keys import CliCmd, CliOpt
from topmark.constants import TOPMARK_VERSION
from topmark.utils.version import convert_pep440_to_semver

if TYPE_CHECKING:
    from click.testing import Result

_SEMVER_RE: re.Pattern[str] = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z.-]+)?$"
)


def test_version_outputs_pep440_version() -> None:
    """It should output the PEP 440 version string (exact match)."""
    result: Result = run_cli(
        [
            CliOpt.NO_COLOR_MODE,  # Disable color mode for RE pattern matching
            CliCmd.VERSION,
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
            CliOpt.NO_COLOR_MODE,  # Disable color mode for RE pattern matching
            CliCmd.VERSION,
            CliOpt.SEMVER_VERSION,
        ]
    )

    assert_SUCCESS(result)

    out: str = result.output.strip()
    expected: str = convert_pep440_to_semver(TOPMARK_VERSION)

    # 1) Exact mapping check: CLI output should equal our conversion helper
    assert out == expected

    # 2) SemVer-ish format check (relaxed):
    #    X.Y.Z
    #    X.Y.Z-<ident>(.<ident>)*   (pre/dev like rc.N, alpha.N, dev.N)
    #    X.Y.Z+<build>(.<build>)*   (optional build metadata)
    assert re.fullmatch(_SEMVER_RE, out) is not None


@pytest.mark.parametrize("use_semver", [False, True])
def test_version_json_format(use_semver: bool) -> None:
    """`version --output-format json` returns parseable JSON with a correct version value."""
    args: list[str] = [CliOpt.NO_COLOR_MODE, CliCmd.VERSION, CliOpt.OUTPUT_FORMAT, "json"]
    if use_semver:
        args.append(CliOpt.SEMVER_VERSION)

    result: Result = run_cli(args)
    assert_SUCCESS(result)

    # Must be valid JSON
    try:
        payload = json.loads(result.output)
    except json.JSONDecodeError as exc:  # pragma: no cover - clearer error
        raise AssertionError(f"Output is not valid JSON: {exc}\nRAW:\n{result.output}") from exc

    assert isinstance(payload, dict), "JSON payload must be an object"

    # Envelope shape: {"meta": {...}, "version_info": {"version": ..., "version_format": ...}}
    assert "meta" in payload and isinstance(payload["meta"], dict)
    assert "version_info" in payload and isinstance(payload["version_info"], dict)

    version_info = cast("dict[str, object]", payload["version_info"])
    assert "version" in version_info, "JSON payload must contain version_info.version"
    assert "version_format" in version_info, "JSON payload must contain version_info.version_format"

    out: str = cast("str", version_info["version"]).strip()
    out_fmt: str = cast("str", version_info["version_format"]).strip().lower()

    if use_semver:
        expected: str = convert_pep440_to_semver(TOPMARK_VERSION)
        assert out == expected
        assert out_fmt == "semver"
        assert re.fullmatch(_SEMVER_RE, out) is not None
    else:
        assert out == TOPMARK_VERSION
        assert out_fmt == "pep440"
        # Validate PEP 440
        try:
            Version(out)
        except InvalidVersion as exc:
            pytest.fail(f"Not a valid PEP 440 version: {out!r} ({exc})")


@pytest.mark.parametrize("use_semver", [False, True])
def test_version_markdown_format(use_semver: bool) -> None:
    """`version --output-format markdown` prints a readable line with the correct version."""
    args: list[str] = [CliOpt.NO_COLOR_MODE, CliCmd.VERSION, CliOpt.OUTPUT_FORMAT, "markdown"]
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
        assert re.fullmatch(_SEMVER_RE, expected) is not None
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

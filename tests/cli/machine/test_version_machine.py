# topmark:header:start
#
#   project      : TopMark
#   file         : test_version_machine.py
#   file_relpath : tests/cli/machine/test_version_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI machine-output tests for `topmark version`."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from packaging.version import InvalidVersion
from packaging.version import Version

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_single_ndjson_record
from tests.helpers.version import SEMVER_RE
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.constants import TOPMARK_VERSION
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_mapping
from topmark.utils.version import convert_pep440_to_semver

if TYPE_CHECKING:
    from click.testing import Result


@pytest.mark.parametrize("use_semver", [False, True])
def test_version_json_format(use_semver: bool) -> None:
    """`version --output-format json` returns a valid machine payload."""
    args: list[str] = [
        CliCmd.VERSION,
        CliOpt.NO_COLOR_MODE,
        CliOpt.OUTPUT_FORMAT,
        "json",
    ]
    if use_semver:
        args.append(CliOpt.SEMVER_VERSION)

    result: Result = run_cli(args)
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)

    # Envelope shape: {"meta": {...}, "version_info": {"version": ..., "version_format": ...}}
    assert "meta" in payload and is_mapping(payload["meta"])

    assert "version_info" in payload
    assert is_mapping(payload["version_info"])

    version_info: dict[str, object] = as_object_dict(payload["version_info"])

    version_obj: object | None = version_info.get("version")
    format_obj: object | None = version_info.get("version_format")
    assert isinstance(version_obj, str)
    assert isinstance(format_obj, str)

    out: str = version_obj.strip()
    out_fmt: str = format_obj.strip().lower()

    if use_semver:
        expected: str = convert_pep440_to_semver(TOPMARK_VERSION)
        assert out == expected
        assert out_fmt == "semver"
        # 2) Validate the rendered SemVer token against the shared relaxed SemVer pattern.
        assert re.fullmatch(SEMVER_RE, out) is not None
    else:
        assert out == TOPMARK_VERSION
        assert out_fmt == "pep440"
        # Validate PEP 440
        try:
            Version(out)
        except InvalidVersion as exc:
            pytest.fail(f"Not a valid PEP 440 version: {out!r} ({exc})")


def test_version_quiet_does_not_suppress_json_output() -> None:
    """`version --quiet --output-format json` should still emit machine output."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)
    assert "version_info" in payload
    assert is_mapping(payload["version_info"])

    version_info: dict[str, object] = as_object_dict(payload["version_info"])
    assert version_info.get("version") == TOPMARK_VERSION
    assert version_info.get("version_format") == "pep440"


def test_version_verbose_does_not_change_json_output() -> None:
    """`version -v --output-format json` should emit clean machine output."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "json",
        ]
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_json_object(result.output)
    assert "version_info" in payload
    assert is_mapping(payload["version_info"])

    version_info: dict[str, object] = as_object_dict(payload["version_info"])
    assert version_info.get("version") == TOPMARK_VERSION
    assert version_info.get("version_format") == "pep440"


@pytest.mark.parametrize("use_semver", [False, True])
def test_version_ndjson_format(use_semver: bool) -> None:
    """`version --output-format ndjson` returns a valid machine record."""
    args: list[str] = [
        CliCmd.VERSION,
        CliOpt.NO_COLOR_MODE,
        CliOpt.OUTPUT_FORMAT,
        "ndjson",
    ]
    if use_semver:
        args.append(CliOpt.SEMVER_VERSION)

    result: Result = run_cli(args)
    assert_SUCCESS(result)

    payload: dict[str, object] = parse_single_ndjson_record(result.output)

    assert payload.get("kind") == "version"

    meta: dict[str, object] = assert_ndjson_meta(
        payload.get("meta"),
        expected_detail_level="brief",
    )
    assert meta.get("version") == TOPMARK_VERSION

    version_obj: object | None = payload.get("version")
    assert is_mapping(version_obj)
    version_info: dict[str, object] = as_object_dict(version_obj)

    rendered_version_obj: object | None = version_info.get("version")
    format_obj: object | None = version_info.get("version_format")
    assert isinstance(rendered_version_obj, str)
    assert isinstance(format_obj, str)

    out: str = rendered_version_obj.strip()
    out_fmt: str = format_obj.strip().lower()

    if use_semver:
        expected: str = convert_pep440_to_semver(TOPMARK_VERSION)
        assert out == expected
        assert out_fmt == "semver"
        assert re.fullmatch(SEMVER_RE, out) is not None
    else:
        assert out == TOPMARK_VERSION
        assert out_fmt == "pep440"
        try:
            Version(out)
        except InvalidVersion as exc:
            pytest.fail(f"Not a valid PEP 440 version: {out!r} ({exc})")


def test_version_quiet_does_not_suppress_ndjson_output() -> None:
    """`version --quiet --output-format ndjson` should still emit machine output."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
            CliOpt.QUIET,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_single_ndjson_record(result.output)
    assert payload.get("kind") == "version"

    version_obj: object | None = payload.get("version")
    assert is_mapping(version_obj)
    version_info: dict[str, object] = as_object_dict(version_obj)
    assert version_info.get("version") == TOPMARK_VERSION
    assert version_info.get("version_format") == "pep440"


def test_version_verbose_does_not_change_ndjson_output() -> None:
    """`version -v --output-format ndjson` should emit clean machine output."""
    result: Result = run_cli(
        [
            CliCmd.VERSION,
            CliOpt.NO_COLOR_MODE,
            CliOpt.VERBOSE,
            CliOpt.OUTPUT_FORMAT,
            "ndjson",
        ]
    )

    assert_SUCCESS(result)

    payload: dict[str, object] = parse_single_ndjson_record(result.output)
    assert payload.get("kind") == "version"

    version_obj: object | None = payload.get("version")
    assert is_mapping(version_obj)
    version_info: dict[str, object] = as_object_dict(version_obj)
    assert version_info.get("version") == TOPMARK_VERSION
    assert version_info.get("version_format") == "pep440"

# topmark:header:start
#
#   project      : TopMark
#   file         : test_hard_link_identity_machine.py
#   file_relpath : tests/cli/machine/test_hard_link_identity_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output regressions for hard-linked processing targets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_SUCCESS_or_WOULD_CHANGE
from tests.cli.conftest import assert_UNSUPPORTED_FILE_TYPE
from tests.cli.conftest import run_cli_in
from tests.helpers.json import parse_json_object
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.formats import OutputFormat
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import FsStatus
from topmark.resolution.probe import ResolutionProbeReason
from topmark.resolution.probe import ResolutionProbeStatus

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def _link_or_skip(source: Path, target: Path) -> None:
    """Create a hard link or skip when the current filesystem forbids it."""
    try:
        os.link(source, target)
    except OSError as exc:
        pytest.skip(f"hard links are not supported in this test environment: {exc}")


def _results(payload: dict[str, object]) -> list[dict[str, object]]:
    """Return typed processing result payloads."""
    results_obj: object = payload["results"]
    assert is_any_list(results_obj)
    return [as_object_dict(item) for item in results_obj if is_mapping(item)]


def _status_fs(result: dict[str, object]) -> str:
    """Return the filesystem status value from a processing result payload."""
    status_obj: object = result["status"]
    assert is_mapping(status_obj)
    status: dict[str, object] = as_object_dict(status_obj)
    fs_obj: object = status["fs"]
    assert is_mapping(fs_obj)
    fs: dict[str, object] = as_object_dict(fs_obj)
    label: object = fs["label"]
    assert isinstance(label, str)
    return label


@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
def test_processing_json_blocks_hard_link_pair(tmp_path: Path, command: str) -> None:
    """`check` and `strip` emit one blocked result per hard-linked selected path."""
    first: Path = tmp_path / "a.py"
    second: Path = tmp_path / "b.py"
    first.write_text("print('hello')\n", encoding="utf-8")
    _link_or_skip(first, second)

    result: Result = run_cli_in(
        tmp_path,
        [
            command,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            "a.py",
            "b.py",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    results: list[dict[str, object]] = _results(payload)

    assert len(results) == 2
    assert [_status_fs(item) for item in results] == [
        FsStatus.HARD_LINK_DUPLICATE.value,
        FsStatus.HARD_LINK_DUPLICATE.value,
    ]


def test_processing_json_continues_after_hard_link_block(tmp_path: Path) -> None:
    """A normal selected file still appears as a normal result beside blocked hard links."""
    first: Path = tmp_path / "a.py"
    second: Path = tmp_path / "b.py"
    normal: Path = tmp_path / "normal.py"
    first.write_text("print('hello')\n", encoding="utf-8")
    normal.write_text("print('normal')\n", encoding="utf-8")
    _link_or_skip(first, second)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            "a.py",
            "normal.py",
            "b.py",
        ],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    results: list[dict[str, object]] = _results(payload)
    statuses_by_path: dict[str, str] = {str(item["path"]): _status_fs(item) for item in results}

    assert statuses_by_path["a.py"] == FsStatus.HARD_LINK_DUPLICATE.value
    assert statuses_by_path["b.py"] == FsStatus.HARD_LINK_DUPLICATE.value
    assert statuses_by_path["normal.py"] == FsStatus.OK.value


def test_probe_json_reports_hard_links_as_unsupported(tmp_path: Path) -> None:
    """`probe` reports hard-linked processing targets as unsupported probe results."""
    first: Path = tmp_path / "a.py"
    second: Path = tmp_path / "b.py"
    first.write_text("print('hello')\n", encoding="utf-8")
    _link_or_skip(first, second)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.PROBE,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.JSON.value,
            "a.py",
            "b.py",
        ],
    )
    assert_UNSUPPORTED_FILE_TYPE(result)

    payload: dict[str, object] = parse_json_object(result.output)
    probes_obj: object = payload["probes"]
    assert is_any_list(probes_obj)
    probes: list[dict[str, object]] = [
        as_object_dict(item) for item in probes_obj if is_mapping(item)
    ]

    assert len(probes) == 2
    assert {probe["status"] for probe in probes} == {ResolutionProbeStatus.UNSUPPORTED.value}
    assert {probe["reason"] for probe in probes} == {
        ResolutionProbeReason.HARD_LINK_DUPLICATE.value
    }


def test_processing_ndjson_contains_hard_link_hint_code(tmp_path: Path) -> None:
    """NDJSON detail mode preserves one result per blocked selected path."""
    first: Path = tmp_path / "a.py"
    second: Path = tmp_path / "b.py"
    first.write_text("print('hello')\n", encoding="utf-8")
    _link_or_skip(first, second)

    result: Result = run_cli_in(
        tmp_path,
        [
            CliCmd.CHECK,
            CliOpt.OUTPUT_FORMAT,
            OutputFormat.NDJSON.value,
            "a.py",
            "b.py",
        ],
    )
    assert_SUCCESS(result)

    records: list[dict[str, object]] = [
        as_object_dict(as_object_dict(parse_json_object(line))["result"])
        for line in result.output.splitlines()
        if as_object_dict(parse_json_object(line)).get("kind") == "result"
    ]

    assert len(records) == 2
    assert [_status_fs(record) for record in records] == [
        FsStatus.HARD_LINK_DUPLICATE.value,
        FsStatus.HARD_LINK_DUPLICATE.value,
    ]

    for record in records:
        hints_obj: object = record["hints"]
        assert is_any_list(hints_obj)
        hints: list[dict[str, object]] = [
            as_object_dict(item) for item in hints_obj if is_mapping(item)
        ]
        assert len(hints) == 1
        assert hints[0]["code"] == KnownCode.FS_HARD_LINK_DUPLICATE.value
        assert hints[0]["reason"] == FsStatus.HARD_LINK_DUPLICATE.value

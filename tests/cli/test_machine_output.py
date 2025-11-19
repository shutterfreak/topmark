# topmark:header:start
#
#   project      : TopMark
#   file         : test_machine_output.py
#   file_relpath : tests/cli/test_machine_output.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for TopMark CLI commands.

This module verifies the JSON and NDJSON output emitted by TopMark’s
machine-readable modes (`--output-format json` and `--output-format ndjson`).

The tests serve as high-level contract checks to ensure that:

- Commands in the `topmark config` family emit a well-formed JSON object
  containing at least:
    - a `meta` block with `tool` and `version`,
    - a `config` payload.

- Processing commands such as `check` emit machine output that also
  includes the `meta` block and follows the documented schema
  (see `docs/dev/machine-output.md`).

These tests intentionally avoid checking full schema content
(e.g. all config fields), focusing instead on structural stability and
the presence of required top-level keys. Detailed schema validation is
covered by lower-level tests in `topmark.cli_shared.machine_output`.

All CLI invocations are executed via Click’s `CliRunner`, using the
helpers in `tests.cli.conftest` to control the working directory and
assert exit codes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from tests.cli.conftest import (
    assert_SUCCESS,
    assert_SUCCESS_or_WOULD_CHANGE,
    run_cli,
    run_cli_in,
)

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


def test_config_dump_json_includes_meta() -> None:
    """Ensure JSON output for `config dump` includes meta/tool/version.

    This is a high-level contract test for machine-readable output: the
    top-level JSON object must contain a `meta` block with `tool` and
    `version`, plus a `config` snapshot.
    """
    result: Result = run_cli(["config", "dump", "--output-format", "json"])
    assert_SUCCESS(result)

    payload: dict[str, Any] = json.loads(result.output)

    # Top-level keys
    assert "meta" in payload
    assert "config" in payload

    meta_obj = payload.get("meta")
    assert isinstance(meta_obj, dict)
    meta: dict[str, object] = cast("dict[str, object]", meta_obj)

    tool_obj = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    # Version should be a non-empty string
    version_obj = meta.get("version")
    assert isinstance(version_obj, str)
    assert version_obj != ""


def test_check_json_includes_meta(tmp_path: Path) -> None:
    """Ensure JSON machine output for `check` includes meta/tool/version."""
    # Create a tiny fake project so `check` has something to scan
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        ["check", "--output-format", "json", "."],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, Any] = json.loads(result.output)
    assert "meta" in payload

    meta_obj = payload.get("meta")
    assert isinstance(meta_obj, dict)
    meta: dict[str, object] = cast("dict[str, object]", meta_obj)

    tool_obj = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    version_obj = meta.get("version")
    assert isinstance(version_obj, str)
    assert version_obj != ""


def test_strip_json_includes_meta(tmp_path: Path) -> None:
    """Ensure JSON machine output for `strip` includes meta/tool/version."""
    # Create a tiny fake project so `strip` has something to scan
    (tmp_path / "example.py").write_text(
        "#!/usr/bin/env python3\nprint('hi')\n",
        encoding="utf-8",
    )

    result: Result = run_cli_in(
        tmp_path,
        ["strip", "--output-format", "json", "."],
    )
    assert_SUCCESS_or_WOULD_CHANGE(result)

    payload: dict[str, Any] = json.loads(result.output)
    assert "meta" in payload

    meta_obj = payload.get("meta")
    assert isinstance(meta_obj, dict)
    meta: dict[str, object] = cast("dict[str, object]", meta_obj)

    tool_obj = meta.get("tool")
    assert isinstance(tool_obj, str)
    assert tool_obj == "topmark"

    version_obj = meta.get("version")
    assert isinstance(version_obj, str)
    assert version_obj != ""

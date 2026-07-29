# topmark:header:start
#
#   project      : TopMark
#   file         : test_unified_check_apply.py
#   file_relpath : tests/cli/test_unified_check_apply.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI check/apply behavior tests.

This module verifies the unified `topmark check` behavior:
- default mode is a dry-run and does not write files,
- dry-run exits with WOULD_CHANGE when a header would be inserted,
- `--apply` writes changes and exits successfully.

Pure exit-code contract coverage lives in `tests/cli/test_check_exit_codes.py`;
this module focuses on the corresponding filesystem behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result


# --- Dry-run behavior ---


def test_check_dry_run_reports_would_change_without_writing(tmp_path: Path) -> None:
    """Default `check` mode should report WOULD_CHANGE without modifying the file."""
    f: Path = tmp_path / "a.py"
    f.write_text("print('x')\n", encoding="utf-8")

    result: Result = run_cli([CliCmd.CHECK, str(f)])

    assert_WOULD_CHANGE(result)

    # Dry-run mode must not modify the file.
    assert f.read_text(encoding="utf-8") == "print('x')\n"


# --- Apply behavior ---


def test_check_apply_writes_changes_and_exits_success(tmp_path: Path) -> None:
    """`check --apply` should write changes and exit SUCCESS."""
    f: Path = tmp_path / "b.py"
    before = "print('y')\n"
    f.write_text(before, encoding="utf-8")

    result: Result = run_cli([CliCmd.CHECK, CliOpt.APPLY_CHANGES, str(f)])

    assert_SUCCESS(result)

    after: str = f.read_text(encoding="utf-8")

    # The file should be changed by header insertion.
    assert after != before, "file should have been modified"


@pytest.mark.parametrize(
    "apply",
    [
        False,
        True,
    ],
)
def test_check_previews_and_applies_multiline_toml_field(
    tmp_path: Path,
    apply: bool,
) -> None:
    """TOML multiline strings render canonically and converge after apply."""
    path: Path = tmp_path / "multiline.py"
    original = "print('safe')\n"
    path.write_text(original, encoding="utf-8")
    (tmp_path / "topmark.toml").write_text(
        """
[config]
root = true

[fields]
project = \"\"\"safe
escaped\"\"\"

[header]
fields = ["project"]
""".lstrip(),
        encoding="utf-8",
    )
    argv: list[str] = [CliCmd.CHECK]
    if apply:
        argv.append(CliOpt.APPLY_CHANGES)
    argv.append(path.name)

    result: Result = run_cli_in(tmp_path, argv)

    if not apply:
        assert_WOULD_CHANGE(result)
        assert path.read_text(encoding="utf-8") == original
        return

    assert_SUCCESS(result)
    rendered: str = path.read_text(encoding="utf-8")
    assert "#   project :" in rendered
    assert "#     | safe" in rendered
    assert "#     | escaped" in rendered
    assert_SUCCESS(run_cli_in(tmp_path, [CliCmd.CHECK, path.name]))


def test_multiline_insert_strip_insert_is_byte_stable(tmp_path: Path) -> None:
    """Preview, apply, strip, and reinsert converge on one canonical block."""
    path: Path = tmp_path / "roundtrip.py"
    original = "print('round trip')\n"
    path.write_text(original, encoding="utf-8")
    (tmp_path / "topmark.toml").write_text(
        """
[config]
root = true

[fields]
notice = \"\"\"first

third
\"\"\"

[header]
fields = ["notice"]
""".lstrip(),
        encoding="utf-8",
    )

    preview: Result = run_cli_in(
        tmp_path,
        [CliCmd.CHECK, CliOpt.RENDER_DIFF, path.name],
    )
    assert_WOULD_CHANGE(preview)
    assert "#     | first" in preview.output
    assert "#     |" in preview.output

    assert_SUCCESS(run_cli_in(tmp_path, [CliCmd.CHECK, CliOpt.APPLY_CHANGES, path.name]))
    first_insert: str = path.read_text(encoding="utf-8")
    assert_SUCCESS(run_cli_in(tmp_path, [CliCmd.CHECK, path.name]))

    assert_SUCCESS(run_cli_in(tmp_path, [CliCmd.STRIP, CliOpt.APPLY_CHANGES, path.name]))
    assert path.read_text(encoding="utf-8") == original

    assert_SUCCESS(run_cli_in(tmp_path, [CliCmd.CHECK, CliOpt.APPLY_CHANGES, path.name]))
    assert path.read_text(encoding="utf-8") == first_insert

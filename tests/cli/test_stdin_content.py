# topmark:header:start
#
#   project      : TopMark
#   file         : test_stdin_content.py
#   file_relpath : tests/cli/test_stdin_content.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end
"""Content-on-STDIN CLI behavior tests.

This module covers the mode where a single file's content is provided on
STDIN using `-` as the input path and `--stdin-filename` for file-type
resolution.

The tests verify that `check` and `strip` behave consistently for dry-run and
`--apply` invocations. In apply mode, transformed content is written to STDOUT;
no filesystem target is written.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest
from click.testing import Result

from tests.cli.conftest import assert_human_output_contains
from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import assert_WOULD_CHANGE
from tests.cli.conftest import run_cli
from tests.cli.conftest import run_cli_in
from topmark.cli.commands import check as check_module
from topmark.cli.commands import strip as strip_module
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from click.testing import Result

# --- Check command: dry-run and apply ---


def test_check_content_stdin_dry_run_reports_would_change() -> None:
    """`check - --stdin-filename` should report WOULD_CHANGE in dry-run mode."""
    body = "print('x')\n"
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            "-",
            CliOpt.STDIN_FILENAME,
            "x.py",
        ],
        input_text=body,
    )
    # Header insertion would be needed, so dry-run reports WOULD_CHANGE.
    assert_WOULD_CHANGE(result)
    # Should not write to disk (it prints diagnostics only); no file exists here.


def test_check_content_stdin_apply_prints_modified_content_to_stdout(tmp_path: Path) -> None:
    """`check --apply -` should print modified STDIN content to STDOUT."""
    body = "print('x')\n"
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            CliOpt.APPLY_CHANGES,
            "-",
            CliOpt.STDIN_FILENAME,
            "x.py",
        ],
        input_text=body,
    )
    assert_SUCCESS(result)

    # Apply mode for content-on-STDIN writes transformed content to STDOUT.
    assert TOPMARK_START_MARKER in result.output


def test_check_content_stdin_default_filename_path_uses_plain_tempfile() -> None:
    """`check -` with the default stdin filename should not require a suffix."""
    result: Result = run_cli(
        [
            CliCmd.CHECK,
            "-",
            CliOpt.STDIN_FILENAME,
            "stdin",
        ],
        input_text="plain text\n",
    )

    assert_SUCCESS(result)
    assert_human_output_contains(
        output_format=None,
        output=result.output,
        expected="Unsupported: 1 file(s)",
    )


# --- Strip command: dry-run and apply ---


def test_strip_content_stdin_dry_run_reports_would_change() -> None:
    """`strip - --stdin-filename` should report WOULD_CHANGE when removal is needed."""
    body: str = f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint()\n"
    result: Result = run_cli(
        [
            CliCmd.STRIP,
            "-",
            CliOpt.STDIN_FILENAME,
            "x.py",
        ],
        input_text=body,
    )
    assert_WOULD_CHANGE(result)


def test_strip_content_stdin_apply_prints_stripped_content_to_stdout() -> None:
    """`strip --apply -` should print stripped STDIN content to STDOUT."""
    body: str = f"# {TOPMARK_START_MARKER}\n# test:header\n# {TOPMARK_END_MARKER}\nprint('ok')\n"
    result: Result = run_cli(
        [
            CliCmd.STRIP,
            CliOpt.APPLY_CHANGES,
            "-",
            CliOpt.STDIN_FILENAME,
            "x.py",
        ],
        input_text=body,
    )
    assert_SUCCESS(result)

    # Header should be absent from transformed STDOUT content.
    assert TOPMARK_START_MARKER not in result.output
    assert "print('ok')" in result.output


# --- STDIN content temp file cleanup ---


def _write_stdin_content_config(tmp_path: Path) -> None:
    """Write a minimal project config for deterministic STDIN header generation."""
    (tmp_path / "topmark.toml").write_text(
        textwrap.dedent(
            """\
            [config]
            root = true

            [fields]
            project = "TopMark"

            [header]
            fields = ["file", "project"]
            """
        ).lstrip(),
        encoding="utf-8",
    )


def _headered_stdin_python_content() -> str:
    """Return Python content containing the deterministic test TopMark header."""
    return textwrap.dedent(
        f"""\
        # {TOPMARK_START_MARKER}
        #
        #   file    : stdin.py
        #   project : TopMark
        #
        # {TOPMARK_END_MARKER}

        print('clean')
        """
    ).lstrip()


@pytest.mark.parametrize(
    ("cmd", "module", "input_text", "apply", "expected_assertion", "expected_unlinks"),
    [
        pytest.param(
            CliCmd.CHECK,
            check_module,
            "print('clean')\n",
            False,
            assert_WOULD_CHANGE,
            0,
            id="check-clean-dry-run",
        ),
        pytest.param(
            CliCmd.CHECK,
            check_module,
            "print('clean')\n",
            True,
            assert_SUCCESS,
            1,
            id="check-clean-apply",
        ),
        pytest.param(
            CliCmd.CHECK,
            check_module,
            _headered_stdin_python_content(),
            False,
            assert_SUCCESS,
            1,
            id="check-headered-dry-run",
        ),
        pytest.param(
            CliCmd.CHECK,
            check_module,
            _headered_stdin_python_content(),
            True,
            assert_SUCCESS,
            1,
            id="check-headered-apply",
        ),
        pytest.param(
            CliCmd.STRIP,
            strip_module,
            "print('clean')\n",
            False,
            assert_SUCCESS,
            1,
            id="strip-clean-dry-run",
        ),
        pytest.param(
            CliCmd.STRIP,
            strip_module,
            "print('clean')\n",
            True,
            assert_SUCCESS,
            1,
            id="strip-clean-apply",
        ),
        pytest.param(
            CliCmd.STRIP,
            strip_module,
            _headered_stdin_python_content(),
            False,
            assert_WOULD_CHANGE,
            0,
            id="strip-headered-dry-run",
        ),
        pytest.param(
            CliCmd.STRIP,
            strip_module,
            _headered_stdin_python_content(),
            True,
            assert_SUCCESS,
            1,
            id="strip-headered-apply",
        ),
    ],
)
def test_content_stdin_success_cleans_temp_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cmd: str,
    module: object,
    input_text: str,
    apply: bool,
    expected_assertion: Callable[[Result], None],
    expected_unlinks: int,
) -> None:
    """Content-STDIN commands should clean temp files on successful completion paths."""
    _write_stdin_content_config(tmp_path)
    unlinked_paths: list[Path] = []

    def record_safe_unlink(path: Path | None) -> None:
        if path is not None:
            assert path.exists()
            unlinked_paths.append(path)
            path.unlink()

    # Patch safe_unlink on each command module, because each command imports it
    # into its own module namespace.
    monkeypatch.setattr(module, "safe_unlink", record_safe_unlink)

    args: list[str] = [cmd, "-", CliOpt.STDIN_FILENAME, "stdin.py"]
    if apply:
        args.append(CliOpt.APPLY_CHANGES)

    result: Result = run_cli_in(
        tmp_path,
        args,
        input_text=input_text,
    )

    expected_assertion(result)
    assert len(unlinked_paths) == expected_unlinks
    for path in unlinked_paths:
        assert not path.exists()

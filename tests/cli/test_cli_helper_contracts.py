# topmark:header:start
#
#   project      : TopMark
#   file         : test_cli_helper_contracts.py
#   file_relpath : tests/cli/test_cli_helper_contracts.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for CLI helper seams.

These tests intentionally cover narrow CLI infrastructure helpers whose public
behavior is observable through command-line parsing, STDIN handling, and console
rendering, while avoiding broad command-level duplication.
"""

from __future__ import annotations

import io
import sys
from os import terminal_size
from pathlib import Path
from typing import NoReturn

import click
import pytest

from topmark.cli.console.color import ColorMode
from topmark.cli.console.color import resolve_color_mode
from topmark.cli.console.standard_console import StdConsole
from topmark.cli.console.utils import get_console_line_width
from topmark.cli.errors import TopmarkCliUsageError
from topmark.cli.io import InputPlan
from topmark.cli.io import StdinMode
from topmark.cli.io import StdinResult
from topmark.cli.io import consume_stdin
from topmark.cli.io import merge_cli_paths_with_stdin
from topmark.cli.io import plan_cli_inputs


class _TtyStdin(io.StringIO):
    """StringIO variant that behaves like an interactive stdin stream."""

    def isatty(self) -> bool:
        """Return True to simulate an interactive terminal."""
        return True


class _RaisingStdout(io.StringIO):
    """StringIO variant whose TTY probe fails."""

    def isatty(self) -> bool:
        """Raise an OS error to exercise defensive color fallback."""
        raise OSError("tty probe failed")


def test_consume_stdin_returns_none_for_tty_and_empty_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STDIN consumption should be a no-op for interactive or empty input."""
    monkeypatch.setattr(sys, "stdin", _TtyStdin("ignored"))
    assert consume_stdin().mode is StdinMode.NONE

    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert consume_stdin().mode is StdinMode.NONE


def test_consume_stdin_list_mode_ignores_blank_and_comment_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """List mode should parse newline-delimited paths and skip comments."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("a.py\n\n# comment\n docs/index.md \n"))

    result: StdinResult = consume_stdin(expect="list")

    assert result.mode is StdinMode.LIST
    assert result.paths == [Path("a.py"), Path("docs/index.md")]
    assert result.temp_path is None
    assert result.errors == []


def test_consume_stdin_content_mode_uses_filename_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Content mode should preserve a useful suffix for file-type resolution."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("print('stdin')\n"))

    result: StdinResult = consume_stdin(expect="content", stdin_filename="example.py")

    assert result.mode is StdinMode.CONTENT
    assert result.temp_path is not None
    assert result.temp_path.suffix == ".py"
    assert result.paths == [result.temp_path]
    assert result.temp_path.read_text(encoding="utf-8") == "print('stdin')\n"
    result.temp_path.unlink()


def test_consume_stdin_content_mode_without_filename_uses_no_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forced content mode without a filename should still materialize STDIN."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("plain text\n"))

    result: StdinResult = consume_stdin(expect="content")

    assert result.mode is StdinMode.CONTENT
    assert result.temp_path is not None
    assert result.temp_path.suffix == ""
    assert result.paths == [result.temp_path]
    assert result.temp_path.read_text(encoding="utf-8") == "plain text\n"
    result.temp_path.unlink()


def test_consume_stdin_content_mode_reports_tempfile_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tempfile failures should be reported as non-fatal STDIN errors."""

    def raise_oserror(*_args: object, **_kwargs: object) -> NoReturn:
        raise OSError("disk full")

    monkeypatch.setattr(sys, "stdin", io.StringIO("print()\n"))
    monkeypatch.setattr("topmark.cli.io.tempfile.NamedTemporaryFile", raise_oserror)

    result: StdinResult = consume_stdin(expect="content", stdin_filename="example.py")

    assert result.mode is StdinMode.NONE
    assert result.paths == []
    assert result.temp_path is None
    assert result.errors == ["#ERROR: failed to create temp file for STDIN content: disk full"]


def test_merge_cli_paths_with_stdin_respects_stdin_mode() -> None:
    """Path merging should preserve the documented precedence for each STDIN mode."""
    assert merge_cli_paths_with_stdin(["cli.py"], StdinResult(StdinMode.NONE, [], None, [])) == [
        Path("cli.py")
    ]
    assert merge_cli_paths_with_stdin(
        ["cli.py"], StdinResult(StdinMode.LIST, [Path("stdin.py")], None, [])
    ) == [
        Path("cli.py"),
        Path("stdin.py"),
    ]
    assert merge_cli_paths_with_stdin(
        ["cli.py"],
        StdinResult(StdinMode.CONTENT, [Path("content.py")], Path("content.py"), []),
    ) == [Path("content.py")]


def test_plan_cli_inputs_allows_empty_paths_when_requested() -> None:
    """File-agnostic commands should be able to build an empty input plan."""
    ctx = click.Context(click.Command("dump-config"))

    plan: InputPlan = plan_cli_inputs(
        ctx=ctx,
        files_from=[],
        include_from=[],
        exclude_from=[],
        include_patterns=[],
        exclude_patterns=[],
        stdin_filename=None,
        allow_empty_paths=True,
    )

    assert not plan.stdin_mode
    assert plan.stdin_filename is None
    assert plan.temp_path is None
    assert plan.paths == []
    assert plan.include_patterns == []
    assert plan.exclude_patterns == []
    assert plan.files_from == []
    assert plan.include_from == []
    assert plan.exclude_from == []


def test_plan_cli_inputs_rejects_empty_paths_by_default() -> None:
    """Path-oriented commands should reject invocations with no candidate paths."""
    ctx = click.Context(click.Command("check"))

    with pytest.raises(TopmarkCliUsageError, match="No arguments provided"):
        plan_cli_inputs(
            ctx=ctx,
            files_from=[],
            include_from=[],
            exclude_from=[],
            include_patterns=[],
            exclude_patterns=[],
            stdin_filename=None,
        )


def test_plan_cli_inputs_rejects_empty_content_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content STDIN mode should fail clearly when '-' receives no data."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    ctx = click.Context(click.Command("check"))
    ctx.args = ["-"]

    with pytest.raises(TopmarkCliUsageError, match="No data received on STDIN"):
        plan_cli_inputs(
            ctx=ctx,
            files_from=[],
            include_from=[],
            exclude_from=[],
            include_patterns=[],
            exclude_patterns=[],
            stdin_filename="stdin.py",
        )


def test_plan_cli_inputs_rejects_content_stdin_mixed_with_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content STDIN should not compete with list STDIN routed to from-options."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("src/topmark/__init__.py\n"))
    ctx = click.Context(click.Command("check"))
    ctx.args = ["-"]

    with pytest.raises(TopmarkCliUsageError, match="Cannot combine '-'"):
        plan_cli_inputs(
            ctx=ctx,
            files_from=["-"],
            include_from=[],
            exclude_from=[],
            include_patterns=[],
            exclude_patterns=[],
            stdin_filename="stdin.py",
        )


def test_plan_cli_inputs_rejects_dash_mixed_with_other_paths() -> None:
    """A dash PATH should only mean content STDIN when it is the sole PATH."""
    ctx = click.Context(click.Command("check"))
    ctx.args = ["-", "src/topmark/__init__.py"]

    with pytest.raises(TopmarkCliUsageError, match="only valid as the sole PATH"):
        plan_cli_inputs(
            ctx=ctx,
            files_from=[],
            include_from=[],
            exclude_from=[],
            include_patterns=[],
            exclude_patterns=[],
            stdin_filename="stdin.py",
        )


def test_plan_cli_inputs_routes_include_and_exclude_patterns_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pattern STDIN routing should strip '-' from from-option file lists."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("src/**\n# ignored\ntests/**\n"))
    ctx = click.Context(click.Command("check"))
    ctx.args = ["src/topmark/__init__.py"]

    plan: InputPlan = plan_cli_inputs(
        ctx=ctx,
        files_from=[],
        include_from=["-", "include-patterns.txt"],
        exclude_from=[],
        include_patterns=["docs/**"],
        exclude_patterns=[],
        stdin_filename=None,
    )

    assert not plan.stdin_mode
    assert plan.stdin_filename is None
    assert plan.temp_path is None
    assert plan.paths == ["src/topmark/__init__.py"]
    assert plan.include_patterns == ["docs/**", "src/**", "tests/**"]
    assert plan.exclude_patterns == []
    assert plan.files_from == []
    assert plan.include_from == ["include-patterns.txt"]
    assert plan.exclude_from == []


def test_resolve_color_mode_obeys_machine_formats_and_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Color resolution should keep non-human formats colorless and honor env flags."""
    assert not resolve_color_mode(
        color_mode_override=ColorMode.ALWAYS,
        output_format="json",
        stdout_isatty=True,
    )
    assert not resolve_color_mode(
        color_mode_override=ColorMode.ALWAYS,
        output_format="markdown",
        stdout_isatty=True,
    )
    assert resolve_color_mode(
        color_mode_override=ColorMode.ALWAYS,
        output_format=None,
        stdout_isatty=False,
    )
    assert not resolve_color_mode(
        color_mode_override=ColorMode.NEVER,
        output_format=None,
        stdout_isatty=True,
    )

    monkeypatch.setenv("FORCE_COLOR", "1")
    assert resolve_color_mode(color_mode_override=None, output_format=None, stdout_isatty=False)

    monkeypatch.setenv("FORCE_COLOR", "0")
    monkeypatch.setenv("NO_COLOR", "")
    assert not resolve_color_mode(color_mode_override=None, output_format=None, stdout_isatty=True)


def test_resolve_color_mode_falls_back_when_stdout_tty_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing stdout TTY probe should disable color rather than raising."""
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys, "stdout", _RaisingStdout())

    assert not resolve_color_mode(color_mode_override=ColorMode.AUTO, output_format=None)


def test_resolve_color_mode_auto_uses_explicit_tty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto mode should reflect the supplied TTY state when no overrides apply."""
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    assert resolve_color_mode(
        color_mode_override=ColorMode.AUTO,
        output_format=None,
        stdout_isatty=True,
    )
    assert not resolve_color_mode(
        color_mode_override=ColorMode.AUTO,
        output_format=None,
        stdout_isatty=False,
    )


def test_std_console_writes_to_injected_streams() -> None:
    """The stdlib console should route normal output and diagnostics separately."""
    out = io.StringIO()
    err = io.StringIO()
    console = StdConsole(enable_color=True, out=out, err=err)

    console.print("hello", nl=False)
    console.warn("careful")
    console.error("failed", nl=False)

    assert console.enable_color
    assert out.getvalue() == "hello"
    assert err.getvalue() == "careful\nfailed"


def test_get_console_line_width_caps_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Console width detection should cap wide terminals and survive OS errors."""

    def wide_terminal_size(fallback: tuple[int, int] = (80, 24)) -> terminal_size:
        _, _ = fallback
        return terminal_size((120, 24))

    monkeypatch.setattr("topmark.cli.console.utils.shutil.get_terminal_size", wide_terminal_size)
    assert get_console_line_width(default=80, max_width=100) == 100

    def raise_terminal_size_oserror(
        fallback: tuple[int, int] = (80, 24),
    ) -> terminal_size:
        _, _ = fallback
        raise OSError("no terminal")

    monkeypatch.setattr(
        "topmark.cli.console.utils.shutil.get_terminal_size",
        raise_terminal_size_oserror,
    )
    assert get_console_line_width(default=72, max_width=100) == 72

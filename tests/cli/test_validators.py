# topmark:header:start
#
#   project      : TopMark
#   file         : test_validators.py
#   file_relpath : tests/cli/test_validators.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for CLI validation and option-policy helpers."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import click
import pytest

from topmark.cli.console.click_console import Console
from topmark.cli.console.color import ColorMode
from topmark.cli.errors import TopmarkCliUsageError
from topmark.cli.state import TopmarkCliState
from topmark.cli.validators import _extra_arg_matches_option  # pyright: ignore[reportPrivateUsage]
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.cli.validators import validate_common_forbidden_path_command_options_in_extra_args
from topmark.cli.validators import validate_diff_policy_for_output_format
from topmark.cli.validators import validate_forbidden_options_in_extra_args
from topmark.cli.validators import validate_human_only_config_flags_for_machine_format
from topmark.cli.validators import validate_machine_format_forbids_flags
from topmark.cli.validators import validate_mutually_exclusive
from topmark.cli.validators import validate_output_verbosity_policy
from topmark.cli.validators import validate_stdin_dash_requires_piped_input
from topmark.cli.validators import warn_and_clear
from topmark.cli.validators import warn_if_report_scope_ignored
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.pipeline.reporting import ReportScope

if TYPE_CHECKING:
    from collections.abc import Sequence


class TtyStdin:
    """Minimal stdin stub used to test TTY detection."""

    def isatty(self) -> bool:
        """Return True to emulate an interactive terminal."""
        return True


class PipedStdin:
    """Minimal stdin stub used to test piped input detection."""

    def isatty(self) -> bool:
        """Return False to emulate piped input."""
        return False


def _make_click_context(
    *,
    args: Sequence[str] = (),
    state: TopmarkCliState | None = None,
) -> click.Context:
    """Create a minimal Click context for validator unit tests."""
    ctx = click.Context(
        click.Command("topmark-test"),
        info_name="topmark-test",
    )
    ctx.args = list(args)
    ctx.obj = state if state is not None else TopmarkCliState()
    return ctx


def _state_with_console(
    *,
    color_mode: ColorMode = ColorMode.AUTO,
    color_enabled: bool = False,
) -> tuple[TopmarkCliState, io.StringIO]:
    """Create CLI state with a captureable warning stream."""
    err = io.StringIO()
    state = TopmarkCliState(
        color_mode=color_mode,
        color_enabled=color_enabled,
        console=Console(enable_color=False, err=err),
    )
    return state, err


@pytest.mark.parametrize(
    ("arg", "opt", "expected"),
    [
        ("--stdin", "--stdin", True),
        ("--stdin=value", "--stdin", True),
        ("--stdin-filename", "--stdin", False),
        ("--std", "--stdin", False),
        ("path.py", "--stdin", False),
    ],
)
def test_extra_arg_matches_option(arg: str, opt: str, expected: bool) -> None:
    """Extra option matching should support exact and assignment forms only."""
    assert _extra_arg_matches_option(arg, opt) is expected


def test_validate_common_forbidden_path_options_accepts_absent_options() -> None:
    """Common forbidden-option validator should pass when no known option remains."""
    ctx = _make_click_context(args=["--unknown", "file.py"])

    validate_common_forbidden_path_command_options_in_extra_args(ctx)


@pytest.mark.parametrize("arg", ["--stdin", "--stdin=ignored"])
def test_validate_common_forbidden_path_options_rejects_stdin(arg: str) -> None:
    """Path commands should reject leftover `--stdin` spellings."""
    ctx = _make_click_context(args=[arg])

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"Option '--stdin' is not supported for 'topmark-test'",
    ):
        validate_common_forbidden_path_command_options_in_extra_args(ctx)


def test_validate_forbidden_options_in_extra_args_rejects_custom_option() -> None:
    """Custom forbidden options should be rejected from permissive extra args."""
    ctx = _make_click_context(args=["--unsafe=true"])

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"Option '--unsafe' is not supported for 'topmark-test'. not allowed",
    ):
        validate_forbidden_options_in_extra_args(
            ctx,
            forbidden_opts={"--unsafe": "not allowed"},
        )


def test_validate_forbidden_options_in_extra_args_ignores_unmatched_options() -> None:
    """Custom forbidden-option validator should ignore unrelated extras."""
    ctx = _make_click_context(args=["--other", "file.py"])

    validate_forbidden_options_in_extra_args(
        ctx,
        forbidden_opts={"--unsafe": "not allowed"},
    )


def test_validate_mutually_exclusive_accepts_zero_or_one_enabled_flag() -> None:
    """Mutual-exclusion validator should allow zero or one enabled flag."""
    ctx = _make_click_context()

    validate_mutually_exclusive(
        ctx,
        flags={
            "--a": False,
            "--b": False,
        },
    )
    validate_mutually_exclusive(
        ctx,
        flags={
            "--a": True,
            "--b": False,
        },
    )


def test_validate_mutually_exclusive_reports_default_two_flag_message() -> None:
    """Mutual-exclusion validator should report the enabled option spellings."""
    ctx = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"topmark-test: --a and --b are mutually exclusive.",
    ):
        validate_mutually_exclusive(
            ctx,
            flags={
                "--a": True,
                "--b": True,
            },
        )


def test_validate_mutually_exclusive_uses_custom_message() -> None:
    """Mutual-exclusion validator should preserve explicit custom messages."""
    ctx = _make_click_context()

    with pytest.raises(TopmarkCliUsageError, match="custom conflict"):
        validate_mutually_exclusive(
            ctx,
            flags={
                "--a": True,
                "--b": True,
            },
            message="custom conflict",
        )


def test_validate_machine_format_forbids_flags_allows_text_and_disabled_flags() -> None:
    """Machine-format validator should pass for text or when all flags are off."""
    ctx = _make_click_context()

    validate_machine_format_forbids_flags(
        ctx,
        fmt=OutputFormat.TEXT,
        flags={"--diff": True},
        reason="is not supported.",
    )
    validate_machine_format_forbids_flags(
        ctx,
        fmt=OutputFormat.JSON,
        flags={"--diff": False},
        reason="is not supported.",
    )


def test_validate_machine_format_forbids_flags_reports_single_flag() -> None:
    """Machine-format validator should report one incompatible enabled flag."""
    ctx = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"topmark-test: --output-format=json: --diff is not supported.",
    ):
        validate_machine_format_forbids_flags(
            ctx,
            fmt=OutputFormat.JSON,
            flags={"--diff": True},
            reason="is not supported.",
        )


def test_validate_machine_format_forbids_flags_reports_multiple_flags() -> None:
    """Machine-format validator should report multiple incompatible flags."""
    ctx = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=(
            r"topmark-test: --output-format=ndjson: "
            r"--root and --pyproject are not supported."
        ),
    ):
        validate_machine_format_forbids_flags(
            ctx,
            fmt=OutputFormat.NDJSON,
            flags={
                "--root": True,
                "--pyproject": True,
            },
            reason="are not supported.",
        )


def test_warn_and_clear_updates_color_enabled_and_returns_value() -> None:
    """warn_and_clear should emit a warning and mutate supported typed state."""
    state, err = _state_with_console(color_enabled=True)
    ctx = _make_click_context(state=state)

    result = warn_and_clear(
        ctx,
        message="color ignored",
        obj_key=ArgKey.COLOR_ENABLED,
        cleared_value=False,
    )

    assert result is False
    assert state.color_enabled is False
    assert err.getvalue() == "color ignored\n"


def test_warn_and_clear_rejects_wrong_cleared_type() -> None:
    """warn_and_clear should validate cleared values for supported fields."""
    state, _err = _state_with_console(color_enabled=True)
    ctx = _make_click_context(state=state)

    with pytest.raises(TypeError, match="color_enabled must be cleared with a bool value"):
        warn_and_clear(
            ctx,
            message="bad clear",
            obj_key=ArgKey.COLOR_ENABLED,
            cleared_value="false",
        )


def test_warn_and_clear_rejects_unsupported_state_key() -> None:
    """warn_and_clear should not become a generic state mutation helper."""
    ctx = _make_click_context()

    with pytest.raises(KeyError, match="Unsupported TopmarkCliState clear key"):
        warn_and_clear(
            ctx,
            message="bad key",
            obj_key="unsupported",
            cleared_value=False,
        )


def test_apply_color_policy_keeps_text_color_state_unchanged() -> None:
    """TEXT output should not force color state changes."""
    state, err = _state_with_console(
        color_mode=ColorMode.ALWAYS,
        color_enabled=True,
    )
    ctx = _make_click_context(state=state)

    apply_color_policy_for_output_format(ctx, fmt=OutputFormat.TEXT)

    assert state.color_enabled is True
    assert err.getvalue() == ""


def test_apply_color_policy_disables_non_text_color_without_warning_for_auto() -> None:
    """Non-TEXT output should disable color silently unless color was forced."""
    state, err = _state_with_console(
        color_mode=ColorMode.AUTO,
        color_enabled=True,
    )
    ctx = _make_click_context(state=state)

    apply_color_policy_for_output_format(ctx, fmt=OutputFormat.MARKDOWN)

    assert state.color_enabled is False
    assert err.getvalue() == ""


def test_apply_color_policy_warns_when_forced_color_is_ignored() -> None:
    """Forced color should warn when a non-TEXT output format is selected."""
    state, err = _state_with_console(
        color_mode=ColorMode.ALWAYS,
        color_enabled=True,
    )
    ctx = _make_click_context(state=state)

    apply_color_policy_for_output_format(ctx, fmt=OutputFormat.JSON)

    assert state.color_enabled is False
    assert err.getvalue() == (
        "Note: topmark-test: --color=ColorMode.ALWAYS is ignored when --output-format=json.\n"
    )


def test_apply_ignore_positional_paths_policy_noops_without_extra_args() -> None:
    """File-agnostic path policy should be silent when there are no extras."""
    state, err = _state_with_console()
    ctx = _make_click_context(state=state)

    apply_ignore_positional_paths_policy(ctx)

    assert ctx.args == []
    assert err.getvalue() == ""


def test_apply_ignore_positional_paths_policy_warns_and_clears_args() -> None:
    """File-agnostic path policy should warn and clear unexpected paths."""
    state, err = _state_with_console()
    ctx = _make_click_context(args=["-", "src"], state=state)

    apply_ignore_positional_paths_policy(ctx)

    assert ctx.args == []
    assert err.getvalue() == (
        "Note: topmark-test is file-agnostic; '-' (content from STDIN) is ignored.\n"
        "Note: topmark-test is file-agnostic; positional paths are ignored.\n"
    )


def test_apply_ignore_positional_paths_policy_can_suppress_stdin_dash_warning() -> None:
    """STDIN dash warning should be suppressible while keeping the path warning."""
    state, err = _state_with_console()
    ctx = _make_click_context(args=["-"], state=state)

    apply_ignore_positional_paths_policy(ctx, warn_stdin_dash=False)

    assert ctx.args == []
    assert err.getvalue() == (
        "Note: topmark-test is file-agnostic; positional paths are ignored.\n"
    )


def test_validate_output_verbosity_policy_allows_text_without_conflict() -> None:
    """TEXT verbosity policy should allow either verbose or quiet alone."""
    ctx = _make_click_context()

    validate_output_verbosity_policy(
        ctx,
        verbosity=1,
        quiet=False,
        fmt=OutputFormat.TEXT,
    )
    validate_output_verbosity_policy(
        ctx,
        verbosity=0,
        quiet=True,
        fmt=OutputFormat.TEXT,
    )


def test_validate_output_verbosity_policy_rejects_text_verbose_and_quiet() -> None:
    """TEXT verbosity policy should reject verbose and quiet together."""
    ctx = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"topmark-test: --verbose and --quiet are mutually exclusive.",
    ):
        validate_output_verbosity_policy(
            ctx,
            verbosity=1,
            quiet=True,
            fmt=OutputFormat.TEXT,
        )


def test_validate_output_verbosity_policy_clears_non_text_controls() -> None:
    """Non-TEXT output should silently clear TEXT-only verbosity controls."""
    state = TopmarkCliState(verbosity=2, quiet=True)
    ctx = _make_click_context(state=state)

    validate_output_verbosity_policy(
        ctx,
        verbosity=2,
        quiet=True,
        fmt=OutputFormat.MARKDOWN,
    )

    assert state.verbosity == 0
    assert state.quiet is False


def test_validate_diff_policy_for_output_format_rejects_machine_diff() -> None:
    """Unified diffs should be rejected for machine-readable output."""
    ctx = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=(
            r"topmark-test: --output-format=json: "
            r"--diff is not supported with machine-readable output formats."
        ),
    ):
        validate_diff_policy_for_output_format(
            ctx,
            diff=True,
            fmt=OutputFormat.JSON,
        )


def test_validate_diff_policy_for_output_format_allows_text_diff() -> None:
    """Unified diffs should be allowed for human-readable text output."""
    ctx = _make_click_context()

    validate_diff_policy_for_output_format(
        ctx,
        diff=True,
        fmt=OutputFormat.TEXT,
    )


def test_validate_human_only_config_flags_rejects_machine_format() -> None:
    """Human-only config template flags should be rejected for machine formats."""
    ctx = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=(
            r"topmark-test: --output-format=ndjson: "
            r"--root and --pyproject are not supported with machine-readable output formats."
        ),
    ):
        validate_human_only_config_flags_for_machine_format(
            ctx,
            config_root=True,
            for_pyproject=True,
            fmt=OutputFormat.NDJSON,
        )


def test_validate_human_only_config_flags_allows_markdown_format() -> None:
    """Human-only config template flags should be allowed for Markdown output."""
    ctx = _make_click_context()

    validate_human_only_config_flags_for_machine_format(
        ctx,
        config_root=True,
        for_pyproject=True,
        fmt=OutputFormat.MARKDOWN,
    )


def test_warn_if_report_scope_ignored_noops_when_report_was_not_explicit() -> None:
    """Report-scope warnings should only fire for command-line report values."""
    state, err = _state_with_console()
    ctx = _make_click_context(state=state)

    warn_if_report_scope_ignored(
        ctx,
        output_format=OutputFormat.JSON,
        summary_mode=True,
        report_scope=ReportScope.ALL,
    )

    assert err.getvalue() == ""


def test_warn_if_report_scope_ignored_warns_for_machine_and_summary() -> None:
    """Explicit report scope should warn for every policy reason that ignores it."""
    state, err = _state_with_console()
    ctx = _make_click_context(state=state)
    ctx.set_parameter_source(
        ArgKey.REPORT_SCOPE,
        click.core.ParameterSource.COMMANDLINE,
    )

    warn_if_report_scope_ignored(
        ctx,
        output_format=OutputFormat.JSON,
        summary_mode=True,
        report_scope=ReportScope.ALL,
    )

    assert err.getvalue() == (
        "Note: topmark-test: --report=all is ignored when --output-format=json.\n"
        "Note: topmark-test: --report=all is ignored when --summary is enabled.\n"
    )


def test_warn_if_report_scope_ignored_noops_when_explicit_but_effective() -> None:
    """Explicit report scope should not warn when the selected modes use it."""
    state, err = _state_with_console()
    ctx = _make_click_context(state=state)
    ctx.set_parameter_source(
        ArgKey.REPORT_SCOPE,
        click.core.ParameterSource.COMMANDLINE,
    )

    warn_if_report_scope_ignored(
        ctx,
        output_format=OutputFormat.TEXT,
        summary_mode=False,
        report_scope=ReportScope.NONCOMPLIANT,
    )

    assert err.getvalue() == ""


def test_validate_stdin_dash_requires_piped_input_allows_absent_dash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STDIN dash validation should pass when no option uses dash."""
    monkeypatch.setattr("sys.stdin", TtyStdin())

    validate_stdin_dash_requires_piped_input(
        _make_click_context(),
        files_from=["paths.txt"],
        include_from=None,
        exclude_from=None,
    )


def test_validate_stdin_dash_requires_piped_input_allows_piped_dash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STDIN dash validation should pass when dash is paired with piped input."""
    monkeypatch.setattr("sys.stdin", PipedStdin())

    validate_stdin_dash_requires_piped_input(
        _make_click_context(),
        files_from=["-"],
        include_from=None,
        exclude_from=None,
    )


def test_validate_stdin_dash_requires_piped_input_rejects_tty_dash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STDIN dash validation should fail fast when dash is used without a pipe."""
    monkeypatch.setattr("sys.stdin", TtyStdin())

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"topmark-test: '-' requests patterns/paths from STDIN",
    ):
        validate_stdin_dash_requires_piped_input(
            _make_click_context(),
            files_from=None,
            include_from=["-"],
            exclude_from=None,
        )

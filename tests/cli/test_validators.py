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
from topmark.cli.validators import apply_color_policy_for_output_format
from topmark.cli.validators import apply_ignore_positional_paths_policy
from topmark.cli.validators import validate_diff_apply_mutual_exclusion
from topmark.cli.validators import validate_human_only_config_flags_for_machine_format
from topmark.cli.validators import validate_machine_format_forbids_flags
from topmark.cli.validators import validate_mutually_exclusive
from topmark.cli.validators import validate_output_verbosity_policy
from topmark.cli.validators import validate_stdin_dash_requires_piped_input
from topmark.cli.validators import warn_and_clear
from topmark.cli.validators import warn_if_machine_summary_diff_ignored
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
    "flags",
    [
        pytest.param({"--a": False, "--b": False}, id="zero-enabled"),
        pytest.param({"--a": True, "--b": False}, id="one-enabled"),
    ],
)
def test_validate_mutually_exclusive_accepts_zero_or_one_enabled_flag(
    flags: dict[str, bool],
) -> None:
    """Mutual-exclusion validator should allow zero or one enabled flag."""
    ctx: click.Context = _make_click_context()

    validate_mutually_exclusive(ctx, flags=flags)


def test_validate_mutually_exclusive_reports_default_two_flag_message() -> None:
    """Mutual-exclusion validator should report the enabled option spellings."""
    ctx: click.Context = _make_click_context()

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
    ctx: click.Context = _make_click_context()

    with pytest.raises(TopmarkCliUsageError, match="custom conflict"):
        validate_mutually_exclusive(
            ctx,
            flags={
                "--a": True,
                "--b": True,
            },
            message="custom conflict",
        )


@pytest.mark.parametrize(
    ("fmt", "flags"),
    [
        pytest.param(OutputFormat.TEXT, {"--root": True}, id="text-enabled-flag-ok"),
        pytest.param(OutputFormat.JSON, {"--root": False}, id="json-disabled-flag-ok"),
        pytest.param(OutputFormat.NDJSON, {"--pyproject": False}, id="ndjson-disabled-flag-ok"),
    ],
)
def test_validate_machine_format_forbids_flags_allows_text_and_disabled_flags(
    *,
    fmt: OutputFormat,
    flags: dict[str, bool],
) -> None:
    """Machine-format validator should pass for text or when all flags are off."""
    ctx: click.Context = _make_click_context()

    validate_machine_format_forbids_flags(
        ctx,
        fmt=fmt,
        flags=flags,
        reason="is not supported.",
    )


def test_validate_machine_format_forbids_flags_reports_single_flag() -> None:
    """Machine-format validator should report one incompatible enabled flag."""
    ctx: click.Context = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"topmark-test: --output-format=json: --root is not supported.",
    ):
        validate_machine_format_forbids_flags(
            ctx,
            fmt=OutputFormat.JSON,
            flags={"--root": True},
            reason="is not supported.",
        )


def test_validate_machine_format_forbids_flags_reports_multiple_flags() -> None:
    """Machine-format validator should report multiple incompatible flags."""
    ctx: click.Context = _make_click_context()

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
    ctx: click.Context = _make_click_context(state=state)

    result: bool = warn_and_clear(
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
    ctx: click.Context = _make_click_context(state=state)

    with pytest.raises(TypeError, match="color_enabled must be cleared with a bool value"):
        warn_and_clear(
            ctx,
            message="bad clear",
            obj_key=ArgKey.COLOR_ENABLED,
            cleared_value="false",
        )


def test_warn_and_clear_rejects_unsupported_state_key() -> None:
    """warn_and_clear should not become a generic state mutation helper."""
    ctx: click.Context = _make_click_context()

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
    ctx: click.Context = _make_click_context(state=state)

    apply_color_policy_for_output_format(ctx, fmt=OutputFormat.TEXT)

    assert state.color_enabled is True
    assert err.getvalue() == ""


def test_apply_color_policy_disables_non_text_color_without_warning_for_auto() -> None:
    """Non-TEXT output should disable color silently unless color was forced."""
    state, err = _state_with_console(
        color_mode=ColorMode.AUTO,
        color_enabled=True,
    )
    ctx: click.Context = _make_click_context(state=state)

    apply_color_policy_for_output_format(ctx, fmt=OutputFormat.MARKDOWN)

    assert state.color_enabled is False
    assert err.getvalue() == ""


def test_apply_color_policy_warns_when_forced_color_is_ignored() -> None:
    """Forced color should warn when a non-TEXT output format is selected."""
    state, err = _state_with_console(
        color_mode=ColorMode.ALWAYS,
        color_enabled=True,
    )
    ctx: click.Context = _make_click_context(state=state)

    apply_color_policy_for_output_format(ctx, fmt=OutputFormat.JSON)

    assert state.color_enabled is False
    assert err.getvalue() == (
        "Note: topmark-test: --color=always is ignored when --output-format=json.\n"
    )


def test_apply_ignore_positional_paths_policy_noops_without_extra_args() -> None:
    """File-agnostic path policy should be silent when there are no extras."""
    state, err = _state_with_console()
    ctx: click.Context = _make_click_context(state=state)

    apply_ignore_positional_paths_policy(ctx)

    assert ctx.args == []
    assert err.getvalue() == ""


def test_apply_ignore_positional_paths_policy_warns_and_clears_args() -> None:
    """File-agnostic path policy should warn and clear unexpected paths."""
    state, err = _state_with_console()
    ctx: click.Context = _make_click_context(args=["-", "src"], state=state)

    apply_ignore_positional_paths_policy(ctx)

    assert ctx.args == []
    assert err.getvalue() == (
        "Note: topmark-test is file-agnostic; '-' (content from STDIN) is ignored.\n"
        "Note: topmark-test is file-agnostic; positional paths are ignored.\n"
    )


def test_apply_ignore_positional_paths_policy_can_suppress_stdin_dash_warning() -> None:
    """STDIN dash warning should be suppressible while keeping the path warning."""
    state, err = _state_with_console()
    ctx: click.Context = _make_click_context(args=["-"], state=state)

    apply_ignore_positional_paths_policy(ctx, warn_stdin_dash=False)

    assert ctx.args == []
    assert err.getvalue() == (
        "Note: topmark-test is file-agnostic; positional paths are ignored.\n"
    )


@pytest.mark.parametrize(
    ("verbosity", "quiet"),
    [
        pytest.param(1, False, id="verbose-only"),
        pytest.param(0, True, id="quiet-only"),
    ],
)
def test_validate_output_verbosity_policy_allows_text_without_conflict(
    *,
    verbosity: int,
    quiet: bool,
) -> None:
    """TEXT verbosity policy should allow either verbose or quiet alone."""
    ctx: click.Context = _make_click_context()

    validate_output_verbosity_policy(
        ctx,
        verbosity=verbosity,
        quiet=quiet,
        fmt=OutputFormat.TEXT,
    )


def test_validate_output_verbosity_policy_rejects_text_verbose_and_quiet() -> None:
    """TEXT verbosity policy should reject verbose and quiet together."""
    ctx: click.Context = _make_click_context()

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"topmark-test: --verbose \(-v\) and --quiet \(-q\) are mutually exclusive.",
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
    ctx: click.Context = _make_click_context(state=state)

    validate_output_verbosity_policy(
        ctx,
        verbosity=2,
        quiet=True,
        fmt=OutputFormat.MARKDOWN,
    )

    assert state.verbosity == 0
    assert state.quiet is False


@pytest.mark.parametrize(
    ("diff", "apply_changes", "allowed"),
    [
        pytest.param(False, False, True, id="nodiff-dryrun-ok"),
        pytest.param(True, False, True, id="diff-dryrun-ok"),
        pytest.param(False, True, True, id="nodiff-apply-ok"),
        pytest.param(True, True, False, id="diff-apply-error"),
    ],
)
def test_validate_diff_apply_mutual_exclusion(
    *,
    diff: bool,
    apply_changes: bool,
    allowed: bool,
) -> None:
    """Unified diffs should be rejected only when apply mode is enabled."""
    ctx: click.Context = _make_click_context()

    if allowed:
        validate_diff_apply_mutual_exclusion(
            ctx,
            diff=diff,
            apply_changes=apply_changes,
        )
        return

    with pytest.raises(
        TopmarkCliUsageError,
        match=r"topmark-test: --diff and --apply are mutually exclusive.",
    ):
        validate_diff_apply_mutual_exclusion(
            ctx,
            diff=diff,
            apply_changes=apply_changes,
        )


def test_validate_human_only_config_flags_rejects_machine_format() -> None:
    """Human-only config template flags should be rejected for machine formats."""
    ctx: click.Context = _make_click_context()

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
    ctx: click.Context = _make_click_context()

    validate_human_only_config_flags_for_machine_format(
        ctx,
        config_root=True,
        for_pyproject=True,
        fmt=OutputFormat.MARKDOWN,
    )


def test_warn_if_report_scope_ignored_noops_when_report_was_not_explicit() -> None:
    """Report-scope warnings should only fire for command-line report values."""
    state, err = _state_with_console()
    ctx: click.Context = _make_click_context(state=state)

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
    ctx: click.Context = _make_click_context(state=state)
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
    ctx: click.Context = _make_click_context(state=state)
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


@pytest.mark.parametrize(
    ("output_format", "summary_mode", "diff", "explicit_diff"),
    [
        pytest.param(OutputFormat.JSON, True, True, False, id="not-explicit"),
        pytest.param(OutputFormat.TEXT, True, True, True, id="human-output"),
        pytest.param(OutputFormat.MARKDOWN, True, True, True, id="markdown-output"),
        pytest.param(OutputFormat.JSON, False, True, True, id="machine-detail"),
        pytest.param(OutputFormat.NDJSON, True, False, True, id="machine-summary-no-diff"),
    ],
)
def test_warn_if_machine_summary_diff_ignored_noops_unless_explicit_machine_summary_diff(
    *,
    output_format: OutputFormat,
    summary_mode: bool,
    diff: bool,
    explicit_diff: bool,
) -> None:
    """Diff-summary warning should only fire for explicit machine summary diffs."""
    state, err = _state_with_console()
    ctx: click.Context = _make_click_context(state=state)
    if explicit_diff:
        ctx.set_parameter_source(
            ArgKey.RENDER_DIFF,
            click.core.ParameterSource.COMMANDLINE,
        )

    warn_if_machine_summary_diff_ignored(
        ctx,
        output_format=output_format,
        summary_mode=summary_mode,
        diff=diff,
    )

    assert err.getvalue() == ""


def test_warn_if_machine_summary_diff_ignored_warns_for_explicit_machine_summary_diff() -> None:
    """Explicit machine summary diffs should warn because per-file diffs are omitted."""
    state, err = _state_with_console()
    ctx: click.Context = _make_click_context(state=state)
    ctx.set_parameter_source(
        ArgKey.RENDER_DIFF,
        click.core.ParameterSource.COMMANDLINE,
    )

    warn_if_machine_summary_diff_ignored(
        ctx,
        output_format=OutputFormat.NDJSON,
        summary_mode=True,
        diff=True,
    )

    assert err.getvalue() == (
        "Note: topmark-test: --diff does not emit per-file diff payloads when "
        "--summary is enabled with --output-format=ndjson.\n"
    )


@pytest.mark.parametrize(
    ("stdin", "files_from", "include_from", "exclude_from"),
    [
        pytest.param(TtyStdin(), ["paths.txt"], None, None, id="tty-no-dash"),
        pytest.param(PipedStdin(), ["-"], None, None, id="piped-files-dash"),
    ],
)
def test_validate_stdin_dash_requires_piped_input_allows_supported_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdin: object,
    files_from: list[str] | None,
    include_from: list[str] | None,
    exclude_from: list[str] | None,
) -> None:
    """STDIN dash validation should pass when dash is absent or paired with piped input."""
    monkeypatch.setattr("sys.stdin", stdin)

    validate_stdin_dash_requires_piped_input(
        _make_click_context(),
        files_from=files_from,
        include_from=include_from,
        exclude_from=exclude_from,
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

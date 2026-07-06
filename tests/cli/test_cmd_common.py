# topmark:header:start
#
#   project      : TopMark
#   file         : test_cmd_common.py
#   file_relpath : tests/cli/test_cmd_common.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared CLI command helper contract tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
import pytest

import topmark.cli.cmd_common as cmd_common
from topmark.cli.cmd_common import build_file_resolution
from topmark.cli.cmd_common import build_resolved_toml_sources_and_config_for_plan
from topmark.cli.cmd_common import build_run_options
from topmark.cli.cmd_common import exit_for_config_validation_error
from topmark.cli.cmd_common import exit_if_no_files
from topmark.cli.cmd_common import resolve_human_console
from topmark.cli.io import InputPlan
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.config.model import FrozenConfig
from topmark.config.model import MutableConfig
from topmark.config.resolution.bridge import ResolvedConfigDraft
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.core.errors import ConfigValidationError
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.machine.payloads import build_meta_payload
from topmark.pipeline.pipelines import PipelineSelection
from topmark.pipeline.pipelines import select_pipeline
from topmark.runtime.model import RunOptions
from topmark.runtime.writer_options import WriterOptions
from topmark.toml.resolution import ResolvedTopmarkTomlSources

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.cli.console.protocols import ConsoleProtocol
    from topmark.config.overrides import ConfigOverrides
    from topmark.resolution.files import FileListResolution


class _CapturingConsole:
    """Small console double for command helper tests."""

    def __init__(self) -> None:
        self.printed: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def print(self, text: str = "", *, nl: bool = True) -> None:
        self.printed.append(text + ("\n" if nl else ""))

    def warn(self, text: str, *, nl: bool = True) -> None:
        self.warnings.append(text + ("\n" if nl else ""))

    def error(self, text: str, *, nl: bool = True) -> None:
        self.errors.append(text + ("\n" if nl else ""))


def _empty_input_plan(
    *,
    stdin_mode: bool = False,
    stdin_filename: str | None = None,
    paths: list[str] | None = None,
    files_from: list[str] | None = None,
    include_from: list[str] | None = None,
    exclude_from: list[str] | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> InputPlan:
    """Build a minimal input plan for command-common tests."""
    return InputPlan(
        stdin_mode=stdin_mode,
        stdin_filename=stdin_filename,
        temp_path=None,
        paths=paths or [],
        files_from=files_from or [],
        include_from=include_from or [],
        exclude_from=exclude_from or [],
        include_patterns=include_patterns or [],
        exclude_patterns=exclude_patterns or [],
    )


def _mutable_config_with_error() -> MutableConfig:
    """Build a mutable config carrying one rendered validation diagnostic."""
    config = MutableConfig()
    config.validation_logs.merged_config.add_error("invalid config value")
    return config


def _mutable_config_without_diagnostics() -> MutableConfig:
    """Build a mutable config carrying no rendered validation diagnostics."""
    return MutableConfig()


def test_build_file_resolution_requires_temp_path_for_stdin_mode() -> None:
    """Content-STDIN file resolution should fail fast without its temp path."""
    run_options = RunOptions(stdin_mode=True)

    with pytest.raises(RuntimeError, match="temp_path should not be undefined"):
        build_file_resolution(
            run_options=run_options,
            config=None,  # pyright: ignore[reportArgumentType]
            temp_path=None,
        )


def test_build_file_resolution_selects_stdin_temp_path(tmp_path: Path) -> None:
    """Content-STDIN file resolution should select only the staged temp path."""
    temp_path: Path = tmp_path / "stdin.py"
    run_options = RunOptions(stdin_mode=True)

    resolution: FileListResolution = build_file_resolution(
        run_options=run_options,
        config=None,  # pyright: ignore[reportArgumentType]
        temp_path=temp_path,
    )

    assert resolution.selected == (temp_path,)
    assert resolution.missing_literals == ()
    assert resolution.unmatched_patterns == ()


def test_exit_if_no_files_reports_friendly_message() -> None:
    """The no-file helper should report and consume empty work lists."""
    console = _CapturingConsole()

    assert exit_if_no_files([], console=console, styled=False)
    assert console.printed == ["\nℹ️  No files to process.\n\n"]


def test_exit_if_no_files_leaves_non_empty_work_lists_unreported(tmp_path: Path) -> None:
    """The no-file helper should not print anything when work exists."""
    console = _CapturingConsole()

    assert not exit_if_no_files([tmp_path / "x.py"], console=console, styled=False)
    assert console.printed == []


def test_build_run_options_uses_pipeline_selection_without_click_context() -> None:
    """Runtime options should be buildable outside an active Click context."""
    pipeline: PipelineSelection = select_pipeline("check", apply=False, diff=True)

    run_options: RunOptions = build_run_options(
        pipeline=pipeline,
        write_mode=None,
        stdin_mode=False,
        stdin_filename=None,
    )

    assert run_options.pipeline_kind == "check"
    assert run_options.apply_changes is False
    assert run_options.emit_diff is True
    assert run_options.output_target is None
    assert run_options.file_write_strategy is None


def test_build_run_options_applies_resolved_writer_options_from_click_state() -> None:
    """Resolved TOML writer preferences should influence mutable file runs."""
    pipeline: PipelineSelection = select_pipeline("check", apply=True, diff=False)
    ctx = click.Context(click.Command("check"))
    state: TopmarkCliState = bootstrap_cli_state(ctx)
    state.resolved_writer_options = WriterOptions(
        file_write_strategy=FileWriteStrategy.INPLACE,
    )

    with ctx:
        run_options: RunOptions = build_run_options(
            pipeline=pipeline,
            write_mode=None,
            stdin_mode=False,
            stdin_filename=None,
        )

    assert run_options.output_target is OutputTarget.FILE
    assert run_options.file_write_strategy is FileWriteStrategy.INPLACE


def test_build_run_options_routes_mutating_stdin_to_stdout() -> None:
    """Mutating content-STDIN runs should reserve STDOUT for transformed content."""
    pipeline: PipelineSelection = select_pipeline("check", apply=True, diff=False)

    run_options: RunOptions = build_run_options(
        pipeline=pipeline,
        write_mode=None,
        stdin_mode=True,
        stdin_filename="stdin.py",
    )

    assert run_options.output_target is OutputTarget.STDOUT
    assert run_options.file_write_strategy is None
    assert run_options.stdin_mode is True
    assert run_options.stdin_filename == "stdin.py"


@pytest.mark.parametrize(
    ("write_mode", "expected_strategy"),
    [
        pytest.param(
            FileWriteStrategy.ATOMIC.value,
            FileWriteStrategy.ATOMIC,
            id="atomic",
        ),
        pytest.param(
            FileWriteStrategy.INPLACE.value,
            FileWriteStrategy.INPLACE,
            id="inplace",
        ),
    ],
)
def test_build_run_options_honors_explicit_file_write_modes(
    write_mode: str,
    expected_strategy: FileWriteStrategy,
) -> None:
    """Explicit write modes should select file output and the requested strategy."""
    pipeline: PipelineSelection = select_pipeline("check", apply=True, diff=False)

    run_options: RunOptions = build_run_options(
        pipeline=pipeline,
        write_mode=write_mode,
        stdin_mode=False,
        stdin_filename=None,
    )

    assert run_options.output_target is OutputTarget.FILE
    assert run_options.file_write_strategy is expected_strategy


def test_resolve_human_console_reuses_stdout_console_when_not_reserved() -> None:
    """Human output should keep the existing console when STDOUT is available."""
    ctx = click.Context(click.Command("check"))
    state: TopmarkCliState = bootstrap_cli_state(ctx)
    original_console: ConsoleProtocol = state.console
    run_options = RunOptions(apply_changes=False, emit_diff=False)

    console: ConsoleProtocol = resolve_human_console(
        ctx, run_options=run_options, enable_color=False
    )

    assert console is original_console
    assert state.console is original_console


@pytest.mark.parametrize(
    "run_options",
    [
        pytest.param(RunOptions(emit_diff=True), id="diff-output"),
        pytest.param(
            RunOptions(apply_changes=True, stdin_mode=True),
            id="applied-stdin-content",
        ),
        pytest.param(
            RunOptions(apply_changes=True, output_target=OutputTarget.STDOUT),
            id="applied-stdout-write-mode",
        ),
    ],
)
def test_resolve_human_console_moves_human_output_to_stderr_when_stdout_reserved(
    run_options: RunOptions,
) -> None:
    """Human output should move to STDERR when STDOUT is reserved for payloads."""
    ctx = click.Context(click.Command("check"))
    state: TopmarkCliState = bootstrap_cli_state(ctx)
    original_console: ConsoleProtocol = state.console

    console: ConsoleProtocol = resolve_human_console(
        ctx, run_options=run_options, enable_color=False
    )

    assert console is state.console
    assert console is not original_console


def test_bootstrapped_state_starts_with_text_output_format() -> None:
    """Command helper tests rely on the default human text output state."""
    ctx = click.Context(click.Command("check"))
    state: TopmarkCliState = bootstrap_cli_state(ctx)

    assert state.output_format is OutputFormat.TEXT


def test_exit_for_config_validation_error_renders_markdown_diagnostics() -> None:
    """Markdown validation failures should render diagnostic details before exit."""
    mutable_config = _mutable_config_with_error()
    config: FrozenConfig = mutable_config.freeze()
    exc = ConfigValidationError(validation_logs=mutable_config.validation_logs, strict=False)
    console = _CapturingConsole()
    ctx = click.Context(click.Command("check"))

    with pytest.raises(click.exceptions.Exit) as exc_info:
        exit_for_config_validation_error(
            ctx=ctx,
            console=console,
            exc=exc,
            config=config,
            fmt=OutputFormat.MARKDOWN,
            meta=build_meta_payload(),
            verbosity_level=0,
            quiet=False,
            color=False,
        )

    assert exc_info.value.exit_code == ExitCode.CONFIG_ERROR
    assert console.errors == [f"Processing stopped: {exc}\n"]
    assert any("invalid config value" in item for item in console.printed)


def test_exit_for_config_validation_error_skips_empty_markdown_diagnostics() -> None:
    """Markdown validation exits should not print empty diagnostic details."""
    mutable_config = _mutable_config_without_diagnostics()
    config: FrozenConfig = mutable_config.freeze()
    exc = ConfigValidationError(validation_logs=mutable_config.validation_logs, strict=False)
    console = _CapturingConsole()
    ctx = click.Context(click.Command("check"))

    with pytest.raises(click.exceptions.Exit) as exc_info:
        exit_for_config_validation_error(
            ctx=ctx,
            console=console,
            exc=exc,
            config=config,
            fmt=OutputFormat.MARKDOWN,
            meta=build_meta_payload(),
            verbosity_level=0,
            quiet=False,
            color=False,
        )

    assert exc_info.value.exit_code == ExitCode.CONFIG_ERROR
    assert console.errors == [f"Processing stopped: {exc}\n"]
    assert console.printed == []


@pytest.mark.parametrize(
    ("quiet", "expects_details"),
    [
        pytest.param(False, True, id="text-details"),
        pytest.param(True, False, id="quiet-text"),
    ],
)
def test_exit_for_config_validation_error_honors_text_quiet_mode(
    quiet: bool,
    expects_details: bool,
) -> None:
    """TEXT validation failures should always show the stop reason but honor quiet."""
    mutable_config = _mutable_config_with_error()
    config: FrozenConfig = mutable_config.freeze()
    exc = ConfigValidationError(validation_logs=mutable_config.validation_logs, strict=False)
    console = _CapturingConsole()
    ctx = click.Context(click.Command("check"))

    with pytest.raises(click.exceptions.Exit) as exc_info:
        exit_for_config_validation_error(
            ctx=ctx,
            console=console,
            exc=exc,
            config=config,
            fmt=OutputFormat.TEXT,
            meta=build_meta_payload(),
            verbosity_level=0,
            quiet=quiet,
            color=False,
        )

    assert exc_info.value.exit_code == ExitCode.CONFIG_ERROR
    assert console.errors == [f"Processing stopped: {exc}\n"]
    assert any("invalid config value" in item for item in console.printed) is expects_details


def test_exit_for_config_validation_error_skips_empty_text_diagnostics() -> None:
    """TEXT validation exits should not print empty diagnostic details."""
    mutable_config = _mutable_config_without_diagnostics()
    config: FrozenConfig = mutable_config.freeze()
    exc = ConfigValidationError(validation_logs=mutable_config.validation_logs, strict=False)
    console = _CapturingConsole()
    ctx = click.Context(click.Command("check"))

    with pytest.raises(click.exceptions.Exit) as exc_info:
        exit_for_config_validation_error(
            ctx=ctx,
            console=console,
            exc=exc,
            config=config,
            fmt=OutputFormat.TEXT,
            meta=build_meta_payload(),
            verbosity_level=0,
            quiet=False,
            color=False,
        )

    assert exc_info.value.exit_code == ExitCode.CONFIG_ERROR
    assert console.errors == [f"Processing stopped: {exc}\n"]
    assert console.printed == []


@pytest.mark.parametrize(
    ("stdin_filename", "expected_inputs"),
    [
        pytest.param(
            "pkg/module.py",
            [(Path.cwd() / "pkg").resolve()],
            id="relative-parent",
        ),
        pytest.param(
            str(Path("/example-topmark-stdin/pkg/module.py")),
            [Path("/example-topmark-stdin/pkg")],
            id="absolute-parent",
        ),
        pytest.param("stdin.py", None, id="plain-filename"),
        pytest.param(None, None, id="missing-filename"),
    ],
)
def test_build_resolved_config_uses_stdin_filename_as_discovery_anchor(
    monkeypatch: pytest.MonkeyPatch,
    stdin_filename: str | None,
    expected_inputs: list[Path] | None,
) -> None:
    """STDIN filenames should provide discovery anchors only when they name a parent."""
    captured_inputs: list[Path] | None = None
    draft = MutableConfig()
    writer_options = WriterOptions(file_write_strategy=FileWriteStrategy.ATOMIC)

    def fake_resolve(
        *,
        input_paths: Iterable[Path] | None = None,
        extra_config_files: Iterable[Path] | None = None,
        strict: bool | None = None,
        no_config: bool = False,
    ) -> ResolvedConfigDraft:
        nonlocal captured_inputs
        captured_inputs = list(input_paths) if input_paths is not None else None
        assert list(extra_config_files or ()) == [Path("extra.toml")]
        assert strict is True
        assert no_config is False
        return ResolvedConfigDraft(
            resolved=ResolvedTopmarkTomlSources(
                sources=[],
                writer_options=writer_options,
                strict=True,
            ),
            draft=draft,
        )

    def fake_apply_config_overrides(
        config: MutableConfig,
        *,
        overrides: ConfigOverrides,
    ) -> MutableConfig:
        assert config is draft
        return config

    monkeypatch.setattr(
        cmd_common,
        "resolve_toml_sources_and_build_mutable_config",
        fake_resolve,
    )
    monkeypatch.setattr(cmd_common, "apply_config_overrides", fake_apply_config_overrides)
    ctx = click.Context(click.Command("check"))

    prepared = build_resolved_toml_sources_and_config_for_plan(
        ctx=ctx,
        plan=_empty_input_plan(stdin_mode=True, stdin_filename=stdin_filename),
        no_config=False,
        config_paths=["extra.toml"],
        strict=True,
        include_file_types=[],
        exclude_file_types=[],
        align_fields=None,
        relative_to=None,
    )

    state: TopmarkCliState = bootstrap_cli_state(ctx)
    assert captured_inputs == expected_inputs
    assert state.resolved_writer_options is writer_options
    assert prepared.draft is draft


def test_build_resolved_config_applies_cli_override_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI input plans and filters should be forwarded as config overrides."""
    captured_inputs: list[Path] | None = None
    captured_overrides: ConfigOverrides | None = None
    draft = MutableConfig()

    def fake_resolve(
        *,
        input_paths: Iterable[Path] | None = None,
        extra_config_files: Iterable[Path] | None = None,
        strict: bool | None = None,
        no_config: bool = False,
    ) -> ResolvedConfigDraft:
        nonlocal captured_inputs
        captured_inputs = list(input_paths) if input_paths is not None else None
        assert list(extra_config_files or ()) == []
        assert strict is None
        assert no_config is True
        return ResolvedConfigDraft(
            resolved=ResolvedTopmarkTomlSources(
                sources=[],
                writer_options=None,
                strict=None,
            ),
            draft=draft,
        )

    def fake_apply_config_overrides(
        config: MutableConfig,
        *,
        overrides: ConfigOverrides,
    ) -> MutableConfig:
        nonlocal captured_overrides
        assert config is draft
        captured_overrides = overrides
        return config

    monkeypatch.setattr(
        cmd_common,
        "resolve_toml_sources_and_build_mutable_config",
        fake_resolve,
    )
    monkeypatch.setattr(cmd_common, "apply_config_overrides", fake_apply_config_overrides)
    ctx = click.Context(click.Command("check"))
    plan = _empty_input_plan(
        paths=["src/topmark/__init__.py", "-"],
        files_from=["files.txt"],
        include_from=["include.txt"],
        exclude_from=["exclude.txt"],
        include_patterns=["src/**"],
        exclude_patterns=["build/**"],
    )

    build_resolved_toml_sources_and_config_for_plan(
        ctx=ctx,
        plan=plan,
        no_config=True,
        config_paths=[],
        strict=None,
        include_file_types=["python"],
        exclude_file_types=["json"],
        align_fields=True,
        relative_to="src",
    )

    assert captured_inputs == [Path("src/topmark/__init__.py")]
    assert captured_overrides is not None
    assert captured_overrides.files == ["src/topmark/__init__.py", "-"]
    assert captured_overrides.files_from == ["files.txt"]
    assert captured_overrides.include_from == ["include.txt"]
    assert captured_overrides.exclude_from == ["exclude.txt"]
    assert captured_overrides.include_patterns == ["src/**"]
    assert captured_overrides.exclude_patterns == ["build/**"]
    assert captured_overrides.include_file_types == ["python"]
    assert captured_overrides.exclude_file_types == ["json"]
    assert captured_overrides.align_fields is True
    assert captured_overrides.relative_to == "src"

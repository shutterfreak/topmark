# topmark:header:start
#
#   project      : TopMark
#   file         : test_engine_path_configs.py
#   file_relpath : tests/pipeline/test_engine_path_configs.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Engine-level tests for path-scoped config application.

These tests lock down the contract of `run_steps_for_files()` now that the
engine can receive per-path effective configs.

They intentionally avoid real pipeline work and instead verify that the engine:

- uses the shared config when no `path_configs` mapping is supplied
- uses the per-path config when `path_configs` is supplied
- builds policy registries consistently for the selected effective config
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import Any

import pytest

from tests.helpers.config import make_frozen_config
from tests.helpers.pipeline import TEST_NOOP_PIPELINE_SELECTION
from topmark.pipeline import engine
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.config.policy import PolicyRegistry


def _fake_runner_run(
    ctx: Any,
    pipeline: object,
    *,
    prune_views: bool = True,
    keep_diff_view: bool = False,
) -> Any:
    """Faked no-op runner.run()."""
    return ctx


@pytest.mark.pipeline
def test_run_steps_for_files_uses_path_specific_configs_when_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-path configs should be passed into bootstrap instead of the shared config."""
    file_a: Path = tmp_path / "a.py"
    file_b: Path = tmp_path / "b.py"
    file_a.write_text("print('a')\n", encoding="utf-8")
    file_b.write_text("print('b')\n", encoding="utf-8")

    shared_cfg: FrozenConfig = make_frozen_config(header_fields=["project"])
    cfg_a: FrozenConfig = make_frozen_config(header_fields=["file"])
    cfg_b: FrozenConfig = make_frozen_config(header_fields=["license"])

    path_configs: dict[Path, FrozenConfig] = {
        file_a: cfg_a,
        file_b: cfg_b,
    }

    bootstrap_calls: list[tuple[Path, FrozenConfig, RunOptions, object]] = []
    policy_calls: list[FrozenConfig] = []

    class FakeProcessingContext:
        """Minimal stand-in exposing the bootstrap contract used by the engine."""

        @classmethod
        def bootstrap(
            cls,
            *,
            path: Path,
            config: FrozenConfig,
            run_options: RunOptions,
            policy_registry_override: PolicyRegistry | None = None,
        ) -> Any:
            bootstrap_calls.append((path, config, run_options, policy_registry_override))
            return SimpleNamespace(path=path, config=config, run_options=run_options)

    def fake_make_policy_registry(config: FrozenConfig) -> object:
        policy_calls.append(config)
        return {"header_fields": tuple(config.header_fields)}

    monkeypatch.setattr(engine, "ProcessingContext", FakeProcessingContext)
    monkeypatch.setattr(engine, "make_policy_registry", fake_make_policy_registry)
    monkeypatch.setattr(engine.runner, "run", _fake_runner_run)

    run_options: RunOptions = RunOptions(apply_changes=False)

    pipeline_run: engine.PipelineExecution = engine.run_steps_for_files(
        run_options=run_options,
        config=shared_cfg,
        path_configs=path_configs,
        pipeline=TEST_NOOP_PIPELINE_SELECTION,
        file_list=[file_a, file_b],
    )

    assert pipeline_run.exit_code is None
    assert [result.path for result in pipeline_run.contexts] == [file_a, file_b]

    assert len(bootstrap_calls) == 2
    assert bootstrap_calls[0][0] == file_a
    assert bootstrap_calls[0][1] is cfg_a
    assert bootstrap_calls[1][0] == file_b
    assert bootstrap_calls[1][1] is cfg_b

    assert bootstrap_calls[0][2] is run_options
    assert bootstrap_calls[1][2] is run_options

    # With path_configs, the engine should build registries only for the effective
    # per-path configs and skip the unused shared-config registry.
    assert policy_calls == [cfg_a, cfg_b]

    assert bootstrap_calls[0][3] == {"header_fields": ("file",)}
    assert bootstrap_calls[1][3] == {"header_fields": ("license",)}


@pytest.mark.pipeline
def test_run_steps_for_files_falls_back_to_shared_config_without_path_configs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without path_configs, the shared config and one shared policy registry are reused."""
    file_a: Path = tmp_path / "a.py"
    file_b: Path = tmp_path / "b.py"
    file_a.write_text("print('a')\n", encoding="utf-8")
    file_b.write_text("print('b')\n", encoding="utf-8")

    shared_cfg: FrozenConfig = make_frozen_config(header_fields=["project", "file"])

    bootstrap_calls: list[tuple[Path, FrozenConfig, RunOptions, object]] = []
    policy_calls: list[FrozenConfig] = []

    class FakeProcessingContext:
        """Minimal stand-in exposing the bootstrap contract used by the engine."""

        @classmethod
        def bootstrap(
            cls,
            *,
            path: Path,
            config: FrozenConfig,
            run_options: RunOptions,
            policy_registry_override: PolicyRegistry | None = None,
        ) -> Any:
            bootstrap_calls.append((path, config, run_options, policy_registry_override))
            return SimpleNamespace(path=path, config=config, run_options=run_options)

    def fake_make_policy_registry(config: FrozenConfig) -> object:
        policy_calls.append(config)
        return {"header_fields": tuple(config.header_fields)}

    monkeypatch.setattr(engine, "ProcessingContext", FakeProcessingContext)
    monkeypatch.setattr(engine, "make_policy_registry", fake_make_policy_registry)
    monkeypatch.setattr(engine.runner, "run", _fake_runner_run)

    run_options: RunOptions = RunOptions(apply_changes=False)

    pipeline_run: engine.PipelineExecution = engine.run_steps_for_files(
        run_options=run_options,
        config=shared_cfg,
        path_configs=None,
        pipeline=TEST_NOOP_PIPELINE_SELECTION,
        file_list=[file_a, file_b],
    )

    assert pipeline_run.exit_code is None
    assert [result.path for result in pipeline_run.contexts] == [file_a, file_b]

    assert len(bootstrap_calls) == 2
    assert bootstrap_calls[0][1] is shared_cfg
    assert bootstrap_calls[1][1] is shared_cfg

    assert bootstrap_calls[0][2] is run_options
    assert bootstrap_calls[1][2] is run_options

    # Without path_configs, one shared registry should be built and reused.
    assert policy_calls == [shared_cfg]
    assert bootstrap_calls[0][3] == {"header_fields": ("project", "file")}
    assert bootstrap_calls[1][3] == {"header_fields": ("project", "file")}


@pytest.mark.pipeline
def test_iter_steps_for_files_yields_contexts_before_later_files_are_bootstrapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streaming engine iteration should not materialize all contexts up front."""
    file_a: Path = tmp_path / "a.py"
    file_b: Path = tmp_path / "b.py"
    file_a.write_text("print('a')\n", encoding="utf-8")
    file_b.write_text("print('b')\n", encoding="utf-8")

    shared_cfg: FrozenConfig = make_frozen_config(header_fields=["project"])
    bootstrapped_paths: list[Path] = []

    class FakeProcessingContext:
        """Minimal stand-in exposing the bootstrap contract used by the engine."""

        @classmethod
        def bootstrap(
            cls,
            *,
            path: Path,
            config: FrozenConfig,
            run_options: RunOptions,
            policy_registry_override: PolicyRegistry | None = None,
        ) -> Any:
            bootstrapped_paths.append(path)
            return SimpleNamespace(path=path, config=config, run_options=run_options)

    monkeypatch.setattr(engine, "ProcessingContext", FakeProcessingContext)
    monkeypatch.setattr(engine.runner, "run", _fake_runner_run)

    state: engine.PipelineExecutionState = engine.PipelineExecutionState()
    contexts: Iterator[Any] = engine.iter_steps_for_files(
        run_options=RunOptions(apply_changes=False),
        config=shared_cfg,
        path_configs=None,
        pipeline=TEST_NOOP_PIPELINE_SELECTION,
        file_list=[file_a, file_b],
        state=state,
    )

    first: Any = next(contexts)

    assert first.path == file_a
    assert bootstrapped_paths == [file_a]
    assert state.exit_code is None

    second: Any = next(contexts)

    assert second.path == file_b
    assert bootstrapped_paths == [file_a, file_b]


@pytest.mark.pipeline
def test_iter_steps_for_files_records_engine_exit_code_in_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streaming engine iteration should preserve batch error-code semantics."""
    missing: Path = tmp_path / "missing.py"
    present: Path = tmp_path / "present.py"
    present.write_text("print('present')\n", encoding="utf-8")

    shared_cfg: FrozenConfig = make_frozen_config(header_fields=["project"])

    class FakeProcessingContext:
        """Minimal stand-in exposing the bootstrap contract used by the engine."""

        @classmethod
        def bootstrap(
            cls,
            *,
            path: Path,
            config: FrozenConfig,
            run_options: RunOptions,
            policy_registry_override: PolicyRegistry | None = None,
        ) -> Any:
            if path == missing:
                raise FileNotFoundError(path)
            return SimpleNamespace(path=path, config=config, run_options=run_options)

    monkeypatch.setattr(engine, "ProcessingContext", FakeProcessingContext)
    monkeypatch.setattr(engine.runner, "run", _fake_runner_run)

    state: engine.PipelineExecutionState = engine.PipelineExecutionState()
    contexts: list[Any] = list(
        engine.iter_steps_for_files(
            run_options=RunOptions(apply_changes=False),
            config=shared_cfg,
            path_configs=None,
            pipeline=TEST_NOOP_PIPELINE_SELECTION,
            file_list=[missing, present],
            state=state,
        ),
    )

    assert [ctx.path for ctx in contexts] == [present]
    assert state.exit_code is engine.ExitCode.FILE_NOT_FOUND

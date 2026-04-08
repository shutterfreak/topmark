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

from tests.helpers.config import make_config
from topmark.pipeline import engine
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.config.policy import PolicyRegistry


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

    shared_cfg: Config = make_config(header_fields=["project"])
    cfg_a: Config = make_config(header_fields=["file"])
    cfg_b: Config = make_config(header_fields=["license"])

    path_configs: dict[Path, Config] = {
        file_a: cfg_a,
        file_b: cfg_b,
    }

    bootstrap_calls: list[tuple[Path, Config, RunOptions, object]] = []
    policy_calls: list[Config] = []

    class FakeProcessingContext:
        """Minimal stand-in exposing the bootstrap contract used by the engine."""

        @classmethod
        def bootstrap(
            cls,
            *,
            path: Path,
            config: Config,
            run_options: RunOptions,
            policy_registry_override: PolicyRegistry | None = None,
        ) -> Any:
            bootstrap_calls.append((path, config, run_options, policy_registry_override))
            return SimpleNamespace(path=path, config=config, run_options=run_options)

    def fake_make_policy_registry(config: Config) -> object:
        policy_calls.append(config)
        return {"header_fields": tuple(config.header_fields)}

    def fake_runner_run(ctx: Any, pipeline: object, *, prune: bool = True) -> Any:
        return ctx

    monkeypatch.setattr(engine, "ProcessingContext", FakeProcessingContext)
    monkeypatch.setattr(engine, "make_policy_registry", fake_make_policy_registry)
    monkeypatch.setattr(engine.runner, "run", fake_runner_run)

    run_options: RunOptions = RunOptions(apply_changes=False)

    results, encountered_error = engine.run_steps_for_files(
        run_options=run_options,
        config=shared_cfg,
        path_configs=path_configs,
        pipeline=(),
        file_list=[file_a, file_b],
    )

    assert encountered_error is None
    assert [result.path for result in results] == [file_a, file_b]

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

    shared_cfg: Config = make_config(header_fields=["project", "file"])

    bootstrap_calls: list[tuple[Path, Config, RunOptions, object]] = []
    policy_calls: list[Config] = []

    class FakeProcessingContext:
        """Minimal stand-in exposing the bootstrap contract used by the engine."""

        @classmethod
        def bootstrap(
            cls,
            *,
            path: Path,
            config: Config,
            run_options: RunOptions,
            policy_registry_override: PolicyRegistry | None = None,
        ) -> Any:
            bootstrap_calls.append((path, config, run_options, policy_registry_override))
            return SimpleNamespace(path=path, config=config, run_options=run_options)

    def fake_make_policy_registry(config: Config) -> object:
        policy_calls.append(config)
        return {"header_fields": tuple(config.header_fields)}

    def fake_runner_run(ctx: Any, pipeline: object, *, prune: bool = True) -> Any:
        return ctx

    monkeypatch.setattr(engine, "ProcessingContext", FakeProcessingContext)
    monkeypatch.setattr(engine, "make_policy_registry", fake_make_policy_registry)
    monkeypatch.setattr(engine.runner, "run", fake_runner_run)

    run_options: RunOptions = RunOptions(apply_changes=False)

    results, encountered_error = engine.run_steps_for_files(
        run_options=run_options,
        config=shared_cfg,
        path_configs=None,
        pipeline=(),
        file_list=[file_a, file_b],
    )

    assert encountered_error is None
    assert [result.path for result in results] == [file_a, file_b]

    assert len(bootstrap_calls) == 2
    assert bootstrap_calls[0][1] is shared_cfg
    assert bootstrap_calls[1][1] is shared_cfg

    assert bootstrap_calls[0][2] is run_options
    assert bootstrap_calls[1][2] is run_options

    # Without path_configs, one shared registry should be built and reused.
    assert policy_calls == [shared_cfg]
    assert bootstrap_calls[0][3] == {"header_fields": ("project", "file")}
    assert bootstrap_calls[1][3] == {"header_fields": ("project", "file")}

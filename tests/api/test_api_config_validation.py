# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_config_validation.py
#   file_relpath : tests/api/test_api_config_validation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API preflight rejects invalid configuration before discovery, events, or writes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Literal

import pytest

import topmark.api.runtime as runtime
from topmark import api
from topmark.api.types import PublicPolicy
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.errors import ConfigValidationError
from topmark.toml.render import render_toml_table
from topmark.toml.typing_guards import toml_table_from_mapping

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.config.validation import FrozenValidationLogs
    from topmark.diagnostic.model import FrozenDiagnosticLog
    from topmark.diagnostic.model import MutableDiagnosticLog
    from topmark.resolution.files import FileListResolution

Command = Literal[
    "check",
    "strip",
    "probe",
    "stream_check",
    "stream_strip",
    "stream_probe",
]

COMMANDS: tuple[Command, ...] = (
    "check",
    "strip",
    "probe",
    "stream_check",
    "stream_strip",
    "stream_probe",
)


def _invoke(
    command: Command,
    path: Path,
    config: Mapping[str, object] | FrozenConfig | None,
) -> None:
    """Invoke batch processing or request the first streaming event."""
    if command == "check":
        api.check([path], config=config, apply=True)
    elif command == "strip":
        api.strip([path], config=config, apply=True)
    elif command == "probe":
        api.probe([path], config=config)
    elif command == "stream_check":
        next(api.stream_check([path], config=config, apply=True))
    elif command == "stream_strip":
        next(api.stream_strip([path], config=config, apply=True))
    else:
        next(api.stream_probe([path], config=config))


def _input_file(
    tmp_path: Path,
    command: Command,
) -> Path:
    """Provide content that would change if check or strip reached the pipeline."""
    path: Path = tmp_path / "sample.py"
    path.write_text("print(1)\n", encoding="utf-8")
    if "strip" in command:
        api.check([path], apply=True, config={"header": {"fields": ["file"]}})
        assert TOPMARK_START_MARKER in path.read_text(encoding="utf-8")
    return path


def _reject_discovery(
    config: FrozenConfig,
    *,
    file_type_config_for_path: Callable[[Path], FrozenConfig] | None = None,
) -> FileListResolution:
    """Fail if an invalid configuration reaches file-list resolution."""
    pytest.fail("Invalid configuration reached file discovery")


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize(
    "rules",
    [
        "*.py",
        [{"file_type": "missing", "patterns": ["*.py"]}],
        [{"action": "infer", "file_type": "python", "patterns": ["*.py"]}],
        [{"action": "infer", "file_type": "", "patterns": ["*.py"]}],
        [{"action": "assign", "patterns": ["*.py"]}],
        [{"action": "unknown", "patterns": ["*.py"]}],
        [{"file_type": "python", "patterns": []}],
        [{"file_type": "python", "patterns": "*.py"}],
        [{"file_type": "python", "patterns": ["[z-a]"]}],
    ],
)
def test_invalid_mapping_rejected_before_discovery_and_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: Command,
    rules: object,
) -> None:
    """Every entry point rejects malformed rules before fallback inference can mutate files."""
    path: Path = _input_file(tmp_path, command)
    before: bytes = path.read_bytes()
    monkeypatch.setattr(runtime, "resolve_file_list_with_diagnostics", _reject_discovery)
    with pytest.raises(ConfigValidationError) as exc_info:
        _invoke(
            command,
            path,
            {
                "header": {
                    "fields": ["file"],
                },
                "files": {
                    "file_type_assignments": rules,
                },
            },
        )
    diagnostics: MutableDiagnosticLog | FrozenDiagnosticLog | None = (
        exc_info.value.context.diagnostics
    )
    assert diagnostics is not None and diagnostics.stats().n_error >= 1
    assert path.read_bytes() == before


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("source", ["mapping", "topmark", "pyproject"])
@pytest.mark.parametrize("warning", ["unknown_key", "contradictory_duplicate", "unknown_section"])
def test_effective_source_strictness_applies_to_assignment_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: Command,
    strict: bool,
    source: str,
    warning: str,
) -> None:
    """Mapping and discovered source strictness reject warnings before the first stream event."""
    monkeypatch.chdir(tmp_path)
    path: Path = _input_file(tmp_path, command)
    before: bytes = path.read_bytes()
    rules: list[dict[str, object]] = [
        {
            "file_type": "python",
            "patterns": ["*.py"],
        }
    ]
    if warning == "unknown_key":
        rules[0]["typo"] = True
    elif warning == "contradictory_duplicate":
        rules.append(
            {
                "action": "infer",
                "patterns": ["*.py"],
            }
        )
    mapping: dict[str, object] = {
        "config": {
            "root": True,
            "strict": strict,
        },
        "header": {
            "fields": ["file"],
        },
        "files": {
            "file_type_assignments": rules,
        },
    }
    if warning == "unknown_section":
        mapping["unexpected"] = {"value": True}
    config: Mapping[str, object] | None = mapping
    if source != "mapping":
        table: Mapping[str, object] = (
            mapping
            if source == "topmark"
            else {
                "tool": {"topmark": mapping},
            }
        )
        filename: str = "topmark.toml" if source == "topmark" else "pyproject.toml"
        (tmp_path / filename).write_text(
            render_toml_table(toml_table_from_mapping(table)), encoding="utf-8"
        )
        config = None
    if strict:
        monkeypatch.setattr(runtime, "resolve_file_list_with_diagnostics", _reject_discovery)
        with pytest.raises(ConfigValidationError) as exc_info:
            _invoke(command, path, config)
        diagnostics: MutableDiagnosticLog | FrozenDiagnosticLog | None = (
            exc_info.value.context.diagnostics
        )
        assert diagnostics is not None and diagnostics.stats().n_warning >= 1
        assert diagnostics.stats().n_error == 0
        if warning == "unknown_section":
            assert any("Unknown TOML section" in d.message for d in diagnostics)
        assert "strict = True" in str(exc_info.value)
        assert path.read_bytes() == before
    else:
        _invoke(command, path, config)
        if "strip" in command:
            assert path.read_text(encoding="utf-8") == "print(1)\n"
        elif "check" in command:
            assert TOPMARK_START_MARKER in path.read_text(encoding="utf-8")
        else:
            assert path.read_bytes() == before


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("stage", ["toml_source", "merged_config", "runtime_applicability"])
def test_frozen_seed_errors_rejected_without_mutating_seed(
    tmp_path: Path,
    command: Command,
    stage: str,
) -> None:
    """Immutable seeds retain every validation stage while errors remain fatal."""
    path: Path = _input_file(tmp_path, command)
    before: bytes = path.read_bytes()
    draft: runtime.MutableConfig = mutable_config_from_defaults()
    logs: dict[str, MutableDiagnosticLog] = {
        "toml_source": draft.validation_logs.toml_source,
        "merged_config": draft.validation_logs.merged_config,
        "runtime_applicability": draft.validation_logs.runtime_applicability,
    }
    logs[stage].add_error("preserved seed error")
    seed: runtime.FrozenConfig = draft.freeze()
    original_logs: FrozenValidationLogs = seed.validation_logs
    with pytest.raises(ConfigValidationError, match="strict = False") as exc_info:
        _invoke(command, path, seed)
    assert seed.validation_logs == original_logs
    diagnostics: MutableDiagnosticLog | FrozenDiagnosticLog | None = (
        exc_info.value.context.diagnostics
    )
    assert diagnostics is not None and any(d.message == "preserved seed error" for d in diagnostics)
    assert path.read_bytes() == before


def test_strict_validation_runs_after_api_policy_overlays(
    tmp_path: Path,
) -> None:
    """Warnings introduced by explicit overlays participate in strict validation."""
    path: Path = _input_file(tmp_path, "check")
    before: bytes = path.read_bytes()
    with pytest.raises(ConfigValidationError) as exc_info:
        api.check(
            [path],
            apply=True,
            config={
                "config": {
                    "strict": True,
                },
                "header": {
                    "fields": ["file"],
                },
            },
            policy_by_type={
                "missing": PublicPolicy(allow_reflow=True),
            },
        )
    diagnostics: MutableDiagnosticLog | FrozenDiagnosticLog | None = (
        exc_info.value.context.diagnostics
    )
    assert diagnostics is not None
    assert any("Unknown policy_by_type" in d.message for d in diagnostics)
    assert path.read_bytes() == before


def test_valid_invocation_filter_can_replace_invalid_seed_filter(
    tmp_path: Path,
) -> None:
    """Validate after explicit filter overrides, retaining established precedence."""
    path: Path = _input_file(tmp_path, "check")
    result: api.RunResult = api.check(
        [path],
        apply=True,
        include_file_types=["python"],
        config={
            "config": {
                "strict": True,
            },
            "header": {
                "fields": ["file"],
            },
            "files": {
                "include_file_types": ["missing"],
            },
        },
    )
    assert result.written == 1


def test_frozen_seed_warnings_are_advisory_without_source_strictness(
    tmp_path: Path,
) -> None:
    """FrozenConfig has no source-local strictness preference and retains warning diagnostics."""
    path: Path = _input_file(tmp_path, "check")
    draft: runtime.MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_warning("retained advisory")
    seed: runtime.FrozenConfig = draft.freeze()
    result: api.RunResult = api.check(
        [path],
        apply=True,
        config=seed,
    )
    assert result.written == 1
    assert seed.validation_logs.merged_config.stats().n_warning == 1


@pytest.mark.parametrize("command", COMMANDS)
def test_strict_scoped_runtime_diagnostics_cannot_be_hidden_by_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: Command,
) -> None:
    """Validate every scoped discovery config before any file can be changed."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        '[config]\nroot=true\nstrict=true\n[header]\nfields=["file"]\n',
        encoding="utf-8",
    )
    paths: list[Path] = []
    for folder, target in [("a", "missing"), ("b", "python")]:
        directory: Path = tmp_path / folder
        directory.mkdir()
        paths.append(_input_file(directory, command))
        (directory / "topmark.toml").write_text(
            f'[header]\nfields=["file"]\n[files]\ninclude_file_types=["{target}"]\n',
            encoding="utf-8",
        )
    original: dict[Path, bytes] = {path: path.read_bytes() for path in paths}
    with pytest.raises(ConfigValidationError) as exc_info:
        _invoke(command, tmp_path, None)
    diagnostics: MutableDiagnosticLog | FrozenDiagnosticLog | None = (
        exc_info.value.context.diagnostics
    )
    assert diagnostics is not None
    assert any("Unknown included file types" in d.message for d in diagnostics)
    assert {path: path.read_bytes() for path in paths} == original

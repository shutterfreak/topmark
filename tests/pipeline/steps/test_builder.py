# topmark:header:start
#
#   project      : TopMark
#   file         : test_builder.py
#   file_relpath : tests/pipeline/steps/test_builder.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Direct contracts for the builder pipeline step."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.paths import symlink_or_skip
from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import run_builder
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.model import MutableConfig
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import GenerationStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.steps import builder as builder_module
from topmark.pipeline.steps.builder import BuilderStep
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.hints import Hint


def _builder_config(
    *,
    header_fields: list[str],
    field_values: dict[str, str] | None = None,
) -> FrozenConfig:
    """Return a coherent effective config with explicit builder inputs."""
    config: MutableConfig = mutable_config_from_defaults()
    config.header_fields = header_fields
    config.field_values = field_values or {}
    return config.freeze()


def _builder_context(path: Path, cfg: FrozenConfig) -> ProcessingContext:
    """Return an unhalted post-scanner context accepted by the builder."""
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.status.fs = FsStatus.OK
    ctx.status.content = ContentStatus.OK
    ctx.status.header = HeaderStatus.MISSING
    return ctx


def _only_hint(ctx: ProcessingContext) -> Hint:
    """Return the context's sole hint."""
    assert len(ctx.diagnostic_hints.items) == 1
    return ctx.diagnostic_hints.items[0]


def _policy_refuses(ctx: ProcessingContext) -> bool:
    """Return a deterministic builder-stage policy refusal."""
    _: ProcessingContext = ctx
    return False


def _build_for_path(path: Path, cfg: FrozenConfig) -> ProcessingContext:
    """Run the builder step for an existing path.

    Args:
        path: Existing path used to seed the processing context.
        cfg: Frozen configuration used by the builder.

    Returns:
        The processed context after running the builder step.
    """
    return run_builder(_builder_context(path, cfg))


def test_builder_declares_only_the_generation_axis_and_consumes_no_views() -> None:
    """Builder output is generation state derived without consuming pipeline views."""
    step = BuilderStep()

    assert step.primary_axis is Axis.GENERATION
    assert step.axes_written == (Axis.GENERATION,)
    assert step.consumes_views == frozenset()


def test_builder_generates_complete_builtins_and_ordered_selection_for_empty_file(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Readable zero-byte input still produces metadata and selected custom fields."""
    monkeypatch.chdir(tmp_path)
    file_path: Path = tmp_path / "empty.py"
    file_path.write_text("", encoding="utf-8", newline="")
    cfg: FrozenConfig = _builder_config(
        header_fields=["owner", "file_relpath", "file"],
        field_values={"owner": "TopMark", "unselected": "not rendered"},
    )
    ctx: ProcessingContext = _builder_context(file_path, cfg)
    ctx.status.fs = FsStatus.EMPTY

    run_builder(ctx)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.builtins == {
        "file": "empty.py",
        "file_relpath": "empty.py",
        "file_abspath": file_path.resolve().as_posix(),
        "relpath": ".",
        "abspath": tmp_path.resolve().as_posix(),
    }
    assert ctx.views.build.selected == {
        "owner": "TopMark",
        "file_relpath": "empty.py",
        "file": "empty.py",
    }
    assert ctx.views.build.selected is not None
    assert list(ctx.views.build.selected) == ["owner", "file_relpath", "file"]
    assert ctx.views.image is None
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    assert ctx.diagnostic_hints.items == []


def test_builder_preserves_derived_builtins_while_configured_overrides_win(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Configured built-in values affect selection, not the derived mapping."""
    monkeypatch.chdir(tmp_path)
    file_path: Path = tmp_path / "source.py"
    file_path.write_text("print('hello')\n", encoding="utf-8", newline="")
    cfg: FrozenConfig = _builder_config(
        header_fields=["file", "project", "abspath"],
        field_values={
            "abspath": "configured/directory",
            "file": "configured.py",
            "project": "TopMark",
            "unselected": "not rendered",
        },
    )

    ctx: ProcessingContext = _build_for_path(file_path, cfg)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.builtins is not None
    assert ctx.views.build.builtins["file"] == "source.py"
    assert ctx.views.build.builtins["abspath"] == tmp_path.resolve().as_posix()
    assert ctx.views.build.selected == {
        "file": "configured.py",
        "project": "TopMark",
        "abspath": "configured/directory",
    }
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.WARNING, "Redefined built-in fields: abspath, file")
    ]
    assert ctx.halt_state is None
    assert ctx.diagnostic_hints.items == []


def test_builder_reports_unknown_requested_field_and_keeps_known_selection(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """An unknown request is diagnosed without discarding known generated fields."""
    monkeypatch.chdir(tmp_path)
    file_path: Path = tmp_path / "source.py"
    file_path.write_text("print('hello')\n", encoding="utf-8", newline="")
    cfg: FrozenConfig = _builder_config(
        header_fields=["file", "unknown", "project"],
        field_values={"project": "TopMark"},
    )

    ctx: ProcessingContext = _build_for_path(file_path, cfg)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.selected == {"file": "source.py", "project": "TopMark"}
    assert ctx.views.build.selected is not None
    assert list(ctx.views.build.selected) == ["file", "project"]
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.ERROR, "Unknown header field: unknown")
    ]
    assert ctx.halt_state is None
    assert ctx.diagnostic_hints.items == []


def test_builder_maps_no_configured_fields_without_creating_a_view(tmp_path: Path) -> None:
    """No requested fields produce a non-terminal no-fields outcome."""
    file_path: Path = tmp_path / "source.py"
    file_path.write_text("print('hello')\n", encoding="utf-8", newline="")
    cfg: FrozenConfig = _builder_config(header_fields=[])

    ctx: ProcessingContext = _build_for_path(file_path, cfg)

    assert ctx.status.generation is GenerationStatus.NO_FIELDS
    assert ctx.views.build is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, "No header fields specified.")
    ]
    assert ctx.halt_state is None
    hint: Hint = _only_hint(ctx)
    assert (hint.axis, hint.code, hint.cluster, hint.message, hint.terminal) == (
        Axis.GENERATION,
        KnownCode.GENERATION_NO_FIELDS.value,
        Cluster.BLOCKED_POLICY.value,
        "no header fields configured",
        False,
    )


def test_builder_maps_policy_refusal_before_generating_fields(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Builder-stage policy refusal skips generation and owns the terminal halt."""
    file_path: Path = tmp_path / "source.py"
    file_path.write_text("print('hello')\n", encoding="utf-8", newline="")
    cfg: FrozenConfig = _builder_config(header_fields=["file"])
    ctx: ProcessingContext = _builder_context(file_path, cfg)
    ctx.status.header = HeaderStatus.DETECTED
    monkeypatch.setattr(builder_module, "check_permitted_by_policy", _policy_refuses)

    run_builder(ctx)

    assert ctx.status.generation is GenerationStatus.SKIPPED
    assert ctx.views.build is None
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, "header field generation skipped by policy")
    ]
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "BuilderStep"
    assert ctx.halt_state.reason_code == "header field generation skipped by policy"
    hint: Hint = _only_hint(ctx)
    assert (hint.axis, hint.code, hint.cluster, hint.message, hint.terminal) == (
        Axis.GENERATION,
        KnownCode.PLAN_SKIP.value,
        Cluster.BLOCKED_POLICY.value,
        "header field generation skipped",
        True,
    )


def test_builder_uses_logical_stdin_path_but_materialized_content_directory(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Stdin metadata separates the logical header path from actual content storage."""
    monkeypatch.chdir(tmp_path)
    content_path: Path = tmp_path / "materialized" / "stdin-content.py"
    content_path.parent.mkdir()
    content_path.write_text("print('hello')\n", encoding="utf-8", newline="")
    logical_path = "logical/input.py"
    cfg: FrozenConfig = _builder_config(
        header_fields=["file", "file_relpath", "file_abspath", "relpath", "abspath"]
    )
    ctx: ProcessingContext = _builder_context(content_path, cfg)
    ctx.run_options = RunOptions(
        pipeline_kind="check",
        apply_changes=False,
        stdin_mode=True,
        stdin_filename=logical_path,
    )

    run_builder(ctx)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.builtins == {
        "file": "input.py",
        "file_relpath": "logical/input.py",
        "file_abspath": (tmp_path / logical_path).resolve().as_posix(),
        "relpath": "logical",
        "abspath": content_path.parent.resolve().as_posix(),
    }
    assert ctx.views.build.selected == ctx.views.build.builtins
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    assert ctx.diagnostic_hints.items == []


def test_builder_generates_path_fields_from_matching_filesystem_spelling(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Generate built-in path fields from a normally cased file path."""
    monkeypatch.chdir(tmp_path)

    file_path: Path = tmp_path / "README.md"
    file_path.write_text("# README\n", encoding="utf-8")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = _build_for_path(file_path, cfg)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.builtins is not None
    assert ctx.views.build.builtins["file"] == "README.md"
    assert ctx.views.build.builtins["file_relpath"] == "README.md"
    assert ctx.views.build.builtins["file_abspath"] == file_path.resolve().as_posix()


@pytest.mark.case_insensitive_fs
def test_builder_generates_path_fields_from_canonical_filesystem_spelling(
    case_insensitive_fs: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Generate built-in path fields from canonical casing after resolution.

    This reproduces issue #75: on a case-insensitive filesystem, the invocation
    path may resolve successfully even when its casing differs from the directory
    entries stored on disk. Built-in fields should use the canonical filesystem
    spelling, not the invocation spelling.
    """
    monkeypatch.chdir(case_insensitive_fs)

    actual_dir: Path = case_insensitive_fs / "Docs"
    actual_dir.mkdir()
    actual_file: Path = actual_dir / "README.md"
    actual_file.write_text("# README\n", encoding="utf-8")

    invocation_path: Path = case_insensitive_fs / "docs" / "REadme.md"
    assert invocation_path.exists()

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = _build_for_path(invocation_path, cfg)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.builtins is not None
    assert ctx.views.build.builtins["file"] == "README.md"
    assert ctx.views.build.builtins["file_relpath"] == "Docs/README.md"
    assert ctx.views.build.builtins["file_abspath"] == actual_file.resolve().as_posix()


@pytest.mark.case_insensitive_fs
def test_builder_generates_relpath_from_canonical_filesystem_spelling_with_relative_to(
    case_insensitive_fs: Path,
) -> None:
    """Generate `file_relpath` from canonical casing relative to a configured base."""
    project_root: Path = case_insensitive_fs / "ProjectRoot"
    actual_dir: Path = project_root / "Docs"
    actual_dir.mkdir(parents=True)
    actual_file: Path = actual_dir / "README.md"
    actual_file.write_text("# README\n", encoding="utf-8")

    invocation_path: Path = case_insensitive_fs / "projectroot" / "docs" / "REadme.md"
    assert invocation_path.exists()

    cfg: FrozenConfig = (
        mutable_config_from_defaults().merge_with(
            MutableConfig(
                relative_to=project_root,
            )
        )
    ).freeze()

    ctx: ProcessingContext = _build_for_path(invocation_path, cfg)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.builtins is not None
    assert ctx.views.build.builtins["file"] == "README.md"
    assert ctx.views.build.builtins["file_relpath"] == "Docs/README.md"
    assert ctx.views.build.builtins["file_abspath"] == actual_file.resolve().as_posix()


def test_builder_generates_path_fields_from_symlink_target(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Generate filesystem metadata for the resolved target of a symlinked input."""
    monkeypatch.chdir(tmp_path)

    target_path: Path = tmp_path / "real" / "source.py"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("print('hello')\n", encoding="utf-8")
    link_path: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target_path)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = _build_for_path(link_path, cfg)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.views.build is not None
    assert ctx.views.build.builtins is not None
    assert ctx.views.build.builtins["file"] == "source.py"
    assert ctx.views.build.builtins["file_relpath"] == "real/source.py"
    assert ctx.views.build.builtins["file_abspath"] == target_path.resolve().as_posix()
    assert ctx.views.build.builtins["relpath"] == "real"
    assert ctx.views.build.builtins["abspath"] == (tmp_path / "real").resolve().as_posix()
    assert ctx.diagnostics.has_error is False
    assert ctx.diagnostics.has_warning is False


def test_builder_generates_same_path_fields_for_symlink_and_target(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Generate stable metadata when a target is reached through a symlink spelling."""
    monkeypatch.chdir(tmp_path)

    target_path: Path = tmp_path / "real" / "source.py"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("print('hello')\n", encoding="utf-8")
    link_path: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target_path)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    target_ctx: ProcessingContext = _build_for_path(target_path, cfg)
    link_ctx: ProcessingContext = _build_for_path(link_path, cfg)

    assert target_ctx.status.generation is GenerationStatus.GENERATED
    assert link_ctx.status.generation is GenerationStatus.GENERATED
    assert target_ctx.views.build is not None
    assert link_ctx.views.build is not None
    assert target_ctx.views.build.builtins == link_ctx.views.build.builtins


def test_builder_does_not_warn_when_given_symlink_spelling_directly(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Avoid pretending the builder can diagnose original symlink spelling reliably.

    Normal file-list resolution already collapses symlink spellings before the
    processing context is bootstrapped. Lower-level callers may still pass a
    symlink path directly, but warning consistently would require retaining the
    original invocation spelling as separate context state.
    """
    monkeypatch.chdir(tmp_path)

    target_path: Path = tmp_path / "real" / "source.py"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("print('hello')\n", encoding="utf-8")
    link_path: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target_path)

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = _build_for_path(link_path, cfg)

    assert ctx.status.generation is GenerationStatus.GENERATED
    assert ctx.diagnostics.has_error is False
    assert ctx.diagnostics.has_warning is False

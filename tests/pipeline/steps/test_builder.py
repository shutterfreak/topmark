# topmark:header:start
#
#   project      : TopMark
#   file         : test_builder.py
#   file_relpath : tests/pipeline/steps/test_builder.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for the `builder` pipeline step.

These tests validate built-in field generation before rendering/comparison.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import run_builder
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.model import MutableConfig
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import GenerationStatus

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


def _build_for_path(path: Path, cfg: FrozenConfig) -> ProcessingContext:
    """Run the builder step for an existing path.

    Args:
        path: Existing path used to seed the processing context.
        cfg: Frozen configuration used by the builder.

    Returns:
        The processed context after running the builder step.
    """
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    ctx.status.content = ContentStatus.OK
    return run_builder(ctx)


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

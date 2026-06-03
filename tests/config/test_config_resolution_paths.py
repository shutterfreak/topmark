# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_resolution_paths.py
#   file_relpath : tests/config/test_config_resolution_paths.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for config path resolution and path-based normalization.

These tests exercise:
- resolution of `relative_to` against config directories,
- normalization of `include_from`, `exclude_from`, and `files_from`,
- cwd-sensitive CLI path overrides,
- inheritance and overriding of path bases across discovered configs,
- and glob evaluation relative to the effective workspace base.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from tests.toml.conftest import draft_from_topmark_toml_file
from tests.toml.conftest import write_toml_document
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_mutable_config
from topmark.resolution.files import resolve_file_list_with_diagnostics

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.config.resolution.bridge import ResolvedConfigDraft
    from topmark.config.types import PatternSource
    from topmark.resolution.files import FileListResolution


@pytest.mark.config
def test_relative_to_resolves_against_config_dir(
    tmp_path: Path,
) -> None:
    """`relative_to = "."` in a config file resolves to that file's directory."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src" / "pkg"
    src.mkdir(parents=True)

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "."
        """,
    )

    # Anchor discovery under nested path
    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[src],
    )
    assert resolved_config.draft.relative_to is not None
    assert resolved_config.draft.relative_to == proj.resolve()


@pytest.mark.config
def test_include_from_normalized_to_patternsources(
    tmp_path: Path,
) -> None:
    """`include_from` entries are normalized into absolute `PatternSource`s."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / ".gitignore",
        content="*.tmp\n",
    )
    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.files]
            include_from = [".gitignore"]
        """,
    )

    draft: MutableConfig = draft_from_topmark_toml_file(proj / "pyproject.toml")
    assert draft.include_from, "include_from should not be empty"
    ps: PatternSource = draft.include_from[0]
    assert ps.path.is_absolute()
    assert ps.base == proj.resolve()


@pytest.mark.config
def test_cli_path_options_resolve_from_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI path-to-file options resolve against the invocation CWD."""
    cwd: Path = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    # Create a file the CLI would reference relatively
    gi: Path = cwd / ".gitignore"
    gi.write_text("*.log\n", encoding="utf-8")

    draft: MutableConfig = mutable_config_from_defaults()
    overrides = ConfigOverrides(
        include_from=[".gitignore"],
    )
    apply_config_overrides(
        draft,
        overrides,
    )

    assert draft.include_from, "CLI include_from should be normalized"
    ps: PatternSource = draft.include_from[0]
    assert ps.path == gi.resolve()
    assert ps.base == cwd.resolve()


@pytest.mark.config
def test_globs_evaluated_relative_to_relative_to(
    tmp_path: Path,
) -> None:
    """Globs are evaluated relative to `relative_to` (workspace base)."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src" / "pkg"
    src.mkdir(parents=True)
    py: Path = src / "mod.py"
    py.write_text("print('ok')\n", encoding="utf-8")

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "."
            [tool.topmark.files]
            include_patterns = ["src/**/*.py"]
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[proj],
    )
    # File-list resolution should include our file based on the glob evaluated from proj.
    resolution: FileListResolution = resolve_file_list_with_diagnostics(
        resolved_config.draft.freeze()
    )
    paths: list[Path] = list(resolution.selected)
    assert py.resolve() in paths


@pytest.mark.config
def test_relative_to_inheritance_across_multiple_discovered_configs(
    tmp_path: Path,
) -> None:
    """Child config inherits parent's `relative_to` when not set."""
    root: Path = tmp_path / "root"
    child: Path = root / "apps" / "a"
    child.mkdir(parents=True)

    # Parent declares relative_to="."
    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "."
        """,
    )
    # Child has a config but doesn't set relative_to (should inherit)
    write_toml_document(
        path=child / "pyproject.toml",
        content="""
            [tool.topmark]
            # no header.relative_to here
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child],
    )
    assert resolved_config.draft.relative_to is not None
    assert resolved_config.draft.relative_to == root.resolve()


@pytest.mark.config
def test_child_overrides_relative_to_with_its_own_dir(
    tmp_path: Path,
) -> None:
    """Child config can override `relative_to`, resolved against its own config directory."""
    root: Path = tmp_path / "root"
    child: Path = root / "apps" / "a"
    sub: Path = child / "subroot"
    sub.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "."
        """,
    )
    write_toml_document(
        path=child / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "subroot"
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child],
    )
    assert resolved_config.draft.relative_to is not None
    assert resolved_config.draft.relative_to == sub.resolve()


@pytest.mark.config
def test_parent_include_from_and_child_exclude_from_normalized_with_proper_bases(
    tmp_path: Path,
) -> None:
    """include_from/exclude_from from different configs normalize with the correct bases."""
    root: Path = tmp_path / "root"
    child: Path = root / "mod"
    child.mkdir(parents=True)
    write_toml_document(
        path=root / ".gitignore",
        content="*.tmp\n",
    )
    write_toml_document(
        path=child / ".ignore",
        content="*.log\n",
    )

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.files]
            include_from = [".gitignore"]
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [files]
            exclude_from = [".ignore"]
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child],
    )
    # include_from normalized to root base
    assert resolved_config.draft.include_from
    assert resolved_config.draft.include_from[0].base == root.resolve()
    # exclude_from normalized to child base
    assert resolved_config.draft.exclude_from
    assert resolved_config.draft.exclude_from[0].base == child.resolve()


@pytest.mark.config
def test_config_seeding_globs_when_no_inputs_and_cwd_differs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config-declared globs still seed candidates when CWD differs and no inputs are given."""
    proj: Path = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "mod.py").write_text("x", encoding="utf-8")
    elsewhere: Path = tmp_path / "elsewhere"
    elsewhere.mkdir()

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.files]
            include_patterns = ["src/**/*.py"]
        """,
    )

    # Build merged config anchored under "elsewhere"
    monkeypatch.chdir(elsewhere)
    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[elsewhere],
        extra_config_files=[proj / "pyproject.toml"],
    )
    resolution: FileListResolution = resolve_file_list_with_diagnostics(
        resolved_config.draft.freeze()
    )
    files: list[Path] = list(resolution.selected)
    # Normalize paths relative to the test root for stable assertions.
    rel: list[str] = sorted(
        (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
    )
    assert rel == ["proj/src/mod.py"]


@pytest.mark.config
def test_include_patterns_seed_candidates_when_no_files_are_configured(
    tmp_path: Path,
) -> None:
    """Config include patterns should seed discovery without explicit files.

    include_patterns should seed candidates even when no files are configured.
    """
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src"
    src.mkdir(parents=True)
    py: Path = src / "seeded.py"
    txt: Path = src / "ignored.txt"
    py.write_text("print('ok')\n", encoding="utf-8")
    txt.write_text("ignored\n", encoding="utf-8")

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "."

            [tool.topmark.files]
            include_patterns = ["src/**/*.py"]
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[],
        extra_config_files=[proj / "pyproject.toml"],
    )
    resolution: FileListResolution = resolve_file_list_with_diagnostics(
        resolved_config.draft.freeze()
    )

    assert list(resolution.selected) == [py.resolve()]


@pytest.mark.config
def test_files_from_declared_in_config_normalizes_to_patternsource(
    tmp_path: Path,
) -> None:
    """files_from entries become absolute PatternSource with base set to the config dir."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()
    lst: Path = proj / "files.txt"
    lst.write_text("src/a.py\n", encoding="utf-8")

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.files]
            files_from = ["files.txt"]
        """,
    )

    draft: MutableConfig = draft_from_topmark_toml_file(proj / "pyproject.toml")
    assert draft.files_from
    ps: PatternSource = draft.files_from[0]
    assert ps.path == lst.resolve()
    assert ps.base == proj.resolve()


@pytest.mark.config
@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive semantics only")
def test_cli_path_options_resolve_from_windows_drive_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI path-to-file options should resolve against a Windows drive CWD."""
    cwd: Path = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    pattern_file: Path = cwd / "files.txt"
    pattern_file.write_text("src/a.py\n", encoding="utf-8")

    draft: MutableConfig = mutable_config_from_defaults()
    overrides = ConfigOverrides(
        files_from=["files.txt"],
        include_from=["files.txt"],
        exclude_from=["files.txt"],
    )
    apply_config_overrides(draft, overrides)

    assert draft.files_from
    assert draft.include_from
    assert draft.exclude_from
    for pattern_source in (*draft.files_from, *draft.include_from, *draft.exclude_from):
        assert pattern_source.path == pattern_file.resolve()
        assert pattern_source.base == cwd.resolve()
        assert pattern_source.path.drive == cwd.resolve().drive


@pytest.mark.config
@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive semantics only")
def test_relative_to_resolves_against_windows_config_drive(
    tmp_path: Path,
) -> None:
    """`relative_to` should resolve against the config file's Windows drive."""
    proj: Path = tmp_path / "proj"
    workspace: Path = proj / "workspace"
    workspace.mkdir(parents=True)

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "workspace"
        """,
    )

    draft: MutableConfig = draft_from_topmark_toml_file(proj / "pyproject.toml")

    assert draft.relative_to == workspace.resolve()
    assert draft.relative_to is not None
    assert draft.relative_to.drive == workspace.resolve().drive


@pytest.mark.config
@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive semantics only")
def test_config_file_discovery_accepts_windows_absolute_input_path(
    tmp_path: Path,
) -> None:
    """Config discovery should accept absolute Windows input paths."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src"
    src.mkdir(parents=True)

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.header]
            relative_to = "."
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[src.resolve()],
    )

    assert resolved_config.draft.relative_to == proj.resolve()
    assert resolved_config.draft.relative_to is not None
    assert resolved_config.draft.relative_to.drive == proj.resolve().drive


@pytest.mark.config
@pytest.mark.skipif(sys.platform != "win32", reason="Windows absolute path semantics only")
def test_config_resolution_preserves_absolute_cli_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absolute CLI path options should not be rebased onto the invocation CWD."""
    cwd: Path = tmp_path / "work"
    cwd.mkdir()
    absolute_file: Path = tmp_path / "absolute" / "patterns.txt"
    absolute_file.parent.mkdir(parents=True)
    absolute_file.write_text("src/a.py\n", encoding="utf-8")
    monkeypatch.chdir(cwd)

    draft: MutableConfig = mutable_config_from_defaults()
    overrides = ConfigOverrides(include_from=[str(absolute_file)])
    apply_config_overrides(draft, overrides)

    assert draft.include_from
    ps: PatternSource = draft.include_from[0]
    assert ps.path == absolute_file.resolve(strict=False)
    assert ps.path.is_absolute()
    assert ps.path.drive == absolute_file.drive

# topmark:header:start
#
#   project      : TopMark
#   file         : test_inputs.py
#   file_relpath : tests/resolution/files/test_inputs.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Input expansion and candidate normalization tests for file-list resolution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.helpers.config import make_frozen_config
from tests.helpers.paths import symlink_or_skip
from tests.resolution.files._helpers import file_resolver_mod
from tests.resolution.files._helpers import resolve_selected
from tests.resolution.files._helpers import write
from topmark.config.types import PatternGroup

if TYPE_CHECKING:
    import pytest

    from topmark.config.model import FrozenConfig


def test_candidates_from_positional_and_globs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expand candidate files from positional args and glob patterns.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    # Create files
    write(tmp_path / "a.txt", "x")
    write(tmp_path / "b.py", "x")
    write(tmp_path / "pkg" / "c.py", "x")
    write(tmp_path / "pkg" / "d.md", "x")

    # Glob relative to tmp_path as CWD
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(files=["**/*.py"])
        files: list[Path] = resolve_selected(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["b.py", "pkg/c.py"]


def test_fallback_to_include_seed_when_no_positional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no positional paths are provided, include globs can seed candidates.

    Config-declared globs are evaluated relative to the declaring config file's
    directory; CLI-declared globs are evaluated relative to CWD. Here we simulate
    a discovered config file by providing its path via `config_files` so that
    the seeding step expands the include pattern against that base.
    """
    write(tmp_path / "src" / "x.py", "x")
    write(tmp_path / "src" / "x.txt", "x")

    # Create a real config file to act as a base for config-declared globs
    cfg_file: Path = tmp_path / "pyproject.toml"
    cfg_file.write_text("[tool.topmark]\n", encoding="utf-8")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(
            config_files=[str(cfg_file)],
            include_pattern_groups=[
                PatternGroup(
                    patterns=("src/**/*",),
                    base=cfg_file.parent.resolve(),
                ),
            ],
        )
        files: list[Path] = resolve_selected(cfg)
        # Results may contain absolute paths (from seeding). Normalize to tmp_path-relative.
        rel: list[str] = sorted(
            (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
        )
        assert rel == ["src/x.py", "src/x.txt"]


def test_returns_sorted_and_files_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return files only (no directories) in deterministic sorted order."""
    write(tmp_path / "z.py", "x")
    write(tmp_path / "a.py", "x")
    (tmp_path / "dir").mkdir()
    write(tmp_path / "dir" / "b.py", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(files=["."])
        files: list[Path] = resolve_selected(cfg)
        # No directories, sorted
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["a.py", "dir/b.py", "z.py"]


def test_no_inputs_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return an empty list when both positional and config_files are absent."""
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config()

    assert resolve_selected(cfg) == []


def test_include_no_matches_yields_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Include patterns that match nothing yield an empty result set."""
    (tmp_path / "a.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_pattern_groups=[
            PatternGroup(
                patterns=("**/*.md",),
                base=tmp_path.resolve(),
            ),
        ],
    )
    assert resolve_selected(cfg) == []


def test_include_seed_without_inputs_ignores_directory_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Include seeding should only add files, not matching directories."""
    (tmp_path / "src").mkdir()
    cfg_file: Path = tmp_path / "pyproject.toml"
    cfg_file.write_text("[tool.topmark]\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg: FrozenConfig = make_frozen_config(
        config_files=[str(cfg_file)],
        include_pattern_groups=[
            PatternGroup(
                patterns=("src",),
                base=tmp_path.resolve(),
            ),
        ],
    )

    assert resolve_selected(cfg) == []


def test_include_seed_without_inputs_with_no_matches_yields_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Include seeding should remain empty when configured globs match nothing."""
    cfg_file: Path = tmp_path / "pyproject.toml"
    cfg_file.write_text("[tool.topmark]\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg: FrozenConfig = make_frozen_config(
        config_files=[str(cfg_file)],
        include_pattern_groups=[
            PatternGroup(
                patterns=("missing/**/*.py",),
                base=tmp_path.resolve(),
            ),
        ],
    )

    resolution: file_resolver_mod.FileListResolution = (
        file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
    )
    assert resolution.selected == ()
    assert resolution.missing_literals == ()
    assert resolution.unmatched_patterns == ()


def test_glob_relative_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expand globs relative to the current working directory (CWD)."""
    (tmp_path / "src" / "x.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "x.py").write_text("x")
    monkeypatch.chdir(tmp_path / "src")
    cfg: FrozenConfig = make_frozen_config(
        files=["*.py"],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == ["x.py"]


def test_includes_dotfiles_and_dotdirs_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Include dotfiles and files in dot-directories unless excluded."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".x.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_pattern_groups=[
            PatternGroup(
                patterns=("**/*.py",),
                base=tmp_path.resolve(),
            ),
        ],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == [".hidden/.x.py"]


def test_deduplicates_overlapping_roots_and_globs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De-duplicate results when roots and globs overlap."""
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "dir" / "b.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "dir" / "b.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=[".", "dir", "**/*.py"],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == ["a.py", "dir/b.py"]


def test_deduplicates_mixed_absolute_and_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De-duplicate when the same file is reachable via absolute and relative specs."""
    a = tmp_path / "pkg" / "a.py"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["pkg", str(a.resolve()), "**/a.py"],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    # Only one instance should remain
    assert rel == ["pkg/a.py"]


def test_symlinked_file_input_resolves_to_canonical_target_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A symlinked file input should dedupe by real path and report the target."""
    target: Path = write(tmp_path / "real" / "source.py", "x")
    symlink_or_skip(tmp_path / "links" / "source-link.py", target)

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(files=["links/source-link.py"])

    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]

    assert rel == ["real/source.py"]


def test_symlinked_directory_input_resolves_descendants_to_canonical_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A symlinked directory input should report discovered target paths."""
    target_dir: Path = tmp_path / "real-src"
    write(target_dir / "pkg" / "module.py", "x")
    symlink_or_skip(
        tmp_path / "linked-src",
        target_dir,
        target_is_directory=True,
    )

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(files=["linked-src"])

    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]

    assert rel == ["real-src/pkg/module.py"]


def test_nested_directory_symlink_is_not_traversed_during_directory_walk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Directory traversal should not recurse into nested directory symlinks."""
    root: Path = tmp_path / "root"
    target_dir: Path = tmp_path / "external-target"
    write(root / "direct.py", "x")
    write(target_dir / "nested.py", "x")
    symlink_or_skip(
        root / "linked-target",
        target_dir,
        target_is_directory=True,
    )

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(files=["root"])

    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]

    assert rel == ["root/direct.py"]


def test_real_file_and_symlink_input_are_deduplicated_by_real_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real and symlink spellings of the same file should select one target."""
    target: Path = write(tmp_path / "real" / "source.py", "x")
    symlink_or_skip(tmp_path / "links" / "source-link.py", target)

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=[
            "real/source.py",
            "links/source-link.py",
        ],
    )

    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]

    assert rel == ["real/source.py"]


def test_positional_glob_matches_path_rglob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positional glob expansion should mirror Path('.').rglob(pattern).

    This guards the behavior of the `expand_path` glob branch: using
    Path('.').rglob(pattern) semantics for CLI-style globs.
    """
    # Arrange: small tree
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")
    write(tmp_path / "pkg" / "c.py", "x")
    write(tmp_path / "pkg" / "d.md", "x")

    pattern: str = "pkg/**/*.py"

    with monkeypatch.context() as m:
        m.chdir(tmp_path)

        # Expected behavior from Path('.').rglob(pattern)
        expected: list[Path] = sorted(p for p in Path().rglob(pattern) if p.is_file())

        # TopMark resolver using the same positional glob
        cfg: FrozenConfig = make_frozen_config(files=[pattern])
        files: list[Path] = resolve_selected(cfg)
        result: list[Path] = sorted(files)

        assert [p.as_posix() for p in result] == [p.as_posix() for p in expected]


def test_resolve_file_list_wrapper_returns_selected_files_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatibility wrapper should return only selected files."""
    write(tmp_path / "a.py", "x")
    missing: Path = tmp_path / "missing.py"

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(files=["a.py", str(missing)])
        resolution: file_resolver_mod.FileListResolution = (
            file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
        )
        files: list[Path] = list(resolution.selected)

    assert [p.as_posix() for p in files] == ["a.py"]

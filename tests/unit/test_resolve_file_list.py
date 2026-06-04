# topmark:header:start
#
#   project      : TopMark
#   file         : test_resolve_file_list.py
#   file_relpath : tests/unit/test_resolve_file_list.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for file-list resolution in `topmark.resolution.files`.

These tests verify candidate expansion from positional args and config files,
include/exclude filtering, pattern file handling, file type filtering, and
edge cases such as dotfiles, globs, duplicates, and discovery diagnostics.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import topmark.resolution.files as file_resolver_mod

# Import the module under test
from tests.helpers.config import make_frozen_config
from tests.helpers.paths import symlink_or_skip
from tests.helpers.registry import make_file_type
from topmark.config.types import PatternGroup
from topmark.filetypes.model import ContentGate
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest

    from topmark.config.model import FrozenConfig
    from topmark.filetypes.model import FileType


def _py_content_matcher(path: Path) -> bool:
    """Typed content matcher (Pyright)."""
    return path.suffix == ".py"


def _text_content_matcher(path: Path) -> bool:
    """Typed content matcher (Pyright)."""
    return path.suffix in {".txt", ".md"}


class DummyType:
    """Minimal dummy file type for testing.

    Args:
        name: The identifier of the file type.
        predicate: A callable that returns True if a path matches this type.
    """

    def __init__(self, name: str, predicate: Callable[[Path], bool]) -> None:
        self.name: str = name
        self._pred: Callable[[Path], bool] = predicate

    def matches(self, path: Path) -> bool:
        """Check if a given path matches this dummy file type.

        Args:
            path: Path to test.

        Returns:
            True if the path matches, False otherwise.
        """
        return self._pred(path)


def write(p: Path, text: str = "") -> Path:
    """Write text to a file, creating parent directories if needed.

    Args:
        p: Path of the file to create.
        text: Content to write.

    Returns:
        The created file path.
    """
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def resolve_selected(config: FrozenConfig) -> list[Path]:
    """Resolve files and return only the selected processing candidates."""
    return list(file_resolver_mod.resolve_file_list_with_diagnostics(config).selected)


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


def test_include_intersection_filters_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apply include pattern groups as an intersection filter on candidates."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            include_pattern_groups=[
                PatternGroup(
                    patterns=("**/*.py",),
                    base=tmp_path.resolve(),
                ),
            ],
        )
        files: list[Path] = resolve_selected(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["a.py"]


def test_exclude_subtraction_filters_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apply exclude pattern groups as a subtraction filter on candidates."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.md", "x")
    write(tmp_path / "c.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            exclude_pattern_groups=[
                PatternGroup(
                    patterns=("**/*.md",),
                    base=tmp_path.resolve(),
                ),
            ],
        )
        files: list[Path] = resolve_selected(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["a.py", "c.txt"]


def test_include_from_and_exclude_from_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Combine include_from and exclude_from files; exclude removes matching paths."""
    # Create a small tree
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.py", "x")
    write(tmp_path / "docs" / "readme.md", "x")

    # Pattern files
    inc: Path = write(tmp_path / "inc.txt", "**/*.py\n# comment\n")
    exc: Path = write(tmp_path / "exc.txt", "b.py\n")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            include_from=[str(inc)],
            exclude_from=[str(exc)],
        )
        files: list[Path] = resolve_selected(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["a.py"]  # b.py excluded, readme.md not included


def test_file_types_filtering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter final results by configured include_file_types: tuple[str, ...] = () with registry."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)

        ft_py: FileType = make_file_type(
            local_key="py",
            content_matcher=_py_content_matcher,
            content_gate=ContentGate.ALWAYS,
        )
        FileTypeRegistry.register(ft_py)

        ft_text: FileType = make_file_type(
            local_key="text",
            content_matcher=_text_content_matcher,
            content_gate=ContentGate.ALWAYS,
        )
        FileTypeRegistry.register(ft_text)

        try:
            cfg: FrozenConfig = make_frozen_config(
                files=["."],
                include_file_types={"py"},
            )
            files: list[Path] = resolve_selected(cfg)
            rel: list[str] = sorted(p.as_posix() for p in files)

            assert rel == ["a.py"]
        finally:
            FileTypeRegistry.unregister_by_local_key("py")
            FileTypeRegistry.unregister_by_local_key("text")


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


def test_include_and_exclude_together(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When include and exclude both match a file, exclude wins."""
    write(tmp_path / "keep/yes.py", "x")
    write(tmp_path / "keep/no.py", "x")
    write(tmp_path / "drop/skip.py", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            include_pattern_groups=[
                PatternGroup(
                    patterns=("keep/**/*.py",),
                    base=tmp_path.resolve(),
                ),
            ],
            exclude_pattern_groups=[
                PatternGroup(
                    patterns=("**/no.py",),
                    base=tmp_path.resolve(),
                ),
            ],
        )
        files: list[Path] = resolve_selected(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["keep/yes.py"]


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


def test_exclude_wins_over_include(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclude takes precedence over include when both match."""
    (tmp_path / "keep.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_pattern_groups=[
            PatternGroup(
                patterns=("**/*.md",),
                base=tmp_path.resolve(),
            ),
        ],
        exclude_pattern_groups=[
            PatternGroup(
                patterns=("**/*.md",),
                base=tmp_path.resolve(),
            ),
        ],
    )
    assert resolve_selected(cfg) == []


def test_pattern_files_ignore_comments_and_blanks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ignore blank lines and lines starting with '#' in pattern files."""
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("x")
    inc: Path = tmp_path / "inc.txt"
    inc.write_text("#comment\n\n**/*.py\n")
    exc: Path = tmp_path / "exc.txt"
    exc.write_text("b.py\n# another\n\n")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_from=[str(inc)],
        exclude_from=[str(exc)],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == ["a.py"]


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


def test_file_type_unknown_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Warn and ignore unknown file types.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.
        caplog: Pytest fixture to capture log records.
    """
    (tmp_path / "a.py").write_text("x")
    monkeypatch.chdir(tmp_path)

    ft_py: FileType = make_file_type(
        local_key="py",
        content_matcher=_py_content_matcher,
        content_gate=ContentGate.ALWAYS,
    )
    FileTypeRegistry.register(ft_py)

    try:
        caplog.set_level("WARNING")
        include_file_types: set[str] = {"py", "unknown"}
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            include_file_types=include_file_types,
        )
        files: list[Path] = resolve_selected(cfg)
        assert [p.as_posix() for p in files] == ["a.py"]
        assert any(
            "Unknown included file types specified" in r.message
            # NOTE: see src/topmark/file_resolver.py
            for r in caplog.records
        )
    finally:
        FileTypeRegistry.unregister_by_local_key("py")


def test_config_files_respected_by_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply include/exclude filters after expanding config_files fallback."""
    (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x")
    (tmp_path / "src" / "b.txt").write_text("x")

    monkeypatch.chdir(tmp_path)
    # Create a real config file so the include pattern is evaluated against its directory
    cfg_file: Path = tmp_path / "pyproject.toml"
    cfg_file.write_text("[tool.topmark]\n", encoding="utf-8")

    cfg: FrozenConfig = make_frozen_config(
        config_files=[str(cfg_file)],
        include_pattern_groups=[
            PatternGroup(
                patterns=("src/**/*.py",),
                base=tmp_path.resolve(),
            ),
        ],
    )
    files: list[Path] = resolve_selected(cfg)
    rel: list[str] = sorted(
        (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
    )
    assert rel == ["src/a.py"]


def test_empty_include_means_no_include_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No include patterns means no include filtering (pass all candidates)."""
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == ["a.py", "b.txt"]


def test_no_seeding_when_files_from_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seeding only when there are no inputs.

    Case A: files_from present → do not seed from include_patterns.
    Case B: positional files present → do not seed from include_patterns.
    """
    inc: Path = tmp_path / "inc.txt"
    inc.write_text("**/*.py\n", encoding="utf-8")
    # files_from lists a literal that doesn't exist: still counts as "inputs present"
    lst: Path = tmp_path / "list.txt"
    lst.write_text("missing.py\n", encoding="utf-8")
    (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        include_pattern_groups=[
            PatternGroup(
                patterns=("src/**/*.py",),
                base=tmp_path.resolve(),
            ),
        ],  # would seed if no inputs
        files_from=[str(lst)],
        include_from=[str(inc)],  # irrelevant here
    )
    files: list[Path] = resolve_selected(cfg)
    # Because files_from existed, no seeding should occur → no files
    assert files == []


def test_config_declared_globs_match_under_config_dir_even_if_cwd_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Config-declared include globs are evaluated relative to the declaring config directory.

    Put a `pyproject.toml` in `proj/` and run from a sibling directory. Confirm files under
    `proj/src/` match via the config-declared base even though the current working directory
    doesn't match.
    """
    proj: Path = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "elsewhere").mkdir()

    cfg_file: Path = proj / "pyproject.toml"
    cfg_file.write_text("[tool.topmark]\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path / "elsewhere")
    cfg: FrozenConfig = make_frozen_config(
        config_files=[str(cfg_file)],
        include_pattern_groups=[
            PatternGroup(
                patterns=("src/**/*.py",),
                base=proj,
            )
        ],
    )
    files: list[Path] = resolve_selected(cfg)
    # Normalize relative to tmp_path for stability
    rel: list[str] = sorted(
        (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
    )
    assert rel == ["proj/src/a.py"]


def test_pattern_file_base_outside_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """include_from and exclude_from bases respected.

    Store a pattern file outside CWD and confirm matching occurs relative to
    the pattern file's directory.
    """
    root: Path = tmp_path / "root"
    ext: Path = tmp_path / "ext"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("x", encoding="utf-8")

    inc: Path = ext / "inc.txt"
    inc.parent.mkdir()
    inc.write_text("pkg/**/*.py\n", encoding="utf-8")

    monkeypatch.chdir(root)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_from=[str(inc)],
    )
    files: list[Path] = resolve_selected(cfg)
    assert files == []


def test_pattern_file_base_outside_cwd_matches_within_pattern_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pattern-file bases are respected when matching files under that base.

    Store a pattern file outside CWD and create matching files beneath that
    pattern file's directory. Matching should occur relative to the pattern
    file's own base directory, not rebased onto the current working directory.
    """
    root: Path = tmp_path / "root"
    ext: Path = tmp_path / "ext"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("x", encoding="utf-8")
    (ext / "pkg").mkdir(parents=True)
    (ext / "pkg" / "b.py").write_text("x", encoding="utf-8")

    inc: Path = ext / "inc.txt"
    inc.write_text("pkg/**/*.py\n", encoding="utf-8")

    monkeypatch.chdir(root)
    cfg: FrozenConfig = make_frozen_config(
        files=[".", str(ext.resolve())],
        include_from=[str(inc)],
    )
    files: list[Path] = resolve_selected(cfg)
    rel: list[str] = sorted(
        (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
    )

    assert rel == ["ext/pkg/b.py"]


def test_include_intersection_mixed_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Include intersection from both include_patterns and include_from.

    The effective include set is the union of pattern sources; the intersection
    is then applied against the candidate set. Here:
      - include_patterns keeps anything under src/**.py
      - include_from contributes "**/*.md"
    After intersecting with the candidate set (files=["."]), we should keep
    both a.py and docs/readme.md.
    """
    (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "docs" / "readme.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "readme.md").write_text("x", encoding="utf-8")
    inc_file: Path = tmp_path / "inc.txt"
    inc_file.write_text("**/*.md\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_pattern_groups=[
            PatternGroup(
                patterns=("src/**/*.py",),
                base=tmp_path,
            )
        ],
        include_from=[str(inc_file)],
    )
    rel: list[str] = sorted(p.as_posix() for p in resolve_selected(cfg))
    assert rel == ["docs/readme.md", "src/a.py"]


def test_exclude_from_overrides_include_patterns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exclude patterns from a pattern file remove matches from included set."""
    (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("x", encoding="utf-8")

    exc_file: Path = tmp_path / "exc.txt"
    exc_file.write_text("**/b.py\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_pattern_groups=[
            PatternGroup(
                patterns=("src/**/*.py",),
                base=tmp_path,
            )
        ],
        exclude_from=[str(exc_file)],
    )
    rel: list[str] = sorted(p.as_posix() for p in resolve_selected(cfg))
    assert rel == ["src/a.py"]


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


def test_broken_symlink_literal_is_reported_as_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken symlink literal should be reported as a missing input path."""
    link: Path = symlink_or_skip(tmp_path / "links" / "missing.py", tmp_path / "missing.py")

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(files=["links/missing.py"])

    result: file_resolver_mod.FileListResolution = (
        file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
    )

    assert result.selected == ()
    assert result.unmatched_patterns == ()
    assert result.missing_literals == (Path("links/missing.py"),)
    assert link.is_symlink()


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


def test_multiple_unknown_file_types_warn_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When multiple unknown file types are configured, warn once listing all."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    ft_py: FileType = make_file_type(
        local_key="py",
        content_matcher=_py_content_matcher,
        content_gate=ContentGate.ALWAYS,
    )
    FileTypeRegistry.register(ft_py)

    try:
        caplog.set_level("WARNING")
        include_file_types: set[str] = {"unknown1", "py", "unknown2"}
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            include_file_types=include_file_types,
        )
        files: list[Path] = resolve_selected(cfg)
        assert [p.as_posix() for p in files] == ["a.py"]
        msgs: list[str] = [
            r.message
            for r in caplog.records
            if "Unknown included file types specified" in r.message
            # NOTE: see src/topmark/file_resolver.py
        ]
        assert len(msgs) == 1
        assert "unknown1" in msgs[0] and "unknown2" in msgs[0]
    finally:
        FileTypeRegistry.unregister_by_local_key("py")


def test_pattern_files_trim_whitespace_and_trailing_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pattern loader ignores whitespace-only lines and trims trailing spaces."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "b.py").write_text("x", encoding="utf-8")

    inc: Path = tmp_path / "inc.txt"
    inc.write_text("   \n**/*.py   \n   \n", encoding="utf-8")
    exc: Path = tmp_path / "exc.txt"
    exc.write_text("b.py   \n   \n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_from=[str(inc)],
        exclude_from=[str(exc)],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == ["a.py"]


def test_missing_pattern_files_fail_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing include_from/exclude_from files log an error and (for include) filter to none."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    caplog.set_level("ERROR")

    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_from=[str(tmp_path / "missing-include.txt")],  # non-existent
    )
    files: list[Path] = resolve_selected(cfg)
    # include_from with no readable patterns → include filter removes all
    assert files == []
    assert any("Cannot read patterns from" in r.message for r in caplog.records)


def test_exclude_dotfiles_with_pattern(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dotfiles and dotdirs are included by default but can be excluded via patterns."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".x.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_patterns=["**/*.py"],
        include_pattern_groups=[
            PatternGroup(
                patterns=("**/*.py",),
                base=tmp_path,
            )
        ],
        exclude_pattern_groups=[
            PatternGroup(
                patterns=("**/.*",),
                base=tmp_path,
            )
        ],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == []


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


def test_files_from_seeds_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """files_from should seed candidates before include/exclude filtering.

    A list file can introduce explicit paths, which are then subject to the
    usual include/exclude logic. Here we verify that literal paths from
    files_from are honored when they exist.
    """
    # Create some files
    write(tmp_path / "src" / "a.py", "x")
    write(tmp_path / "src" / "b.txt", "x")
    write(tmp_path / "other" / "c.py", "x")

    # List file with two entries (one .py, one .txt)
    lst: Path = write(
        tmp_path / "files.txt",
        "src/a.py\nsrc/b.txt\n",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)

        # Use files_from as the only input source; no positional paths.
        cfg: FrozenConfig = make_frozen_config(
            files_from=[str(lst)],
        )
        files: list[Path] = resolve_selected(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        # Expect both listed files, but not 'other/c.py' (not in the list)
        assert rel == ["src/a.py", "src/b.txt"]


def test_nonexistent_literal_paths_are_reported_as_missing_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing literal paths should be omitted from selected files but reported."""
    # One real file and one missing literal
    write(tmp_path / "a.py", "x")
    missing: Path = tmp_path / "missing.py"

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        caplog.set_level("WARNING")

        cfg: FrozenConfig = make_frozen_config(files=["a.py", str(missing)])
        resolution: file_resolver_mod.FileListResolution = (
            file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
        )
        rel: list[str] = [p.as_posix() for p in resolution.selected]

        # Only the existing file should remain selected for processing.
        assert rel == ["a.py"]
        assert resolution.missing_literals == (missing,)
        assert resolution.unmatched_patterns == ()

        # Missing literal paths are still logged as discovery diagnostics.
        msgs: list[str] = [
            r.message for r in caplog.records if "No such file or directory" in r.message
        ]
        assert msgs, "Expected a warning about the missing literal path"


def test_unmatched_glob_patterns_are_reported_as_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unmatched glob patterns should be omitted from selected files but reported."""
    monkeypatch.chdir(tmp_path)
    caplog.set_level("WARNING")

    cfg: FrozenConfig = make_frozen_config(files=["missing/**/*.py"])
    resolution: file_resolver_mod.FileListResolution = (
        file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
    )

    assert resolution.selected == ()
    assert resolution.missing_literals == ()
    assert resolution.unmatched_patterns == ("missing/**/*.py",)
    assert any("No matches for glob pattern" in r.message for r in caplog.records)


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

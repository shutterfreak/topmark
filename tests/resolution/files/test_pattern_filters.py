# topmark:header:start
#
#   project      : TopMark
#   file         : test_pattern_filters.py
#   file_relpath : tests/resolution/files/test_pattern_filters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pattern include/exclude tests for file-list resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.config import make_frozen_config
from tests.resolution.files._helpers import resolve_selected
from tests.resolution.files._helpers import write
from topmark.config.types import PatternGroup

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from topmark.config.model import FrozenConfig


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


def test_empty_include_pattern_group_means_no_include_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty include pattern groups should be ignored rather than filtering all files."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")
    monkeypatch.chdir(tmp_path)

    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_pattern_groups=[
            PatternGroup(
                patterns=(),
                base=tmp_path.resolve(),
            ),
        ],
    )

    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == ["a.py", "b.txt"]


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


def test_excluded_root_directory_prunes_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Excluded explicit root directories should not contribute descendants."""
    write(tmp_path / "ignored" / "a.py", "x")
    write(tmp_path / "kept" / "b.py", "x")
    monkeypatch.chdir(tmp_path)

    cfg: FrozenConfig = make_frozen_config(
        files=["ignored", "kept"],
        exclude_pattern_groups=[
            PatternGroup(
                patterns=("ignored/",),
                base=tmp_path.resolve(),
            ),
        ],
    )

    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]
    assert rel == ["kept/b.py"]

# topmark:header:start
#
#   project      : TopMark
#   file         : test_resolve_file_list.py
#   file_relpath : tests/unit/test_resolve_file_list.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for `resolve_file_list` in `topmark.click_test.options`.

These tests verify candidate expansion from positional args and config files,
as well as include/exclude filtering, pattern file handling, file type filtering,
and other edge cases like dotfiles, globs, and duplicates.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import topmark.file_resolver as file_resolver_mod

# Import the module under test
from tests.conftest import make_config, make_file_type
from topmark.registry import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest

    from topmark.config import Config
    from topmark.filetypes.base import FileType


class DummyType:
    """Minimal dummy file type for testing.

    Args:
        name (str): The identifier of the file type.
        predicate (Callable[[Path], bool]): A callable that returns True
            if a path matches this type.
    """

    def __init__(self, name: str, predicate: Callable[[Path], bool]) -> None:
        self.name: str = name
        self._pred: Callable[[Path], bool] = predicate

    def matches(self, path: Path) -> bool:
        """Check if a given path matches this dummy file type.

        Args:
            path (Path): Path to test.

        Returns:
            bool: True if the path matches, False otherwise.
        """
        return self._pred(path)


def write(p: Path, text: str = "") -> Path:
    """Write text to a file, creating parent directories if needed.

    Args:
        p (Path): Path of the file to create.
        text (str): Content to write.

    Returns:
        Path: The created file path.
    """
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_candidates_from_positional_and_globs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expand candidate files from positional args and glob patterns.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
    """
    # Create files
    write(tmp_path / "a.txt", "x")
    write(tmp_path / "b.py", "x")
    write(tmp_path / "pkg" / "c.py", "x")
    write(tmp_path / "pkg" / "d.md", "x")

    # Glob relative to tmp_path as CWD
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: Config = make_config(files=["**/*.py"])
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["b.py", "pkg/c.py"]


def test_fallback_to_include_seed_when_no_positional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no positional paths are provided, include globs can seed candidates.

    Config-declared globs are evaluated relative to the declaring config file’s
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
        cfg: Config = make_config(
            config_files=[str(cfg_file)],
            include_patterns=["src/**/*"],
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        # Results may contain absolute paths (from seeding). Normalize to tmp_path-relative.
        rel: list[str] = sorted(
            (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
        )
        assert rel == ["src/x.py", "src/x.txt"]


def test_include_intersection_filters_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apply include_patterns as an intersection filter on candidates."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: Config = make_config(
            files=["."],
            include_patterns=["**/*.py"],
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["a.py"]


def test_exclude_subtraction_filters_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apply exclude_patterns as a subtraction filter on candidates."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.md", "x")
    write(tmp_path / "c.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: Config = make_config(
            files=["."],
            exclude_patterns=["**/*.md"],
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
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
        cfg: Config = make_config(
            files=["."],
            include_from=[str(inc)],
            exclude_from=[str(exc)],
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["a.py"]  # b.py excluded, readme.md not included


def test_file_types_filtering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter final results by configured include_file_types: tuple[str, ...] = () with registry."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)

        def _py_content_matcher(p: Path) -> bool:
            """Typed content matcher (Pyright)."""
            return p.suffix == ".py"

        ft_py: FileType = make_file_type(
            name="py",
            content_matcher=_py_content_matcher,
        )
        FileTypeRegistry.register(ft_py)

        def _text_content_matcher(p: Path) -> bool:
            """Typed content matcher (Pyright)."""
            return p.suffix in {".txt", ".md"}

        ft_text: FileType = make_file_type(
            name="text",
            content_matcher=_text_content_matcher,
        )
        FileTypeRegistry.register(ft_text)

        try:
            cfg: Config = make_config(
                files=["."],
                include_file_types=set(["py"]),
            )
            files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
            rel: list[str] = sorted(p.as_posix() for p in files)

            assert rel == ["a.py"]
        finally:
            FileTypeRegistry.unregister("py")
            FileTypeRegistry.unregister("text")


def test_returns_sorted_and_files_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return files only (no directories) in deterministic sorted order."""
    write(tmp_path / "z.py", "x")
    write(tmp_path / "a.py", "x")
    (tmp_path / "dir").mkdir()
    write(tmp_path / "dir" / "b.py", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: Config = make_config(files=["."])
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
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
        cfg: Config = make_config(
            files=["."],
            include_patterns=["keep/**/*.py"],
            exclude_patterns=["**/no.py"],
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        assert rel == ["keep/yes.py"]


def test_no_inputs_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return an empty list when both positional and config_files are absent."""
    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config()

    assert file_resolver_mod.resolve_file_list(cfg) == []


def test_include_no_matches_yields_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Include patterns that match nothing yield an empty result set."""
    (tmp_path / "a.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config(
        files=["."],
        include_patterns=["**/*.md"],
    )
    assert file_resolver_mod.resolve_file_list(cfg) == []


def test_exclude_wins_over_include(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclude takes precedence over include when both match."""
    (tmp_path / "keep.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config(
        files=["."],
        include_patterns=["**/*.md"],
        exclude_patterns=["**/*.md"],
    )
    assert file_resolver_mod.resolve_file_list(cfg) == []


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
    cfg: Config = make_config(
        files=["."],
        include_from=[str(inc)],
        exclude_from=[str(exc)],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["a.py"]


def test_glob_relative_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expand globs relative to the current working directory (CWD)."""
    (tmp_path / "src" / "x.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "x.py").write_text("x")
    monkeypatch.chdir(tmp_path / "src")
    cfg: Config = make_config(
        files=["*.py"],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["x.py"]


def test_includes_dotfiles_and_dotdirs_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Include dotfiles and files in dot-directories unless excluded."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".x.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config(
        files=["."],
        include_patterns=["**/*.py"],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == [".hidden/.x.py"]


def test_deduplicates_overlapping_roots_and_globs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De-duplicate results when roots and globs overlap."""
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "dir" / "b.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "dir" / "b.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config(
        files=[".", "dir", "**/*.py"],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["a.py", "dir/b.py"]


def test_file_type_unknown_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Warn and ignore unknown file types.

    Args:
        tmp_path (Path): Pytest temporary directory fixture.
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
        caplog (pytest.LogCaptureFixture): Pytest fixture to capture log records.
    """
    (tmp_path / "a.py").write_text("x")
    monkeypatch.chdir(tmp_path)

    def _py_content_matcher(p: Path) -> bool:
        """Typed content matcher (Pyright)."""
        return p.suffix == ".py"

    ft_py: FileType = make_file_type(
        name="py",
        content_matcher=_py_content_matcher,
    )
    FileTypeRegistry.register(ft_py)

    try:
        caplog.set_level("WARNING")
        include_file_types: set[str] = set(["py", "unknown"])
        cfg: Config = make_config(
            files=["."],
            include_file_types=include_file_types,
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        assert [p.as_posix() for p in files] == ["a.py"]
        assert any(
            "Unknown included file types specified" in r.message
            # NOTE: see src/topmark/file_resolver.py
            for r in caplog.records
        )
    finally:
        FileTypeRegistry.unregister("py")


def test_config_files_respected_by_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply include/exclude filters after expanding config_files fallback."""
    (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x")
    (tmp_path / "src" / "b.txt").write_text("x")

    monkeypatch.chdir(tmp_path)
    # Create a real config file so the include pattern is evaluated against its directory
    cfg_file: Path = tmp_path / "pyproject.toml"
    cfg_file.write_text("[tool.topmark]\n", encoding="utf-8")

    cfg: Config = make_config(
        config_files=[str(cfg_file)],
        include_patterns=["src/**/*.py"],
    )
    files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
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
    cfg: Config = make_config(
        files=["."],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
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
    # files_from lists a literal that doesn't exist: still counts as “inputs present”
    lst: Path = tmp_path / "list.txt"
    lst.write_text("missing.py\n", encoding="utf-8")
    (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config(
        include_patterns=["src/**/*.py"],  # would seed if no inputs
        files_from=[str(lst)],
        include_from=[str(inc)],  # irrelevant here
    )
    files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
    # Because files_from existed, no seeding should occur → no files
    assert files == []


def test_config_declared_globs_match_under_config_dir_even_if_cwd_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Config-declared glob bases vs CWD; both bases are tried.

    Put a pyproject.toml in proj/ and run from a sibling directory;
    confirm files under proj/src/ match via config base even though CWD doesn’t match.
    """
    proj: Path = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "elsewhere").mkdir()

    cfg_file: Path = proj / "pyproject.toml"
    cfg_file.write_text("[tool.topmark]\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path / "elsewhere")
    cfg: Config = make_config(
        config_files=[str(cfg_file)],
        include_patterns=["src/**/*.py"],
    )
    files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
    # Normalize relative to tmp_path for stability
    rel: list[str] = sorted(
        (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
    )
    assert rel == ["proj/src/a.py"]


def test_pattern_file_base_outside_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """include_from and exclude_from bases respected.

    Store a pattern file outside CWD and confirm matching occurs relative to
    the pattern file’s directory.
    """
    root: Path = tmp_path / "root"
    ext: Path = tmp_path / "ext"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("x", encoding="utf-8")

    inc: Path = ext / "inc.txt"
    inc.parent.mkdir()
    inc.write_text("pkg/**/*.py\n", encoding="utf-8")

    monkeypatch.chdir(root)
    cfg: Config = make_config(
        files=["."],
        include_from=[str(inc)],
    )
    files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
    assert [p.as_posix() for p in files] == ["pkg/a.py"]


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
    cfg: Config = make_config(
        files=["."],
        include_patterns=["src/**/*.py"],
        include_from=[str(inc_file)],
    )
    rel: list[str] = sorted(p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg))
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
    cfg: Config = make_config(
        files=["."],
        include_patterns=["src/**/*.py"],
        exclude_from=[str(exc_file)],
    )
    rel: list[str] = sorted(p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg))
    assert rel == ["src/a.py"]


def test_deduplicates_mixed_absolute_and_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De-duplicate when the same file is reachable via absolute and relative specs."""
    a = tmp_path / "pkg" / "a.py"
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config(
        files=["pkg", str(a.resolve()), "**/a.py"],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    # Only one instance should remain
    assert rel == ["pkg/a.py"]


def test_multiple_unknown_file_types_warn_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When multiple unknown file types are configured, warn once listing all."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def _py_content_matcher(p: Path) -> bool:
        """Typed content matcher (Pyright)."""
        return p.suffix == ".py"

    ft_py: FileType = make_file_type(
        name="py",
        content_matcher=_py_content_matcher,
    )
    FileTypeRegistry.register(ft_py)

    try:
        caplog.set_level("WARNING")
        include_file_types: set[str] = set(["unknown1", "py", "unknown2"])
        cfg: Config = make_config(
            files=["."],
            include_file_types=include_file_types,
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
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
        FileTypeRegistry.unregister("py")


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
    cfg: Config = make_config(
        files=["."],
        include_from=[str(inc)],
        exclude_from=[str(exc)],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["a.py"]


def test_missing_pattern_files_fail_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing include_from/exclude_from files log an error and (for include) filter to none."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    caplog.set_level("ERROR")

    cfg: Config = make_config(
        files=["."],
        include_from=[str(tmp_path / "missing-include.txt")],  # non-existent
    )
    files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
    # include_from with no readable patterns → include filter removes all
    assert files == []
    assert any("Cannot read patterns from" in r.message for r in caplog.records)


def test_exclude_dotfiles_with_pattern(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dotfiles and dotdirs are included by default but can be excluded via patterns."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".x.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg: Config = make_config(
        files=["."],
        include_patterns=["**/*.py"],
        exclude_patterns=["**/.*"],
    )
    rel: list[str] = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
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
        expected: list[Path] = sorted(p for p in Path(".").rglob(pattern) if p.is_file())

        # TopMark resolver using the same positional glob
        cfg: Config = make_config(files=[pattern])
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
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
        cfg: Config = make_config(
            files_from=[str(lst)],
        )
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        rel: list[str] = sorted(p.as_posix() for p in files)

        # Expect both listed files, but not 'other/c.py' (not in the list)
        assert rel == ["src/a.py", "src/b.txt"]


def test_nonexistent_literal_paths_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Nonexistent literal paths should be ignored after logging a warning.

    This pins down current behavior: literal paths that do not exist
    are not fatal and do not contribute to the final candidate set.
    """
    # One real file and one missing literal
    write(tmp_path / "a.py", "x")
    missing: Path = tmp_path / "missing.py"

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        caplog.set_level("WARNING")

        cfg: Config = make_config(files=["a.py", str(missing)])
        files: list[Path] = file_resolver_mod.resolve_file_list(cfg)
        rel: list[str] = [p.as_posix() for p in files]

        # Only the existing file should remain
        assert rel == ["a.py"]

        # And we should have logged at least one warning about the missing path
        msgs: list[str] = [
            r.message for r in caplog.records if "No such file or directory" in r.message
        ]
        assert msgs, "Expected a warning about the missing literal path"

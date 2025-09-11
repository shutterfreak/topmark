# topmark:header:start
#
#   file         : test_resolve_file_list.py
#   file_relpath : tests/unit/test_resolve_file_list.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for `resolve_file_list` in `topmark.click_test.options`.

These tests verify candidate expansion from positional args and config files,
as well as include/exclude filtering, pattern file handling, file type filtering,
and other edge cases like dotfiles, globs, and duplicates.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Callable, cast

import pytest

# Import the module under test
import topmark.file_resolver as file_resolver_mod
from topmark.config import Config


class DummyType:
    """Minimal dummy file type for testing.

    Args:
        name (str): The identifier of the file type.
        predicate (Callable[[Path], bool]): A callable that returns True
            if a path matches this type.
    """

    def __init__(self, name: str, predicate: Callable[[Path], bool]):
        self.name = name
        self._pred = predicate

    def matches(self, path: Path) -> bool:
        """Check if a given path matches this dummy file type.

        Args:
            path (Path): Path to test.

        Returns:
            bool: True if the path matches, False otherwise.
        """
        return self._pred(path)


def make_config(
    *,
    files: list[str] | None = None,
    include_patterns: list[str] | None = None,
    include_from: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    exclude_from: list[str] | None = None,
    config_files: list[str] | None = None,
    file_types: list[str] | None = None,
) -> Config:
    """Construct a Config-like object for tests.

    Missing fields default to None, which the resolver interprets as unset.

    Args:
        files (list[str] | None): Positional paths or globs.
        include_patterns (list[str] | None): Glob patterns to intersect with candidates.
        include_from (list[str] | None): Paths to files with include patterns.
        exclude_patterns (list[str] | None): Glob patterns to exclude from candidates.
        exclude_from (list[str] | None): Paths to files with exclude patterns.
        config_files (list[str] | None): Config-defined fallback paths.
        file_types (list[str] | None): File types to filter by.

    Returns:
        Config: A namespace with the required attributes.
    """
    return cast(
        "Config",
        SimpleNamespace(
            files=list(files or []),
            files_from=list(files or []),
            include_patterns=list(include_patterns or []),
            include_from=list(include_from or []),
            exclude_patterns=list(exclude_patterns or []),
            exclude_from=list(exclude_from or []),
            config_files=list(config_files or []),
            file_types=list(file_types or []),
        ),
    )


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
        cfg = make_config(files=["**/*.py"])
        files = file_resolver_mod.resolve_file_list(cfg)
        rel = sorted(p.as_posix() for p in files)

        assert rel == ["b.py", "pkg/c.py"]


def test_fallback_to_config_files_when_no_positional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fall back to config_files when no positional paths are provided."""
    write(tmp_path / "src" / "x.py", "x")
    write(tmp_path / "src" / "x.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg = make_config(config_files=["src"])
        files = file_resolver_mod.resolve_file_list(cfg)
        rel = sorted(p.as_posix() for p in files)

        assert rel == ["src/x.py", "src/x.txt"]


def test_include_intersection_filters_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Apply include_patterns as an intersection filter on candidates."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg = make_config(files=["."], include_patterns=["**/*.py"])
        files = file_resolver_mod.resolve_file_list(cfg)
        rel = sorted(p.as_posix() for p in files)

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
        cfg = make_config(files=["."], exclude_patterns=["**/*.md"])
        files = file_resolver_mod.resolve_file_list(cfg)
        rel = sorted(p.as_posix() for p in files)

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
    inc = write(tmp_path / "inc.txt", "**/*.py\n# comment\n")
    exc = write(tmp_path / "exc.txt", "b.py\n")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg = make_config(files=["."], include_from=[str(inc)], exclude_from=[str(exc)])
        files = file_resolver_mod.resolve_file_list(cfg)
        rel = sorted(p.as_posix() for p in files)

        assert rel == ["a.py"]  # b.py excluded, readme.md not included


def test_file_types_filtering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter final results by configured file_types using the registry."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")

    # Monkeypatch the registry used by the module
    def fake_registry() -> dict[str, DummyType]:
        return {
            "py": DummyType("py", lambda p: p.suffix == ".py"),
            "text": DummyType("text", lambda p: p.suffix in {".txt", ".md"}),
        }

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        m.setattr(file_resolver_mod, "get_file_type_registry", lambda: fake_registry())
        cfg = make_config(files=["."], file_types=["py"])
        files = file_resolver_mod.resolve_file_list(cfg)
        rel = sorted(p.as_posix() for p in files)

        assert rel == ["a.py"]


def test_returns_sorted_and_files_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return files only (no directories) in deterministic sorted order."""
    write(tmp_path / "z.py", "x")
    write(tmp_path / "a.py", "x")
    (tmp_path / "dir").mkdir()
    write(tmp_path / "dir" / "b.py", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg = make_config(files=["."])
        files = file_resolver_mod.resolve_file_list(cfg)
        # No directories, sorted
        rel = sorted(p.as_posix() for p in files)

        assert rel == ["a.py", "dir/b.py", "z.py"]


def test_include_and_exclude_together(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When include and exclude both match a file, exclude wins."""
    write(tmp_path / "keep/yes.py", "x")
    write(tmp_path / "keep/no.py", "x")
    write(tmp_path / "drop/skip.py", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg = make_config(
            files=["."],
            include_patterns=["keep/**/*.py"],
            exclude_patterns=["**/no.py"],
        )
        files = file_resolver_mod.resolve_file_list(cfg)
        rel = sorted(p.as_posix() for p in files)

        assert rel == ["keep/yes.py"]


def test_no_inputs_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return an empty list when both positional and config_files are absent."""
    monkeypatch.chdir(tmp_path)
    cfg = make_config()

    assert file_resolver_mod.resolve_file_list(cfg) == []


def test_include_no_matches_yields_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Include patterns that match nothing yield an empty result set."""
    (tmp_path / "a.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg = make_config(
        files=["."],
        include_patterns=["**/*.md"],
    )
    assert file_resolver_mod.resolve_file_list(cfg) == []


def test_exclude_wins_over_include(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exclude takes precedence over include when both match."""
    (tmp_path / "keep.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg = make_config(
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
    inc = tmp_path / "inc.txt"
    inc.write_text("#comment\n\n**/*.py\n")
    exc = tmp_path / "exc.txt"
    exc.write_text("b.py\n# another\n\n")
    monkeypatch.chdir(tmp_path)
    cfg = make_config(
        files=["."],
        include_from=[str(inc)],
        exclude_from=[str(exc)],
    )
    rel = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["a.py"]


def test_glob_relative_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expand globs relative to the current working directory (CWD)."""
    (tmp_path / "src" / "x.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "x.py").write_text("x")
    monkeypatch.chdir(tmp_path / "src")
    cfg = make_config(
        files=["*.py"],
    )
    rel = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["x.py"]


def test_includes_dotfiles_and_dotdirs_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Include dotfiles and files in dot-directories unless excluded."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / ".x.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg = make_config(
        files=["."],
        include_patterns=["**/*.py"],
    )
    rel = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == [".hidden/.x.py"]


def test_deduplicates_overlapping_roots_and_globs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De-duplicate results when roots and globs overlap."""
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "dir" / "b.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "dir" / "b.py").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg = make_config(
        files=[".", "dir", "**/*.py"],
    )
    rel = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
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

    def fake_registry() -> dict[str, DummyType]:
        return {"py": DummyType("py", lambda p: p.suffix == ".py")}

    monkeypatch.setattr(file_resolver_mod, "get_file_type_registry", lambda: fake_registry())
    caplog.set_level("WARNING")
    cfg = make_config(
        files=["."],
        file_types=["py", "unknown"],
    )
    files = file_resolver_mod.resolve_file_list(cfg)
    assert [p.as_posix() for p in files] == ["a.py"]
    assert any("Unknown file types specified" in r.message for r in caplog.records)


def test_config_files_respected_by_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply include/exclude filters after expanding config_files fallback."""
    (tmp_path / "src" / "a.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("x")
    (tmp_path / "src" / "b.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg = make_config(
        config_files=["src"],
        include_patterns=["**/*.py"],
    )
    rel = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["src/a.py"]


def test_empty_include_means_no_include_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No include patterns means no include filtering (pass all candidates)."""
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    cfg = make_config(
        files=["."],
    )
    rel = [p.as_posix() for p in file_resolver_mod.resolve_file_list(cfg)]
    assert rel == ["a.py", "b.txt"]

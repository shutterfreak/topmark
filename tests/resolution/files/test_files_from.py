# topmark:header:start
#
#   project      : TopMark
#   file         : test_files_from.py
#   file_relpath : tests/resolution/files/test_files_from.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""files_from seed input tests for file-list resolution."""

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


def test_files_from_ignores_blank_and_comment_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """files_from sources should ignore blank lines and comments."""
    write(tmp_path / "src" / "a.py", "x")
    write(tmp_path / "src" / "b.py", "x")
    lst: Path = write(
        tmp_path / "files.txt",
        "# generated file list\n\n src/a.py \n\n# another comment\nsrc/b.py\n",
    )

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        cfg: FrozenConfig = make_frozen_config(files_from=[str(lst)])
        rel: list[str] = sorted(p.as_posix() for p in resolve_selected(cfg))

    assert rel == ["src/a.py", "src/b.py"]

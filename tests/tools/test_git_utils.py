# topmark:header:start
#
#   project      : TopMark
#   file         : test_git_utils.py
#   file_relpath : tests/tools/test_git_utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for Git helpers used by repository-maintenance tooling."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from tools.docs import git_utils
from tools.docs.git_utils import iter_non_gitignored_paths


def test_iter_non_gitignored_paths_accepts_empty_input() -> None:
    """An empty candidate sequence requires no Git lookup and remains empty."""
    assert list(iter_non_gitignored_paths(())) == []


def test_iter_non_gitignored_paths_preserves_paths_when_git_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ad-hoc runs retain candidates when Git is unavailable."""
    candidate: Path = tmp_path / "sample.py"

    def no_git(command: str) -> None:
        """Report the requested executable as unavailable."""
        assert command == "git"
        return None

    monkeypatch.setattr(git_utils.shutil, "which", no_git)

    assert list(iter_non_gitignored_paths((candidate,))) == [candidate]


def test_iter_non_gitignored_paths_preserves_paths_outside_a_work_tree(
    tmp_path: Path,
) -> None:
    """Ad-hoc directories outside Git work trees retain their candidates."""
    candidate: Path = tmp_path / "sample.py"

    assert list(iter_non_gitignored_paths((candidate,), cwd=tmp_path)) == [candidate]


def test_iter_non_gitignored_paths_preserves_paths_when_git_cannot_start(
    tmp_path: Path,
) -> None:
    """An invalid working directory does not prevent hygiene checks from running."""
    candidate: Path = tmp_path / "sample.py"

    assert list(iter_non_gitignored_paths((candidate,), cwd=tmp_path / "missing")) == [candidate]


if TYPE_CHECKING:
    from pathlib import Path


def test_iter_non_gitignored_paths_excludes_gitignored_files(
    tmp_path: Path,
) -> None:
    """Git ignore rules remove matching paths while preserving candidates' order."""
    git_executable: str | None = shutil.which("git")
    if git_executable is None:
        pytest.skip("Git is not available")

    subprocess.run(  # noqa: S603
        [git_executable, "init", "--quiet"],
        check=True,
        cwd=tmp_path,
    )
    (tmp_path / ".gitignore").write_text("*.generated.py\n", encoding="utf-8")
    included_first: Path = tmp_path / "first.py"
    ignored: Path = tmp_path / "generated.generated.py"
    included_last: Path = tmp_path / "last.py"
    for path in (included_first, ignored, included_last):
        path.write_text("pass\n", encoding="utf-8")

    assert list(
        iter_non_gitignored_paths(
            (included_first, ignored, included_last),
            cwd=tmp_path,
        )
    ) == [included_first, included_last]

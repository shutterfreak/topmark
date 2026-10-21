# topmark:header:start
#
#   project      : TopMark
#   file         : git_utils.py
#   file_relpath : tools/docs/git_utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Small Git helpers for documentation-maintenance tooling."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from pathlib import Path


def iter_non_gitignored_paths(
    paths: Iterable[Path],
    *,
    cwd: Path | None = None,
) -> Iterator[Path]:
    """Yield paths that do not match Git's ignore rules, preserving input order.

    Paths are checked in one ``git check-ignore`` invocation. If Git is unavailable or ``cwd``
    is outside a Git work tree, all input paths are yielded so callers remain usable for ad-hoc
    file selections and temporary directories.

    Args:
        paths: Candidate file paths, relative to ``cwd`` when possible.
        cwd: Working directory used to resolve Git ignore rules. Defaults to the current directory.

    Yields:
        Candidate paths that are not Git-ignored.
    """
    candidates: list[Path] = list(paths)
    if not candidates:
        return

    git_executable: str | None = shutil.which("git")
    if git_executable is None:
        yield from candidates
        return

    path_strings: list[str] = [str(path) for path in candidates]
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
            [git_executable, "check-ignore", "-z", "--stdin"],
            check=False,
            cwd=cwd,
            input="\0".join(path_strings) + "\0",
            capture_output=True,
            text=True,
        )
    except OSError:
        yield from candidates
        return

    if result.returncode not in {0, 1}:
        yield from candidates
        return

    ignored_paths: frozenset[str] = frozenset(result.stdout.rstrip("\0").split("\0"))
    for path, path_string in zip(candidates, path_strings, strict=True):
        if path_string not in ignored_paths:
            yield path

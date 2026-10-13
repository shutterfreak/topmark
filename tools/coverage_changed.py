# topmark:header:start
#
#   project      : TopMark
#   file         : coverage_changed.py
#   file_relpath : tools/coverage_changed.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Report uncovered executable Python lines changed from a Git base revision.

This local developer diagnostic deliberately does not impose a coverage threshold or
change CI policy. It compares the working tree with a merge base, so uncommitted
changes are included when it is run after the canonical coverage session.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final
from typing import cast

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence


DEFAULT_COVERAGE_PATH: Final[Path] = Path("coverage.json")
SOURCE_PREFIX: Final[str] = "src/topmark/"
# Git's unified-diff format uses this POSIX spelling as a cross-platform sentinel for a missing
# old or new path; it is never opened as a local filesystem device.
GIT_NULL_PATH: Final[str] = "/dev/null"


@dataclass(frozen=True)
class ChangedFile:
    """Added line numbers for one current-path file in a Git diff."""

    path: str
    added_lines: frozenset[int]


@dataclass(frozen=True)
class CoverageDiagnostic:
    """One uncovered changed statement or branch."""

    path: str
    line: int
    kind: str
    detail: str
    source: str


@dataclass(frozen=True)
class CoverageAssessment:
    """Result of comparing changed source lines with a coverage JSON report."""

    assessed: bool
    diagnostics: tuple[CoverageDiagnostic, ...]
    message: str


def _run_git(*args: str) -> str:
    """Run Git and return standard output, raising a concise error on failure.

    Args:
        *args: Arguments after the ``git`` executable.

    Returns:
        Decoded standard output from Git.

    Raises:
        RuntimeError: If Git cannot execute the requested command.
    """
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [_git_executable(), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail: str = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _git_ref_exists(reference: str) -> bool:
    """Return whether ``reference`` resolves to a Git revision."""
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [
            _git_executable(),
            "rev-parse",
            "--verify",
            "--quiet",
            f"{reference}^{{commit}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _git_executable() -> str:
    """Return the absolute Git executable path required by the process runner."""
    executable: str | None = shutil.which("git")
    if executable is None:
        raise RuntimeError("Git is not available on PATH")
    return executable


def choose_base_reference(explicit_base: str | None) -> str:
    """Choose a usable base revision for local and CI-style comparisons.

    Args:
        explicit_base: Revision passed through ``--base``, if any.

    Returns:
        A Git revision name suitable for ``git merge-base``.

    Raises:
        RuntimeError: If no documented base reference is available locally.
    """
    if explicit_base:
        return explicit_base

    configured_base: str | None = os.environ.get("COVERAGE_CHANGED_BASE")
    if configured_base:
        return configured_base

    github_base: str | None = os.environ.get("GITHUB_BASE_REF")
    if github_base:
        remote_base: str = f"origin/{github_base}"
        return remote_base if _git_ref_exists(remote_base) else github_base

    for candidate in ("origin/main", "main"):
        if _git_ref_exists(candidate):
            return candidate

    raise RuntimeError(
        "Cannot determine a coverage comparison base. Pass --base <revision> or set "
        "COVERAGE_CHANGED_BASE."
    )


def changed_files(base_reference: str) -> tuple[ChangedFile, ...]:
    """Return added working-tree lines relative to the merge base of ``base_reference``.

    Args:
        base_reference: Branch, tag, or commit used to find the merge base with ``HEAD``.

    Returns:
        Changed current-path files and their added or modified line numbers.
    """
    merge_base: str = _run_git("merge-base", base_reference, "HEAD").strip()
    patch: str = _run_git(
        "diff",
        "--no-ext-diff",
        "--find-renames",
        "--unified=0",
        "--format=",
        merge_base,
        "--",
        SOURCE_PREFIX,
    )
    return parse_unified_diff(patch)


def parse_unified_diff(patch: str) -> tuple[ChangedFile, ...]:
    """Parse added current-file lines from a zero-context unified Git diff.

    Deleted files have no current executable source and are omitted. Renames are represented by
    the current ``+++ b/...`` path, which also handles a rename with content changes.

    Args:
        patch: Output from ``git diff --unified=0``.

    Returns:
        Changed files with added line numbers.
    """
    paths_to_lines: dict[str, set[int]] = {}
    current_path: str | None = None
    for raw_line in patch.splitlines():
        if raw_line.startswith("+++ "):
            path_token: str = raw_line[4:]
            current_path = None if path_token == GIT_NULL_PATH else _strip_diff_prefix(path_token)
            continue
        if not raw_line.startswith("@@ ") or current_path is None:
            continue
        new_range: str = raw_line.split(" ")[2]
        start, count = _parse_hunk_range(new_range)
        if count:
            paths_to_lines.setdefault(current_path, set()).update(range(start, start + count))
    return tuple(
        ChangedFile(path=path, added_lines=frozenset(lines))
        for path, lines in sorted(paths_to_lines.items())
    )


def _strip_diff_prefix(path_token: str) -> str:
    """Return a repository-relative path from a Git ``b/`` diff token."""
    return path_token[2:] if path_token.startswith("b/") else path_token


def _parse_hunk_range(value: str) -> tuple[int, int]:
    """Parse a unified-diff range such as ``+12,3`` into start and count."""
    raw_range: str = value[1:]
    if "," not in raw_range:
        return int(raw_range), 1
    start_text, count_text = raw_range.split(",", maxsplit=1)
    return int(start_text), int(count_text)


def assess_coverage(
    coverage_path: Path,
    changed: Iterable[ChangedFile],
    *,
    repository_root: Path,
) -> CoverageAssessment:
    """Compare changed Python statements and branches with a canonical coverage JSON report.

    Args:
        coverage_path: Canonical JSON report generated by ``make coverage``.
        changed: Changed current-path files from Git.
        repository_root: Root used to read source context.

    Returns:
        A non-enforcing assessment with uncovered changed diagnostics.

    Raises:
        TypeError: If ``coverage_path`` is not a canonical coverage JSON report.
    """
    if not coverage_path.is_file():
        return CoverageAssessment(
            assessed=False,
            diagnostics=(),
            message=(
                f"Coverage was not assessed: {coverage_path} is absent. "
                "Run `make coverage` before `make coverage-changed`."
            ),
        )

    payload: object = cast("object", json.loads(coverage_path.read_text(encoding="utf-8")))
    if not isinstance(payload, dict):
        raise TypeError(f"{coverage_path} is not a canonical coverage JSON report")
    payload_dict: dict[str, object] = cast("dict[str, object]", payload)
    raw_files: object | None = payload_dict.get("files")
    if not isinstance(raw_files, dict):
        raise TypeError(f"{coverage_path} is not a canonical coverage JSON report")
    files: Mapping[str, object] = cast("Mapping[str, object]", raw_files)
    diagnostics: list[CoverageDiagnostic] = []
    for changed_file in changed:
        file_data: object | None = files.get(changed_file.path)
        if not isinstance(file_data, dict):
            continue
        diagnostics.extend(
            _assess_file(
                changed_file,
                cast("Mapping[str, object]", file_data),
                repository_root=repository_root,
            )
        )
    return CoverageAssessment(
        assessed=True,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.path, item.line, item.kind))),
        message="Coverage assessed for changed executable source lines.",
    )


def _assess_file(
    changed_file: ChangedFile,
    file_data: Mapping[str, object],
    *,
    repository_root: Path,
) -> list[CoverageDiagnostic]:
    """Return uncovered statement and branch diagnostics for one changed file."""
    missing_lines: set[int] = _integer_set(file_data.get("missing_lines"))
    executable_lines: set[int] = missing_lines | _integer_set(file_data.get("executed_lines"))
    source_lines: list[str] = _read_source_lines(repository_root / changed_file.path)
    diagnostics: list[CoverageDiagnostic] = []
    for line in sorted(changed_file.added_lines & missing_lines & executable_lines):
        diagnostics.append(
            _diagnostic(
                changed_file.path,
                line,
                "line",
                "statement not executed",
                source_lines,
            )
        )
    for branch in _branch_pairs(file_data.get("missing_branches")):
        line, destination = branch
        if line in changed_file.added_lines:
            diagnostics.append(
                _diagnostic(
                    changed_file.path,
                    line,
                    "branch",
                    f"branch to line {destination} not taken",
                    source_lines,
                )
            )
    return diagnostics


def _integer_set(value: object) -> set[int]:
    """Return integer entries from a coverage JSON list."""
    values: list[object] | None = _object_list(value)
    if values is None:
        return set()
    return {item for item in values if isinstance(item, int) and not isinstance(item, bool)}


def _branch_pairs(value: object) -> tuple[tuple[int, int], ...]:
    """Return well-formed source/destination pairs from coverage branch data."""
    values: list[object] | None = _object_list(value)
    if values is None:
        return ()
    pairs: list[tuple[int, int]] = []
    for item in values:
        pair: list[object] | None = _object_list(item)
        if (
            pair is not None
            and len(pair) == 2
            and isinstance(pair[0], int)
            and isinstance(pair[1], int)
        ):
            pairs.append((pair[0], pair[1]))
    return tuple(pairs)


def _object_list(value: object) -> list[object] | None:
    """Return a list with its deserialized entries treated as objects."""
    return cast("list[object]", value) if isinstance(value, list) else None


def _read_source_lines(path: Path) -> list[str]:
    """Read source context without failing if a file disappeared after coverage ran."""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []


def _diagnostic(
    path: str,
    line: int,
    kind: str,
    detail: str,
    source_lines: Sequence[str],
) -> CoverageDiagnostic:
    """Create one diagnostic with an optional source line excerpt."""
    source: str = (
        source_lines[line - 1].strip() if line <= len(source_lines) else "<source unavailable>"
    )
    return CoverageDiagnostic(path=path, line=line, kind=kind, detail=detail, source=source)


def format_assessment(assessment: CoverageAssessment) -> str:
    """Format an assessment as concise, actionable human-facing output."""
    if not assessment.assessed:
        return assessment.message
    if not assessment.diagnostics:
        return f"{assessment.message} No uncovered changed lines or branches found."
    lines: list[str] = [assessment.message, "Uncovered changed code:"]
    for diagnostic in assessment.diagnostics:
        lines.append(
            f"  {diagnostic.path}:{diagnostic.line}: {diagnostic.kind}: "
            f"{diagnostic.detail} — {diagnostic.source}"
        )
    lines.append(
        "Add or adjust focused tests, then rerun `make coverage` and `make coverage-changed`."
    )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the changed-lines coverage diagnostic."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Git revision to compare with the current branch")
    parser.add_argument(
        "--coverage",
        type=Path,
        default=DEFAULT_COVERAGE_PATH,
        help="Path to the canonical coverage JSON report (default: coverage.json)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the non-enforcing changed-lines coverage diagnostic.

    Args:
        argv: Optional command-line arguments excluding the executable name.

    Returns:
        Zero for a completed diagnostic, or two when its Git/report inputs are invalid.
    """
    args: argparse.Namespace = parse_args(argv)
    try:
        if not args.coverage.is_file():
            assessment: CoverageAssessment = assess_coverage(
                args.coverage,
                (),
                repository_root=Path.cwd(),
            )
            print(format_assessment(assessment))
            return 0
        base_reference: str = choose_base_reference(args.base)
        assessment: CoverageAssessment = assess_coverage(
            args.coverage,
            changed_files(base_reference),
            repository_root=Path.cwd(),
        )
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Coverage changed-lines diagnostic could not run: {error}", file=sys.stderr)
        return 2
    print(format_assessment(assessment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

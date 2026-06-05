# topmark:header:start
#
#   project      : TopMark
#   file         : audit_action_pins.py
#   file_relpath : tools/ci/audit_action_pins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Audit pinned GitHub Actions references used by TopMark CI files.

This repository tool scans workflow files and local composite action metadata for
`uses: owner/repo@ref` entries. It reports when the same external GitHub Action is
referenced with multiple refs, which can happen when Dependabot updates workflow files
but does not update nested local composite actions under `.github/actions/`.

The audit is intentionally offline. By default it is read-only and reports
inconsistent refs already present in the repository. With `--fix`, it rewrites stale
repeated refs to the preferred ref already present in the scanned files. It never
queries GitHub, resolves tags, upgrades actions, or replaces Dependabot.

Examples:
    Run the audit from the repository root:

    ```bash
    python tools/ci/audit_action_pins.py
    ```

    Scan a different repository root:

    ```bash
    python tools/ci/audit_action_pins.py --root /path/to/repo
    ```

    Repair stale repeated refs when the preferred ref can be selected unambiguously:

    ```bash
    python tools/ci/audit_action_pins.py --fix
    ```

    Print an alphabetical summary of all action refs and counts:

    ```bash
    python tools/ci/audit_action_pins.py --report summary
    ```

    Print action refs grouped by source file:

    ```bash
    python tools/ci/audit_action_pins.py --report files
    ```

Raises:
    SystemExit: Exits with status code 1 when divergent refs remain or automatic repair
        cannot select one preferred ref unambiguously.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence


WORKFLOW_GLOBS: Final[tuple[str, ...]] = (
    ".github/workflows/**/*.yml",
    ".github/workflows/**/*.yaml",
)
ACTION_METADATA_GLOBS: Final[tuple[str, ...]] = (
    ".github/actions/**/action.yml",
    ".github/actions/**/action.yaml",
)
USES_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
    ^
    (?P<prefix>\s*uses:\s*)
    (?P<target>[^\s#]+)
    (?P<suffix>\s*(?:\#\s*(?P<comment>.*))?)
    \s*$
    """,
    re.VERBOSE,
)
EXTERNAL_ACTION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<ref>[^\s#]+)$"
)

REPORT_MODES: Final[tuple[str, ...]] = ("none", "summary", "files", "all")

VERSION_COMMENT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^v(?P<parts>\d+(?:\.\d+)*)(?:[-+][A-Za-z0-9_.-]+)?$"
)
SHA_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


@dataclass(frozen=True, kw_only=True, slots=True)
class ActionUse:
    """A single `uses:` reference to an external GitHub Action.

    Attributes:
        action: The `owner/repo` action identifier.
        ref: The ref used after `@`, usually a pinned commit SHA.
        path: Repository-relative file path containing the reference.
        line_number: One-based source line number.
        comment: Optional trailing comment, commonly used for the human-readable tag.
        line: Original source line containing the reference.
        prefix: Text before the action ref, including indentation and `uses:`.
        suffix: Text after the action ref, including any trailing comment.
    """

    action: str
    ref: str
    path: Path
    line_number: int
    comment: str | None
    line: str
    prefix: str
    suffix: str

    @property
    def ref_display(self) -> str:
        """Return the ref with its optional explanatory comment.

        Returns:
            The pinned ref, including the trailing comment when present.
        """
        if self.comment is None:
            return self.ref
        return f"{self.ref} # {self.comment}"

    @property
    def target(self) -> str:
        """Return the complete external action target.

        Returns:
            The `owner/repo@ref` action target.
        """
        return f"{self.action}@{self.ref}"

    @property
    def replacement_line(self) -> str:
        """Return the original line rewritten with this action target.

        Returns:
            Source line containing the current action target and original suffix.
        """
        return f"{self.prefix}{self.target}{self.suffix}"

    def with_ref_display(self, ref_display: str) -> ActionUse:
        """Return this action use with a different ref display.

        Args:
            ref_display: Replacement ref, optionally followed by a trailing `#` comment.

        Returns:
            Updated action use preserving the original source location and line prefix.
        """
        ref, comment = split_ref_display(ref_display)
        suffix = "" if comment is None else f" # {comment}"
        return ActionUse(
            action=self.action,
            ref=ref,
            path=self.path,
            line_number=self.line_number,
            comment=comment,
            line=self.line,
            prefix=self.prefix,
            suffix=suffix,
        )

    def format_location(self) -> str:
        """Return a compact source location for reports.

        Returns:
            A `path:line` location string.
        """
        return f"{self.path.as_posix()}:{self.line_number}"


@dataclass(frozen=True, kw_only=True, slots=True)
class AuditResult:
    """Result of auditing GitHub Action references.

    Attributes:
        uses: All discovered external action references.
        divergent_actions: Action references grouped by action name when multiple refs exist.
        unfixable_actions: Divergent action names that cannot be repaired automatically.
    """

    uses: tuple[ActionUse, ...]
    divergent_actions: dict[str, tuple[ActionUse, ...]]
    unfixable_actions: dict[str, tuple[str, ...]]

    @property
    def has_failures(self) -> bool:
        """Return whether the audit found divergent refs.

        Returns:
            `True` when at least one action is pinned to multiple refs.
        """
        return bool(self.divergent_actions)

    @property
    def can_fix(self) -> bool:
        """Return whether all divergent refs can be repaired automatically.

        Returns:
            `True` when divergent actions exist and none are ambiguous.
        """
        return self.has_failures and not self.unfixable_actions


def split_ref_display(ref_display: str) -> tuple[str, str | None]:
    """Split a ref display string into ref and optional comment.

    Args:
        ref_display: Ref text, optionally containing a trailing `#` comment.

    Returns:
        Pair of ref and optional comment text.
    """
    ref, separator, comment = ref_display.partition("#")
    stripped_ref = ref.strip()
    if not separator:
        return stripped_ref, None
    stripped_comment = comment.strip()
    return stripped_ref, stripped_comment or None


def parse_version_comment(comment: str | None) -> tuple[int, ...] | None:
    """Parse a SemVer-like version comment.

    Args:
        comment: Optional trailing action-pin comment.

    Returns:
        Numeric version tuple when the comment looks like `v1.2.3`, otherwise `None`.
    """
    if comment is None:
        return None
    match: re.Match[str] | None = VERSION_COMMENT_PATTERN.match(comment.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group("parts").split("."))


def choose_preferred_ref_display(action_uses: Sequence[ActionUse]) -> str | None:
    """Choose the ref display to use when repairing one divergent action group.

    The repair strategy intentionally avoids network lookups. It can only select a
    preferred ref when exactly one ref display has the highest SemVer-like trailing
    version comment.

    Args:
        action_uses: Divergent references for one action.

    Returns:
        Preferred ref display, or `None` when no unique preferred ref can be selected.
    """
    candidates: dict[str, tuple[int, ...]] = {}
    for action_use in action_uses:
        version = parse_version_comment(action_use.comment)
        if version is not None and SHA_PATTERN.match(action_use.ref):
            candidates[action_use.ref_display] = version

    if not candidates:
        return None

    highest_version = max(candidates.values())
    preferred = [ref for ref, version in candidates.items() if version == highest_version]
    if len(preferred) != 1:
        return None
    return preferred[0]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Raw command-line arguments excluding the program name.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Audit GitHub Actions pins in workflows and local composite actions."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to scan. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--report",
        choices=REPORT_MODES,
        default="none",
        help=(
            "Optional report mode. Use 'summary' for aggregated action/ref counts, "
            "'files' for counts grouped by source file, or 'all' for both."
        ),
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help=(
            "Rewrite stale repeated action refs to the preferred ref already present "
            "in scanned files. The preferred ref is selected from the highest "
            "SemVer-like trailing version comment, such as '# v8.2.0'."
        ),
    )
    return parser.parse_args(argv)


def iter_candidate_files(root: Path) -> Iterable[Path]:
    """Yield workflow and local composite-action metadata files.

    Args:
        root: Repository root.

    Yields:
        Matching files in deterministic sorted order.
    """
    seen: set[Path] = set()
    for pattern in (*WORKFLOW_GLOBS, *ACTION_METADATA_GLOBS):
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def parse_action_uses(root: Path, path: Path) -> tuple[ActionUse, ...]:
    """Parse external GitHub Action references from one file.

    Local actions such as `./.github/actions/setup-python-nox` and reusable workflows
    are ignored because the audit is concerned with external action version drift.

    Args:
        root: Repository root.
        path: File to parse.

    Returns:
        External GitHub Action references discovered in the file.
    """
    uses: list[ActionUse] = []
    relative_path: Path = path.relative_to(root)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match: re.Match[str] | None = USES_PATTERN.match(line)
        if match is None:
            continue

        target = match.group("target")
        action_match: re.Match[str] | None = EXTERNAL_ACTION_PATTERN.match(target)
        if action_match is None:
            continue

        uses.append(
            ActionUse(
                action=action_match.group("action"),
                ref=action_match.group("ref"),
                path=relative_path,
                line_number=line_number,
                comment=match.group("comment"),
                line=line,
                prefix=match.group("prefix"),
                suffix=match.group("suffix"),
            )
        )
    return tuple(uses)


def audit_repository(root: Path) -> AuditResult:
    """Audit external GitHub Action refs under a repository root.

    Args:
        root: Repository root to scan.

    Returns:
        Audit result containing all references and divergent action groups.

    Raises:
        FileNotFoundError: If the root path does not exist.
        NotADirectoryError: If the root path is not a directory.
    """
    resolved_root: Path = root.resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"Repository root does not exist: {resolved_root}")
    if not resolved_root.is_dir():
        raise NotADirectoryError(f"Repository root is not a directory: {resolved_root}")

    all_uses: list[ActionUse] = []
    for path in iter_candidate_files(resolved_root):
        all_uses.extend(parse_action_uses(resolved_root, path))

    grouped: dict[str, list[ActionUse]] = defaultdict(list)
    for action_use in all_uses:
        grouped[action_use.action].append(action_use)

    divergent_actions: dict[str, tuple[ActionUse, ...]] = {
        action: tuple(action_uses)
        for action, action_uses in sorted(grouped.items())
        if len({action_use.ref for action_use in action_uses}) > 1
    }
    unfixable_actions: dict[str, tuple[str, ...]] = {
        action: tuple(sorted({action_use.ref_display for action_use in action_uses}))
        for action, action_uses in divergent_actions.items()
        if choose_preferred_ref_display(action_uses) is None
    }
    return AuditResult(
        uses=tuple(all_uses),
        divergent_actions=divergent_actions,
        unfixable_actions=unfixable_actions,
    )


def fix_repository(root: Path, result: AuditResult) -> tuple[ActionUse, ...]:
    """Rewrite stale repeated action refs to their preferred pinned refs.

    Args:
        root: Repository root to update.
        result: Audit result containing divergent action groups.

    Returns:
        Updated action references that were rewritten.

    Raises:
        ValueError: If at least one divergent action cannot be repaired automatically.
    """
    if result.unfixable_actions:
        action_names = ", ".join(sorted(result.unfixable_actions))
        raise ValueError(f"Cannot select preferred refs for: {action_names}")

    replacements_by_path: dict[Path, dict[int, ActionUse]] = defaultdict(dict)
    for action_uses in result.divergent_actions.values():
        preferred_ref_display = choose_preferred_ref_display(action_uses)
        if preferred_ref_display is None:
            continue
        for action_use in action_uses:
            if action_use.ref_display == preferred_ref_display:
                continue
            replacements_by_path[action_use.path][action_use.line_number] = (
                action_use.with_ref_display(preferred_ref_display)
            )

    rewritten: list[ActionUse] = []
    for relative_path, replacements in sorted(
        replacements_by_path.items(), key=lambda item: item[0].as_posix()
    ):
        path = root / relative_path
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        for line_number, replacement in sorted(replacements.items()):
            original = lines[line_number - 1]
            newline = "\n" if original.endswith("\n") else ""
            if original.endswith("\r\n"):
                newline = "\r\n"
            lines[line_number - 1] = f"{replacement.replacement_line}{newline}"
            rewritten.append(replacement)
        path.write_text("".join(lines), encoding="utf-8")

    return tuple(rewritten)


# ---- Reporting helpers ----


def format_ref_count(ref: str, count: int, file_count: int | None = None) -> str:
    """Format one action ref count.

    Args:
        ref: Action ref used after `@`.
        count: Number of references using the ref.
        file_count: Optional number of unique files using the ref.

    Returns:
        Human-readable count line for reports.
    """
    reference_suffix = "reference" if count == 1 else "references"

    if file_count is None:
        return f"    - {ref}: {count} {reference_suffix}"

    file_suffix = "file" if file_count == 1 else "files"
    return f"    - {ref}: {count} {reference_suffix} across {file_count} {file_suffix}"


def format_summary_report(uses: Sequence[ActionUse]) -> str:
    """Format an alphabetical summary of action refs across all scanned files.

    Args:
        uses: Action references to summarize.

    Returns:
        Human-readable summary grouped by action and ref.
    """
    lines: list[str] = []
    lines.append("GitHub Actions pin summary")
    lines.append("==========================")
    lines.append("")

    if not uses:
        lines.append("No external GitHub Action references found.")
        return "\n".join(lines)

    grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    grouped_files: dict[str, dict[str, set[Path]]] = defaultdict(lambda: defaultdict(set))
    for action_use in uses:
        grouped[action_use.action][action_use.ref_display] += 1
        grouped_files[action_use.action][action_use.ref_display].add(action_use.path)

    for action in sorted(grouped):
        total = sum(grouped[action].values())
        suffix = "reference" if total == 1 else "references"
        lines.append(f"{action} ({total} {suffix})")
        for ref, count in sorted(grouped[action].items()):
            lines.append(
                format_ref_count(
                    ref,
                    count,
                    file_count=len(grouped_files[action][ref]),
                )
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def format_file_report(uses: Sequence[ActionUse]) -> str:
    """Format action refs grouped alphabetically by source file.

    Args:
        uses: Action references to summarize.

    Returns:
        Human-readable report grouped by file, action, and ref.
    """
    lines: list[str] = []
    lines.append("GitHub Actions pins by file")
    lines.append("===========================")
    lines.append("")

    if not uses:
        lines.append("No external GitHub Action references found.")
        return "\n".join(lines)

    grouped: dict[Path, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    for action_use in uses:
        grouped[action_use.path][action_use.action][action_use.ref_display] += 1

    for path in sorted(grouped, key=lambda item: item.as_posix()):
        lines.append(path.as_posix())
        for action in sorted(grouped[path]):
            total = sum(grouped[path][action].values())
            suffix = "reference" if total == 1 else "references"
            lines.append(f"  {action} ({total} {suffix})")
            for ref, count in sorted(grouped[path][action].items()):
                lines.append(format_ref_count(ref, count))
        lines.append("")

    return "\n".join(lines).rstrip()


def format_optional_reports(result: AuditResult, report_mode: str) -> str:
    """Format optional action-pin inventory reports.

    Args:
        result: Audit result containing discovered action references.
        report_mode: Selected report mode from `REPORT_MODES`.

    Returns:
        Empty text for `none`, otherwise one or more formatted reports.
    """
    if report_mode == "none":
        return ""
    if report_mode == "summary":
        return format_summary_report(result.uses)
    if report_mode == "files":
        return format_file_report(result.uses)
    return f"{format_summary_report(result.uses)}\n\n{format_file_report(result.uses)}"


def format_audit_report(result: AuditResult) -> str:
    """Format a human-readable audit report.

    Args:
        result: Audit result to render.

    Returns:
        Text report suitable for local terminals and GitHub Actions logs.
    """
    lines: list[str] = []
    lines.append("GitHub Actions pin audit")
    lines.append("========================")
    lines.append("")
    lines.append(f"External action references scanned: {len(result.uses)}")

    if not result.uses:
        lines.append("")
        lines.append("No external GitHub Action references found.")
        return "\n".join(lines)

    if not result.divergent_actions:
        lines.append("")
        lines.append("OK: all repeated external actions use consistent refs.")
        return "\n".join(lines)

    lines.append("")
    lines.append("FAIL: divergent refs detected for repeated external actions.")
    lines.append("")

    for action, action_uses in result.divergent_actions.items():
        lines.append(f"{action}:")
        for action_use in action_uses:
            lines.append(f"  - {action_use.format_location()}")
            lines.append(f"    {action_use.ref_display}")
        lines.append("")

    lines.append(
        "Update the stale references so each action uses one pinned ref "
        "across workflows and local actions."
    )
    return "\n".join(lines)


def format_fix_report(rewritten: Sequence[ActionUse]) -> str:
    """Format a human-readable repair report.

    Args:
        rewritten: Action references rewritten by `--fix`.

    Returns:
        Text report suitable for local terminals and GitHub Actions logs.
    """
    lines: list[str] = []
    lines.append("GitHub Actions pin repair")
    lines.append("=========================")
    lines.append("")

    if not rewritten:
        lines.append("No stale repeated action refs needed rewriting.")
        return "\n".join(lines)

    lines.append(f"Rewritten action references: {len(rewritten)}")
    lines.append("")
    for action_use in rewritten:
        lines.append(f"- {action_use.format_location()}")
        lines.append(f"  {action_use.ref_display}")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the action-pin audit CLI.

    Args:
        argv: Optional command-line arguments excluding the program name.

    Returns:
        Process exit code. Returns 0 when refs are consistent and 1 when divergence is detected.
    """
    args: argparse.Namespace = parse_args(sys.argv[1:] if argv is None else argv)
    root: Path = args.root.resolve()
    result: AuditResult = audit_repository(root)
    optional_report: str = format_optional_reports(result, args.report)
    if optional_report:
        print(optional_report)
        print()

    if args.fix and result.has_failures:
        if not result.can_fix:
            print(format_audit_report(result))
            print()
            print("Automatic repair skipped: no unique preferred ref could be selected.")
            return 1
        try:
            rewritten = fix_repository(root, result)
        except ValueError as error:
            print(format_audit_report(result))
            print()
            print(f"Automatic repair failed: {error}")
            return 1
        print(format_fix_report(rewritten))
        print()
        result = audit_repository(root)

    print(format_audit_report(result))
    return 1 if result.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

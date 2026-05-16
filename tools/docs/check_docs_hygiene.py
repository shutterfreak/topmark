#!/usr/bin/env python3

# topmark:header:start
#
#   project      : TopMark
#   file         : check_docs_hygiene.py
#   file_relpath : tools/docs/check_docs_hygiene.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static documentation hygiene checks for TopMark.

This tool validates two documentation surfaces:

* Python docstring link style.
* Markdown snippet/include, navigation, heading, and section-structure hygiene under ``docs/``.

The checks are intentionally syntactic and deterministic. They are not a substitute for human
review, strict MkDocs builds, or link checking. They catch small authoring mistakes that are easy to
miss in rendered documentation.

Usage:
    # Default: scan Python docstrings under src/
    python tools/docs/check_docs_hygiene.py --stats

    # Explicit Python files or directories
    python tools/docs/check_docs_hygiene.py src/topmark/foo.py src/topmark/bar.py

    # Check Markdown snippet/include hygiene
    python tools/docs/check_docs_hygiene.py --docs-hygiene --stats

Exit codes:
    0  no errors found
    1  errors found, or warnings found when --fail-on-warnings is used
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

from yachalk import chalk

if TYPE_CHECKING:
    from collections.abc import Sequence

# Default Markdown paths to process.
# The docs-hygiene scan covers documentation sources recursively and top-level Markdown files.
DOCS_PATHS: Final[tuple[str, ...]] = ("docs", ".")

# Reference-style links accepted by the checker:
#   1) Full reference form:            [Text][pkg.mod.Object]
#   2) Code label + full ref:          [`pkg.mod.Object`][pkg.mod.Object]
#   3) Shortcut reference link:        [`pkg.mod.Object`][]
REF_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    \[
      (?:`?[\w\.\-]+`?|\S[^]]+?) # label: either code-ish or any text
    \]
    \[
      [\w\.\-]*                  # ref: fully qualified target or label (allow empty for shortcut)
    \]
    """,
    re.VERBOSE,
)

# Internal FQNs that *look like* symbols (final segment capitalized). We avoid module-only names.
INTERNAL_FQN_RE: Final[re.Pattern[str]] = re.compile(
    r"\btopmark(?:\.[A-Za-z_][\w]*)+\.[A-Z][\w]*\b",
)

# Any raw URL inside a docstring is flagged unless whitelisted in ALLOWED_URLS.
# Allow literal URLs matching these patterns inside docstrings
ALLOWED_URLS: Final[tuple[str, ...]] = (
    r"https?://(www\.)?example\.(com|org|net)/?",
    r"https?://(docs\.)?python\.org/.*",
)


URL_RE: Final[re.Pattern[str]] = re.compile(
    r"https?://\S+",
)

# We may ignore code regions when scanning text. For accurate index math (to compute line numbers),
# code regions are masked with spaces (same length) rather than removed.
# Regexes to ignore code segments in docstrings
CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"```.*?```",
    re.DOTALL,
)  # fenced code blocks
INLINE_CODE_RE: Final[re.Pattern[str]] = re.compile(
    r"`[^`]+`",
)  # inline code spans
# Lightweight Markdown hygiene checks.
INCLUDE_MARKDOWN_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    \{%-?\s*include-markdown\s+
    (?P<quote>[\"'])
    (?P<path>[^\"']+)
    (?P=quote)
    \s*-?%\}
    """,
    re.VERBOSE,
)
HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^#{1,6}\s+",
    re.MULTILINE,
)
HEADING_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<marker>#{1,6})\s+(?P<title>.+)$",
    re.MULTILINE,
)

# Dedicated changelog hygiene constants
CHANGELOG_PATH: Final[Path] = Path("CHANGELOG.md")
CHANGELOG_RELEASE_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^## \[(?P<version>[^\]]+)\] - \d{4}-\d{2}-\d{2}$"
)
CHANGELOG_SECTION_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^### (?P<section>[A-Za-z][A-Za-z /-]*) - (?P<version>\S+)$"
)
CHANGELOG_ALLOWED_SECTIONS: Final[frozenset[str]] = frozenset(
    {
        "Added",
        "Breaking Changes",
        "Changed",
        "Deprecated",
        "Documentation",
        "Fixed",
        "Highlights",
        "Internal",
        "Notes",
        "Removed",
        "Security",
    }
)

# This deliberately checks a broad Unicode-symbol range rather than full emoji grapheme clusters.
# The docs policy is stricter than "no rendered emoji": documentation headings should avoid
# decorative symbols entirely. That makes a lightweight dependency-free check sufficient here.
DECORATIVE_SYMBOL_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0x1F1E6, 0x1F1FF),  # flags
    (0x1F300, 0x1F5FF),  # symbols and pictographs
    (0x1F600, 0x1F64F),  # emoticons
    (0x1F680, 0x1F6FF),  # transport and map symbols
    (0x1F900, 0x1F9FF),  # supplemental symbols and pictographs
    (0x1FA70, 0x1FAFF),  # symbols and pictographs extended-a
    (0x2600, 0x26FF),  # miscellaneous symbols
    (0x2700, 0x27BF),  # dingbats
)


def has_decorative_symbol(text: str) -> bool:
    """Return True when text contains a decorative symbol disallowed in headings."""
    return any(
        start <= ord(char) <= end for char in text for start, end in DECORATIVE_SYMBOL_RANGES
    )


SMART_PUNCTUATION_RE: Final[re.Pattern[str]] = re.compile(
    r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2018\u2019\u201A\u201B\u201C\u201D\u201E\u201F\u2026]"
)


def describe_smart_punctuation(char: str) -> str:
    """Return a short replacement hint for a smart-punctuation character."""
    replacements: dict[str, str] = {
        "\u2010": "hyphen '-'",
        "\u2011": "hyphen '-'",
        "\u2012": "hyphen '-'",
        "\u2013": "hyphen '-' or '--'",
        "\u2014": "hyphen '-' or '--'",
        "\u2015": "hyphen '-' or '--'",
        "\u2018": 'apostrophe "\'"',
        "\u2019": 'apostrophe "\'"',
        "\u201a": 'apostrophe "\'"',
        "\u201b": 'apostrophe "\'"',
        "\u201c": "quote '\"'",
        "\u201d": "quote '\"'",
        "\u201e": "quote '\"'",
        "\u201f": "quote '\"'",
        "\u2026": "three periods '...'",
    }
    return replacements.get(char, "ASCII punctuation")


LEVEL2_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+",
    re.MULTILINE,
)
HORIZONTAL_RULE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$",
)
RELATIVE_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"\[[^\]]+\]\((?!https?://|mailto:|#|/)(?P<target>[^)]+)\)",
)
MKDOCS_NAV_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<path>[A-Za-z0-9_./-]+\.md)(?:[#?][^\s'\"]*)?",
)

SNIPPET_INCLUDE_PREFIX: Final[str] = r"\_snippets/"
SNIPPET_DIR: Final[Path] = Path("docs/_snippets")
DOCS_DIR: Final[Path] = Path("docs")
MKDOCS_CONFIG: Final[Path] = Path("mkdocs.yml")


@dataclass(frozen=True, kw_only=True, slots=True)
class Diagnostic:
    """A docs-hygiene diagnostic.

    Attributes:
        severity: Either ``"error"`` or ``"warning"``.
        path: File path associated with the diagnostic.
        line: Optional 1-based line number.
        message: Human-readable message.
    """

    severity: str
    path: Path
    line: int | None
    message: str

    def render(self) -> str:
        """Render the diagnostic in a grep-friendly format.

        Returns:
            Human-readable diagnostic string.
        """
        location = (
            f"{self.path.as_posix()}:{self.line}" if self.line is not None else self.path.as_posix()
        )
        label = (
            chalk.red.bold("error") if self.severity == "error" else chalk.yellow.bold("warning")
        )
        return f"{chalk.bold(location)}: {label}: {self.message}"


def iter_markdown_files(paths: Sequence[str] | None) -> list[Path]:
    """Expand input paths into a de-duplicated, lexicographically sorted list of Markdown files.

    Args:
        paths: File or directory paths to scan.

    Returns:
        Markdown source files to scan.
    """
    todo: list[Path] = []
    use_paths: Sequence[str] = paths or DOCS_PATHS
    for p in use_paths:
        path = Path(p)
        if path.is_dir():
            if path == Path():
                todo.extend(child for child in path.glob("*.md") if child.is_file())
            else:
                todo.extend(path.rglob("*.md"))
        elif path.is_file() and path.suffix == ".md":
            todo.append(path)

    seen: set[Path] = set()
    out: list[Path] = []
    for f in sorted(todo):
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _relative_to_docs(path: Path) -> Path:
    """Return a docs-root-relative path.

    Args:
        path: Markdown file under ``docs/``.

    Returns:
        Path relative to ``DOCS_DIR``.
    """
    return path.resolve().relative_to(DOCS_DIR.resolve())


def _line_for_offset(text: str, offset: int) -> int:
    """Return the 1-based line number for ``offset`` in ``text``.

    Args:
        text: Source text.
        offset: Character offset.

    Returns:
        1-based line number.
    """
    return text.count("\n", 0, offset) + 1


def _is_under(path: Path, parent: Path) -> bool:
    """Return True when ``path`` is under ``parent`` after resolution.

    Args:
        path: Candidate path.
        parent: Expected parent directory.

    Returns:
        True if ``path`` is within ``parent``.
    """
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _normalize_include_path(raw_path: str) -> str:
    """Normalize an include path from Markdown source.

    Args:
        raw_path: Raw path captured from an include-markdown directive.

    Returns:
        The docs-root-relative include path after formatter escape normalization.
    """
    return raw_path.replace(r"\_", "_")


def _is_snippet(path: Path) -> bool:
    """Return True if ``path`` is a reusable Markdown snippet.

    Args:
        path: Candidate path.

    Returns:
        True if ``path`` is under ``docs/_snippets`` and is Markdown content.
    """
    return (
        _is_under(path, SNIPPET_DIR) and path.suffix == ".md" and path.name != ".markdownlint.jsonc"
    )


def _is_nav_exempt(path: Path) -> bool:
    """Return True when a Markdown file is exempt from MkDocs nav membership.

    Args:
        path: Candidate Markdown file.

    Returns:
        True when the file is allowed to exist outside the MkDocs nav.
    """
    return _is_snippet(path)


# Allow certain snippets to intentionally use relative links.
def _allows_relative_links(path: Path) -> bool:
    """Return True when a snippet intentionally allows relative links.

    Relative links in snippets are allowed when they are intended to be rewritten relative to the
    consuming page by mkdocs-include-markdown-plugin. Shared navigation snippets and shared note
    snippets may centralize such links safely.

    Args:
        path: Candidate Markdown snippet.

    Returns:
        True when the snippet intentionally permits relative links.
    """
    return _is_snippet(path) and (
        path.name.startswith("related-pages") or path.name == "terminology.md"
    )


def _extract_mkdocs_nav_block(text: str) -> str:
    """Extract the top-level MkDocs `nav` block from a config file.

    Args:
        text: Contents of `mkdocs.yml`.

    Returns:
        The raw nav block text, or an empty string if no top-level nav block is present.
    """
    lines: list[str] = text.splitlines()
    nav_lines: list[str] = []
    in_nav = False
    for line in lines:
        if not in_nav:
            if line == "nav:":
                in_nav = True
                nav_lines.append(line)
            continue

        if line and not line.startswith((" ", "-")):
            break
        nav_lines.append(line)
    return "\n".join(nav_lines)


def _extract_nav_markdown_paths(mkdocs_config: Path) -> set[Path]:
    """Extract Markdown paths referenced by the MkDocs nav section.

    Args:
        mkdocs_config: Path to `mkdocs.yml`.

    Returns:
        Docs-root-relative Markdown paths referenced by the nav section.
    """
    if not mkdocs_config.exists():
        return set()

    nav_block: str = _extract_mkdocs_nav_block(mkdocs_config.read_text(encoding="utf-8"))
    return {Path(match.group("path")) for match in MKDOCS_NAV_PATH_RE.finditer(nav_block)}


def _mask_code_regions(text: str, *, ignore_inline: bool = False) -> str:
    """Return a copy of *text* with code regions masked by spaces (same length).

    This preserves character indices so regex match offsets remain valid when we later map them
    back to absolute line numbers in the original source file.

    Args:
        text: The original docstring text.
        ignore_inline: If True, mask both fenced code blocks and inline code spans; otherwise
            mask only fenced code blocks, and still check inline code for style violations.

    Returns:
        The masked string.
    """

    def repl(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    # Always mask fenced code blocks
    text = CODE_FENCE_RE.sub(repl, text)
    # Optionally also mask inline code spans
    if ignore_inline:
        text = INLINE_CODE_RE.sub(repl, text)
    return text


def iter_python_files(paths: list[str]) -> list[Path]:
    """Expand input paths into a de-duplicated, lexicographically-sorted list of Python files.

    Each path may be a directory (recursively scanned for ``*.py``) or a single Python file.
    If *paths* is empty, defaults to scanning ``["src"]``.

    Args:
        paths: File or directory paths to scan.

    Returns:
        A list of ``Path`` objects pointing to Python source files.
    """
    todo: list[Path] = []
    use_paths: list[str] = paths or ["src"]
    for p in use_paths:
        path = Path(p)
        if path.is_dir():
            todo.extend(path.rglob("*.py"))
        elif path.is_file() and path.suffix == ".py":
            todo.append(path)
    # De-duplicate while preserving a stable order
    seen: set[Path] = set()
    out: list[Path] = []
    for f in sorted(todo):
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def extract_docstrings(py_path: Path) -> list[tuple[int, int, str]]:
    """Collect docstrings from a Python module with precise line ranges.

    For each module/class/function/async function, we return the starting and ending source
    line numbers of the docstring and the docstring text itself. Line numbers are derived
    from the AST nodes that contain the docstring expressions.

    Args:
        py_path: Path to a Python source file.

    Returns:
        A list of tuples ``(start_lineno, end_lineno, docstring_text)``.
    """
    text: str = py_path.read_text(encoding="utf-8")
    try:
        tree: ast.Module = ast.parse(text)
    except SyntaxError:
        return []
    results: list[tuple[int, int, str]] = []

    # Module docstring
    if tree.body:
        first_stmt: ast.stmt = tree.body[0]
        if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Constant):
            const: ast.Constant = first_stmt.value
            if isinstance(const.value, str):
                ds: str = const.value
                start_lineno: int = first_stmt.lineno
                end_lineno: int = start_lineno + ds.count("\n")
                results.append((start_lineno, end_lineno, ds))

    # Class/def/async def docstrings
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and node.body:
            first_stmt = node.body[0]
            if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Constant):
                const = first_stmt.value
                if isinstance(const.value, str):
                    ds = const.value
                    start_lineno = first_stmt.lineno
                    end_lineno = start_lineno + ds.count("\n")
                    results.append((start_lineno, end_lineno, ds))

    return results


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the documentation hygiene checker."""
    parser = argparse.ArgumentParser(description="Check TopMark documentation hygiene.")
    parser.add_argument("paths", nargs="*", help="Files or directories to check")
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print summary statistics after checking",
    )
    parser.add_argument(
        "--ignore-inline-code",
        action="store_true",
        help=(
            "Ignore inline code spans when checking docstrings. Defaults to checking inline code."
        ),
    )
    parser.add_argument(
        "--docs-hygiene",
        action="store_true",
        help="Check Markdown snippet/include hygiene instead of Python docstrings",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Make docs-hygiene warnings fail the command",
    )
    return parser.parse_args()


def _check_changelog_hygiene(path: Path, text: str) -> list[Diagnostic]:
    """Validate TopMark-specific changelog heading conventions.

    Args:
        path: Changelog path.
        text: Changelog source text.

    Returns:
        Diagnostics for changelog structure violations.
    """
    diagnostics: list[Diagnostic] = []

    for heading in HEADING_LINE_RE.finditer(text):
        marker: str = heading.group("marker")
        title: str = heading.group("title")
        line: int = _line_for_offset(text, heading.start())

        if marker == "#":
            continue

        if marker == "##":
            if not CHANGELOG_RELEASE_HEADING_RE.fullmatch(heading.group(0)):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=line,
                        message=(
                            "CHANGELOG.md level-2 headings must be release entries shaped "
                            f"like '## [1.0.0] - YYYY-MM-DD', found '{marker} {title}'"
                        ),
                    )
                )
            continue

        if marker == "###":
            section_match: re.Match[str] | None = CHANGELOG_SECTION_HEADING_RE.fullmatch(
                heading.group(0)
            )
            if section_match is None:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=line,
                        message=(
                            "CHANGELOG.md level-3 headings must be release sections shaped "
                            f"like '### Fixed - 1.0.0', found '{marker} {title}'"
                        ),
                    )
                )
                continue

            section: str = section_match.group("section")
            if section not in CHANGELOG_ALLOWED_SECTIONS:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=line,
                        message=(
                            "CHANGELOG.md level-3 heading uses an unsupported section name: "
                            f"{section!r}"
                        ),
                    )
                )

            if has_decorative_symbol(title):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=line,
                        message="emoji are not allowed in CHANGELOG.md headings",
                    )
                )
            continue

        diagnostics.append(
            Diagnostic(
                severity="error",
                path=path,
                line=line,
                message=(
                    "CHANGELOG.md must not use level-4 or deeper headings; "
                    "use bold list labels for level-4 and list labels for level-5+ sections instead"
                ),
            )
        )

    return diagnostics


def check_docs_hygiene(
    paths: Sequence[str] | None,
    *,
    stats: bool = False,
    fail_on_warnings: bool = False,
) -> int:
    """Validate lightweight Markdown documentation hygiene.

    Hard failures cover objective problems:
    - accidental macOS ``._*`` resource files under documentation sources;
    - Markdown files under ``docs/`` that are missing from ``mkdocs.yml`` nav;
    - emoji in Markdown headings;
    - malformed or broken ``include-markdown`` paths;
    - nested snippet includes;
    - level-2 Markdown sections that are not separated by a horizontal rule.

    Warnings cover maintainability concerns:
    - orphaned snippets;
    - headings inside snippets;
    - smart punctuation in Markdown prose;
    - relative links inside snippets that appear incompatible with include-markdown link rewriting;
    - snippet include paths missing the mdformat-stable escaped underscore convention.

    Args:
        paths: File or directory paths to check. If None or empty, defaults to ``DOCS_PATHS``.
        stats: If True, print summary counts.
        fail_on_warnings: If True, warnings also produce a non-zero exit code.

    Returns:
        0 if no errors were found; 1 otherwise. Warnings only fail when ``fail_on_warnings`` is set.
    """
    md_files: list[Path] = iter_markdown_files(paths or DOCS_PATHS)
    diagnostics: list[Diagnostic] = []
    normal_markdown_files: list[Path] = []
    included_targets: set[Path] = set()
    nav_paths: set[Path] = _extract_nav_markdown_paths(MKDOCS_CONFIG)

    for path in md_files:
        if any(part.startswith("._") for part in path.parts):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    path=path,
                    line=None,
                    message="remove accidental macOS resource-fork file from docs sources",
                )
            )
            continue

        try:
            text: str = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    path=path,
                    line=None,
                    message=f"could not read Markdown file as UTF-8: {exc}",
                )
            )
            continue

        if not _is_snippet(path):
            normal_markdown_files.append(path)

            if _is_under(path, DOCS_DIR) and not _is_nav_exempt(path):
                docs_relative_path = _relative_to_docs(path)
                if docs_relative_path not in nav_paths:
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            path=path,
                            line=None,
                            message=(
                                "Markdown file under docs/ is missing from mkdocs.yml nav: "
                                f"{docs_relative_path.as_posix()}"
                            ),
                        )
                    )

            for heading in HEADING_LINE_RE.finditer(text):
                if has_decorative_symbol(heading.group("title")):
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            path=path,
                            line=_line_for_offset(text, heading.start()),
                            message="emoji are not allowed in Markdown headings",
                        )
                    )
            if path == CHANGELOG_PATH:
                diagnostics.extend(_check_changelog_hygiene(path, text))

            prose_text: str = _mask_code_regions(text)
            for smart_punctuation in SMART_PUNCTUATION_RE.finditer(prose_text):
                char: str = smart_punctuation.group(0)
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        path=path,
                        line=_line_for_offset(text, smart_punctuation.start()),
                        message=(
                            "replace smart punctuation "
                            f"{char!r} with {describe_smart_punctuation(char)}"
                        ),
                    )
                )

            level2_matches: list[re.Match[str]] = list(LEVEL2_HEADING_RE.finditer(text))
            for heading_match in level2_matches[1:]:
                heading_line: int = _line_for_offset(text, heading_match.start())
                preceding_lines: list[str] = text[: heading_match.start()].splitlines()
                previous_non_empty: str = next(
                    (line for line in reversed(preceding_lines) if line.strip()),
                    "",
                )
                if not HORIZONTAL_RULE_RE.fullmatch(previous_non_empty):
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            path=path,
                            line=heading_line,
                            message=(
                                "level-2 Markdown sections must be separated by a horizontal rule"
                            ),
                        )
                    )

        for match in INCLUDE_MARKDOWN_RE.finditer(text):
            raw_include = match.group("path")
            include_line: int = _line_for_offset(text, match.start())
            normalized: str = _normalize_include_path(raw_include)

            if raw_include.startswith("_snippets/"):
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        path=path,
                        line=include_line,
                        message=(
                            "snippet include should use the mdformat-stable escaped prefix "
                            f"{SNIPPET_INCLUDE_PREFIX!r}"
                        ),
                    )
                )

            normalized_parts: tuple[str, ...] = Path(normalized).parts
            if (
                normalized.startswith("/")
                or normalized.startswith("./")
                or ".." in normalized_parts
            ):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=include_line,
                        message="include-markdown paths must be docs-root-relative "
                        "and must not traverse parents",
                    )
                )
                continue

            target: Path = DOCS_DIR / normalized
            if not _is_under(target, DOCS_DIR):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=include_line,
                        message="include-markdown target resolves outside docs/",
                    )
                )
                continue

            if not target.exists():
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=include_line,
                        message=f"include-markdown target does not exist: {normalized}",
                    )
                )
                continue

            included_targets.add(target)

            if _is_snippet(path) and _is_snippet(target):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        path=path,
                        line=include_line,
                        message="snippets must not include other snippets",
                    )
                )

    snippets: list[Path] = (
        sorted(p for p in SNIPPET_DIR.rglob("*.md") if _is_snippet(p))
        if SNIPPET_DIR.exists()
        else []
    )
    for snippet in snippets:
        if snippet not in included_targets:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    path=snippet,
                    line=None,
                    message="snippet is not included by any Markdown page",
                )
            )

        text = snippet.read_text(encoding="utf-8")
        for heading in HEADING_RE.finditer(text):
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    path=snippet,
                    line=_line_for_offset(text, heading.start()),
                    message="avoid headings inside reusable snippets",
                )
            )

        prose_text = _mask_code_regions(text)
        for smart_punctuation in SMART_PUNCTUATION_RE.finditer(prose_text):
            char = smart_punctuation.group(0)
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    path=snippet,
                    line=_line_for_offset(text, smart_punctuation.start()),
                    message=(
                        "replace smart punctuation "
                        f"{char!r} with {describe_smart_punctuation(char)}"
                    ),
                )
            )

        if _allows_relative_links(snippet):
            continue
        for rel_link in RELATIVE_LINK_RE.finditer(text):
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    path=snippet,
                    line=_line_for_offset(text, rel_link.start()),
                    message="avoid relative links inside reusable snippets unless include-markdown "
                    "link rewriting is intentional",
                )
            )

    errors: list[Diagnostic] = [d for d in diagnostics if d.severity == "error"]
    warnings: list[Diagnostic] = [d for d in diagnostics if d.severity == "warning"]

    for diagnostic in diagnostics:
        print(diagnostic.render())

    if stats:
        print(f"Markdown files checked: {len(md_files)}")
        print(f"Normal Markdown files checked: {len(normal_markdown_files)}")
        print(f"Snippets checked: {len(snippets)}")
        print(f"MkDocs nav entries checked: {len(nav_paths)}")
        print(f"Errors found: {len(errors)}")
        print(f"Warnings found: {len(warnings)}")

    if errors:
        return 1
    if warnings and fail_on_warnings:
        return 1
    return 0


def main(
    paths: list[str] | None,
    stats: bool = False,
    ignore_inline_code: bool = False,
) -> int:
    """Validate docstring link style across the given files or directories.

    Args:
        paths: File or directory paths to check. If None or empty,
            defaults to ``["src"]``.
        stats: If True, print a summary of files/docstrings examined and errors found.
        ignore_inline_code: If True, ignore inline code spans (mask them) when scanning;
            by default, inline code is checked so that backticked FQNs still require
            reference links.

    Returns:
        0 if no violations were found; 1 otherwise. All violations are printed to stdout in a
        grep-friendly ``path:lineno: message`` format.
    """
    errors: list[str] = []

    allow_re: re.Pattern[str] | None = re.compile("|".join(ALLOWED_URLS)) if ALLOWED_URLS else None

    files_checked = 0
    docstrings_checked = 0

    py_files: list[Path] = iter_python_files(paths or ["src"])
    for path in py_files:
        files_checked += 1

        for start_lineno, end_lineno, ds in extract_docstrings(path):
            docstrings_checked += 1
            # Ignore fenced and inline code when matching FQNs/URLs
            masked: str = _mask_code_regions(ds, ignore_inline=ignore_inline_code)

            # Map a regex match inside the docstring to an absolute source line number
            def _abs_line(m: re.Match[str], *, docstring: str, start_lineno: int) -> int:
                local_line: int = (
                    docstring.count("\n", 0, m.start()) + 1
                )  # 1-based within docstring
                return start_lineno + local_line - 1

            # 1) Flag literal URLs unless whitelisted
            for m in URL_RE.finditer(masked):
                url: str = m.group(0)
                if not allow_re or not allow_re.search(url):
                    ln: int = _abs_line(m, docstring=ds, start_lineno=start_lineno)
                    errors.append(
                        f"{chalk.bold(path)}:{chalk.bold(ln)}: "
                        f"avoid raw URL in docstring -> {url}"
                        f"  (docstring {start_lineno}–{end_lineno})"
                    )  # Include docstring range for quick context

            # 2) For internal fully-qualified names, require a reference-style link nearby.
            #    Skip occurrences inside existing reference links.
            # Compute spans of existing reference links (from the *original* text)
            ref_spans: list[tuple[int, int]] = [
                (m.start(), m.end()) for m in REF_LINK_RE.finditer(ds)
            ]
            missing: list[tuple[str, int]] = []
            for fqn_m in INTERNAL_FQN_RE.finditer(masked):
                s: int = fqn_m.start()
                if any(a <= s < b for (a, b) in ref_spans):
                    continue  # already inside a ref link
                miss_line: int = _abs_line(fqn_m, docstring=ds, start_lineno=start_lineno)
                missing.append((fqn_m.group(0), miss_line))

            if missing:
                lines: list[str] = []
                for name, ln in sorted(set(missing)):
                    lines.append(
                        f"{chalk.bold(path)}:{chalk.bold(ln)}: "
                        "internal names should be reference-linked: "
                        f"{name}  (docstring {start_lineno}–{end_lineno})\n"
                        + chalk.italic(
                            "\tuse "
                            + chalk.yellow.bold(f"[`{name}`][]")
                            + " or "
                            + chalk.yellow.bold(f"[Text][{name}]")
                        )
                    )  # Show both exact line and encompassing docstring range

                errors.append("\n".join(lines))

    if errors:
        print("\n".join(errors))

    if stats:
        print(f"Files checked: {files_checked}")
        print(f"Docstrings checked: {docstrings_checked}")
        print(f"Errors found: {len(errors)}")

    return 1 if errors else 0


if __name__ == "__main__":
    args: argparse.Namespace = parse_args()
    if args.docs_hygiene:
        sys.exit(
            check_docs_hygiene(
                args.paths,
                stats=args.stats,
                fail_on_warnings=args.fail_on_warnings,
            )
        )

    sys.exit(
        main(
            args.paths or ["src"],
            stats=args.stats,
            ignore_inline_code=args.ignore_inline_code,
        )
    )

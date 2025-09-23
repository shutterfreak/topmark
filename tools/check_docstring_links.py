#!/usr/bin/env python3

# topmark:header:start
#
#   project      : TopMark
#   file         : check_docstring_links.py
#   file_relpath : tools/check_docstring_links.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static style checker for links used in Python docstrings.

This tool enforces TopMark's docstring link style:

* Prefer **reference-style links** for Python objects resolved by mkdocstrings+autorefs,
  e.g. ``[`topmark.module.Class`][]`` or ``[Text][topmark.module.Class]``.
* Avoid **raw HTTP(S) URLs** in docstrings unless they match an allowlist
  (examples, stdlib docs, etc.).

The checker is intentionally *syntactic*. It does not resolve targets; MkDocs does that during
the docs build. We only look for patterns that indicate intent and good authoring style.

Usage:
    # Default: scan the TopMark source tree
    python tools/check_docstring_links.py --stats

    # Explicit files
    python tools/check_docstring_links.py src/topmark/foo.py src/topmark/bar.py

    # Directories are supported (recursively)
    python tools/check_docstring_links.py src

    # Also ignore inline code spans (treat them like code blocks)
    python tools/check_docstring_links.py --ignore-inline-code src

Exit codes:
    0  no issues found
    1  violations detected (messages printed to stdout)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Pattern

from yachalk import chalk

# Reference-style links accepted by the checker:
#   1) Full reference form:            [Text][pkg.mod.Object]
#   2) Code label + full ref:          [`pkg.mod.Object`][pkg.mod.Object]
#   3) Shortcut reference link:        [`pkg.mod.Object`][]
REF_LINK_RE: Pattern[str] = re.compile(
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
INTERNAL_FQN_RE: Pattern[str] = re.compile(r"\btopmark(?:\.[A-Za-z_][\w]*)+\.[A-Z][\w]*\b")

# Any raw URL inside a docstring is flagged unless whitelisted in ALLOWED_URLS.
# Allow literal URLs matching these patterns inside docstrings
ALLOWED_URLS: tuple[str, ...] = (
    r"https?://(www\.)?example\.(com|org|net)/?",
    r"https?://(docs\.)?python\.org/.*",
)


URL_RE: Pattern[str] = re.compile(r"https?://\S+")

# We may ignore code regions when scanning text. For accurate index math (to compute line numbers),
# code regions are masked with spaces (same length) rather than removed.
# Regexes to ignore code segments in docstrings
CODE_FENCE_RE: Pattern[str] = re.compile(r"```.*?```", re.DOTALL)  # fenced code blocks
INLINE_CODE_RE: Pattern[str] = re.compile(r"`[^`]+`")  # inline code spans


def _mask_code_regions(text: str, *, ignore_inline: bool = False) -> str:
    """Return a copy of *text* with code regions masked by spaces (same length).

    This preserves character indices so regex match offsets remain valid when we later map them
    back to absolute line numbers in the original source file.

    Args:
        text (str): The original docstring text.
        ignore_inline (bool): If True, mask both fenced code blocks and inline code spans; otherwise
            mask only fenced code blocks, and still check inline code for style violations.

    Returns:
        str: The masked string.
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
        paths (list[str]): File or directory paths to scan.

    Returns:
        list[Path]: A list of ``Path`` objects pointing to Python source files.
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
        py_path (Path): Path to a Python source file.

    Returns:
        list[tuple[int, int, str]]: A list of tuples ``(start_lineno, end_lineno, docstring_text)``.
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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
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
    """Parse command-line arguments for the docstring link checker."""
    parser = argparse.ArgumentParser(description="Check docstring link style in Python files.")
    parser.add_argument("paths", nargs="*", help="Files or directories to check (default: src)")
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print summary statistics after checking",
    )
    parser.add_argument(
        "--ignore-inline-code",
        action="store_true",
        help=(
            "Ignore inline code spans when checking (mask them like fenced code). "
            "Defaults to checking inline code."
        ),
    )
    return parser.parse_args()


def main(
    paths: list[str] | None,
    stats: bool = False,
    ignore_inline_code: bool = False,
) -> int:
    """Validate docstring link style across the given files or directories.

    Args:
        paths (list[str] | None): File or directory paths to check. If None or empty,
            defaults to ``["src"]``.
        stats (bool): If True, print a summary of files/docstrings examined and errors found.
        ignore_inline_code (bool): If True, ignore inline code spans (mask them) when scanning;
            by default, inline code is checked so that backticked FQNs still require
            reference links.

    Returns:
        int: 0 if no violations were found; 1 otherwise. All violations are printed to stdout in a
            grep-friendly ``path:lineno: message`` format.
    """
    errors: list[str] = []

    allow_re: Pattern[str] | None = re.compile("|".join(ALLOWED_URLS)) if ALLOWED_URLS else None

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
    sys.exit(
        main(
            args.paths or ["src"],
            stats=args.stats,
            ignore_inline_code=args.ignore_inline_code,
        )
    )

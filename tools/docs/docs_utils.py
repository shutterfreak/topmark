# topmark:header:start
#
#   project      : TopMark
#   file         : docs_utils.py
#   file_relpath : tools/docs/docs_utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared reference-hygiene helpers for TopMark docs.

This module centralizes small, deterministic helpers used by:
- `tools/docs/hooks.py` (MkDocs simple-hooks)
- `tools/docs/gen_api_pages.py` (mkdocs-gen-files script)

It intentionally contains small utilities only:
- Markdown link/reference hygiene helpers (including mdformat bracket unescape)
- Inline-code symbol scanning helpers
- Environment flag parsing
- Repo-path formatting helpers

Configuration is read from environment variables at import time (e.g.
`TOPMARK_DOCS_NONLINKED_SYMBOLS`), but no I/O beyond that is performed.

This module is safe for Python 3.10-3.14.

Callers are responsible for logging and for deciding severity based on
`TOPMARK_DOCS_DEBUG` / `TOPMARK_DOCS_STRICT_REFS`.

Because it’s executed as a script (not imported as a package), helpers must be imported via
absolute module paths (e.g. tools.docs.…).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from re import Match
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# ---------- config: public API surfaces ----------

# Modules/prefixes to skip from internals (documented on the Public API page)
PUBLIC_API_PREFIXES: tuple[str, ...] = (
    "topmark.api",
    "topmark.registry",
)

# ---------- helpers: docstring symbol reference hygiene ----------

# Fix reference-style links where the reference label accidentally includes backticks.
# Example (bad):   [`topmark.core.keys.ArgKey`][]
# This resolves to a reference label of "`topmark.core.keys.ArgKey`" (with backticks)
# which mkdocs-autorefs will not match.
# Example (good):  [`topmark.core.keys.ArgKey`][topmark.core.keys.ArgKey]
_BACKTICKED_EMPTY_REF_RE: re.Pattern[str] = re.compile(
    r"\[`(?P<sym>[^`]+)`\]\[\]",
)

_BACKTICKED_REF_LABEL_RE: re.Pattern[str] = re.compile(
    r"\[`(?P<sym>[^`]+)`\]\[`(?P=sym)`\]",
)

# Heuristic for Python-like fully-qualified symbol paths.
# We only use this for debug warnings; we don't auto-rewrite these.
_SYMBOL_PATH_RE: re.Pattern[str] = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")

# mdformat sometimes escapes the *outer* brackets of reference-style links so that
# the construct is rendered as literal text, e.g.:
#   \\[`topmark.registry`\\][topmark.registry]
# This breaks mkdocs-autorefs resolution. We normalize these back into real links.
_ESCAPED_REF_LINK_RE: re.Pattern[str] = re.compile(
    r"""
    \\\[(?P<text>[^\]]+?)\\\]    # escaped first bracket pair: \[...\]
    \[(?P<label>[^\]]*?)\]          # reference label: [...]
    """,
    re.VERBOSE,
)


# By default we only enforce links for TopMark's own symbols.
# This avoids false positives like `pyproject.toml`, `README.md`, `tool.topmark`, etc.
_STRICT_SYMBOL_PREFIXES: tuple[str, ...] = ("topmark.",)

# Some references look like TopMark-qualified names but are actually filenames / artifacts,
# not Python symbols that mkdocs-autorefs can resolve.
# Example: `topmark.toml` (a config filename).
_NON_SYMBOL_SUFFIXES: tuple[str, ...] = (
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
)


# ---------- helpers: environment parsing ----------


# Robust boolean environment flag parser
def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment flag.

    We treat these values (case-insensitive) as truthy: "1", "true", "yes", "on".
    These values are falsy: "0", "false", "no", "off", "".

    Args:
        name (str): Environment variable name.
        default (bool): Value used when the variable is not set.

    Returns:
        bool: Parsed boolean.
    """
    raw: str | None = os.environ.get(name)
    if raw is None:
        return default
    val: str = raw.strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off", ""}:  # noqa: SIM103
        return False
    # Any other non-empty value enables the flag.
    return True


def load_nonlinked_symbols(env: Mapping[str, str] | None = None) -> frozenset[str]:
    """Load the exact-match whitelist from the environment.

    The value is read from `TOPMARK_DOCS_NONLINKED_SYMBOLS` as a comma-separated list.

    Args:
        env (Mapping[str, str] | None): Optional environment mapping. Defaults to `os.environ`.

    Returns:
        frozenset[str]: Exact symbol strings that are allowed to remain backticked without linking.
    """
    if env is None:
        env = os.environ

    raw: str = env.get("TOPMARK_DOCS_NONLINKED_SYMBOLS", "")
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


# Symbols that are allowed to appear backticked without linking, even in strict mode.
# Exact matches only (no prefix matching).
NONLINKED_SYMBOLS: frozenset[str] = load_nonlinked_symbols()

# Default maximum number of symbols to show inline in summary logs.
# In debug mode we show all symbols (no truncation).
MAX_INLINE_SYMBOLS: int = 12


def format_inline_symbols(
    symbols: list[str],
    *,
    debug: bool,
    max_inline: int = MAX_INLINE_SYMBOLS,
) -> str:
    """Format a list of symbols for inline summary logging.

    In non-debug mode, the output is truncated to `max_inline` symbols and appends
    "(+N more)" when applicable.

    Args:
        symbols (list[str]): Sorted list of symbol strings.
        debug (bool): When True, do not truncate.
        max_inline (int): Maximum symbols to show inline when `debug` is False.

    Returns:
        str: Comma-separated symbols suitable for logging.
    """
    if not symbols:
        return ""

    if debug is True:
        return ", ".join(symbols)

    shown: list[str] = symbols[:max_inline]
    more: int = max(0, len(symbols) - len(shown))
    msg: str = ", ".join(shown)
    return msg + (f" (+{more} more)" if more else "")


# ---------- helpers: GH Actions shielding ----------

# Fenced code blocks inside docstrings (````` / ~~~) should not be scanned.
_FENCED_BLOCK_RE: re.Pattern[str] = re.compile(
    r"""
    ^([ \t]{0,3})                # optional indent
    (?P<fence>`{3,}|~{3,})       # opening fence
    [^\n]*                       # info string / lang
    \n
    (.*?)                        # content
    ^\1(?P=fence)[ \t]*$         # matching closing fence
    """,
    re.MULTILINE | re.DOTALL | re.VERBOSE,
)

_GHA_MARKER = "${{"


def wrap_actions_blocks_with_raw(markdown: str) -> str:
    """(Harmless) shield fenced blocks containing GitHub Actions expressions.

    With ``mkdocs-simple-hooks`` we do not evaluate Jinja in Markdown, so this is a no-op
    in practice. Kept for clarity and parity with earlier macro-based builds.

    Args:
        markdown (str): Page Markdown as a raw string.

    Returns:
        str: The input Markdown, unchanged except for potential guard wrapping.
    """

    def _repl(m: Match[str]) -> str:
        block: str = m.group(0)
        inner: str | Any = m.group(3)
        # No Jinja in Markdown with simple-hooks, but safe to leave as noop
        return block if _GHA_MARKER not in inner else block

    return _FENCED_BLOCK_RE.sub(_repl, markdown)


# Centralized logic for deciding if a candidate symbol should be enforced for linking.
def should_enforce_link(candidate: str) -> bool:
    """Return True if `candidate` should be required to be linked.

    Enforcement rules:
    - Must look like a Python dotted path (matches `_SYMBOL_PATH_RE`).
    - Must start with one of `_STRICT_SYMBOL_PREFIXES` (defaults to `topmark.`).
    - Must not be on the exact-match `NONLINKED_SYMBOLS` whitelist.
    - Must not look like a filename/artifact (suffix in `_NON_SYMBOL_SUFFIXES`).

    Args:
        candidate (str): Inline-code candidate string.

    Returns:
        bool: True when link enforcement should apply.
    """
    if not candidate:
        return False

    # Only flag Python dotted path (matches `_SYMBOL_PATH_RE`)
    if not _SYMBOL_PATH_RE.match(candidate):
        return False

    # Only flag TopMark symbols (by default). This keeps strict mode focused on
    # API/docstring references and avoids file-name/table-name false positives.
    if not candidate.startswith(_STRICT_SYMBOL_PREFIXES):
        return False

    # Explicitly allow certain symbols to remain backticked without linking.
    if candidate in NONLINKED_SYMBOLS:
        return False

    # Ignore TopMark-qualified filename-like references (e.g. `topmark.toml`).
    cand_lower: str = candidate.lower()
    return not cand_lower.endswith(_NON_SYMBOL_SUFFIXES)


def fix_backticked_reference_links(markdown: str) -> str:
    """Fix reference-style links whose label mistakenly includes backticks.

    This targets patterns like ``[`X`][]`` and ``[`X`][`X`]`` and rewrites them to
    use a plain reference label ``X``.

    Args:
        markdown (str): Markdown fragment (not including fenced code blocks).

    Returns:
        str: Updated Markdown fragment.
    """

    def _repl_empty(m: Match[str]) -> str:
        sym: str = m.group("sym")
        return f"[`{sym}`][{sym}]"

    def _repl_label(m: Match[str]) -> str:
        sym: str = m.group("sym")
        return f"[`{sym}`][{sym}]"

    markdown = _BACKTICKED_EMPTY_REF_RE.sub(_repl_empty, markdown)
    markdown = _BACKTICKED_REF_LABEL_RE.sub(_repl_label, markdown)
    return markdown


def unescape_reference_link_text(markdown: str) -> str:
    r"""Unescape mdformat-escaped reference-style links.

    mdformat can escape the outer bracket pair of a reference-style link (the link text)
    which turns it into literal text and prevents Markdown from forming a link.

    Example (broken):
        \\[`topmark.registry`\\][topmark.registry]

    Normalized (working):
        [`topmark.registry`][topmark.registry]

    This function only targets the specific pattern where the *outer* brackets are
    escaped (``\\[`` and ``\\]``). It does not touch fenced code blocks; callers
    should apply it via `apply_outside_fenced_blocks`.

    Args:
        markdown (str): Markdown fragment (not including fenced code blocks).

    Returns:
        str: Updated Markdown fragment with unescaped reference-style link text.
    """

    def _repl(m: Match[str]) -> str:
        text: str = m.group("text")
        label: str = m.group("label")
        # Preserve empty labels: ``[... ][]``.
        return f"[{text}][{label}]" if label else f"[{text}][]"

    return _ESCAPED_REF_LINK_RE.sub(_repl, markdown)


def find_unlinked_backticked_symbols_with_locations(
    markdown: str,
) -> dict[str, set[int]]:
    """Find unlinked backticked TopMark symbol references and where they occur.

    This is a best-effort debug helper: it scans inline code spans outside of fenced blocks
    and records their 1-based line numbers when they look like fully-qualified Python symbol
    paths and start with one of `_STRICT_SYMBOL_PREFIXES`.

    Args:
        markdown (str): Markdown fragment (not including fenced code blocks).

    Returns:
        dict[str, set[int]]: Mapping from symbol string to a set of 1-based line numbers.

    """
    findings: dict[str, set[int]] = {}

    def _iter_inline_code_spans(fragment: str, fragment_start: int) -> list[tuple[str, int, int]]:
        """Return inline code spans in `text` (CommonMark-style backtick runs).

        Returns tuples of (code_text, abs_start, abs_end) where abs_start/abs_end
        delimit the full span including backticks.
        """
        spans: list[tuple[str, int, int]] = []
        i: int = 0
        n: int = len(fragment)
        while i < n:
            if fragment[i] != "`":
                i += 1
                continue

            # Count opening backticks
            j: int = i
            while j < n and fragment[j] == "`":
                j += 1
            tick_len: int = j - i

            # Find matching closing run of the same length
            k: int = j
            while k < n:
                if fragment[k] != "`":
                    k += 1
                    continue
                k2: int = k
                while k2 < n and fragment[k2] == "`":
                    k2 += 1
                if (k2 - k) == tick_len:
                    code_raw: str = fragment[j:k]
                    code_text: str = code_raw.strip()
                    abs_start: int = fragment_start + i
                    abs_end: int = fragment_start + k2
                    spans.append((code_text, abs_start, abs_end))
                    i = k2
                    break
                # Different-length run; keep searching.
                k = k2
            else:
                # No closing run found.
                i = j
        return spans

    def _scan_fragment(fragment: str, fragment_start: int) -> None:
        for candidate, abs_start, abs_end in _iter_inline_code_spans(fragment, fragment_start):
            # Only enforce link hygiene for candidates that pass the configured rules.
            if not should_enforce_link(candidate):
                continue

            if _is_linked_inline_code(markdown, abs_start, abs_end):
                continue

            line_no: int = markdown.count("\n", 0, abs_start) + 1
            findings.setdefault(candidate, set()).add(line_no)

    # Iterate non-fenced regions with their absolute offsets.
    last_end: int = 0
    for fm in _FENCED_BLOCK_RE.finditer(markdown):
        start, end = fm.span(0)
        if start > last_end:
            _scan_fragment(markdown[last_end:start], last_end)
        last_end = end
    if last_end < len(markdown):
        _scan_fragment(markdown[last_end:], last_end)

    return findings


def _is_linked_inline_code(markdown: str, code_start: int, code_end: int) -> bool:
    """Return True if the backticked code span is used as the *text* of a Markdown link.

    We treat these as already linked:
      - [`sym`][label]
      - [`sym`](url)

    Args:
        markdown (str): Full Markdown string.
        code_start (int): Absolute start index of the backtick (`) opening the code span.
        code_end (int): Absolute end index (exclusive) of the closing backtick.

    Returns:
        bool: True if the code span participates in link syntax.
    """
    # Must be immediately preceded by '[' (optionally with whitespace before '['
    # already handled by caller).
    if code_start <= 0 or markdown[code_start - 1] != "[":
        return False

    # Find the closing ']' that should immediately follow the code span.
    if code_end >= len(markdown) or markdown[code_end] != "]":
        return False

    # After ']' there may be whitespace, then either '(' or '['.
    i: int = code_end + 1
    while i < len(markdown) and markdown[i] in " \t":
        i += 1
    if i >= len(markdown):
        return False

    return markdown[i] in "(["


def apply_outside_fenced_blocks(markdown: str, fn: Callable[[str], str]) -> str:
    """Apply `fn` to non-fenced regions of Markdown.

    This keeps fenced code blocks intact (including their formatting and any
    content that might look like Markdown).

    Args:
        markdown (str): Full page Markdown.
        fn (Callable[[str], str]): Transformation applied to non-fenced fragments.

    Returns:
        str: The transformed Markdown.
    """
    parts: list[str] = []
    last_end: int = 0
    for m in _FENCED_BLOCK_RE.finditer(markdown):
        start, end = m.span(0)
        if start > last_end:
            parts.append(fn(markdown[last_end:start]))
        parts.append(markdown[start:end])
        last_end = end
    if last_end < len(markdown):
        parts.append(fn(markdown[last_end:]))
    return "".join(parts)


def format_line_numbers(lines: set[int] | list[int] | tuple[int, ...]) -> str:
    """Format 1-based line numbers for logging.

    Args:
        lines (set[int] | list[int] | tuple[int, ...]): Collection of 1-based line numbers.

    Returns:
        str: "line 71" for a single line, "lines 57, 61, 117" for multiple.
            Returns "(unknown line)" if empty.
    """
    if not lines:
        return "(unknown line)"

    nums: list[int] = sorted(lines)
    if len(nums) == 1:
        return f"line {nums[0]}"
    return "lines " + ", ".join(str(n) for n in nums)


def strip_repo_prefix(path: str, root: Literal["docs", "src"]) -> str:
    """Remove a leading `{root}/` prefix from `path` if present.

    Args:
        path (str): A repo-relative path that may already include a `docs/` or `src/` prefix.
        root (Literal["docs", "src"]): The expected prefix root.

    Returns:
        str: The path without the prefix.
    """
    prefix = f"{root}/"
    return path[len(prefix) :] if path.startswith(prefix) else path


def format_repo_path(rel_path: str | None, *, root: Literal["docs", "src"]) -> str:
    """Format a stable local repo path for logging.

    Args:
        rel_path (str | None): Path relative to the repo root (e.g. `dev/api-stability.md` or
            `topmark/api/public_types.py`). If None/empty, returns `<unknown>`.
        root (Literal["docs", "src"]): The repo folder prefix to apply.

    Returns:
        str: A normalized local path like `docs/dev/api-stability.md` or
            `src/topmark/api/public_types.py`.

    Notes:
        If `rel_path` is already prefixed with `{root}/`, it is returned as-is.
    """
    if not rel_path:
        return "<unknown>"

    prefix = f"{root}/"
    return rel_path if rel_path.startswith(prefix) else f"{prefix}{rel_path}"


# ---------- helpers: context lines for logging ----------


def context_lines(
    *,
    edit_url: str | None = None,
    rendered_on: str | None = None,
    source_file: str | None = None,
) -> list[str]:
    """Build optional context lines for logs.

    Callers can log these lines (typically at INFO level) when debugging.

    Args:
        edit_url (str | None): Optional edit URL MkDocs provides.
        rendered_on (str | None): Optional docs-relative path indicating where something
            is rendered.
        source_file (str | None): Optional local repo path to the originating file (e.g.
            `src/topmark/api/public_types.py`).

    Returns:
        list[str]: A list of human-readable context lines.
    """
    out: list[str] = []
    if edit_url:
        out.append(f"Edit URL (context): {edit_url}")
    if rendered_on:
        out.append(f"Rendered on (context): {rendered_on}")
    if source_file:
        out.append(f"Source file (context): {source_file}")
    return out


# ---------- helpers: docs link helpers ----------


def rel_href(from_doc: str, to_doc: str) -> str:
    """Compute a POSIX relative href from one docs file to another.

    Args:
        from_doc (str): Docs-relative source path (e.g. `dev/architecture.md`).
        to_doc (str): Docs-relative target path.

    Returns:
        str: A POSIX-style relative href (slashes), suitable for Markdown links.
    """
    from_dir: str = str(Path(from_doc).parent) or "."
    rel: str = os.path.relpath(to_doc, start=from_dir)
    return rel.replace(os.sep, "/")


def public_ref_doc_for_symbol(sym: str) -> str | None:
    """Return the public reference doc for a symbol, if it belongs to a public surface.

    Uses `PUBLIC_API_PREFIXES` and the convention that public reference pages live under
    `api/reference/<module>.md`.

    Args:
        sym (str): Fully-qualified symbol name.

    Returns:
        str | None: Docs-relative reference page path when the symbol is under a public
            surface; otherwise None.
    """
    for prefix in PUBLIC_API_PREFIXES:
        if sym == prefix or sym.startswith(prefix + "."):
            return f"api/reference/{prefix}.md"
    return None


# ---------- exported symbols ----------


__all__ = [
    "MAX_INLINE_SYMBOLS",
    "NONLINKED_SYMBOLS",
    "PUBLIC_API_PREFIXES",
    "apply_outside_fenced_blocks",
    "context_lines",
    "env_flag",
    "find_unlinked_backticked_symbols_with_locations",
    "fix_backticked_reference_links",
    "format_inline_symbols",
    "format_line_numbers",
    "format_repo_path",
    "load_nonlinked_symbols",
    "public_ref_doc_for_symbol",
    "rel_href",
    "should_enforce_link",
    "strip_repo_prefix",
    "unescape_reference_link_text",
    "wrap_actions_blocks_with_raw",
]

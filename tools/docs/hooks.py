# topmark:header:start
#
#   project      : TopMark
#   file         : hooks.py
#   file_relpath : tools/docs/hooks.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""MkDocs simple-hooks for TopMark documentation.

This module provides small, deterministic Markdown transformations that run during the
MkDocs build. It intentionally avoids Jinja templating and focuses on several tasks:

1) **Version token substitution** (``%%TOPMARK_VERSION%%``) using the installed
   TopMark distribution version (with a fall-back to reading pyproject in a helper),
   captured once in `pre_build`.
2) **GitHub-style callouts** conversion (``> [!NOTE] ...`` etc.) into Material for
   MkDocs admonitions, implemented in `on_page_markdown`. The conversion also
   de-quotes the title when the first body line is a bold heading (``**Title**``).
3) **Fixing Markdown reference-style links** whose reference label incorrectly includes
   backticks (e.g., ``[`topmark.core.keys.ArgKey`][]``), so that mkdocs-autorefs can
   resolve them.
4) (Optionally, when `TOPMARK_DOCS_DEBUG` is set) **logging unlinked backticked symbol
   references** (inline code spans that look like Python symbol paths but are not linked).
   When `TOPMARK_DOCS_STRICT_REFS` is set, the build fails if any such unlinked `topmark.*`
   references are found, enforcing reference hygiene. Debug logs are emitted when
   `TOPMARK_DOCS_DEBUG` is set.

In addition, `on_page_markdown` includes a harmless guard that leaves fenced code
blocks containing GitHub Actions expressions (``${{ ... }}``) untouched. With
``mkdocs-simple-hooks`` we do not run Jinja in Markdown, so this is effectively a no-op,
but it documents intent and keeps parity with earlier macro-based approaches.

The transformations are designed to work both for content authored directly in Markdown
files and for content brought in via snippet inclusion (e.g., include-markdown plugin),
as long as the wrapper allows Markdown rendering (``<div markdown="1"> … </div>``).
"""

from __future__ import annotations

import contextlib
import re
from importlib.metadata import version as get_version
from pathlib import Path
from re import Match
from typing import Any, Final

import tomlkit
from mkdocs.plugins import get_plugin_logger as get_logger

# Use absolute module reference (MkDocs):
from tools.docs.docs_utils import (
    NONLINKED_SYMBOLS,
    apply_outside_fenced_blocks,
    context_lines,
    env_flag,
    find_unlinked_backticked_symbols_with_locations,
    fix_backticked_reference_links,
    format_inline_symbols,
    format_line_numbers,
    format_repo_path,
    public_ref_doc_for_symbol,
    rel_href,
    unescape_reference_link_text,
    wrap_actions_blocks_with_raw,
)

# NOTE: This hook intentionally depends on TopMark internals so that
# documentation reflects the exact config semantics used by the tool.
from topmark.config.io import (
    as_toml_table,
    get_string_value_or_none,
    get_table_value,
)

logger = get_logger("hooks")

# Generate debug logging
# Also enables extra debug checks during the docs build.
TOPMARK_DOCS_DEBUG: bool = env_flag("TOPMARK_DOCS_DEBUG", default=False)
if TOPMARK_DOCS_DEBUG is True:
    logger.info("Debug logging enabled (TOPMARK_DOCS_DEBUG resolves to True)")

# Fail the docs build when unlinked backticked symbol references are found.
# Useful with `mkdocs build --strict` to enforce reference hygiene.
TOPMARK_DOCS_STRICT_REFS: bool = env_flag("TOPMARK_DOCS_STRICT_REFS", default=False)
if TOPMARK_DOCS_STRICT_REFS is True:
    logger.info(
        "Strict symbol reference checking enabled (TOPMARK_DOCS_STRICT_REFS resolves to True)"
    )


def _page_location(page: Any) -> tuple[str, str | None]:
    """Return stable identifiers for a page for logging.

    MkDocs pages are often generated or transformed during the build. For actionable
    diagnostics, we prefer a stable *source* path (``page.file.src_path``). This
    path is always relative to MkDocs' ``docs_dir``.

    We also optionally surface the resolved edit URL (``page.edit_url``) when available.

    Notes:
        - The returned local path is prefixed with ``docs/`` so it is directly actionable
          in a local checkout.
        - For findings originating from source code (e.g. docstrings), loggers should
          use `_local_repo_path(<src-relative>, "src")` explicitly (Option A), rather
          than overloading the page location.

    Args:
        page: MkDocs page object.

    Returns:
        Tuple `(local_docs_path, edit_url)` where:
            - `local_docs_path` is the local docs path (e.g. "docs/dev/api-stability.md")
              or "<unknown>".
            - `edit_url` is the resolved edit link if MkDocs provides it, else None.
    """
    page_path: str | None = getattr(getattr(page, "file", None), "src_path", None)
    local_path: str = format_repo_path(page_path, root="docs")
    edit_url: str | None = getattr(page, "edit_url", None)
    return local_path, edit_url


# Accumulate missing-reference findings across all pages so we can report them once.
# When TOPMARK_DOCS_STRICT_REFS is enabled, we record findings during page processing
# and raise a single aggregated error in `post_build()`.
_UNLINKED_SYMBOL_FINDINGS: list[
    tuple[str, list[str]]
] = []  # (page_path, "sym @ line(s) ..." entries)

# ---------- pre_build: capture version once ----------

# Module-level variable to store the version, accessible by all functions in this module.
topmark_version_id: str = "dev"

VERSION_NOT_FOUND: Final[str] = "(version not found in pyproject.toml)"


def get_version_from_toml() -> str:
    """Read the TopMark version directly from the repository's pyproject.toml.

    This is used by documentation builds when the package version cannot be
    determined from the installed distribution metadata.

    NOTE: if dropping support for Python 3.10, we can use `tomllib` directly.
    """
    # Assumes pyproject.toml is in the project root relative to where the script is run
    toml_path: Path = Path(__file__).resolve().parents[3] / "pyproject.toml"

    # tomlkit.parse expects TOML text, not a Path
    toml_text: str = toml_path.read_text(encoding="utf-8")
    data: tomlkit.TOMLDocument = tomlkit.parse(toml_text)
    data_any: dict[str, Any] = data.unwrap()
    data_tbl: dict[str, Any] | None = as_toml_table(data_any)

    if not data_tbl:
        return VERSION_NOT_FOUND

    project_table: dict[str, Any] = get_table_value(data_tbl, "project")
    if not project_table:
        return VERSION_NOT_FOUND

    ver: str | None = get_string_value_or_none(project_table, "version")
    if not ver:
        return VERSION_NOT_FOUND

    logger.info("Version from pyproject.toml: %s", ver)
    return ver


def pre_build(config: dict[str, Any], **kwargs: Any) -> dict[str, Any] | None:
    """Capture the TopMark version once before any page is processed.

    This function attempts to retrieve the installed TopMark package version using
    `importlib.metadata.version` and stores it in the module-level global
    variable ``topmark_version_id``. This ensures the correct version token can be
    substituted in all pages via the `on_page_markdown` hook.

    Args:
        config: The MkDocs config dictionary. While this hook function doesn't modify the config
            directly to store the version (it uses a global variable instead), it must be passed
            by the MkDocs hook system.
        **kwargs: Additional keyword arguments passed by the MkDocs hook system (e.g., ``files``,
            ``site_dir``, etc.). Currently unused.

    Returns:
        The modified config dictionary. We return the original ``config`` object to satisfy the
        MkDocs hook API, although it has not been modified within this function.
    """
    global topmark_version_id  # MUST declare global intent to WRITE

    with contextlib.suppress(Exception):
        # This will set the actual version (e.g., "0.9.0rc1" or "dev")
        topmark_version_id = get_version("topmark")

    # If the package isn't installed, it keeps the default "dev"

    # Reset per-build state.
    _UNLINKED_SYMBOL_FINDINGS.clear()

    return config


GH_CALLOUT_RE: re.Pattern[str] = re.compile(
    r"""
    ^> \s* \[!(?P<kind>NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]    # tag
    (?: \s+ (?P<title_inline>.+?) )?                            # optional inline title
    \s* \n
    (?P<body>(?:^>.*\n?)*)                                      # subsequent '>' lines
    """,
    re.MULTILINE | re.VERBOSE,
)


def _strip_blockquote_prefix(text: str) -> list[str]:
    """Remove a single leading ``>`` (and an optional following space) from lines.

    Args:
        text: Blockquoted text (each line may begin with ``>``).

    Returns:
        Lines with one leading blockquote marker removed where present.
    """
    out: list[str] = []
    ln: str
    for ln in text.splitlines():
        if ln.startswith(">"):
            ln = ln[1:]
            if ln.startswith(" "):
                ln = ln[1:]
        out.append(ln.rstrip())
    return out


def _extract_title(lines: list[str], inline_title: str | None, kind: str) -> tuple[str, list[str]]:
    """Select a callout title from inline text or first bold body line.

    If an inline title exists (on the same line as ``[!KIND]``), it is used. Otherwise,
    the first non-empty body line is inspected and, when wrapped in ``**..**`` or
    ``__..__``, it is used as the title (without the bold markers). If neither applies,
    a humanized version of ``kind`` is returned.

    Args:
        lines: Body lines (already stripped from ``>``).
        inline_title: Optional inline title text.
        kind: Callout kind: ``NOTE``, ``TIP``, ``IMPORTANT``, ``WARNING``, ``CAUTION``.

    Returns:
        A pair ``(title, remaining_lines)`` where the title is plain text (no surrounding bold
        markers) and ``remaining_lines`` contains the body lines without the consumed title line
        (if any).
    """

    def _clean_title(raw: str) -> str:
        raw = raw.strip()
        # remove wrapping ** or __ if they fully enclose the title
        if (raw.startswith("**") and raw.endswith("**")) or (
            raw.startswith("__") and raw.endswith("__")
        ):
            raw = raw[2:-2].strip()
        return raw

    if inline_title:
        return _clean_title(inline_title), lines

    # find first non-empty line; if it's bold, use as title
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and (
        (lines[0].startswith("**") and lines[0].endswith("**"))
        or (lines[0].startswith("__") and lines[0].endswith("__"))
    ):
        title = _clean_title(lines.pop(0))
        return title, lines

    return kind.title(), lines


def _render_admonition(kind: str, title: str, inner_markdown: str) -> str:
    """Render a Material admonition block as raw HTML with nested Markdown support.

    Args:
        kind: Callout type; used as CSS class (lowercased).
        title: Title text (plain; the theme already bolds it).
        inner_markdown: Body content to be parsed as Markdown.

    Returns:
        HTML string representing the admonition block.
    """
    return (
        f'<div class="admonition {kind.lower()}" markdown="1">\n'
        f'  <p class="admonition-title">{title}</p>\n'
        f"{inner_markdown}\n"
        f"</div>\n"
    )


if TOPMARK_DOCS_DEBUG and NONLINKED_SYMBOLS:
    logger.info(
        "Non-linked symbol whitelist enabled (%d): %s",
        len(NONLINKED_SYMBOLS),
        ", ".join(sorted(NONLINKED_SYMBOLS)),
    )


# ---------- page_markdown: do transformations ----------


def on_page_markdown(
    markdown: str,
    page: Any,
    config: dict[str, Any],
    files: Any,
) -> str:
    """Transform Markdown for each page before Markdown extensions run.

    The transformation pipeline performs:

    1. Version token substitution (``%%TOPMARK_VERSION%%``) from ``config['extra']``.
    2. A harmless guard for GitHub Actions expressions in fenced blocks (no-op here).
    3. Conversion of GitHub-style callouts into Material admonition blocks.
    4. Fix backticked reference-style link labels (outside fenced blocks)
    5. (Debug only) Log unlinked backticked symbol references

    Args:
        markdown: Page Markdown text.
        page: MkDocs page object (unused).
        config: MkDocs config; ``extra.topmark_version`` may be read.
        files: MkDocs files collection (unused).

    Returns:
        The transformed Markdown string.
    """
    # 0) Replace version tokens
    global topmark_version_id  # MUST declare global intent to READ
    markdown = markdown.replace("%%TOPMARK_VERSION%%", str(topmark_version_id))

    # 1) Shield GH Actions blocks (noop for simple-hooks)
    markdown = wrap_actions_blocks_with_raw(markdown)

    # 2) Convert GH-style callouts to Material admonitions
    def _replace(m: Match[str]) -> str:
        kind: str = m.group("kind")
        inline_title: str | None = m.group("title_inline")
        body_raw: str = m.group("body") or ""
        body_lines: list[str] = _strip_blockquote_prefix(body_raw)
        title: str
        remaining: list[str]
        title, remaining = _extract_title(body_lines, inline_title, kind)
        inner_markdown: str = "\n".join(remaining).strip("\n")
        return _render_admonition(kind, title, inner_markdown)

    markdown = GH_CALLOUT_RE.sub(_replace, markdown)

    # 3) Unescape reference-style links that mdformat renders as literal text.
    #
    # mdformat may escape the outer link brackets like:
    #   \\[`sym`\\][topmark.sym]
    # which renders as literal text and prevents mkdocs-autorefs from resolving.
    # We normalize these back to real reference-style links before any further
    # reference hygiene steps.
    markdown = apply_outside_fenced_blocks(markdown, unescape_reference_link_text)

    # 4) Fix reference labels that accidentally include backticks.
    markdown = apply_outside_fenced_blocks(markdown, fix_backticked_reference_links)

    # 5) Debug and/or strict: report or fail on backticked symbols that aren't linked.
    if TOPMARK_DOCS_DEBUG is True or TOPMARK_DOCS_STRICT_REFS is True:
        findings_by_symbol: dict[str, set[int]] = find_unlinked_backticked_symbols_with_locations(
            markdown
        )

        if findings_by_symbol:
            page_path, edit_link = _page_location(page)

            symbols_sorted: list[str] = sorted(findings_by_symbol)

            # Keep logs readable in non-debug mode; show all symbols in debug mode.
            inline_msg: str = format_inline_symbols(
                symbols_sorted,
                debug=TOPMARK_DOCS_DEBUG is True,
            )

            if TOPMARK_DOCS_DEBUG is True:
                logger.debug(
                    "%s - Found %d unlinked backticked TopMark symbol reference(s): %s",
                    page_path,
                    len(symbols_sorted),
                    inline_msg,
                )

            # In strict mode, emit a clear error line (without stopping at the first page).
            if TOPMARK_DOCS_STRICT_REFS is True:
                logger.error(
                    "%s - Unlinked backticked TopMark symbol reference(s): %s",
                    page_path,
                    inline_msg,
                )

            # The docs source path is the actionable location for local edits.
            # The edit URL is optional context (often GitHub) and is only logged in debug mode.
            if TOPMARK_DOCS_DEBUG is True:
                for line in context_lines(edit_url=edit_link, rendered_on=None):
                    logger.info("%s - %s", page_path, line)

            # Emit actionable details (line numbers + recommended fix) at WARNING level
            # so they show up even without debug.
            from_doc: str = getattr(getattr(page, "file", None), "src_path", "<unknown>")

            for seq, sym in enumerate(symbols_sorted, start=1):
                logger.warning(
                    "%s - [%d] (%s) %s — Fix: [`%s`][%s]",
                    page_path,
                    seq,
                    format_line_numbers(findings_by_symbol[sym]),
                    sym,
                    sym,
                    sym,
                )

                if TOPMARK_DOCS_DEBUG is True:
                    ref_doc: str | None = public_ref_doc_for_symbol(sym)
                    if ref_doc is not None and from_doc != "<unknown>":
                        href: str = rel_href(from_doc, ref_doc)
                        logger.info(
                            "%s - Alt: [`%s`](%s#%s)",
                            page_path,
                            sym,
                            href,
                            sym,
                        )

            if TOPMARK_DOCS_STRICT_REFS is True:
                # Record full set for post-build aggregation; do not stop at the first page.
                _UNLINKED_SYMBOL_FINDINGS.append(
                    (
                        page_path,
                        [
                            f"{s} ({format_line_numbers(findings_by_symbol[s])})"
                            for s in symbols_sorted
                        ],
                    )
                )

    return markdown


# ---------- post_build: aggregate strict ref hygiene errors ----------


def post_build(config: dict[str, Any], **kwargs: Any) -> dict[str, Any] | None:
    """Fail the build after processing all pages when strict ref hygiene is enabled.

    When `TOPMARK_DOCS_STRICT_REFS` is set, `on_page_markdown` records any pages that
    contain unlinked backticked symbol references. This hook aggregates those
    findings and raises one error at the end of the build, so users see the full
    list instead of stopping at the first page.

    Args:
        config: The MkDocs config dictionary.
        **kwargs: Additional keyword arguments passed by the MkDocs hook system.

    Returns:
        The config dictionary (unchanged).

    Raises:
        Abort: If strict refs are enabled and any pages contained unlinked backticked
            symbol references.
        RuntimeError: If `Abort` cannot be imported.
    """
    if TOPMARK_DOCS_STRICT_REFS is not True:
        return config

    if not _UNLINKED_SYMBOL_FINDINGS:
        return config

    pages: set[str] = {page_path for (page_path, _syms) in _UNLINKED_SYMBOL_FINDINGS}
    total_refs: int = sum(len(syms) for (_page_path, syms) in _UNLINKED_SYMBOL_FINDINGS)
    message: str = (
        f"Found {total_refs} unlinked backticked symbol reference(s) "
        f"across {len(pages)} page(s) (TOPMARK_DOCS_STRICT_REFS={TOPMARK_DOCS_STRICT_REFS!r}).\n"
        "See error/warning output above for file/line details.\n"
        "Set TOPMARK_DOCS_STRICT_REFS=0 to disable strict mode."
    )

    # Prefer MkDocs' Abort exception to stop the build with a clean error message
    # (without a full traceback). Fall back to RuntimeError only if Abort cannot be imported.
    try:
        from mkdocs.exceptions import Abort
    except ImportError as err:
        raise RuntimeError(message) from err

    raise Abort(message)

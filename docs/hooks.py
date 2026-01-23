# topmark:header:start
#
#   project      : TopMark
#   file         : hooks.py
#   file_relpath : docs/hooks.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""MkDocs simple-hooks for TopMark documentation.

This module provides small, deterministic Markdown transformations that run during the
MkDocs build. It intentionally avoids Jinja templating and focuses on two tasks:

1) **Version token substitution** (``%%TOPMARK_VERSION%%``) using the installed
   TopMark distribution version, captured once in `pre_build`.
2) **GitHub-style callouts** conversion (``> [!NOTE] ...`` etc.) into Material for
   MkDocs admonitions, implemented in `on_page_markdown`. The conversion also
   de-quotes the title when the first body line is a bold heading (``**Title**``).

In addition, `on_page_markdown` includes a harmless guard that leaves fenced code
blocks containing GitHub Actions expressions (``${{ ... }}``) untouched. With
``mkdocs-simple-hooks`` we do not run Jinja in Markdown, so this is effectively a no-op,
but it documents intent and keeps parity with earlier macro-based approaches.

The transformations are designed to work both for content authored directly in Markdown
files and for content brought in via snippet inclusion (e.g., include-markdown plugin),
as long as the wrapper allows Markdown rendering (``<div markdown="1"> … </div>``).
"""

from __future__ import annotations

import logging
import re
from importlib.metadata import version as get_version
from pathlib import Path
from re import Match
from typing import Any, Final

import tomlkit

# NOTE: This hook intentionally depends on TopMark internals so that
# documentation reflects the exact config semantics used by the tool.
from topmark.config.io import (
    as_toml_table,
    get_string_value_or_none,
    get_table_value,
)

logger: logging.Logger = logging.getLogger(__name__)

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
        config (dict[str, Any]): The MkDocs config dictionary. While this hook
            function doesn't modify the config directly to store the version (it
            uses a global variable instead), it must be passed by the MkDocs hook
            system.
        **kwargs (Any): Additional keyword arguments passed by the MkDocs hook system
            (e.g., ``files``, ``site_dir``, etc.). Currently unused.

    Returns:
        dict[str, Any] | None: The modified config dictionary. We return the original
        ``config`` object to satisfy the MkDocs hook API, although it has not been
        modified within this function.
    """
    global topmark_version_id  # MUST declare global intent to WRITE

    try:
        # This will set the actual version (e.g., "0.9.0rc1" or "dev")
        topmark_version_id = get_version("topmark")
    except Exception:
        # If the package isn't installed, it keeps the default "dev"
        pass

    return config


# ---------- helpers: GH Actions shielding & GH callouts ----------

FENCED_BLOCK_RE: re.Pattern[str] = re.compile(
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


def _wrap_actions_blocks_with_raw(markdown: str) -> str:
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

    return FENCED_BLOCK_RE.sub(_repl, markdown)


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
        text (str): Blockquoted text (each line may begin with ``>``).

    Returns:
        list[str]: Lines with one leading blockquote marker removed where present.
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
        lines (list[str]): Body lines (already stripped from ``>``).
        inline_title (str | None): Optional inline title text.
        kind (str): Callout kind: ``NOTE``, ``TIP``, ``IMPORTANT``, ``WARNING``, ``CAUTION``.

    Returns:
        tuple[str, list[str]]: A pair ``(title, remaining_lines)`` where the title is
        plain text (no surrounding bold markers) and ``remaining_lines`` contains the
        body lines without the consumed title line (if any).
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
        kind (str): Callout type; used as CSS class (lowercased).
        title (str): Title text (plain; the theme already bolds it).
        inner_markdown (str): Body content to be parsed as Markdown.

    Returns:
        str: HTML string representing the admonition block.
    """
    return (
        f'<div class="admonition {kind.lower()}" markdown="1">\n'
        f'  <p class="admonition-title">{title}</p>\n'
        f"{inner_markdown}\n"
        f"</div>\n"
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

    Args:
        markdown (str): Page Markdown text.
        page (Any): MkDocs page object (unused).
        config (dict[str, Any]): MkDocs config; ``extra.topmark_version`` may be read.
        files (Any): MkDocs files collection (unused).

    Returns:
        str: The transformed Markdown string.
    """
    # 0) Replace version tokens
    global topmark_version_id  # MUST declare global intent to READ
    markdown = markdown.replace("%%TOPMARK_VERSION%%", str(topmark_version_id))

    # 1) Shield GH Actions blocks (noop for simple-hooks)
    markdown = _wrap_actions_blocks_with_raw(markdown)

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

    return GH_CALLOUT_RE.sub(_replace, markdown)

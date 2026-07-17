# topmark:header:start
#
#   project      : TopMark
#   file         : surgery.py
#   file_relpath : src/topmark/toml/surgery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Structural TOML document edits using tomlkit.

This module provides helpers that operate on a TOML document (validated via
`tomlkit`) for structural edits such as:

- nesting an existing TopMark TOML document under a dotted section path (for
  example under `tool.topmark` for `pyproject.toml` output)
- setting or removing the `root` discovery flag structurally

Design intent:
- use TOML-aware validation before rewriting document structure
- preserve comments and presentation layout as much as practical for human-
  facing output
- keep generic TOML document surgery separate from annotated template editing

Notes:
- These helpers are intended for structural manipulation of TopMark TOML
  documents.
- For presentation-preserving edits of the bundled example TopMark TOML
  resource (`topmark-example.toml`), prefer the text-based helpers in
  [`topmark.toml.template_surgery`][topmark.toml.template_surgery].
"""

from __future__ import annotations

import re
from typing import cast

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError
from tomlkit.items import Item
from tomlkit.items import Table

from topmark.core.errors import TomlParseError
from topmark.core.errors import TomlSurgeryError

# --- Lossless TOML AST surgery (tomlkit structure-preserving) ---


def set_root_flag(toml_text: str, *, for_pyproject: bool, root: bool) -> str:
    """Set or remove the `root` flag in a TOML document.

    - For a plain TopMark TOML document: sets `[config].root = true` (or
      removes it when false).
    - For `pyproject.toml`: sets `tool.topmark.config.root`.

    Args:
        toml_text: TOML document text.
        for_pyproject: Whether the document is (or will be) a pyproject-style
            document (i.e. root lives at `tool.topmark.config.root`).
        root: Whether to enable the root flag.

    Returns:
        Updated TOML document text.

    Raises:
        TomlParseError: If the TOML document cannot be parsed.
        TomlSurgeryError: If an existing `tool`, `tool.topmark`, or `config` key
            exists but is not a table where a table is required.
    """
    try:
        doc: tomlkit.TOMLDocument = tomlkit.parse(toml_text)
    except TomlkitParseError as exc:
        raise TomlParseError(message=f"Error parsing TOML document: {exc}") from exc

    if for_pyproject:
        tool_item: Item | None
        if "tool" in doc:  # noqa: SIM108
            tool_item = cast("Item", doc["tool"])
        else:
            tool_item = None

        if tool_item is None:
            tool_tbl: Table = tomlkit.table()
            doc["tool"] = tool_tbl
        elif isinstance(tool_item, Table):
            tool_tbl = tool_item
        else:
            raise TomlSurgeryError(
                message="Cannot set tool.topmark.config.root: 'tool' exists but is not a TOML table"
            )

        topmark_item: Item | None
        if "topmark" in tool_tbl:  # noqa: SIM108
            topmark_item = tool_tbl["topmark"]
        else:
            topmark_item = None

        if topmark_item is None:
            topmark_tbl: Table = tomlkit.table()
            tool_tbl["topmark"] = topmark_tbl
        elif isinstance(topmark_item, Table):
            topmark_tbl = topmark_item
        else:
            raise TomlSurgeryError(
                message="Cannot set tool.topmark.config.root: "
                "'tool.topmark' exists but is not a TOML table"
            )

        config_item: Item | None
        if "config" in topmark_tbl:  # noqa: SIM108
            config_item = topmark_tbl["config"]
        else:
            config_item = None

        if config_item is None:
            config_tbl: Table = tomlkit.table()
            topmark_tbl["config"] = config_tbl
        elif isinstance(config_item, Table):
            config_tbl = config_item
        else:
            raise TomlSurgeryError(
                message="Cannot set tool.topmark.config.root: "
                "'tool.topmark.config' exists but is not a TOML table"
            )

        if "root" in topmark_tbl:
            del topmark_tbl["root"]

        if root:
            config_tbl["root"] = True
        else:
            if "root" in config_tbl:
                del config_tbl["root"]
    else:
        config_item: Item | None
        if "config" in doc:  # noqa: SIM108
            config_item = cast("Item", doc["config"])
        else:
            config_item = None

        if config_item is None:
            config_tbl = tomlkit.table()
            doc["config"] = config_tbl
        elif isinstance(config_item, Table):
            config_tbl = config_item
        else:
            raise TomlSurgeryError(
                message="Cannot set config.root: 'config' exists but is not a TOML table"
            )

        if "root" in doc:
            del doc["root"]

        if root:
            config_tbl["root"] = True
        else:
            if "root" in config_tbl:
                del config_tbl["root"]

    return doc.as_string()


def nest_toml_under_section(
    toml_doc: str,
    section_keys: str,
) -> str:
    r"""Return a new TOML document nested under a dotted section path.

    This helper validates the TOML document with `tomlkit`, then preserves
    presentation-oriented text layout while wrapping the document under a
    dotted section path, for example:

        nest_toml_under_section("a = 1\n", "tool.topmark")

    yields a document equivalent to:

        [tool.topmark]
        a = 1

    Comments/whitespace are preserved by keeping the original document text and
    rewriting only the wrapper header plus real table-header lines. Leading
    preamble comments/blank lines and the full keyed body text are preserved.

    Args:
        toml_doc: Original TOML document to nest.
        section_keys: Dotted section path such as ``"tool.topmark"``.
            Empty segments (e.g., ``"tool..topmark"``) are not allowed.

    Returns:
        A new TOML document where the original keyed content lives under the
        final section table (for example `[tool.topmark]`).

    Raises:
        ValueError: If `section_keys` is empty, dot-only, or contains an empty segment.
        TomlParseError: If the TOML document cannot be parsed.
        TomlSurgeryError: If structural nesting invariants are violated while
            checking or applying the requested wrapper path.
    """
    try:
        # 1. Parse the existing document losslessly
        doc: tomlkit.TOMLDocument = tomlkit.parse(toml_doc)
    except TomlkitParseError as exc:
        raise TomlParseError(message=f"Error parsing TOML document: {exc}") from exc

    # 2. Split and validate the section path.

    keys: list[str] = section_keys.split(".")
    if not keys or any(not key for key in keys):
        raise ValueError(
            "section_keys must contain at least one non-empty component and no empty components"
        )

    # 3. Idempotency guard: if the document already represents exactly the
    # requested wrapper, do not wrap again.
    def _container_keys(container: tomlkit.TOMLDocument | Table) -> list[str]:
        """Return keys from a successfully parsed tomlkit mapping container."""
        # TOMLDocument and Table both implement the supported mapping API.
        return [str(key) for key in container]

    def _only_keyed_table_at_level(container: tomlkit.TOMLDocument | Table, expected: str) -> bool:
        keys_list: list[str] = _container_keys(container)
        if len(keys_list) != 1:
            return False
        if keys_list[0] != expected:
            return False
        # Iteration just established that this supported mapping contains the key.
        return isinstance(container[expected], Table)

    already_nested: bool = True
    cur: tomlkit.TOMLDocument | Table = doc
    for k in keys:
        if not _only_keyed_table_at_level(cur, k):
            already_nested = False
            break
        # `_only_keyed_table_at_level` established this supported tomlkit invariant.
        cur = cast("Table", cur[k])

    if already_nested:
        return doc.as_string()

    # 4. Rebuild the document text losslessly enough for config-init style
    # usage: preserve the preamble before the first keyed entry, then inject the
    # wrapper header and prefix all real table headers with the dotted path.
    lines: list[str] = toml_doc.splitlines(keepends=True)
    newline: str = "\r\n" if "\r\n" in toml_doc else "\n"
    original_has_final_newline: bool = toml_doc.endswith(("\n", "\r"))

    def _is_comment_or_blank(line: str) -> bool:
        stripped: str = line.lstrip()
        return stripped == "" or stripped.startswith("#")

    header_re: re.Pattern[str] = re.compile(r"^(\s*)(\[\[?)([^\[\]]+?)(\]\]?)(\s*(?:#.*)?)$")

    def _prefix_header_line(line: str) -> str:
        no_newline: str = line.removesuffix("\n").removesuffix("\r")
        line_ending: str = line[len(no_newline) :]
        match: re.Match[str] | None = header_re.match(no_newline)
        if match is None:
            return line

        indent, opener, name, closer, suffix = match.groups()
        qualified_name: str = f"{section_keys}.{name.strip()}"
        return f"{indent}{opener}{qualified_name}{closer}{suffix}{line_ending}"

    first_keyed_idx: int = len(lines)
    for i, line in enumerate(lines):
        if not _is_comment_or_blank(line):
            first_keyed_idx = i
            break

    preamble_lines: list[str] = lines[:first_keyed_idx]
    body_lines: list[str] = lines[first_keyed_idx:]

    wrapped_body_lines: list[str] = []
    multiline_delimiter: str | None = None
    for line in body_lines:
        stripped: str = line.lstrip()
        delimiter_count: int = 0
        if multiline_delimiter is not None:
            delimiter_count = line.count(multiline_delimiter)
            wrapped_body_lines.append(line)
            if delimiter_count % 2 == 1:
                multiline_delimiter = None
            continue

        if stripped.startswith("[") and not stripped.startswith("#"):
            wrapped_body_lines.append(_prefix_header_line(line))
        else:
            wrapped_body_lines.append(line)

        # TOML multiline strings are the only valid context where a physical
        # line resembling a table header is not a header.
        if not stripped.startswith("#"):
            for delimiter in ('"""', "'''"):
                if line.count(delimiter) % 2 == 1:
                    multiline_delimiter = delimiter
                    break

    has_content: bool = bool(lines)
    wrapper_header: str = f"[{section_keys}]"
    if has_content or original_has_final_newline:
        wrapper_header += newline
    wrapper_gap: str = newline if preamble_lines and preamble_lines[0].strip() != "" else ""

    result: str = "".join([wrapper_header, wrapper_gap, *preamble_lines, *wrapped_body_lines])
    if result and not original_has_final_newline:
        result = result.removesuffix("\n").removesuffix("\r")

    try:
        tomlkit.parse(result)
    except TomlkitParseError as exc:
        raise TomlSurgeryError(
            message=f"Cannot nest TOML document under [{section_keys}]: {exc}"
        ) from exc
    return result

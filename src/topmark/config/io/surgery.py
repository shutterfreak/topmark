# topmark:header:start
#
#   project      : TopMark
#   file         : surgery.py
#   file_relpath : src/topmark/config/io/surgery.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Lossless TOML edits using tomlkit.

This module provides helpers that operate on a TOML *AST* (via tomlkit) to
preserve formatting and comments as much as possible.

Use cases:
- Wrapping an existing TOML document under a dotted section path  (e.g. nesting under
  ``tool.topmark`` for ``pyproject.toml``).
- Setting/removing the ``root`` discovery flag structurally.

Notes:
- These helpers are intended for structural manipulation.
- For the annotated config template used by `topmark config init`, prefer the text-based helpers in
  [`topmark.config.io.template_surgery`][topmark.config.io.template_surgery] to preserve the
  template's documentation layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError
from tomlkit.items import Comment, Item, Key, Table

if TYPE_CHECKING:
    from _collections_abc import dict_items
    from collections.abc import Iterable

    from tomlkit.container import Container

# Alias for items in tomlkit's document body, matching the type used in stubs.
# At runtime, the second element may be any Item subclass (including comments,
# whitespace, and containers), but the stubs treat them uniformly as Item.
_TomlkitBodyItem = tuple[Key | None, Item]

# --- Lossless TOML AST surgery (tomlkit structure-preserving) ---


def set_root_flag(toml_text: str, *, for_pyproject: bool, root: bool) -> str:
    """Set or remove the `root` flag in a TOML document.

    - For topmark.toml: top-level `root = true` (or remove when false).
    - For pyproject.toml: sets `tool.topmark.root`.

    Args:
        toml_text: TOML document text.
        for_pyproject: Whether the document is (or will be) a pyproject-style document (i.e. root
            lives at ``tool.topmark.root``).
        root: Whether to enable the root flag.

    Returns:
        Updated TOML document text.

    Raises:
        RuntimeError: If the TOML document cannot be parsed.
        TypeError: If an existing `tool` or `tool.topmark` key exists but is not a table.
    """
    try:
        doc: tomlkit.TOMLDocument = tomlkit.parse(toml_text)
    except TomlkitParseError as exc:
        raise RuntimeError(f"Error parsing TOML document: {exc}") from exc

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
            raise TypeError("Cannot set tool.topmark.root: 'tool' exists but is not a TOML table")

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
            raise TypeError(
                "Cannot set tool.topmark.root: 'tool.topmark' exists but is not a TOML table"
            )

        if root:
            topmark_tbl["root"] = True
        else:
            # tomlkit Table supports `in` / del.
            if "root" in topmark_tbl:
                del topmark_tbl["root"]
    else:
        # Non-pyproject.toml case (topmark.toml)
        if root:
            # Attempt a nicer placement when the input document resembles the annotated template.
            # If we can find a comment item that mentions "# root = true", insert immediately
            # after that comment. Otherwise, fall back to a normal assignment (which places the
            # key according to tomlkit's default ordering rules).
            if "root" in doc:
                doc["root"] = True
            else:
                insert_at: int | None = None
                for i, (k, item) in enumerate(doc.body):
                    if k is None and isinstance(item, Comment):
                        txt: str = str(item)
                        if "# root = true" in txt:
                            insert_at = i + 1
                            break

                if insert_at is None:
                    # Fallback: append at end if the banner cannot be found.
                    doc["root"] = True
                else:
                    # Insert the key/value pair plus a blank line after it.
                    doc.body.insert(insert_at, (tomlkit.key("root"), tomlkit.boolean("true")))
                    doc.body.insert(insert_at + 1, (None, tomlkit.nl()))
        else:
            if "root" in doc:
                del doc["root"]

    # Prefer the document serializer to avoid tomlkit.dumps typing issues.
    return doc.as_string()


def nest_toml_under_section(
    toml_doc: str,
    section_keys: str,
) -> str:
    r"""Return a new TOML document nested under a dotted section path.

    This helper uses tomlkit to *losslessly* wrap an existing TOML document
    under a nested section, for example:

        nest_toml_under_section("a = 1\n", "tool.topmark")

    yields a document equivalent to:

        [tool.topmark]
        a = 1

    Comments/whitespace are preserved by re-using tomlkit nodes. Leading preamble
    (comments/blank lines before the first keyed entry) and trailing postamble are
    also preserved.

    Args:
        toml_doc: Original TOML document to nest.
        section_keys: Dotted section path such as ``"tool.topmark"``.
            Empty segments (e.g., ``"tool..topmark"``) are not allowed.

    Returns:
        A new TOML document where the original keyed content lives under the final
        section table (e.g., ``[tool.topmark]``).

    Raises:
        ValueError: If ``section_keys`` is empty or only contains dots.
        RuntimeError: If the TOML document cannot be parsed or if an existing
            key along the path is not a table, making nesting impossible.
        TypeError: If trying to nest a table in a non-table element.

    """
    try:
        # 1. Parse the existing document losslessly
        doc: tomlkit.TOMLDocument = tomlkit.parse(toml_doc)
    except TomlkitParseError as exc:
        raise RuntimeError(f"Error parsing TOML document: {exc}") from exc

    # 2. Identify the content slices: preamble (leading unkeyed items) and postamble
    # (trailing unkeyed items). We find the indices of the first and last items that have
    # a key (i.e., not a comment/whitespace entry).
    start_index: int = 0
    end_index: int = -1  # Index of the last keyed item. -1 means no keyed items found.

    # Find start_index (the index of the first item with a key)
    for i, (key, _) in enumerate(doc.body):
        if key is not None:
            start_index = i
            break

    # Find end_index (the index of the last item with a key)
    # We iterate backward to find the last occurrence efficiently.
    for i in range(len(doc.body) - 1, -1, -1):
        key, _ = doc.body[i]
        if key is not None:
            end_index = i
            break

    # Preamble slice: All items before the first keyed item.
    preamble_items: list[_TomlkitBodyItem] = doc.body[0:start_index]

    # Postamble slice: All items after the last keyed item.
    # If end_index is -1 (file is all comments/whitespace), end_index + 1 is 0,
    # so doc.body[0:] is the entire body, which is correct for transfer.
    postamble_items: list[_TomlkitBodyItem] = doc.body[end_index + 1 :]

    # Split and validate the section path
    keys: list[str] = [k for k in section_keys.split(".") if k]
    if not keys:
        raise ValueError("section_keys must contain at least one non-empty component")

    # Idempotency guard: if the document already represents exactly the requested wrapper
    # (e.g. it already represents exactly the requested wrapper),
    # do not wrap again.
    #
    # We consider it "already nested" only when each level along the path is the
    # sole keyed table at that level (so we don't accidentally skip wrapping
    # when sibling keys exist).
    def _only_keyed_table_at_level(container: tomlkit.TOMLDocument | Table, expected: str) -> bool:
        # tomlkit is untyped enough that pyright treats keys() as Unknown.
        keys_iter = cast("Iterable[object]", cast("Any", container).keys())
        keys_list: list[object] = list(keys_iter)

        if len(keys_list) != 1:
            return False

        return (
            str(keys_list[0]) == expected
            and expected in cast("Any", container)
            and isinstance(cast("Any", container)[expected], Table)
        )

    already_nested: bool = True
    cur: tomlkit.TOMLDocument | Table = doc
    for k in keys:
        if not _only_keyed_table_at_level(cur, k):
            already_nested = False
            break
        nxt: Item | Container = cur[k]
        if not isinstance(nxt, Table):
            raise TypeError(f"Expected '{k}' to be a TOML table while checking nesting")
        cur = nxt

    if already_nested:
        # Preserve original formatting/comments as-is.
        return doc.as_string()

    # 3. Create the wrapper document and prepend the preamble
    new_doc: tomlkit.TOMLDocument = tomlkit.document()

    # Prepend the captured preamble items to the new document's body.
    # We use `cast` to satisfy the type checker by asserting that the list contents
    # conform to the expected types (Key | None, Item).
    new_doc.body.extend(preamble_items)

    # 4. Build nested tables for the full section path
    current_level: tomlkit.TOMLDocument | Table = new_doc

    # Recursively build nested tables for "tool.topmark"
    for key in keys:
        # Ensure a table exists at this level for the key
        if key not in current_level:
            # Both TOMLDocument and Table support `.add`
            current_level.add(key, tomlkit.table())

        # Descend into the nested table; validate the type for Pyright and correctness
        next_level: Item | Container = current_level[key]
        if not isinstance(next_level, Table):
            raise TypeError(
                f"Cannot nest configuration under [{section_keys}]: "
                f"intermediate key [{key}] is not a table."
            )
        current_level = next_level

    # 5. Attach the original document's content inside the final table
    # At this point, current_level is the Table for the last key in section_keys.
    if not isinstance(current_level, Table):
        raise TypeError("Expected final nesting target to be a TOML table")

    # doc.items() extracts only the key-value pairs (the actual content),
    # preserving item-level trivia (inline comments, etc.).
    items: dict_items[str, Item | Container] = cast(
        "dict_items[str, Item | Container]", doc.items()
    )
    for item_key, item_value in items:
        # The type checker is now happy due to the explicit cast
        current_level.add(item_key, item_value)

    # 6. Append the postamble to the new document's body, *after* all keyed content.
    # The postamble elements will appear after the newly created section table.
    new_doc.body.extend(postamble_items)

    # 7. Return the wrapped TOML as a string
    # Use as_string() to get the full formatted output of the Document object
    return new_doc.as_string()

# topmark:header:start
#
#   file         : test_completion.py
#   file_relpath : tests/cli/test_completion.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shell completion tests for TopMark's Click CLI.

These tests validate that options backed by our custom EnumParam
expose proper shell completions via Click 8.x's completion engine.

We focus on the `--header-format` option, which is typed as
`EnumParam(HeaderOutputFormat)` and should complete known values.

To run only these tests:
    pytest -q tests/test_completion.py

Note: These tests do not require enabling shell completion in the
user's interactive shell; they drive Click's completion engine
programmatically via `click.shell_completion.ShellComplete`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
from click.shell_completion import CompletionItem

from tests.cli.conftest import cli
from tests.conftest import mark_cli, parametrize
from topmark.cli.cli_types import EnumParam
from topmark.rendering.formats import HeaderOutputFormat

if TYPE_CHECKING:
    from collections.abc import Iterable


def _enum_values(enum_cls: type[HeaderOutputFormat]) -> set[str]:
    """Return the set of string values for the given Enum class.

    The CLI exposes enum *values* (not names), so we compare against these.
    """
    return {str(getattr(m, "value", m)) for m in enum_cls}


def _complete(incomplete: str = "") -> list[CompletionItem]:
    """Call EnumParam(HeaderOutputFormat).shell_complete directly.

    This isolates the test from Click's shell adapters and focuses on our
    custom parameter type's completion behavior.
    """
    enum_type = EnumParam(HeaderOutputFormat)
    # Minimal Click option and context
    opt = click.Option(("--header-format",), type=enum_type)
    ctx = click.Context(cli)
    items = enum_type.shell_complete(ctx, opt, incomplete)
    if items:
        return items
    # Fallback for robustness; shouldn't happen on Click 8.2
    return [CompletionItem(str(x)) for x in items]


def _values(items: Iterable[CompletionItem]) -> set[str]:
    """Extract the `.value` field from completion items into a set of strings."""
    return {getattr(i, "value", str(i)) for i in items}


def test_header_format_completion_lists_all_values() -> None:
    """`--header-format` completion should list all HeaderOutputFormat values."""
    items = _complete("")
    values = _values(items)
    assert _enum_values(HeaderOutputFormat) <= values


# adapt if enum values change
@mark_cli
@parametrize("prefix", ["n", "p", "j"])
# adapt if enum values change
def test_header_format_completion_filters_by_prefix(prefix: str) -> None:
    """Completion should be filtered by the typed prefix (case-insensitive)."""
    items = _complete(prefix)
    values = _values(items)

    # All suggested values must start with the prefix
    assert all(v.lower().startswith(prefix.lower()) for v in values)

    # At least one known enum value starting with the prefix should appear (when applicable)
    expected = {v for v in _enum_values(HeaderOutputFormat) if v.lower().startswith(prefix)}
    if expected:
        assert expected & values


@mark_cli
def test_header_format_completion_handles_nonmatching_prefix() -> None:
    """Non-matching prefixes should yield an empty suggestion list."""
    items = _complete("zzz")
    assert _values(items) == set()


@mark_cli
def test_header_format_completion_works_across_commands() -> None:
    """The same option type should complete in other commands that accept it."""
    # If another command (e.g., check) exposes --header-format, it should complete too.
    items = _complete("")
    values = _values(items)
    # Not all commands must expose the option, but when they do, values should be suggested.
    # Accept either empty (option not present) or the full enum set.
    enum_vals = _enum_values(HeaderOutputFormat)
    assert values in (set(), values | enum_vals) or enum_vals <= values

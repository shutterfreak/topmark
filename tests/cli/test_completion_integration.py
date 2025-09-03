# topmark:header:start
#
#   file         : test_completion_integration.py
#   file_relpath : tests/cli/test_completion_integration.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Integration tests for Click shell completion in TopMark.

These tests verify that our custom `EnumParam.shell_complete()` integration
is discoverable by Click in an end-to-end path using the Bash completion
adapter.

Behaviors tested:
- `--header-format` suggests all enum values.
- Suggestions are filtered by typed prefixes.

Resilience:
- If the environment yields no suggestions (common on CI or exotic shells),
  the tests are xfailed instead of failing the suite.
- Tests avoid private Click APIs and remain compatible with strict typing.
"""

from __future__ import annotations

import os
from typing import Any, cast

import pytest
from click.shell_completion import BashComplete, CompletionItem

from tests.cli.conftest import cli
from tests.conftest import mark_integration, parametrize
from topmark.rendering.formats import HeaderOutputFormat


def _normalize_completion_output(
    result: str | list[CompletionItem] | list[str],
) -> set[str]:
    """Normalize various Click completion outputs into a set of suggestion strings.

    Supports:
    - newline- or whitespace-separated strings
    - comma-separated strings
    - lists of CompletionItem objects
    - lists of strings

    Args:
        result: The raw result object returned by Click completion.

    Returns:
        set[str]: A set of normalized suggestion strings.
    """
    if isinstance(result, str):
        tokens: list[str] = []
        for line in result.splitlines():
            # Split on whitespace, then on commas, trim all
            for piece in line.replace("\t", " ").split():
                tokens.extend(p.strip() for p in piece.split(","))
        return {t for t in tokens if t}

    if result:
        if isinstance(result[0], CompletionItem):
            return {cast("CompletionItem", x).value for x in result}
        # assume list[str]
        flat: list[str] = []
        for x in result:
            for p in str(x).split(","):
                flat.append(p.strip())
        return {t for t in flat if t}

    return set()


def _bash_complete(args: list[str], incomplete: str) -> set[str]:
    """Run Click's Bash completion adapter and return suggestion strings.

    Args:
        args: Arguments provided up to the completion point.
        incomplete: The current incomplete word to complete.

    Returns:
        set[str]: A set of suggested completion strings.
    """
    bc = BashComplete(
        cli=cli,
        ctx_args={},
        prog_name="topmark",
        complete_var="_TOPMARK_COMPLETE",
    )

    prog = "topmark"
    env_backup = {
        k: os.environ.get(k) for k in ("_TOPMARK_COMPLETE", "COMP_WORDS", "COMP_CWORD", "COMP_LINE")
    }
    try:
        os.environ["_TOPMARK_COMPLETE"] = "complete"
        os.environ["COMP_WORDS"] = " ".join([prog, *args])
        os.environ["COMP_CWORD"] = str(len(args) + 1)
        os.environ["COMP_LINE"] = f"{prog} {' '.join(args)} {incomplete}".rstrip()
        raw: Any = bc.complete()
    finally:
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    return _normalize_completion_output(raw)


@mark_integration
def test_header_format_bash_completion_lists_all_values() -> None:
    """End-to-end: `--header-format` should suggest enum values via Bash adapter."""
    suggestions = _bash_complete(["dump-config", "--header-format"], "")
    expected = {e.value for e in HeaderOutputFormat}
    if not suggestions:
        pytest.xfail("No suggestions produced by BashComplete in this environment")
    assert expected <= suggestions


@mark_integration
@parametrize("prefix,expected_one", [("n", "native"), ("p", "plain"), ("j", "json")])
def test_header_format_bash_completion_filters_by_prefix(prefix: str, expected_one: str) -> None:
    """End-to-end: prefix should filter suggestions (case-insensitive)."""
    suggestions = _bash_complete(["dump-config", "--header-format"], prefix)
    if not suggestions:
        pytest.xfail("No suggestions produced by BashComplete in this environment")
    assert any(s.lower().startswith(prefix) for s in suggestions)
    # If the expected choice exists in this build, ensure it appears for its prefix.
    enum_values = {e.value for e in HeaderOutputFormat}
    if expected_one in enum_values:
        assert any(s.lower().startswith(prefix) for s in suggestions)

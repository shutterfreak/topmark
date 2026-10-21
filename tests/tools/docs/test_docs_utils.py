# topmark:header:start
#
#   project      : TopMark
#   file         : test_docs_utils.py
#   file_relpath : tests/tools/docs/test_docs_utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for shared documentation utilities."""

from __future__ import annotations

from typing import Literal

import pytest

from tools.docs import docs_utils
from tools.docs.docs_utils import apply_outside_fenced_blocks
from tools.docs.docs_utils import env_flag
from tools.docs.docs_utils import find_unlinked_backticked_symbols_with_locations
from tools.docs.docs_utils import fix_backticked_reference_links
from tools.docs.docs_utils import load_nonlinked_symbols
from tools.docs.docs_utils import unescape_reference_link_text


@pytest.mark.parametrize(
    ("symbols", "debug", "max_inline", "expected"),
    (
        (
            [],
            False,
            2,
            "",
        ),
        (
            ["topmark.api.A", "topmark.api.B", "topmark.api.C"],
            True,
            2,
            "topmark.api.A, topmark.api.B, topmark.api.C",
        ),
        (
            ["topmark.api.A", "topmark.api.B"],
            False,
            2,
            "topmark.api.A, topmark.api.B",
        ),
        (
            ["topmark.api.A", "topmark.api.B", "topmark.api.C"],
            False,
            2,
            "topmark.api.A, topmark.api.B (+1 more)",
        ),
    ),
)
def test_format_inline_symbols_respects_debug_and_truncation_policy(
    symbols: list[str],
    debug: bool,
    max_inline: int,
    expected: str,
) -> None:
    """Inline summaries retain all debug symbols and truncate ordinary output."""
    assert (
        docs_utils.format_inline_symbols(
            symbols,
            debug=debug,
            max_inline=max_inline,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    (
        (" YES ", True),
        ("off", False),
        ("custom-enabled-value", True),
    ),
)
def test_env_flag_uses_documented_boolean_grammar(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: bool,
) -> None:
    """Environment flags recognize explicit booleans and enable other non-empty values."""
    monkeypatch.setenv("TOPMARK_TEST_DOCS_FLAG", raw_value)

    assert env_flag("TOPMARK_TEST_DOCS_FLAG") is expected


def test_env_flag_uses_its_default_when_the_variable_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent environment variable returns the caller's configured default."""
    monkeypatch.delenv("TOPMARK_TEST_DOCS_FLAG", raising=False)

    assert env_flag("TOPMARK_TEST_DOCS_FLAG", default=True) is True


def test_load_nonlinked_symbols_normalizes_comma_separated_values() -> None:
    """The symbol whitelist trims entries, removes blanks, and de-duplicates values."""
    env = {
        "TOPMARK_DOCS_NONLINKED_SYMBOLS": " topmark.api , ,topmark.registry,topmark.api ",
    }

    assert load_nonlinked_symbols(env) == frozenset(
        {
            "topmark.api",
            "topmark.registry",
        }
    )


@pytest.mark.parametrize(
    ("candidate", "expected"),
    (
        ("", False),
        ("topmark", False),
        ("other.api.Symbol", False),
        ("topmark.settings.toml", False),
        ("topmark.api.Allowed", False),
        ("topmark.api.Required", True),
    ),
)
def test_should_enforce_link_applies_the_symbol_policy(
    monkeypatch: pytest.MonkeyPatch,
    candidate: str,
    expected: bool,
) -> None:
    """Only eligible, non-whitelisted TopMark symbols require reference links."""
    monkeypatch.setattr(
        docs_utils,
        "NONLINKED_SYMBOLS",
        frozenset(
            {
                "topmark.api.Allowed",
            }
        ),
    )

    assert docs_utils.should_enforce_link(candidate) is expected


def test_reference_normalization_preserves_fenced_examples() -> None:
    """Reference repairs apply to prose without rewriting fenced Markdown examples."""
    markdown = (
        "[`topmark.api`][]\n"
        r"\[`topmark.registry`\][topmark.registry]"
        "\n\n```md\n[`topmark.api`][]\n"
        r"\[`topmark.registry`\][topmark.registry]"
        "\n```\n"
    )

    normalized: str = apply_outside_fenced_blocks(markdown, unescape_reference_link_text)
    normalized = apply_outside_fenced_blocks(normalized, fix_backticked_reference_links)

    assert normalized == (
        "[`topmark.api`][topmark.api]\n"
        "[`topmark.registry`][topmark.registry]\n\n"
        "```md\n[`topmark.api`][]\n"
        r"\[`topmark.registry`\][topmark.registry]"
        "\n```\n"
    )


def test_reference_normalization_repairs_explicit_backticked_labels() -> None:
    """Reference links normalize a backticked explicit label to the symbol name."""
    assert (
        docs_utils.fix_backticked_reference_links("[`topmark.api.Symbol`][`topmark.api.Symbol`]")
        == "[`topmark.api.Symbol`][topmark.api.Symbol]"
    )


def test_unlinked_symbol_discovery_respects_links_fences_and_artifacts() -> None:
    """Symbol discovery reports prose references but ignores supported non-candidates."""
    markdown = (
        "`topmark.api.check`\n"
        "[`topmark.api.strip`][topmark.api.strip]\n"
        "`topmark.toml`\n"
        "```py\n`topmark.registry.register`\n```\n"
    )

    assert find_unlinked_backticked_symbols_with_locations(markdown) == {"topmark.api.check": {1}}
    assert (
        find_unlinked_backticked_symbols_with_locations("```py\n`topmark.registry.register`\n```")
        == {}
    )


def test_unlinked_symbol_discovery_handles_malformed_inline_code_and_links() -> None:
    """Malformed link wrappers remain findings while unmatched code delimiters are ignored."""
    markdown = (
        "[`topmark.api.MissingBracket`\n"
        "[`topmark.api.Trailing`]  \n"
        "`topmark.api.Reported`\n"
        "``topmark.api.Unclosed`\n"
    )

    assert find_unlinked_backticked_symbols_with_locations(markdown) == {
        "topmark.api.MissingBracket": {1},
        "topmark.api.Trailing": {2},
        "topmark.api.Reported": {3},
    }

    assert find_unlinked_backticked_symbols_with_locations("[`topmark.api.EndOfInput`]  ") == {
        "topmark.api.EndOfInput": {1}
    }


def test_apply_outside_fenced_blocks_transforms_only_prose_fragments() -> None:
    """Transforms process prose on both sides of a fenced block and preserve the block."""
    markdown = "before\n```text\ninside\n```\nafter"

    assert apply_outside_fenced_blocks(markdown, str.upper) == (
        "BEFORE\n```text\ninside\n```\nAFTER"
    )
    assert apply_outside_fenced_blocks("```text\ninside\n```", str.upper) == "```text\ninside\n```"


def test_wrap_actions_blocks_with_raw_preserves_actions_expressions() -> None:
    """GitHub Actions expressions in fenced blocks remain unchanged by the compatibility helper."""
    markdown = "```yaml\nref: ${{ github.sha }}\n```\n"

    assert docs_utils.wrap_actions_blocks_with_raw(markdown) == markdown


@pytest.mark.parametrize(
    ("lines", "expected"),
    (
        (set[int](), "(unknown line)"),
        ({71}, "line 71"),
        ([117, 57, 61], "lines 57, 61, 117"),
    ),
)
def test_format_line_numbers_produces_sorted_human_readable_output(
    lines: set[int] | list[int],
    expected: str,
) -> None:
    """Line-number summaries distinguish no, one, and several source lines."""
    assert docs_utils.format_line_numbers(lines) == expected


@pytest.mark.parametrize(
    ("path", "root", "expected"),
    (
        ("docs/dev/guide.md", "docs", "dev/guide.md"),
        ("topmark/api.py", "src", "topmark/api.py"),
    ),
)
def test_strip_repo_prefix_removes_only_the_expected_root(
    path: str,
    root: Literal["docs", "src"],
    expected: str,
) -> None:
    """Prefix removal leaves paths without the selected root unchanged."""
    assert docs_utils.strip_repo_prefix(path, root=root) == expected


@pytest.mark.parametrize(
    ("rel_path", "root", "expected"),
    (
        (None, "docs", "<unknown>"),
        ("", "docs", "<unknown>"),
        ("dev/guide.md", "docs", "docs/dev/guide.md"),
        ("src/topmark/api.py", "src", "src/topmark/api.py"),
    ),
)
def test_format_repo_path_returns_a_stable_repo_location(
    rel_path: str | None,
    root: Literal["docs", "src"],
    expected: str,
) -> None:
    """Repository paths receive one root prefix, unless they are absent or already prefixed."""
    assert docs_utils.format_repo_path(rel_path, root=root) == expected


def test_context_lines_include_only_available_context() -> None:
    """Context logging omits absent fields and preserves the documented output order."""
    assert docs_utils.context_lines() == []
    assert docs_utils.context_lines(
        edit_url="https://example.test/edit",
        rendered_on="guide/page.md",
        source_file="src/topmark/api.py",
    ) == [
        "Edit URL (context): https://example.test/edit",
        "Rendered on (context): guide/page.md",
        "Source file (context): src/topmark/api.py",
    ]

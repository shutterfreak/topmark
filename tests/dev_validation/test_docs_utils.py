# topmark:header:start
#
#   project      : TopMark
#   file         : test_docs_utils.py
#   file_relpath : tests/dev_validation/test_docs_utils.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation tests for shared documentation utilities."""

from __future__ import annotations

import pytest

from tools.docs.docs_utils import apply_outside_fenced_blocks
from tools.docs.docs_utils import env_flag
from tools.docs.docs_utils import find_unlinked_backticked_symbols_with_locations
from tools.docs.docs_utils import fix_backticked_reference_links
from tools.docs.docs_utils import load_nonlinked_symbols
from tools.docs.docs_utils import rel_href
from tools.docs.docs_utils import unescape_reference_link_text


@pytest.mark.dev_validation
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


@pytest.mark.dev_validation
def test_load_nonlinked_symbols_normalizes_comma_separated_values() -> None:
    """The symbol whitelist trims entries, removes blanks, and de-duplicates values."""
    env = {"TOPMARK_DOCS_NONLINKED_SYMBOLS": " topmark.api , ,topmark.registry,topmark.api "}

    assert load_nonlinked_symbols(env) == frozenset({"topmark.api", "topmark.registry"})


@pytest.mark.dev_validation
def test_reference_normalization_preserves_fenced_examples() -> None:
    """Reference repairs apply to prose without rewriting fenced Markdown examples."""
    markdown = (
        "[`topmark.api`][]\n"
        r"\[`topmark.registry`\][topmark.registry]"
        "\n\n```md\n[`topmark.api`][]\n"
        r"\[`topmark.registry`\][topmark.registry]"
        "\n```\n"
    )

    normalized = apply_outside_fenced_blocks(markdown, unescape_reference_link_text)
    normalized = apply_outside_fenced_blocks(normalized, fix_backticked_reference_links)

    assert normalized == (
        "[`topmark.api`][topmark.api]\n"
        "[`topmark.registry`][topmark.registry]\n\n"
        "```md\n[`topmark.api`][]\n"
        r"\[`topmark.registry`\][topmark.registry]"
        "\n```\n"
    )


@pytest.mark.dev_validation
def test_unlinked_symbol_discovery_respects_links_fences_and_artifacts() -> None:
    """Symbol discovery reports prose references but ignores supported non-candidates."""
    markdown = (
        "`topmark.api.check`\n"
        "[`topmark.api.strip`][topmark.api.strip]\n"
        "`topmark.toml`\n"
        "```py\n`topmark.registry.register`\n```\n"
    )

    assert find_unlinked_backticked_symbols_with_locations(markdown) == {"topmark.api.check": {1}}


@pytest.mark.dev_validation
def test_relative_documentation_links_use_posix_paths() -> None:
    """Documentation links are relative to the source document and platform-neutral."""
    assert (
        rel_href("dev/architecture/overview.md", "api/reference/topmark.api.md")
        == "../../api/reference/topmark.api.md"
    )

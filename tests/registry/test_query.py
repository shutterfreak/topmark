# topmark:header:start
#
#   project      : TopMark
#   file         : test_query.py
#   file_relpath : tests/registry/test_query.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for effective registry identity selection."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

import pytest

from tests.helpers.registry import make_file_type
from tests.helpers.registry import patched_effective_registries
from topmark.processors.base import HeaderProcessor
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.query import RegistryIdentityQuery
from topmark.registry.query import RegistryRegex
from topmark.registry.query import RegistrySelection

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType


class AcmeProcessor(HeaderProcessor):
    """Processor used to test identity selection."""

    local_key: ClassVar[str] = "python"
    namespace: ClassVar[str] = "acme"
    description: ClassVar[str] = "Acme query test processor."


class ExampleProcessor(HeaderProcessor):
    """Processor used to test identity selection."""

    local_key: ClassVar[str] = "toml"
    namespace: ClassVar[str] = "example"
    description: ClassVar[str] = "Example query test processor."


@pytest.mark.parametrize(
    ("raw_query", "expected_qualified_keys"),
    [
        (
            "html",
            {
                "acme:html",
                "topmark:html",
            },
        ),
        (
            "topmark:",
            {
                "topmark:html",
                "topmark:javascript",
                "topmark:json",
                "topmark:jsonc",
                "topmark:myjson",
            },
        ),
        (
            ":json",
            {
                "acme:json",
                "topmark:json",
            },
        ),
        (
            ":*json",
            {
                "acme:json",
                "topmark:json",
                "topmark:myjson",
            },
        ),
        (
            "*js*",
            {
                "acme:json",
                "js-tools:yaml",
                "topmark:json",
                "topmark:jsonc",
                "topmark:myjson",
            },
        ),
    ],
)
def test_registry_identity_query_implements_the_compact_query_grammar(
    raw_query: str,
    expected_qualified_keys: set[str],
) -> None:
    """Identity queries distinguish local keys, structured fields, and full-key globs."""
    candidates: tuple[tuple[str, str, str], ...] = (
        ("acme:html", "acme", "html"),
        ("acme:json", "acme", "json"),
        ("js-tools:yaml", "js-tools", "yaml"),
        ("topmark:html", "topmark", "html"),
        ("topmark:javascript", "topmark", "javascript"),
        ("topmark:json", "topmark", "json"),
        ("topmark:jsonc", "topmark", "jsonc"),
        ("topmark:myjson", "topmark", "myjson"),
    )
    query: RegistryIdentityQuery = RegistryIdentityQuery.parse(raw_query)

    actual_qualified_keys: set[str] = {
        qualified_key
        for qualified_key, namespace, local_key in candidates
        if query.matches(
            qualified_key=qualified_key,
            namespace=namespace,
            local_key=local_key,
        )
    }

    assert actual_qualified_keys == expected_qualified_keys


@pytest.mark.parametrize(
    ("raw_query", "message"),
    [
        ("", "must not be empty"),
        ("namespace:local:extra", "at most one ':'"),
    ],
)
def test_registry_identity_query_rejects_malformed_input(
    raw_query: str,
    message: str,
) -> None:
    """Identity-query parsing rejects syntax outside the compact grammar."""
    with pytest.raises(ValueError, match=message):
        RegistryIdentityQuery.parse(raw_query)


def test_registry_selection_ors_positional_identity_queries() -> None:
    """Separate positional queries are alternative inclusion predicates."""
    acme_python: FileType = make_file_type(
        local_key="python",
        namespace="acme",
    )
    example_python: FileType = make_file_type(
        local_key="python",
        namespace="example",
    )
    example_toml: FileType = make_file_type(
        local_key="toml",
        namespace="example",
    )
    selection = RegistrySelection(
        identity_queries=(
            RegistryIdentityQuery.parse("example:"),
            RegistryIdentityQuery.parse(":python"),
        ),
    )

    with patched_effective_registries(
        filetypes={
            "acme_python": acme_python,
            "example_python": example_python,
            "example_toml": example_toml,
        },
        processors={
            "acme_python": AcmeProcessor(),
            "example_toml": ExampleProcessor(),
        },
    ):
        assert [item.qualified_key for item in FileTypeRegistry.select(selection)] == [
            "acme:python",
            "example:python",
            "example:toml",
        ]
        assert [item.qualified_key for item in HeaderProcessorRegistry.select(selection)] == [
            "acme:python",
            "example:toml",
        ]


def test_registry_selection_matches_structured_and_exploratory_globs() -> None:
    """Structured queries intersect fields while bare globs inspect full identities."""
    query = RegistrySelection(
        identity_queries=(
            RegistryIdentityQuery.parse("acme:python"),
            RegistryIdentityQuery.parse("*toml"),
        ),
    )

    assert query.matches(
        qualified_key="acme:python",
        local_key="python",
        namespace="acme",
    )
    assert query.matches(
        qualified_key="example:toml",
        local_key="toml",
        namespace="example",
    )
    assert not query.matches(
        qualified_key="acme:yaml",
        local_key="yaml",
        namespace="acme",
    )


def test_builtin_scope_restricts_regex_and_positional_query_results() -> None:
    """Built-in scope is ANDed with every inclusion predicate."""
    selection = RegistrySelection(
        identity_queries=(RegistryIdentityQuery.parse("*python*"),),
        regexes=(RegistryRegex.parse("acme:python"),),
        builtin_only=True,
    )

    assert selection.matches(
        qualified_key="topmark:python",
        local_key="python",
        namespace="topmark",
    )
    assert not selection.matches(
        qualified_key="acme:python",
        local_key="python",
        namespace="acme",
    )


def test_registry_selection_defaults_to_all_entries_and_regexes_fullmatch() -> None:
    """No selectors include every entry; regexes do not implicitly substring-match."""
    assert RegistrySelection().matches(
        qualified_key="acme:python",
        local_key="python",
        namespace="acme",
    )

    regex_selection = RegistrySelection(regexes=(RegistryRegex.parse("topmark:json"),))
    assert regex_selection.matches(
        qualified_key="topmark:json",
        local_key="json",
        namespace="topmark",
    )
    assert not regex_selection.matches(
        qualified_key="topmark:jsonc",
        local_key="jsonc",
        namespace="topmark",
    )

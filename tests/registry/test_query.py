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
from topmark.api.types import BindingInfo
from topmark.processors.base import HeaderProcessor
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.query import BindingQueryBinding
from topmark.registry.query import BindingQueryFileType
from topmark.registry.query import BindingQueryProcessor
from topmark.registry.query import BindingSelection
from topmark.registry.query import RegistryIdentityQuery
from topmark.registry.query import RegistryRegex
from topmark.registry.query import RegistrySelection
from topmark.registry.query import select_binding_view

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType
    from topmark.registry.query import BindingQueryProjection


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


def test_binding_selection_matches_either_endpoint_with_or_semantics() -> None:
    """Binding predicates are alternatives across both endpoint identities."""
    selection = BindingSelection(
        identity_queries=(RegistryIdentityQuery.parse(":json"),),
        regexes=(RegistryRegex.parse("topmark:slash"),),
    )
    binding: BindingInfo = BindingInfo(
        file_type_key="topmark:json-as-jsonc",
        file_type_local_key="json-as-jsonc",
        file_type_namespace="topmark",
        processor_key="topmark:slash",
        processor_local_key="slash",
        processor_namespace="topmark",
        activation="opt-in",
        file_type_description="JSON-as-JSONC",
        processor_description="Slash processor",
    )

    assert selection.matches_binding(binding)


def test_binding_query_projection_preserves_unbound_and_unused_semantics() -> None:
    """Binding projections retain complete-registry unused-processor status."""
    default_binding: BindingQueryBinding = BindingQueryBinding(
        file_type_key="test:bound",
        file_type_local_key="bound",
        file_type_namespace="test",
        processor_key="test:used",
        processor_local_key="used",
        processor_namespace="test",
        activation="default",
        file_type_description="Bound type",
        processor_description="Used processor",
    )
    opt_in_binding: BindingQueryBinding = BindingQueryBinding(
        file_type_key="test:opt-in-bound",
        file_type_local_key="opt-in-bound",
        file_type_namespace="test",
        processor_key="test:used-by-opt-in",
        processor_local_key="used-by-opt-in",
        processor_namespace="test",
        activation="opt-in",
        file_type_description="Opt-in bound type",
        processor_description="Opt-in processor",
    )
    filetypes: list[BindingQueryFileType] = [
        BindingQueryFileType(
            local_key="bound",
            namespace="test",
            qualified_key="test:bound",
            description="Bound type",
            activation="default",
        ),
        BindingQueryFileType(
            local_key="opt-in-bound",
            namespace="test",
            qualified_key="test:opt-in-bound",
            description="Opt-in bound type",
            activation="opt-in",
        ),
        BindingQueryFileType(
            local_key="unbound",
            namespace="test",
            qualified_key="test:unbound",
            description="Unbound type",
            activation="default",
        ),
    ]
    processors: list[BindingQueryProcessor] = [
        BindingQueryProcessor(
            local_key="used",
            namespace="test",
            qualified_key="test:used",
            description="Used processor",
            bound=True,
            line_indent="",
            line_prefix="#",
            line_suffix="",
            block_prefix="",
            block_suffix="",
        ),
        BindingQueryProcessor(
            local_key="used-by-opt-in",
            namespace="test",
            qualified_key="test:used-by-opt-in",
            description="Opt-in processor",
            bound=True,
            line_indent="",
            line_prefix="#",
            line_suffix="",
            block_prefix="",
            block_suffix="",
        ),
        BindingQueryProcessor(
            local_key="unused",
            namespace="test",
            qualified_key="test:unused",
            description="Unused processor",
            bound=False,
            line_indent="",
            line_prefix="#",
            line_suffix="",
            block_prefix="",
            block_suffix="",
        ),
    ]

    unbound_projection: BindingQueryProjection = select_binding_view(
        bindings=[default_binding, opt_in_binding],
        filetypes=filetypes,
        processors=processors,
        selection=BindingSelection(
            identity_queries=(RegistryIdentityQuery.parse("unbound"),),
        ),
    )
    unused_projection: BindingQueryProjection = select_binding_view(
        bindings=[default_binding, opt_in_binding],
        filetypes=filetypes,
        processors=processors,
        selection=BindingSelection(
            identity_queries=(RegistryIdentityQuery.parse("unused"),),
        ),
    )
    activation_projection: BindingQueryProjection = select_binding_view(
        bindings=[default_binding, opt_in_binding],
        filetypes=filetypes,
        processors=processors,
        activation=frozenset({"default"}),
    )

    assert unbound_projection.bindings == ()
    assert [item["qualified_key"] for item in unbound_projection.unbound_filetypes] == [
        "test:unbound",
    ]
    assert unbound_projection.unused_processors == ()
    assert unused_projection.bindings == ()
    assert unused_projection.unbound_filetypes == ()
    assert [item["qualified_key"] for item in unused_projection.unused_processors] == [
        "test:unused",
    ]
    assert [item["file_type_key"] for item in activation_projection.bindings] == ["test:bound"]
    assert [item["qualified_key"] for item in activation_projection.unused_processors] == [
        "test:unused",
    ]

# topmark:header:start
#
#   project      : TopMark
#   file         : query.py
#   file_relpath : src/topmark/registry/query.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Identity selection for effective registry entries.

The query grammar mirrors registry identity shape while keeping the selection
model independent from Click. Positional queries are inclusion predicates;
scope options constrain their result.
"""

from __future__ import annotations

import glob
import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from re import Pattern
from typing import TYPE_CHECKING
from typing import TypeAlias
from typing import TypedDict

from topmark.core.constants import TOPMARK_NAMESPACE

if TYPE_CHECKING:
    from collections.abc import Sequence

RegistryActivationFilter: TypeAlias = frozenset[str]
"""Normalized declared file-type activations for registry filtering."""

RegistryActivationFilterInput: TypeAlias = RegistryActivationFilter | str | None
"""Compatibility input accepted by internal registry presentation helpers."""


class BindingQueryBinding(TypedDict):
    """Minimum binding metadata required by the registry query layer."""

    file_type_key: str
    file_type_local_key: str
    file_type_namespace: str
    processor_key: str
    processor_local_key: str
    processor_namespace: str
    activation: str
    file_type_description: str
    processor_description: str


class BindingQueryFileType(TypedDict):
    """Minimum file-type metadata required by binding report projections."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str
    activation: str


class BindingQueryProcessor(TypedDict):
    """Minimum processor metadata required by binding report projections."""

    local_key: str
    namespace: str
    qualified_key: str
    description: str
    bound: bool
    line_indent: str
    line_prefix: str
    line_suffix: str
    block_prefix: str
    block_suffix: str


def matches_declared_activation(
    declared_activation: str,
    activation_filter: RegistryActivationFilterInput,
) -> bool:
    """Return whether a declared activation passes an optional registry filter.

    A string remains accepted for existing internal callers that select exactly
    one activation. CLI parsing always supplies the normalized set form.

    Args:
        declared_activation: Activation declared by a registry file type.
        activation_filter: Optional normalized set of allowed activations.

    Returns:
        True when no filter is supplied or the declared activation is allowed.
    """
    if activation_filter is None:
        return True
    if isinstance(activation_filter, str):
        return declared_activation == activation_filter
    return declared_activation in activation_filter


@dataclass(frozen=True, kw_only=True, slots=True)
class RegistryIdentityQuery:
    """One glob-based registry identity inclusion predicate.

    A structured query matches both its namespace and local-key components. A
    glob-bearing query without a colon instead matches the full qualified key.
    """

    namespace_glob: str | None = None
    local_key_glob: str | None = None
    qualified_key_glob: str | None = None

    @classmethod
    def parse(
        cls,
        raw: str,
    ) -> RegistryIdentityQuery:
        """Parse one user-supplied positional registry query.

        Args:
            raw: Query text in structured or whole-identity glob form.

        Returns:
            A normalized identity query.

        Raises:
            ValueError: If the query is empty or has more than one colon.
        """
        if not raw:
            raise ValueError("Registry query must not be empty.")
        if raw.count(":") > 1:
            raise ValueError(
                "Registry query must contain at most one ':' separating namespace and local key.",
            )
        if ":" in raw:
            namespace_glob, local_key_glob = raw.split(":", maxsplit=1)
            return cls(
                namespace_glob=namespace_glob or "*",
                local_key_glob=local_key_glob or "*",
            )
        if glob.has_magic(raw):
            return cls(qualified_key_glob=raw)
        return cls(namespace_glob="*", local_key_glob=raw)

    def matches(
        self,
        *,
        qualified_key: str,
        local_key: str,
        namespace: str,
    ) -> bool:
        """Return whether an identity matches this inclusion predicate."""
        if self.qualified_key_glob is not None:
            return fnmatchcase(qualified_key, self.qualified_key_glob)
        namespace_glob: str = self.namespace_glob or "*"
        local_key_glob: str = self.local_key_glob or "*"
        return fnmatchcase(namespace, namespace_glob) and fnmatchcase(
            local_key,
            local_key_glob,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class RegistryRegex:
    """One compiled whole-identity regular-expression inclusion predicate."""

    pattern: Pattern[str]

    @classmethod
    def parse(cls, raw: str) -> RegistryRegex:
        """Compile one user-supplied regular expression.

        Args:
            raw: Python regular-expression source.

        Returns:
            A compiled regular-expression selector.
        """
        return cls(pattern=re.compile(raw))

    def matches(self, qualified_key: str) -> bool:
        """Return whether the expression fully matches a qualified identity."""
        return self.pattern.fullmatch(qualified_key) is not None


@dataclass(frozen=True, kw_only=True, slots=True)
class RegistrySelection:
    """Scope and inclusion predicates for registry identity selection.

    Positional identity queries and regular expressions are ORed. Built-in
    scope is applied independently, so it restricts rather than expands the
    selected result set.
    """

    identity_queries: tuple[RegistryIdentityQuery, ...] = ()
    regexes: tuple[RegistryRegex, ...] = ()
    builtin_only: bool = False

    def matches(
        self,
        *,
        qualified_key: str,
        local_key: str,
        namespace: str,
    ) -> bool:
        """Return whether an identity matches this selection."""
        if self.builtin_only and namespace != TOPMARK_NAMESPACE:
            return False
        if not self.identity_queries and not self.regexes:
            return True
        return any(
            query.matches(
                qualified_key=qualified_key,
                local_key=local_key,
                namespace=namespace,
            )
            for query in self.identity_queries
        ) or any(regex.matches(qualified_key) for regex in self.regexes)


@dataclass(frozen=True, kw_only=True, slots=True)
class BindingSelection:
    """Inclusion predicates for the two canonical identities in a binding.

    Queries and regular expressions are alternatives. Each predicate matches a
    binding when either its file-type or processor endpoint matches. This is a
    separate abstraction from `RegistrySelection`, whose `builtin_only` scope
    has no unambiguous meaning for a relationship with two owners.
    """

    identity_queries: tuple[RegistryIdentityQuery, ...] = ()
    regexes: tuple[RegistryRegex, ...] = ()

    def matches_identity(
        self,
        *,
        qualified_key: str,
        local_key: str,
        namespace: str,
    ) -> bool:
        """Return whether one endpoint identity passes this selection."""
        if not self.identity_queries and not self.regexes:
            return True
        return any(
            query.matches(
                qualified_key=qualified_key,
                local_key=local_key,
                namespace=namespace,
            )
            for query in self.identity_queries
        ) or any(regex.matches(qualified_key) for regex in self.regexes)

    def matches_binding(self, binding: BindingQueryBinding) -> bool:
        """Return whether either endpoint of an effective binding matches."""
        return self.matches_identity(
            qualified_key=binding["file_type_key"],
            local_key=binding["file_type_local_key"],
            namespace=binding["file_type_namespace"],
        ) or self.matches_identity(
            qualified_key=binding["processor_key"],
            local_key=binding["processor_local_key"],
            namespace=binding["processor_namespace"],
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class BindingQueryProjection:
    """Centralized, filtered effective-registry view for binding reports."""

    bindings: tuple[BindingQueryBinding, ...]
    unbound_filetypes: tuple[BindingQueryFileType, ...]
    unused_processors: tuple[BindingQueryProcessor, ...]


def select_binding_view(
    *,
    bindings: Sequence[BindingQueryBinding],
    filetypes: Sequence[BindingQueryFileType],
    processors: Sequence[BindingQueryProcessor],
    activation: RegistryActivationFilterInput = None,
    selection: BindingSelection | None = None,
) -> BindingQueryProjection:
    """Filter and project every section of the binding registry view.

    Unused processors are determined from the complete effective registry,
    before identity or activation filters are projected. Activation restricts
    only file-type-derived sections; identity selection independently projects
    each endpoint-oriented section.
    """
    effective_selection: BindingSelection = selection or BindingSelection()
    bound_filetype_keys: set[str] = {item["file_type_key"] for item in bindings}
    bound_processor_keys: set[str] = {item["processor_key"] for item in bindings}

    selected_bindings: tuple[BindingQueryBinding, ...] = tuple(
        item
        for item in bindings
        if matches_declared_activation(item["activation"], activation)
        and effective_selection.matches_binding(item)
    )
    selected_unbound_filetypes: tuple[BindingQueryFileType, ...] = tuple(
        item
        for item in filetypes
        if item["qualified_key"] not in bound_filetype_keys
        and matches_declared_activation(item["activation"], activation)
        and effective_selection.matches_identity(
            qualified_key=item["qualified_key"],
            local_key=item["local_key"],
            namespace=item["namespace"],
        )
    )
    selected_unused_processors: tuple[BindingQueryProcessor, ...] = tuple(
        item
        for item in processors
        if item["qualified_key"] not in bound_processor_keys
        and effective_selection.matches_identity(
            qualified_key=item["qualified_key"],
            local_key=item["local_key"],
            namespace=item["namespace"],
        )
    )
    return BindingQueryProjection(
        bindings=selected_bindings,
        unbound_filetypes=selected_unbound_filetypes,
        unused_processors=selected_unused_processors,
    )

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
from typing import TypeAlias

from topmark.core.constants import TOPMARK_NAMESPACE

RegistryActivationFilter: TypeAlias = frozenset[str]
"""Normalized declared file-type activations for registry filtering."""

RegistryActivationFilterInput: TypeAlias = RegistryActivationFilter | str | None
"""Compatibility input accepted by internal registry presentation helpers."""


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

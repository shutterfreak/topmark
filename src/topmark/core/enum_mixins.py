# topmark:header:start
#
#   project      : TopMark
#   file         : enum_mixins.py
#   file_relpath : src/topmark/core/enum_mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Generic Enum utilities for TopMark (typing-friendly, UI-agnostic).

This module provides helpers that add lightweight *introspection* to Enum types
without binding callers to UI/CLI concerns (like color). Keep rendering-specific
concepts in ``topmark.rendering`` and reuse these mixins/utilities anywhere else.

Provided:
    - ``enum_from_name(enum_cls, name, *, case_insensitive=False)``:
        Typed lookup by ``name`` from ``__members__``. Returns ``None`` on miss.
    - ``EnumIntrospectionMixin``:
        Adds ``.value_length`` (cached) to any Enum subclass for formatting.

Design:
    - Keep the functions *pure* and side-effect free.
    - Avoid bringing UI libraries (e.g. yachalk) into this module.
    - Prefer functions over overly clever metaclass tricks for type-checker sanity.

Example:
    ```python
    from enum import Enum
    from topmark.core.enum_mixins import EnumIntrospectionMixin, enum_from_name

    class Mode(EnumIntrospectionMixin, str, Enum):
        A = "alpha"
        B = "beta"

    assert Mode.A.value_length == 5
    assert enum_from_name(Mode, "A") is Mode.A
    ```
"""

from __future__ import annotations

from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

_E = TypeVar("_E", bound=Enum)
_KS = TypeVar("_KS", bound="KeyedStrEnum")


def enum_from_name(
    enum_cls: type[_E],
    key_name: str | None,
    *,
    case_insensitive: bool = False,
) -> _E | None:
    """Return the enum member for ``key_name`` from ``enum_cls.__members__``.

    Args:
        enum_cls (type[_E]): The Enum class to search.
        key_name (str | None): The member name (e.g., ``'OK'``). If ``None``, returns ``None``.
        case_insensitive (bool): If True, lookup is performed with ``key_name.upper()``.

    Returns:
        _E | None: The matching enum member, or ``None`` if not found.

    Notes:
        - This is a *name* lookup. If you want to match against values as well,
          normalize the candidate first and query ``__members__`` for both keys,
          or introduce a separate helper (kept out of this core to avoid policy).
    """
    if key_name is None:
        return None
    target: str = key_name.upper() if case_insensitive else key_name
    member: Any | None = getattr(enum_cls, "__members__", {}).get(target)
    return cast("_E | None", member)


class EnumIntrospectionMixin:
    """Small, UI-agnostic mixin that adds introspection conveniences to Enums.

    When mixed into an Enum class, provides:

        • ``value_length`` (cached_property): maximum length (in characters) of all
          ``.value`` strings for the enum class. Useful for printing aligned labels.

    Implementation note:
        We rely on the Enum metaclass providing iterability over members and the
        presence of ``.value`` on each. Static analyzers may not infer this on the
        mixin type itself; local ``# type: ignore`` hints are used sparingly.
    """

    @cached_property
    def value_length(self) -> int:
        """Maximum length of the enum's ``.value`` strings.

        Returns:
            int: The maximum length among all member ``.value`` strings of the
            enum class that this member belongs to.
        """
        # Pyright doesn't know 'self' is an Enum member; runtime guarantees it.
        return max(len(member.value) for member in type(self))  # type: ignore[attr-defined]


def _norm_token(s: str) -> str:
    """Normalize an identifier-like string to match config keys and aliases."""
    return s.strip().lower().replace("-", "_").replace(" ", "_")


class KeyedStrEnum(str, Enum):
    """Enum where `.value` is a stable machine key; metadata lives on attributes.

    Use this when you want:
      - a stable, serialization-friendly key (`.value` / `.key`)
      - a human label (`.label`) and optional aliases for parsing

    Attributes:
        label (str): Human-readable label for the member.
        aliases (tuple[str, ...]): Alternative tokens accepted by `parse()`.

    Example:
        class OutputTarget(KeyedStrEnum):
            FILE = ("file", "Write to file")
            STDOUT = ("stdout", "Write to STDOUT")
    """

    label: str
    aliases: tuple[str, ...]

    def __new__(
        cls: type[_KS],
        key: str,
        label: str,
        aliases: Iterable[str] = (),
    ) -> _KS:
        """Create a new KeyedStrEnum member with key, label, and optional aliases.

        Args:
            key (str): The stable machine key (stored as `.value`).
            label (str): The human-readable label for the enum member.
            aliases (Iterable[str]): Optional aliases for parsing. Defaults to empty.

        Returns:
            _KS: The newly created enum member.
        """
        obj: _KS = str.__new__(cls, key)
        obj._value_ = key  # stable machine value
        obj.label = label
        obj.aliases = tuple(aliases)
        return obj

    @property
    def key(self) -> str:
        """Stable machine key (same as `.value`)."""
        return str(self)

    @classmethod
    def parse(cls: type[_KS], raw: str | None) -> _KS | None:
        """Parse a token into an enum member.

        Matches against:
          - the stable key (`.value`)
          - the member name (`.name`)
          - any configured aliases

        Matching is case-insensitive and normalizes '-', ' ' to '_' via `_norm_token()`.
        """
        if raw is None:
            return None
        token: str = _norm_token(raw)

        for m in cls:
            if token == _norm_token(m.value):
                return m
            if token == _norm_token(m.name):
                return m
            for a in m.aliases:
                if token == _norm_token(a):
                    return m
        return None

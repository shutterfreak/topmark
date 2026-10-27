# topmark:header:start
#
#   project      : TopMark
#   file         : enum_mixins.py
#   file_relpath : src/topmark/core/enum_mixins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Enum introspection utilities for TopMark (typing-friendly, UI-agnostic).

This module provides helpers that add lightweight *introspection* to Enum types
without binding callers to UI/CLI concerns (like color). Keep presentation-specific
concepts in [topmark.presentation][] and reuse these mixins/utilities
anywhere else.

Provided:
    - ``EnumIntrospectionMixin``:
        Adds ``.value_length`` (cached) to any enum subclass with string values.

Design:
    - Keep helper behavior *pure* and side-effect free.
    - Avoid bringing presentation/UI libraries (for example Rich or terminal styling
      adapters) into this module.
    - Prefer a small mixin over metaclass tricks for type-checker sanity.

Example:
    ```python
    from enum import StrEnum

    from topmark.core.enum_mixins import EnumIntrospectionMixin


    class Mode(EnumIntrospectionMixin, StrEnum):
        A = "alpha"
        B = "beta"


    assert Mode.A.value_length == 5
    ```
"""

from __future__ import annotations

from functools import cached_property


class EnumIntrospectionMixin:
    """Small, UI-agnostic mixin that adds introspection to string-valued Enums.

    When mixed into an Enum class, provides:

        - ``value_length`` (cached_property): maximum length (in characters) of all
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
            The maximum length among all member ``.value`` strings of the enum class that this
            member belongs to.
        """
        # Pyright doesn't know 'self' is an Enum member; runtime guarantees it.
        return max(len(member.value) for member in type(self))  # type: ignore[attr-defined]

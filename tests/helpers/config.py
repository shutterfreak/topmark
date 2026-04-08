# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : tests/helpers/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for config-layer tests.

This module contains pure helper functions used by tests that operate on
TopMark's config model and layered-config deserialization boundary.

The helpers here intentionally work with fully materialized config objects or
config-local value types such as `PatternSource` and `PatternGroup`. They do
not perform whole-source TOML loading or schema validation; TOML-layer tests
should instead use helpers from `tests.helpers.toml` or `tests/toml/conftest.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING
from typing import TypeAlias
from typing import TypeGuard

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.types import PatternGroup
from topmark.config.types import PatternSource

if TYPE_CHECKING:
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig


PatternSourceInput: TypeAlias = str | Path | PatternSource
PatternGroupInput: TypeAlias = str | PatternGroup


def _is_non_string_sequence(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, Sequence) and not isinstance(value, str)


def to_pattern_sources(values: Sequence[str | Path | PatternSource]) -> list[PatternSource]:
    """Coerce strings, paths, or existing `PatternSource` values into a list.

    Plain strings and `Path` values are normalized to absolute
    [`PatternSource`][topmark.config.types.PatternSource] objects whose base is
    the resolved parent directory. Existing `PatternSource` instances are
    preserved unchanged.

    Args:
        values: Items to coerce.

    Returns:
        Coerced list of `PatternSource` instances.
    """
    if not values:
        return []
    out: list[PatternSource] = []
    for item in values:
        if isinstance(item, PatternSource):
            out.append(item)
            continue
        p: Path = Path(item).resolve()
        out.append(PatternSource(path=p, base=p.parent))
    return out


def to_pattern_groups(
    values: Sequence[str | PatternGroup],
    *,
    base: Path | None = None,
) -> list[PatternGroup]:
    """Coerce strings or `PatternGroup` values into provenance-aware groups.

    Plain string entries are grouped into a single
    [`PatternGroup`][topmark.config.types.PatternGroup] whose base defaults to
    the current working directory unless explicitly provided. Existing
    `PatternGroup` instances are preserved as-is.

    Args:
        values: Items to coerce.
        base: Optional base directory for plain string pattern entries.

    Returns:
        Coerced list of `PatternGroup` instances.
    """
    if not values:
        return []

    group_base: Path = (base or Path.cwd()).resolve()
    out: list[PatternGroup] = []
    raw_patterns: list[str] = []

    for item in values:
        if isinstance(item, PatternGroup):
            out.append(item)
            continue
        raw_patterns.append(item)

    if raw_patterns:
        out.insert(0, PatternGroup(patterns=tuple(raw_patterns), base=group_base))

    return out


def group_patterns(groups: Sequence[PatternGroup]) -> list[str]:
    """Flatten raw pattern strings from provenance-aware pattern groups."""
    return [pattern for group in groups for pattern in group.patterns]


def _as_pattern_source_sequence(value: object, *, name: str) -> Sequence[PatternSourceInput]:
    """Narrow one override value to a `PatternSource`-compatible sequence.

    Args:
        value: Raw override value.
        name: Override key name used in assertion messages.

    Returns:
        Narrowed sequence suitable for `to_pattern_sources()`.

    Raises:
        TypeError: If the override is not a non-string sequence or
            contains unsupported element types.
    """
    if not _is_non_string_sequence(value):
        raise TypeError(f"{name} override must be a sequence")

    raw_items: list[object] = list(value)
    items: list[PatternSourceInput] = []
    for item in raw_items:
        if isinstance(item, str | Path | PatternSource):
            items.append(item)
            continue
        raise TypeError(
            f"{name} override items must be str, Path, or PatternSource; got {type(item).__name__}"
        )
    return items


def _as_pattern_group_sequence(value: object, *, name: str) -> Sequence[PatternGroupInput]:
    """Narrow one override value to a `PatternGroup`-compatible sequence.

    Args:
        value: Raw override value.
        name: Override key name used in assertion messages.

    Returns:
        Narrowed sequence suitable for `to_pattern_groups()`.

    Raises:
        TypeError: If the override is not a non-string sequence or
            contains unsupported element types.
    """
    if not _is_non_string_sequence(value):
        raise TypeError(f"{name} override must be a sequence")

    raw_items: list[object] = list(value)
    items: list[PatternGroupInput] = []
    for item in raw_items:
        if isinstance(item, str | PatternGroup):
            items.append(item)
            continue
        raise TypeError(
            f"{name} override items must be str or PatternGroup; got {type(item).__name__}"
        )
    return items


def make_mutable_config(**overrides: object) -> MutableConfig:
    """Build a mutable config from defaults plus convenient test overrides.

    This helper is intended for config-layer and merge tests that need a
    `MutableConfig` builder rather than a frozen `Config` snapshot.

    It applies a small amount of test-oriented coercion for pattern- and
    path-related overrides so callers can use concise string/`Path` inputs
    instead of constructing `PatternSource` or `PatternGroup` objects by hand.

    For most tests, prefer the `default_config` fixture.
    Use `make_mutable_config` only when deliberately testing config merge logic.

    Args:
        **overrides: Keyword overrides to apply to the mutable builder.
            Keys `include_from`, `exclude_from`, and `files_from` may be sequences of
            strings, `Path`, or `PatternSource`; these are coerced to `PatternSource`.
            Keys `include_patterns` and `exclude_patterns` may be sequences of strings or
            `PatternGroup`; plain strings are grouped into a single provenance-aware
            `PatternGroup` rooted at the current working directory.

    Returns:
        A mutable configuration object ready to be frozen or further edited.
    """
    m: MutableConfig = mutable_config_from_defaults()

    # Coerce path-to-file overrides to PatternSource where needed
    if "include_from" in overrides:
        m.include_from = to_pattern_sources(
            _as_pattern_source_sequence(overrides.pop("include_from"), name="include_from")
        )
    if "exclude_from" in overrides:
        m.exclude_from = to_pattern_sources(
            _as_pattern_source_sequence(overrides.pop("exclude_from"), name="exclude_from")
        )
    if "files_from" in overrides:
        m.files_from = to_pattern_sources(
            _as_pattern_source_sequence(overrides.pop("files_from"), name="files_from")
        )

    # Coerce flattened pattern overrides to provenance-aware groups.
    if "include_patterns" in overrides:
        m.include_pattern_groups = to_pattern_groups(
            _as_pattern_group_sequence(overrides.pop("include_patterns"), name="include_patterns")
        )
    if "exclude_patterns" in overrides:
        m.exclude_pattern_groups = to_pattern_groups(
            _as_pattern_group_sequence(overrides.pop("exclude_patterns"), name="exclude_patterns")
        )

    # Allow direct group overrides for tests that want explicit provenance bases.
    if "include_pattern_groups" in overrides:
        m.include_pattern_groups = to_pattern_groups(
            _as_pattern_group_sequence(
                overrides.pop("include_pattern_groups"),
                name="include_pattern_groups",
            )
        )
    if "exclude_pattern_groups" in overrides:
        m.exclude_pattern_groups = to_pattern_groups(
            _as_pattern_group_sequence(
                overrides.pop("exclude_pattern_groups"),
                name="exclude_pattern_groups",
            )
        )

    # Apply remaining overrides verbatim (files, types, config_files, etc.)
    for k, v in overrides.items():
        setattr(m, k, v)  # still allow direct overrides for convenience

    return m


def make_config(**overrides: object) -> Config:
    """Return a frozen `Config` built from defaults and config-layer overrides.

    This helper is the strongly typed config-object companion to
    `make_mutable_config()`: it materializes a mutable builder, applies the
    requested overrides, and then freezes the result for use in tests that
    want a real [`Config`][topmark.config.model.Config] instance.

    Unlike `tests.helpers.api.cfg()`, this helper does not build a plain
    mapping for the public API's `config=` branch. Use `make_config()` when a
    test needs an actual frozen config object; use `api.cfg()` when a test
    specifically wants to exercise mapping-based API input.

    Args:
        **overrides: Keyword overrides applied to the mutable builder before
            freezing.

    Returns:
        An immutable configuration snapshot for use in tests.
    """
    m: MutableConfig = make_mutable_config(**overrides)
    return m.freeze()

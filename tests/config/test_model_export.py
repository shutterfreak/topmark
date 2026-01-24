# topmark:header:start
#
#   project      : TopMark
#   file         : test_model_export.py
#   file_relpath : tests/config/test_model_export.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for config model export and TOML rendering.

These tests cover:
- `Config.to_toml_dict()` serialization (including enum stringification), and
- `to_toml()` behavior around TOML-incompatible values like `None`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from topmark.config import MutableConfig
from topmark.config.io import to_toml
from topmark.config.keys import Toml
from topmark.config.model import Config
from topmark.config.types import FileWriteStrategy, OutputTarget
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.config.model import Config


@pytest.mark.pipeline
def test_config_to_toml_dict_serializes_enums_as_strings() -> None:
    """Enums serialize to strings, not iterables/char arrays.

    This guards against the earlier “['f', 'i', 'l', 'e']” failure.
    """
    draft: MutableConfig = MutableConfig.from_defaults()
    draft.output_target = OutputTarget.FILE
    draft.file_write_strategy = FileWriteStrategy.ATOMIC
    c: Config = draft.freeze()

    d: dict[str, Any] = c.to_toml_dict()
    writer = d[Toml.SECTION_WRITER]
    assert writer[Toml.KEY_TARGET] == "file"
    assert writer[Toml.KEY_STRATEGY] == "atomic"


@pytest.mark.pipeline
def test_to_toml_strips_none_entries() -> None:
    """to_toml() rejects None by stripping (regression guard).

    If your to_toml() strips None, validate it doesn’t crash and doesn’t emit None.
    """
    draft: MutableConfig = MutableConfig.from_defaults()
    c: Config = draft.freeze()

    # Create a dict with explicit None where TOML doesn't allow it
    td: dict[str, Any] = c.to_toml_dict()
    td[Toml.SECTION_FORMATTING][Toml.KEY_HEADER_FORMAT] = None

    s: str = to_toml(td)
    assert ArgKey.HEADER_FORMAT not in s  # or whatever your stripper does


@pytest.mark.pipeline
def test_apply_args_bad_types_record_diagnostics() -> None:
    """args_io and apply_args smoke tests.

    Guards the weakly-typed ArgsLike path:
    - mixed-type lists drop non-strings and record diagnostics
    - wrong-type scalars record diagnostics and do not crash
    - empty strings are ignored (when relevant)
    """
    draft: MutableConfig = MutableConfig.from_defaults()
    draft.apply_args(
        {
            # mixed list: should drop non-strings and diagnose
            ArgKey.INCLUDE_PATTERNS: ["src/**", 123],
            # wrong type for int: should diagnose
            ArgKey.VERBOSITY_LEVEL: "nope",
            # empty string: should be ignored / treated as unset (depending on your rule)
            ArgKey.RELATIVE_TO: "",
        }
    )

    msgs: list[str] = [d.message for d in draft.diagnostics]

    assert any(
        ("Ignoring non-string entry" in m) or ("Expected list" in m) or ("Expected string" in m)
        for m in msgs
    ), f"Expected list/string-shape diagnostics, got: {msgs!r}"

    assert any(ArgKey.VERBOSITY_LEVEL in m.lower() for m in msgs), (
        f"Expected verbosity parsing diagnostic to be recorded; got: {msgs!r}"
    )

    # Empty relative_to should not become a meaningful value
    assert draft.relative_to_raw in (None, ""), "Empty relative_to should be ignored or cleared"

    # Only the valid string entry should be applied
    assert "src/**" in draft.include_patterns
    assert all(isinstance(p, str) for p in draft.include_patterns)

    # Verbosity should remain unset/default when an invalid type is provided
    assert draft.verbosity_level in (None, 0)

    # Diagnostics should include at least one message about the include_patterns list
    # (either wrong-type list handling or dropped non-strings)
    assert any(ArgKey.INCLUDE_PATTERNS in m for m in msgs), (
        f"Expected include_patterns diagnostics to be recorded; got: {msgs!r}"
    )

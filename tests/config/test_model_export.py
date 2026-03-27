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

from typing import TYPE_CHECKING

import pytest

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.render import to_toml
from topmark.config.io.serializers import config_to_toml_dict
from topmark.config.keys import Toml
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.core.keys import ArgKey

if TYPE_CHECKING:
    from topmark.config.io.types import TomlTable
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig


@pytest.mark.pipeline
def test_config_to_toml_dict_serializes_enums_as_strings() -> None:
    """Enums serialize to strings, not iterables/char arrays.

    This guards against the earlier “['f', 'i', 'l', 'e']” failure.
    """
    draft: MutableConfig = mutable_config_from_defaults()
    draft.output_target = OutputTarget.FILE
    draft.file_write_strategy = FileWriteStrategy.ATOMIC
    c: Config = draft.freeze()

    d: TomlTable = config_to_toml_dict(
        c,
        include_files=False,
    )
    writer = d[Toml.SECTION_WRITER]
    assert isinstance(writer, dict)
    assert writer[Toml.KEY_TARGET] == "file"
    assert writer[Toml.KEY_STRATEGY] == "atomic"


@pytest.mark.pipeline
def test_to_toml_strips_none_entries() -> None:
    """to_toml() rejects None by stripping (regression guard).

    If your to_toml() strips None, validate it doesn’t crash and doesn’t emit None.
    """
    draft: MutableConfig = mutable_config_from_defaults()
    c: Config = draft.freeze()

    # Create a dict with explicit None where TOML doesn't allow it
    td: TomlTable = config_to_toml_dict(
        c,
        include_files=False,
    )
    formatting_tbl = td[Toml.SECTION_FORMATTING]
    assert isinstance(formatting_tbl, dict)
    formatting_tbl[Toml.KEY_ALIGN_FIELDS] = None

    s: str = to_toml(formatting_tbl)
    assert ArgKey.ALIGN_FIELDS not in s  # or whatever your stripper does

# topmark:header:start
#
#   project      : TopMark
#   file         : test_types.py
#   file_relpath : tests/config/test_types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for lightweight configuration-domain types."""

from __future__ import annotations

import pytest

from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget


@pytest.mark.parametrize(
    ("member", "value"),
    [
        (OutputTarget.FILE, "file"),
        (OutputTarget.STDOUT, "stdout"),
        (FileWriteStrategy.ATOMIC, "atomic"),
        (FileWriteStrategy.INPLACE, "inplace"),
    ],
)
def test_writer_enums_render_as_canonical_configuration_values(
    member: OutputTarget | FileWriteStrategy,
    value: str,
) -> None:
    """Writer enum members expose their stable configuration and display tokens."""
    assert member.value == value
    assert str(member) == value
    assert f"{member}" == value

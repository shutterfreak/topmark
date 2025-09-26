# topmark:header:start
#
#   project      : TopMark
#   file         : test_cblock_affixes.py
#   file_relpath : tests/pipeline/processors/test_cblock_affixes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Verify CBlockHeaderProcessor affixes/indent are honored at runtime."""

from __future__ import annotations

from topmark.pipeline.processors.cblock import CBlockHeaderProcessor


def test_cblock_affixes_are_set_via_class_attrs() -> None:
    """Affixes/indent from class attrs persist after base __init__."""
    p = CBlockHeaderProcessor()
    assert p.block_prefix == "/*"
    assert p.block_suffix == "*/"
    assert p.line_prefix == "*"
    assert p.line_suffix == ""
    assert p.line_indent == "  "

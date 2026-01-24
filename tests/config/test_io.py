# topmark:header:start
#
#   project      : TopMark
#   file         : test_io.py
#   file_relpath : tests/config/test_io.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for TOML I/O helpers in topmark.config.io.

Currently focuses on `nest_toml_under_section`, which wraps an existing TOML
document under a dotted section path (e.g., `tool.topmark`) while preserving
comments and valid structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import tomlkit

from topmark.config.io import get_string_list_value_checked, nest_toml_under_section
from topmark.config.logging import TopmarkLogger, get_logger
from topmark.core.diagnostics import DiagnosticLog

if TYPE_CHECKING:
    import pytest


def test_nest_toml_under_section_basic() -> None:
    """Ensure preamble preserved after nesting TOML document under [tool.topmark].

    Wrapping a simple TOML document nests it under [tool.topmark] and
    preserves the leading comment.

    This serves as a guardrail around the tomlkit-based implementation that
    manipulates TOMLDocument.body; if tomlkit changes its representation, this
    test should catch regressions in the wrapped output.
    """
    source = "# leading comment\n\nanswer = 42\n"
    wrapped: str = nest_toml_under_section(source, "tool.topmark")

    # 1) The wrapped document should still be valid TOML
    parsed: Any = tomlkit.parse(wrapped)

    assert "tool" in parsed
    assert hasattr(parsed["tool"], "keys")
    assert "topmark" in parsed["tool"]
    assert hasattr(parsed["tool"]["topmark"], "keys")

    tool_tbl: Any = parsed["tool"]
    topmark_tbl: Any = tool_tbl["topmark"]
    assert topmark_tbl["answer"] == 42

    # 2) Comments/whitespace should be preserved in the text form
    assert "# leading comment" in wrapped
    # Optional: check that we really got a section header
    assert "[tool.topmark]" in wrapped


def test_nest_toml_under_section_rejects_empty_section() -> None:
    """Ensure that an empty section path is rejected.

    Passing an empty or dot-only section path would produce an invalid or
    ambiguous nesting; we guard against this by raising ValueError/RuntimeError.
    """
    source = "a = 1\n"

    # Adjust to whatever error type you use in io.py (ValueError/RuntimeError/etc.)
    import pytest

    with pytest.raises((ValueError, RuntimeError)):
        nest_toml_under_section(source, "")


def test_nest_toml_under_section_preserves_postamble() -> None:
    """Ensure postamble is preserved after nesting TOML document under [tool.topmark].

    A simple TOML document with a trailing comment should end up nested under
    [tool.topmark], with the trailing comment still present after the nested
    section in the rendered text.
    """
    source = "answer = 42\n\n# trailing comment\n"
    wrapped: str = nest_toml_under_section(source, "tool.topmark")

    # 1) The wrapped document should still be valid TOML
    parsed: Any = tomlkit.parse(wrapped)

    assert "tool" in parsed
    assert hasattr(parsed["tool"], "keys")
    assert "topmark" in parsed["tool"]
    assert hasattr(parsed["tool"]["topmark"], "keys")

    tool_tbl: Any = parsed["tool"]
    topmark_tbl: Any = tool_tbl["topmark"]
    assert topmark_tbl["answer"] == 42

    # 2) The trailing comment should still be present in the text form
    assert "# trailing comment" in wrapped

    # Optional: sanity check that the table header is present and the comment
    # comes after it somewhere.
    header_index: int = wrapped.index("[tool.topmark]")
    comment_index: int = wrapped.index("# trailing comment")
    assert comment_index > header_index


def test_get_string_list_value_filters_and_records_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-string items are dropped and recorded as warnings with location."""
    caplog.set_level("WARNING")
    diagnostics = DiagnosticLog()
    logger: TopmarkLogger = get_logger(__name__)

    table = {"k": ["a", 1, True, "b"]}
    out: list[str] = get_string_list_value_checked(
        table,
        "k",
        where="[files]",
        diagnostics=diagnostics,
        logger=logger,
    )

    assert out == ["a", "b"]

    # Two non-string entries: 1 and True
    assert any("Ignoring non-string entry in [files].k" in r.message for r in caplog.records)
    assert (
        sum(1 for r in caplog.records if "Ignoring non-string entry in [files].k" in r.message) == 2
    )
    assert sum(1 for d in diagnostics if "Ignoring non-string entry in [files].k" in d.message) == 2


def test_nest_toml_under_section_is_idempotent() -> None:
    """nest_toml_under_section idempotency when already nested."""
    source: str = """
    [tool.topmark]
    answer = 42
    """.lstrip()

    wrapped1: str = nest_toml_under_section(source, "tool.topmark")
    wrapped2: str = nest_toml_under_section(wrapped1, "tool.topmark")

    # still valid TOML and still one nested answer
    parsed_doc: tomlkit.TOMLDocument = tomlkit.parse(wrapped2)
    parsed: Any = parsed_doc
    assert parsed["tool"]["topmark"]["answer"] == 42


def test_get_string_list_value_wrong_type_returns_empty_and_records_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """get_string_list_value_checked wrong-type is treated as empty but warns."""
    caplog.set_level("WARNING")
    diagnostics = DiagnosticLog()
    logger: TopmarkLogger = get_logger(__name__)

    table: dict[str, Any] = {"k": True}  # wrong shape
    out: list[str] = get_string_list_value_checked(
        table,
        "k",
        where="[files]",
        diagnostics=diagnostics,
        logger=logger,
    )
    assert out == []

    assert any("Expected list" in r.message for r in caplog.records)
    assert any("Expected list" in d.message for d in diagnostics)

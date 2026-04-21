# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_validation_error.py
#   file_relpath : tests/config/test_config_validation_error.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for `ConfigValidationError` and its boundary-flattening behavior.

This module verifies that:
- staged validation logs (TOML-source, merged-config, runtime-applicability)
  are summarized correctly in the exception message
- flattened compatibility diagnostics are attached at the exception boundary
  in stable stage order

These tests lock the post-refactor contract where staged validation is the
internal model and flattening occurs only at reporting/exception boundaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.config.validation import ValidationLogs
from topmark.core.errors import ConfigValidationError

if TYPE_CHECKING:
    from topmark.diagnostic.model import DiagnosticLog
    from topmark.diagnostic.model import FrozenDiagnosticLog


# --- Helpers ---


def _extract_error_context(error: Exception) -> object:
    """Return the stored `ErrorContext` from a `TopmarkError`-like exception.

    The exact storage attribute is an implementation detail of the shared error
    base classes, so these tests tolerate a few equivalent shapes as long as an
    `ErrorContext`-like object is recoverable.
    """
    for attr_name in ("context", "error_context"):
        ctx: object | None = getattr(error, attr_name, None)
        if ctx is not None:
            return ctx

    if error.args:
        first_arg: object = error.args[0]
        if hasattr(first_arg, "message"):
            return first_arg

    raise AssertionError("Could not recover ErrorContext from ConfigValidationError")


# --- ConfigValidationError ---


@pytest.mark.parametrize(
    ("strict_config_checking", "strict_fragment"),
    [
        (True, "strict = True"),
        (False, "strict = False"),
    ],
)
def test_config_validation_error_message_summarizes_stage_counts(
    *,
    strict_config_checking: bool,
    strict_fragment: str,
) -> None:
    """The error message should summarize counts for each validation stage."""
    logs = ValidationLogs()
    logs.toml_source.add_error("unknown top-level key")
    logs.toml_source.add_warning("missing known section")
    logs.merged_config.add_warning("duplicate include file types")
    logs.runtime_applicability.add_error("invalid include_file_types entry")

    err = ConfigValidationError(
        validation_logs=logs,
        strict_config_checking=strict_config_checking,
    )

    message: str = str(err)
    assert strict_fragment in message
    assert "TOML errors: 1, warnings: 1;" in message
    assert "Merged-config errors: 0, warnings: 1;" in message
    assert "Runtime errors: 1, warnings: 0;" in message


def test_config_validation_error_attaches_flattened_diagnostics_in_stage_order() -> None:
    """The attached diagnostics should be the flattened compatibility view."""
    logs = ValidationLogs()
    logs.toml_source.add_warning("toml warning")
    logs.merged_config.add_warning("merged warning")
    logs.runtime_applicability.add_warning("runtime warning")

    err = ConfigValidationError(
        validation_logs=logs,
        strict_config_checking=False,
    )

    ctx: object = _extract_error_context(err)
    diagnostics: DiagnosticLog | FrozenDiagnosticLog | None = getattr(ctx, "diagnostics", None)
    assert diagnostics is not None

    items = list(getattr(diagnostics, "items", diagnostics))
    assert [item.message for item in items] == [
        "toml warning",
        "merged warning",
        "runtime warning",
    ]


def test_config_validation_error_attaches_empty_flattened_diagnostics_when_logs_empty() -> None:
    """Empty staged logs should still attach an empty flattened diagnostics view."""
    logs = ValidationLogs()

    err = ConfigValidationError(
        validation_logs=logs,
        strict_config_checking=False,
    )

    ctx: object = _extract_error_context(err)
    diagnostics: DiagnosticLog | FrozenDiagnosticLog | None = getattr(ctx, "diagnostics", None)
    assert diagnostics is not None

    items = list(getattr(diagnostics, "items", diagnostics))
    assert items == []

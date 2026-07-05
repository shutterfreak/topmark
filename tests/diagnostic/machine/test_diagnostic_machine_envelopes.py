# topmark:header:start
#
#   project      : TopMark
#   file         : test_diagnostic_machine_envelopes.py
#   file_relpath : tests/diagnostic/machine/test_diagnostic_machine_envelopes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for shared diagnostic NDJSON envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from topmark.core.machine.schemas import MetaPayload
from topmark.diagnostic.machine.envelopes import iter_diagnostic_ndjson_records
from topmark.diagnostic.model import Diagnostic
from topmark.diagnostic.model import DiagnosticLevel
from topmark.diagnostic.model import DiagnosticStats

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Mapping


@dataclass(frozen=True, kw_only=True, slots=True)
class _Diagnostics:
    """Small diagnostic container for envelope contract tests."""

    entries: tuple[Diagnostic, ...]

    def __iter__(self) -> Iterator[Diagnostic]:
        """Yield diagnostic entries."""
        return iter(self.entries)

    def stats(self) -> DiagnosticStats:
        """Return aggregate counts."""
        return DiagnosticStats(n_info=0, n_warning=len(self.entries), n_error=0)

    def to_dict(self) -> Mapping[str, int]:
        """Return aggregate counts as a mapping."""
        return {"warning": len(self.entries)}


class _ExternalLevel(Enum):
    """Enum-like level used to lock down tolerant string conversion."""

    NOTICE = "notice"


class _OpaqueLevel:
    """Level object without a string value used for fallback coercion."""

    def __str__(self) -> str:
        """Return a stable fallback level string."""
        return "opaque-level"


def _machine_meta() -> MetaPayload:
    """Return stable test metadata payload."""
    return MetaPayload(tool="topmark", version="test", platform="test")


def test_diagnostic_ndjson_records_use_stable_domain_and_message_shape() -> None:
    """Shared diagnostic records should preserve domain, level, and message keys."""
    diagnostics = _Diagnostics(
        entries=(Diagnostic(level=DiagnosticLevel.WARNING, message="careful"),),
    )

    records: list[dict[str, object]] = list(
        iter_diagnostic_ndjson_records(
            meta=_machine_meta(),
            domain="config",
            diagnostics=diagnostics,
        )
    )

    assert records == [
        {
            "kind": "diagnostic",
            "meta": {"tool": "topmark", "version": "test", "platform": "test"},
            "diagnostic": {
                "domain": "config",
                "level": "warning",
                "message": "careful",
            },
        }
    ]


def test_diagnostic_ndjson_accepts_string_valued_external_levels() -> None:
    """Shared diagnostics tolerate enum-like levels from other domains."""
    diagnostic = Diagnostic(level=DiagnosticLevel.WARNING, message="heads up")
    object.__setattr__(diagnostic, "level", _ExternalLevel.NOTICE)
    diagnostics = _Diagnostics(entries=(diagnostic,))

    records: list[dict[str, object]] = list(
        iter_diagnostic_ndjson_records(
            meta=_machine_meta(),
            domain="external",
            diagnostics=diagnostics,
        )
    )

    assert records[0]["diagnostic"] == {
        "domain": "external",
        "level": "notice",
        "message": "heads up",
    }


def test_diagnostic_ndjson_falls_back_to_stringified_levels() -> None:
    """Shared diagnostics stringify unexpected level objects deterministically."""
    diagnostic = Diagnostic(level=DiagnosticLevel.WARNING, message="fallback")
    object.__setattr__(diagnostic, "level", _OpaqueLevel())
    diagnostics = _Diagnostics(entries=(diagnostic,))

    records: list[dict[str, object]] = list(
        iter_diagnostic_ndjson_records(
            meta=_machine_meta(),
            domain="external",
            diagnostics=diagnostics,
        )
    )

    assert records[0]["diagnostic"] == {
        "domain": "external",
        "level": "opaque-level",
        "message": "fallback",
    }

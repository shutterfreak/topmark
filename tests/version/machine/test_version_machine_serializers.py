# topmark:header:start
#
#   project      : TopMark
#   file         : test_version_machine_serializers.py
#   file_relpath : tests/version/machine/test_version_machine_serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit contract tests for version machine serializers and envelopes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import MetaPayload
from topmark.version.machine.envelopes import iter_version_ndjson_records
from topmark.version.machine.payloads import VersionPayloadResult
from topmark.version.machine.serializers import serialize_version

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def _machine_meta() -> MetaPayload:
    """Return stable test metadata payload."""
    return MetaPayload(
        tool="topmark",
        version="test",
        platform="test",
    )


def test_version_serializer_rejects_human_output_format() -> None:
    """Version machine serializer should fail closed for human formats."""
    with pytest.raises(ValueError, match="Unsupported machine-readable output format"):
        serialize_version(
            meta=_machine_meta(),
            fmt=OutputFormat.TEXT,
            semver=False,
        )


def test_version_ndjson_emits_diagnostic_after_semver_fallback(
    monkeypatch: MonkeyPatch,
) -> None:
    """SemVer fallback diagnostics remain a second NDJSON record."""

    def build_fallback_payload(*, semver: bool) -> VersionPayloadResult:
        assert semver is True
        return VersionPayloadResult(
            payload={"version": "1.2.3.post1", "version_format": "pep440"},
            err=ValueError("Post-releases are not valid SemVer"),
        )

    monkeypatch.setattr(
        "topmark.version.machine.envelopes.build_version_payload",
        build_fallback_payload,
    )

    records: list[dict[str, object]] = list(
        iter_version_ndjson_records(
            meta=_machine_meta(),
            semver=True,
        )
    )

    assert [record["kind"] for record in records] == ["version", "diagnostic"]
    assert records[0]["version"] == {"version": "1.2.3.post1", "version_format": "pep440"}
    assert records[1]["diagnostic"] == {
        "domain": "version",
        "level": "warning",
        "message": "Post-releases are not valid SemVer",
    }


def test_version_ndjson_serializer_yields_single_newline_terminated_chunk() -> None:
    """Version NDJSON serializer keeps the CLI-friendly chunk contract."""
    chunks: list[str] = list(
        serialize_version(
            meta=_machine_meta(),
            fmt=OutputFormat.NDJSON,
            semver=False,
        )
    )

    assert len(chunks) == 1
    assert chunks[0].endswith("\n")
    assert json.loads(chunks[0])["kind"] == "version"

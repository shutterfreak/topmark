# topmark:header:start
#
#   project      : TopMark
#   file         : test_payloads.py
#   file_relpath : tests/core/machine/test_payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for shared machine-readable metadata payload builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.core.machine import payloads
from topmark.core.machine.payloads import build_meta_payload
from topmark.core.machine.payloads import with_detail_level
from topmark.core.machine.schemas import DetailLevel
from topmark.core.machine.schemas import MachineMetaKey

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_machine_meta_keys_use_literal_json_field_names() -> None:
    """Machine metadata enum values should remain stable JSON field names."""
    assert MachineMetaKey.PYTHON_VERSION.value == "python_version"
    assert MachineMetaKey.MACHINE.value == "machine"


def test_build_meta_payload_includes_normalized_runtime_provenance(
    monkeypatch: MonkeyPatch,
) -> None:
    """Base metadata should include normalized Python release and architecture."""
    build_meta_payload.cache_clear()
    monkeypatch.setattr(
        payloads.platform,
        "python_version",
        lambda: "3.15.0",
    )
    monkeypatch.setattr(
        payloads.platform,
        "machine",
        lambda: "test-machine",
    )

    meta: payloads.MetaPayload = build_meta_payload()
    assert meta == {
        "tool": "topmark",
        "version": meta["version"],
        "platform": meta["platform"],
        "python_version": "3.15.0",
        "machine": "test-machine",
    }


def test_meta_payload_is_process_stable_and_detail_projection_preserves_it(
    monkeypatch: MonkeyPatch,
) -> None:
    """Cached provenance and its detail projection should not re-query platform helpers."""
    build_meta_payload.cache_clear()
    python_versions: list[str] = ["3.15.0", "3.15.1"]
    machines: list[str] = ["first-machine", "second-machine"]
    monkeypatch.setattr(
        payloads.platform,
        "python_version",
        lambda: python_versions.pop(0),
    )
    monkeypatch.setattr(
        payloads.platform,
        "machine",
        lambda: machines.pop(0),
    )

    base: payloads.MetaPayload = build_meta_payload()
    assert build_meta_payload() is base
    detailed: payloads.DetailedMetaPayload = with_detail_level(
        base,
        show_details=True,
    )

    assert base["python_version"] == "3.15.0"
    assert base["machine"] == "first-machine"
    assert detailed["python_version"] == base["python_version"]
    assert detailed["machine"] == base["machine"]
    assert detailed["detail_level"] is DetailLevel.LONG
    assert python_versions == ["3.15.1"]
    assert machines == ["second-machine"]
    build_meta_payload.cache_clear()

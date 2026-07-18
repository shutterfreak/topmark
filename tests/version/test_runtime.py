# topmark:header:start
#
#   project      : TopMark
#   file         : test_runtime.py
#   file_relpath : tests/version/test_runtime.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for deterministic runtime version selection."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import pytest

from topmark.version import runtime
from topmark.version.runtime import compute_version_info
from topmark.version.types import VersionInfo

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_compute_version_info_without_semver_returns_runtime_version_untouched(
    monkeypatch: MonkeyPatch,
) -> None:
    """PEP 440 selection should not enter the conversion boundary."""
    monkeypatch.setattr(
        runtime,
        "TOPMARK_VERSION",
        "1.2.3rc4.dev5+gabc123",
    )

    def unexpected_conversion(version: str) -> str:
        pytest.fail(f"converter unexpectedly called for {version!r}")

    monkeypatch.setattr(runtime, "convert_pep440_to_semver", unexpected_conversion)

    assert compute_version_info(semver=False) == VersionInfo(
        version_text="1.2.3rc4.dev5+gabc123",
        version_format="pep440",
        err=None,
    )


def test_compute_version_info_converts_once_when_semver_is_requested(
    monkeypatch: MonkeyPatch,
) -> None:
    """SemVer selection should call the converter exactly once and expose its result."""
    monkeypatch.setattr(
        runtime,
        "TOPMARK_VERSION",
        "2.3.4b12.dev34+local.1",
    )
    calls: list[str] = []

    def convert(version: str) -> str:
        calls.append(version)
        return "2.3.4-beta.12.dev.34+local.1"

    monkeypatch.setattr(
        runtime,
        "convert_pep440_to_semver",
        convert,
    )

    result: VersionInfo = compute_version_info(semver=True)

    assert calls == ["2.3.4b12.dev34+local.1"]
    assert result == VersionInfo(
        version_text="2.3.4-beta.12.dev.34+local.1",
        version_format="semver",
        err=None,
    )
    assert compute_version_info(semver=True) == result


def test_compute_version_info_retains_value_error_and_pep440_fallback(
    monkeypatch: MonkeyPatch,
) -> None:
    """Conversion errors should remain attached to the untouched fallback version."""
    monkeypatch.setattr(
        runtime,
        "TOPMARK_VERSION",
        "1.2.3.post4",
    )
    conversion_error = ValueError("cannot represent post release")

    def fail_conversion(version: str) -> str:
        assert version == "1.2.3.post4"
        raise conversion_error

    monkeypatch.setattr(
        runtime,
        "convert_pep440_to_semver",
        fail_conversion,
    )

    result: VersionInfo = compute_version_info(semver=True)

    assert result.version_text == "1.2.3.post4"
    assert result.version_format == "pep440"
    assert result.err is conversion_error


def test_compute_version_info_does_not_swallow_unexpected_failures(
    monkeypatch: MonkeyPatch,
) -> None:
    """Only the converter's documented ValueError should trigger fallback."""
    monkeypatch.setattr(
        runtime,
        "TOPMARK_VERSION",
        "1.2.3",
    )

    def fail_unexpectedly(version: str) -> str:
        raise RuntimeError(f"unexpected failure for {version}")

    monkeypatch.setattr(
        runtime,
        "convert_pep440_to_semver",
        fail_unexpectedly,
    )

    with pytest.raises(RuntimeError, match="unexpected failure for 1.2.3"):
        compute_version_info(semver=True)


def test_version_info_is_frozen_and_has_value_equality() -> None:
    """The typed result should remain immutable and comparable by field value."""
    left = VersionInfo(
        version_text="1.2.3",
        version_format="pep440",
        err=None,
    )
    right = VersionInfo(
        version_text="1.2.3",
        version_format="pep440",
        err=None,
    )

    assert left == right
    with pytest.raises(FrozenInstanceError):
        left.version_text = "2.0.0"  # pyright: ignore[reportAttributeAccessIssue]

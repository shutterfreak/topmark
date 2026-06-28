# topmark:header:start
#
#   project      : TopMark
#   file         : test_version.py
#   file_relpath : tests/utils/test_version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Version utility contract tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.utils import version as version_utils
from topmark.utils.version import ComputedVersion
from topmark.utils.version import check_python_version
from topmark.utils.version import compute_version_text
from topmark.utils.version import convert_pep440_to_semver

if TYPE_CHECKING:
    from pytest import CaptureFixture
    from pytest import MonkeyPatch


@pytest.mark.parametrize(
    ("pep440_version", "expected_semver"),
    [
        ("1.2.3", "1.2.3"),
        ("1.2.3a4", "1.2.3-alpha.4"),
        ("1.2.3b4", "1.2.3-beta.4"),
        ("1.2.3rc4", "1.2.3-rc.4"),
        ("1.2.3.dev4", "1.2.3-dev.4"),
        ("1.2.3rc4.dev5", "1.2.3-rc.4.dev.5"),
        ("1.2.3+gabc123", "1.2.3+gabc123"),
        ("1.2.3rc4.dev5+gabc123", "1.2.3-rc.4.dev.5+gabc123"),
    ],
)
def test_convert_pep440_to_semver_supported_forms(
    pep440_version: str,
    expected_semver: str,
) -> None:
    """PEP 440 versions emitted by TopMark should map predictably to SemVer."""
    assert convert_pep440_to_semver(pep440_version) == expected_semver


@pytest.mark.parametrize("pep440_version", ["not-a-version", "1.2.3.post4"])
def test_convert_pep440_to_semver_rejects_unsupported_forms(pep440_version: str) -> None:
    """Unsupported PEP 440 forms should fail instead of emitting invalid SemVer."""
    with pytest.raises(ValueError, match="PEP 440|Post-releases"):
        convert_pep440_to_semver(pep440_version)


def test_compute_version_text_returns_pep440_by_default(monkeypatch: MonkeyPatch) -> None:
    """Default version computation should expose the raw PEP 440 version."""
    monkeypatch.setattr(version_utils, "TOPMARK_VERSION", "1.2.3rc1")

    result: ComputedVersion = compute_version_text(semver=False)

    assert result == ComputedVersion(
        version_text="1.2.3rc1",
        version_format="pep440",
        error=None,
    )


def test_compute_version_text_returns_semver_when_requested(monkeypatch: MonkeyPatch) -> None:
    """SemVer version computation should return converted text on success."""
    monkeypatch.setattr(version_utils, "TOPMARK_VERSION", "1.2.3rc1.dev4+gabc123")

    result: ComputedVersion = compute_version_text(semver=True)

    assert result == ComputedVersion(
        version_text="1.2.3-rc.1.dev.4+gabc123",
        version_format="semver",
        error=None,
    )


def test_compute_version_text_falls_back_to_pep440_when_semver_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    """SemVer conversion failures should retain the PEP 440 version with an error."""
    monkeypatch.setattr(version_utils, "TOPMARK_VERSION", "1.2.3.post4")

    result: ComputedVersion = compute_version_text(semver=True)

    assert result.version_text == "1.2.3.post4"
    assert result.version_format == "pep440"
    assert isinstance(result.error, ValueError)
    assert str(result.error) == "Post-releases are not valid SemVer: '1.2.3.post4'"


def test_check_python_version_accepts_supported_runtime() -> None:
    """Supported Python runtimes should pass without output."""
    check_python_version()


def test_check_python_version_exits_for_unsupported_runtime(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """Unsupported Python runtimes should print a clear stderr error and exit."""
    monkeypatch.setattr(version_utils.sys, "version_info", (3, 9, 0))
    monkeypatch.setattr(version_utils.sys, "version", "3.9.0 (test build)")

    with pytest.raises(SystemExit) as exc_info:
        check_python_version()

    assert exc_info.value.code == 1
    captured: str = capsys.readouterr().err
    assert "requires Python 3.10 or higher" in captured
    assert "Current version: 3.9.0" in captured

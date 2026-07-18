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
from topmark.version import runtime as version_runtime
from topmark.version.convert import convert_pep440_to_semver
from topmark.version.runtime import compute_version_info

if TYPE_CHECKING:
    from pytest import CaptureFixture
    from pytest import MonkeyPatch

    from topmark.version.types import VersionInfo


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


@pytest.mark.parametrize(
    ("version", "semver"),
    [
        ("1.2.3rc1", False),
        ("1.2.3rc1.dev4+gabc123", True),
        ("1.2.3.post4", True),
    ],
)
def test_legacy_and_canonical_runtime_paths_have_semantic_parity(
    monkeypatch: MonkeyPatch,
    version: str,
    semver: bool,
) -> None:
    """The compatibility result should agree with the canonical version domain."""
    monkeypatch.setattr(
        version_utils,
        "TOPMARK_VERSION",
        version,
    )
    monkeypatch.setattr(
        version_runtime,
        "TOPMARK_VERSION",
        version,
    )

    legacy_result: ComputedVersion = compute_version_text(semver=semver)
    canonical_result: VersionInfo = compute_version_info(semver=semver)

    assert legacy_result.version_text == canonical_result.version_text
    assert legacy_result.version_format == canonical_result.version_format
    assert (str(legacy_result.error) if legacy_result.error is not None else None) == (
        str(canonical_result.err) if canonical_result.err is not None else None
    )


@pytest.mark.parametrize(
    "version_info",
    [
        (3, 10, 0),
        (3, 14, 9),
    ],
)
def test_check_python_version_accepts_supported_runtime(
    monkeypatch: MonkeyPatch,
    version_info: tuple[int, int, int],
) -> None:
    """Supported Python runtimes should pass without output."""
    monkeypatch.setattr(version_utils.sys, "version_info", version_info)

    check_python_version()


@pytest.mark.parametrize(
    ("version_info", "version_text"),
    [
        ((2, 7, 18), "2.7.18"),
        ((3, 9, 0), "3.9.0"),
        ((3, 15, 0), "3.15.0"),
        ((4, 0, 0), "4.0.0"),
    ],
)
def test_check_python_version_exits_for_unsupported_runtime(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    version_info: tuple[int, int, int],
    version_text: str,
) -> None:
    """Unsupported Python runtimes should print a clear stderr error and exit."""
    monkeypatch.setattr(version_utils.sys, "version_info", version_info)
    monkeypatch.setattr(version_utils.sys, "version", f"{version_text} (test build)")

    with pytest.raises(SystemExit) as exc_info:
        check_python_version()

    assert exc_info.value.code == 1
    captured: str = capsys.readouterr().err
    assert "requires Python 3.10 through 3.14" in captured
    assert f"Current version: {version_text}" in captured

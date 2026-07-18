# topmark:header:start
#
#   project      : TopMark
#   file         : test_convert.py
#   file_relpath : tests/version/test_convert.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for TopMark's supported PEP 440 to SemVer conversion subset."""

from __future__ import annotations

import pytest

from topmark.version.convert import convert_pep440_to_semver


@pytest.mark.parametrize(
    ("pep440_version", "expected_semver"),
    [
        ("0.0.0", "0.0.0"),
        ("12.34.56", "12.34.56"),
        ("1.2.3a0", "1.2.3-alpha.0"),
        ("1.2.3a4", "1.2.3-alpha.4"),
        ("1.2.3b12", "1.2.3-beta.12"),
        ("1.2.3rc10", "1.2.3-rc.10"),
        ("1.2.3.dev42", "1.2.3-dev.42"),
        ("1.2.3.dev0", "1.2.3-dev.0"),
        ("1.2.3a4.dev5", "1.2.3-alpha.4.dev.5"),
        ("1.2.3b12.dev34", "1.2.3-beta.12.dev.34"),
        ("1.2.3rc10.dev42", "1.2.3-rc.10.dev.42"),
        ("1.2.3+gABC123.d20260718", "1.2.3+gABC123.d20260718"),
        ("1.2.3a4+gabc123", "1.2.3-alpha.4+gabc123"),
        ("1.2.3.dev5+gabc123.d20260718", "1.2.3-dev.5+gabc123.d20260718"),
        (
            "1.2.3rc10.dev42+gabc123.d20260718",
            "1.2.3-rc.10.dev.42+gabc123.d20260718",
        ),
    ],
)
def test_convert_pep440_to_semver_maps_supported_topmark_forms(
    pep440_version: str,
    expected_semver: str,
) -> None:
    """Supported TopMark-emitted forms should map without normalization."""
    assert convert_pep440_to_semver(pep440_version) == expected_semver


def test_convert_pep440_to_semver_is_deterministic_across_repeated_calls() -> None:
    """Repeated conversion should not retain or mutate shared state."""
    pep440_version = "12.34.56rc10.dev42+gabc123.d20260718"

    first_result: str = convert_pep440_to_semver(pep440_version)
    second_result: str = convert_pep440_to_semver(pep440_version)

    assert first_result == "12.34.56-rc.10.dev.42+gabc123.d20260718"
    assert second_result == first_result


@pytest.mark.parametrize(
    "pep440_version",
    [
        "not-a-version",
        "1.2",
        "1.2.3.4",
        " 1.2.3",
        "1.2.3 ",
        "prefix1.2.3suffix",
        "1!1.2.3",
        "v1.2.3",
        "1.2.3alpha1",
        "1.2.3rc",
        "1.2.3.dev",
        "1.2.3a01",
        "1.2.3.dev01",
        "1.2.3+",
        "1.2.3+local-thing",
        "01.2.3",
    ],
)
def test_convert_pep440_to_semver_rejects_inputs_outside_supported_subset(
    pep440_version: str,
) -> None:
    """General PEP 440 spellings and malformed text should fail closed."""
    with pytest.raises(ValueError, match="supported PEP 440") as exc_info:
        convert_pep440_to_semver(pep440_version)

    assert pep440_version in str(exc_info.value)


@pytest.mark.parametrize(
    "pep440_version",
    [
        "1.2.3.post0",
        "1.2.3rc1.post12",
        "1.2.3.post12.dev4+gabc123",
    ],
)
def test_convert_pep440_to_semver_rejects_post_releases_explicitly(
    pep440_version: str,
) -> None:
    """Recognized post releases should produce the actionable post-release error."""
    with pytest.raises(ValueError, match="Post-releases are not valid SemVer") as exc_info:
        convert_pep440_to_semver(pep440_version)

    assert pep440_version in str(exc_info.value)

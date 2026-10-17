# topmark:header:start
#
#   project      : TopMark
#   file         : test_documentation.py
#   file_relpath : tests/cli/test_documentation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for version-aware CLI documentation links."""

from __future__ import annotations

import pytest

from topmark.cli.documentation import command_reference_url
from topmark.cli.documentation import documentation_version_slug


@pytest.mark.parametrize(
    ("version", "expected_slug"),
    [
        ("2.0.0", "v2.0.0"),
        ("2.0.0rc1", "v2.0.0rc1"),
        ("2.0.0.post1", "v2.0.0.post1"),
        ("2.0.1.dev3", "latest"),
        ("2.0.0rc1.dev2", "latest"),
        ("2.0.0+gabc123", "latest"),
        ("not-a-version", "latest"),
        ("2.0.0+bad!", "latest"),
    ],
)
def test_documentation_version_slug(
    version: str,
    expected_slug: str,
) -> None:
    """Tagged releases use their tag slug; development builds use latest."""
    assert documentation_version_slug(version) == expected_slug


def test_command_reference_url_uses_the_version_aware_slug() -> None:
    """Command-reference URLs use the slug selected from the package version."""
    assert command_reference_url("commands/check", version="2.0.0") == (
        "https://topmark.readthedocs.io/en/v2.0.0/usage/commands/check/"
    )
    assert command_reference_url("commands/check", version="2.0.1.dev3+gabc123") == (
        "https://topmark.readthedocs.io/en/latest/usage/commands/check/"
    )

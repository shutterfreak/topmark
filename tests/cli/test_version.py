# topmark:header:start
#
#   file         : test_version.py
#   file_relpath : tests/cli/test_version.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: `version` command output.

Ensures that invoking `topmark version`:

- Exits successfully (exit code 0).
- Outputs the project name.
- Contains a semver-like string with digits and at least one dot.
"""

from tests.cli.conftest import assert_SUCCESS, run_cli


def test_version_text_contains_project_and_semver() -> None:
    """It should output the project name and a semver-like version string."""
    result = run_cli(["version"])

    assert_SUCCESS(result)

    out = result.output.lower()
    assert "topmark" in out

    # loose semver-ish check
    assert any(ch.isdigit() for ch in out) and "." in out

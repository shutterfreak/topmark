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

import re

from tests.cli.conftest import assert_SUCCESS, run_cli
from topmark.constants import TOPMARK_VERSION


def test_version_text_contains_project_and_semver() -> None:
    """It should output the project name and a semver-like version string."""
    result = run_cli(
        [
            "--no-color",  # Disable color mode fior RE pattern matching
            "version",
        ]
    )

    assert_SUCCESS(result)

    out = result.output.lower().strip()
    assert TOPMARK_VERSION in result.output

    # loose semver-ish check (e.g., 1.2.3, 1.2.3-rc.1, 1.2.3+build.5)
    semver_re = r"^\d+\.\d+\.\d+(?:[.-][0-9A-Za-z-]+)?(?:\+[0-9A-Za-z.-]+)?$"
    assert re.fullmatch(semver_re, out) is not None

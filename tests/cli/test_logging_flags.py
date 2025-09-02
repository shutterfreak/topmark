# topmark:header:start
#
#   file         : test_logging_flags.py
#   file_relpath : tests/cli/test_logging_flags.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: logging verbosity and quietness flags.

Ensures that combinations of `-v`/`-vvv` and `-q`/`-qq` parse correctly
and that invoking `topmark version` with them exits successfully.
"""

from tests.cli.conftest import assert_SUCCESS, run_cli


def test_verbose_and_quiet_flags_parse() -> None:
    """It should accept verbosity and quietness flags and exit with code 0."""
    for args in (["-v", "version"], ["-vvv", "version"], ["-q", "version"], ["-qq", "version"]):
        result = run_cli(args)

        assert_SUCCESS(result)

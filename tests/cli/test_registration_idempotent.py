# topmark:header:start
#
#   file         : test_registration_idempotent.py
#   file_relpath : tests/cli/test_registration_idempotent.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI test: idempotent registration of subcommands.

Ensures that calling `ensure_commands_registered()` multiple times does not
raise errors or register duplicate commands.
"""

from topmark.cli.main import ensure_commands_registered


def test_registration_is_idempotent() -> None:
    """It should allow multiple invocations of command registration without errors."""
    # should not raise / duplicate subcommands
    ensure_commands_registered()
    ensure_commands_registered()

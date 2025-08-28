# topmark:header:start
#
#   file         : exit_codes.py
#   file_relpath : src/topmark/cli/exit_codes.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Defines standardized exit codes used by the TopMark CLI application.

This module provides an enumeration of exit codes that the TopMark CLI uses to indicate
the outcome of its execution. These codes help users and other programs understand what
happened during the CLI run, such as success, failure, or a condition where a change would occur.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """Standardized exit codes for TopMark CLI.

    This enumeration defines exit codes returned by the TopMark CLI to indicate the result of
    its execution.

    Attributes:
        SUCCESS (int): Indicates that the CLI executed successfully without errors.
        FAILURE (int): Indicates that the CLI encountered an error or failed to complete
            its intended operation.
        WOULD_CHANGE (int): Indicates that the CLI detected changes that would be made,
            but did not apply them (e.g., a dry-run mode).

    Usage:
        Exit codes can be used in scripts or other programs to determine the outcome of
        running the TopMark CLI. For example:

        ```python
        import subprocess
        from topmark.cli.exit_codes import ExitCode

        result = subprocess.run(['topmark', 'run'])
        if result.returncode == ExitCode.SUCCESS:
            print("TopMark ran successfully.")
        elif result.returncode == ExitCode.WOULD_CHANGE:
            print("TopMark would make changes if run in apply mode.")
        else:
            print("TopMark failed.")
        ```
    """

    SUCCESS = 0
    FAILURE = 1
    WOULD_CHANGE = 2

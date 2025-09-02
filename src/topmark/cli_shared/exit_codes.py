# topmark:header:start
#
#   file         : exit_codes.py
#   file_relpath : src/topmark/cli_shared/exit_codes.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exit codes for TopMark CLI.

TopMark aligns with the BSD `sysexits` convention where practical, so that other tooling
can interpret failures consistently. The one deliberate divergence is `WOULD_CHANGE=2`,
which is used to signal a dry-run state where changes would be made; this allows
automation and tests to distinguish between a "would change" result and a usage error
(which, in Click, also defaults to 2). Tests must assert `result.exception is None`
to disambiguate TopMark's dry-run from Click's own usage errors.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """Standardized exit codes for TopMark CLI.

    TopMark follows the BSD `sysexits` convention where practical so other
    tooling can interpret failures consistently. The one deliberate
    divergence is ``WOULD_CHANGE = 2`` which TopMark uses to signal a dry-run
    state where changes would be made; tests must assert that no Click
    exception was raised (``result.exception is None``) to disambiguate from
    Click's own usage errors (which also default to 2).

    Attributes:
        SUCCESS: Successful execution with no errors.
        FAILURE: Generic failure (non-specific error). Prefer a more specific
            code if available.
        WOULD_CHANGE: Dry-run: changes would be made if ``--apply`` were set.
        USAGE_ERROR: Command-line invocation error (invalid flags/args). Mirrors
            BSD ``EX_USAGE (64)``.
        CONFIG_ERROR: Configuration error (missing/invalid/malformed config).
            Mirrors BSD ``EX_CONFIG (78)``.
        FILE_NOT_FOUND: Input path does not exist. Mirrors BSD ``EX_NOINPUT (66)``.
        PERMISSION_DENIED: Insufficient permissions (read/write). Mirrors BSD
            ``EX_NOPERM (77)``.
        IO_ERROR: I/O error reading/writing a file. Mirrors BSD ``EX_IOERR (74)``.
        ENCODING_ERROR: Text decoding/encoding error (e.g., UnicodeDecodeError).
            Mirrors BSD ``EX_DATAERR (65)``.
        UNSUPPORTED_FILE_TYPE: Known/unsupported file type encountered (skipped
            as per policy). Mirrors BSD ``EX_UNAVAILABLE (69)``.
        PIPELINE_ERROR: Internal pipeline failure (processor/step contract
            violation). Mirrors BSD ``EX_SOFTWARE (70)``.
        UNEXPECTED_ERROR: Unhandled/unknown error (last-resort). Mirrors BSD
            ``EX_SOFTWARE (70)`` but kept distinct for clarity.
    """

    SUCCESS = 0
    FAILURE = 1
    WOULD_CHANGE = 2  # deliberate divergence from sysexits; see class docstring

    # sysexits-aligned values for better interoperability
    USAGE_ERROR = 64  # EX_USAGE
    ENCODING_ERROR = 65  # EX_DATAERR
    FILE_NOT_FOUND = 66  # EX_NOINPUT
    UNSUPPORTED_FILE_TYPE = 69  # EX_UNAVAILABLE
    PIPELINE_ERROR = 70  # EX_SOFTWARE (internal error)
    IO_ERROR = 74  # EX_IOERR
    PERMISSION_DENIED = 77  # EX_NOPERM
    CONFIG_ERROR = 78  # EX_CONFIG

    # Keep a distinct bucket for unknowns; maps to the same category as PIPELINE_ERROR
    UNEXPECTED_ERROR = 255

# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/cli/emitters/text/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TEXT (ANSI-styled) emitters for the `topmark version` command.

These helpers are Click-free: they do not call Click APIs and instead write via
`ConsoleLike`.

Notes:
    Machine formats (JSON/NDJSON) are handled via the version machine serializers
    and the generic CLI machine emitter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.cli_shared.console_api import ConsoleLike


def emit_version_text(
    *,
    console: ConsoleLike,
    version_text: str,
    version_format: str,
    verbosity_level: int,
    error: Exception | None,
) -> None:
    """Emit `topmark version` output in the TEXT (ANSI-styled) format.

    Args:
        console: Console abstraction used by the CLI for styled output.
        version_text: The effective version string (SemVer or PEP 440).
        version_format: The effective format label (e.g. "semver" or "pep440").
        verbosity_level: Effective verbosity for gating extra details.
        error: Optional conversion error when SemVer conversion was requested and failed.
    """
    if verbosity_level > 0:
        console.print(
            console.styled(
                f"TopMark version ({version_format}):\n",
                bold=True,
                underline=True,
            )
        )
        console.print(f"    {console.styled(version_text, bold=True)}")
    else:
        console.print(console.styled(version_text, bold=True))

    if error is not None:
        console.print(console.styled(f"Warning: {error}", dim=True))

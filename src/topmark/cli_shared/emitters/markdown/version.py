# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/cli_shared/emitters/markdown/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown emitters for the `topmark version` command.

These helpers are Click-free: they return Markdown strings and perform no I/O.

Notes:
    Machine formats (JSON/NDJSON) are handled via the version machine serializers
    and the generic CLI machine emitter.
"""

from __future__ import annotations


def emit_version_markdown(
    *,
    version_text: str,
    version_format: str,
    error: Exception | None,
) -> str:
    """Render `topmark version` output as Markdown.

    Args:
        version_text: The effective version string (SemVer or PEP 440).
        version_format: The effective format label (e.g. "semver" or "pep440").
        error: Optional conversion error when SemVer conversion was requested and failed.

    Returns:
        A Markdown document as a single string.
    """
    lines: list[str] = [
        "# TopMark Version",
        "",
        f"**TopMark version ({version_format}): {version_text}**",
    ]

    if error is not None:
        lines.extend(["", f"> **Warning:** {error}"])

    lines.append("")
    return "\n".join(lines)

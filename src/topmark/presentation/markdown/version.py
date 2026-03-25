# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/presentation/markdown/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown renderers for the `topmark version` command.

These helpers return Markdown strings and perform no I/O.

Notes:
    Machine formats (JSON/NDJSON) are handled via the version machine serializers
    and the generic CLI machine emitter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.presentation.shared.version import VersionHumanReport


def render_version_markdown(
    report: VersionHumanReport,
) -> str:
    """Render `topmark version` output as Markdown.

    Args:
        report: The human version information report.

    Returns:
        A Markdown document as a single string.
    """
    lines: list[str] = [
        "# TopMark Version",
        "",
        f"**TopMark version ({report.version_format}): {report.version_text}**",
    ]

    if report.error is not None:
        lines.extend(["", f"> **Warning:** {report.error}"])

    lines.append("")
    return "\n".join(lines)

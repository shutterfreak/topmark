# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : src/topmark/presentation/text/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TEXT (ANSI-styled) renderers for the `topmark version` command.

These helpers only render the content, they do not write to the console.

Notes:
    Machine formats (JSON/NDJSON) are handled via the version machine serializers
    and the generic CLI machine emitter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.presentation import TextStyler
from topmark.cli.presentation import style_for_role
from topmark.core.presentation import StyleRole

if TYPE_CHECKING:
    from topmark.presentation.shared.version import VersionHumanReport


def render_version_text(report: VersionHumanReport) -> str:
    """Render `topmark version` output in the TEXT (ANSI-styled) format.

    Args:
        report: The human version information report.

    Returns:
        A text document as a single string.
    """
    # Note: the stylers already check `report.styled` so we don't need `maybe_style()`
    heading_styler: TextStyler = style_for_role(StyleRole.HEADING_TITLE, styled=report.styled)
    emphasis_styler: TextStyler = style_for_role(StyleRole.EMPHASIS, styled=report.styled)
    warning_styler: TextStyler = style_for_role(StyleRole.WARNING, styled=report.styled)

    parts: list[str] = []

    version_text: str = emphasis_styler(
        report.version_text,
    )

    if report.verbosity_level > 0:
        parts.append(
            heading_styler(
                f"TopMark version ({report.version_format}):",
            )
        )
        parts.append(f"    {version_text}")
    else:
        parts.append(version_text)

    if report.error is not None:
        parts.append(
            warning_styler(
                f"Warning: {report.error}",
            )
        )

    return "\n".join(parts)

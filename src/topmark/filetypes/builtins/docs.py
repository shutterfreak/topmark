# topmark:header:start
#
#   project      : TopMark
#   file         : docs.py
#   file_relpath : src/topmark/filetypes/builtins/docs.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Documentation and text artifacts.

Contains non-code files commonly found in repositories where either headers are
not appropriate (license text) or lightweight (Markdown).

Exports:
    FILETYPES: Concrete definitions for license text files (kept verbatim; not processed) and
        Markdown sources.

Notes:
    Markdown does not require shebang handling and typically embeds headers as
    standard Markdown blocks when configured by TopMark.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.filetypes.factory import BUILTIN_FILETYPE_FACTORY

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType

FILETYPES: list[FileType] = [
    BUILTIN_FILETYPE_FACTORY(
        local_key="license_text",
        extensions=[],
        filenames=["LICENSE", "LICENSE.txt"],
        patterns=[],
        description="License text (keep verbatim)",
        skip_processing=True,
    ),
    BUILTIN_FILETYPE_FACTORY(
        local_key="markdown",
        extensions=[".md", ".markdown"],
        filenames=[],
        patterns=[],
        description="MarkDown source files (*.md)",
    ),
]

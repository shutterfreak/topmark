# topmark:header:start
#
#   file         : base.py
#   file_relpath : src/topmark/filetypes/base.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Abstract base class for all file type implementations in TopMark.

Defines the FileType class, which represents a file type definition used to match files
and generate standardized header blocks. This base class is meant to be subclassed
by specific file type implementations.

If `skip_processing` is True, the pipeline will recognize files of this type and
skip header processing by design.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..config.logging import get_logger
from .policy import FileTypeHeaderPolicy

logger = get_logger(__name__)


@dataclass
class FileType:
    """Represents a file type recognized by TopMark.

    Attributes:
        name (str): Internal name of the file type.
        extensions (list[str]): List of file extensions associated with this type.
        description (str): Human-readable description of the file type.

    If `skip_processing` is True, the pipeline will recognize files of this type and
    skip header processing by design.
    """

    name: str
    extensions: list[str]
    filenames: list[str]
    patterns: list[str]
    description: str
    # When True, TopMark recognizes this file type but will skip header processing.
    # Useful for formats that do not support comments (e.g., JSON), marker files, or LICENSE texts.
    skip_processing: bool = False
    # TODO: call-back for checking the file type based on the file contents
    #       rather than the file name
    content_matcher: Callable[[Path], bool] | None = None
    header_policy: FileTypeHeaderPolicy | None = None

    def matches(self, path: Path) -> bool:
        """Determine if the file type matches the given file path.

        This method must be implemented by subclasses to define matching logic.

        Args:
            path: The path to the file to check.

        Returns:
            True if the file matches this file type, False otherwise.
        """
        # Extension match (simple suffix)
        if path.suffix in self.extensions:
            return True

        # Filenames: support exact basename or tail subpath matches
        # Examples:
        #   - "settings.json" matches only if basename == "settings.json"
        #   - ".vscode/settings.json" matches if path.as_posix().endswith(".vscode/settings.json")
        if self.filenames:
            basename = path.name
            posix = path.as_posix()
            for fname in self.filenames:
                if "/" in fname or "\\" in fname:
                    if posix.endswith(fname):
                        return True
                else:
                    if basename == fname:
                        return True

        # Regex patterns against basename
        for pattern in self.patterns:
            if re.fullmatch(pattern, path.name):
                return True
        if self.content_matcher:
            try:
                return self.content_matcher(path)
            except Exception:
                return False
        return False

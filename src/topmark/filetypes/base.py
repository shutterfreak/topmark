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
from enum import Enum
from pathlib import Path

from topmark.config.logging import get_logger
from topmark.filetypes.policy import FileTypeHeaderPolicy

logger = get_logger(__name__)


class ContentGate(Enum):
    """Policy that controls *when* a `FileType.content_matcher` may run.

    Use a gate to prevent accidental matches (e.g., Markdown containing `//`).
    Most overlay types like JSON-with-comments should use `IF_EXTENSION` so that
    content probing only occurs when the file already looks like the family by
    extension.

    Members:
        NEVER: Never evaluate the content matcher.
        IF_EXTENSION: Probe content only if an extension matched.
        IF_FILENAME: Probe content only if a filename/tail matched.
        IF_PATTERN: Probe content only if a regex pattern matched.
        IF_ANY_NAME_RULE: Probe if any name rule matched (extension OR filename OR
            pattern).
        IF_NONE: Probe only when the type has **no** name rules declared (pure
            content types).
        ALWAYS: Always evaluate the content matcher (use sparingly).
    """

    NEVER = "never"
    IF_EXTENSION = "if_extension"
    IF_FILENAME = "if_filename"
    IF_PATTERN = "if_pattern"
    IF_ANY_NAME_RULE = "if_any_name_rule"
    IF_NONE = "if_none"  # only when no name rules are declared
    ALWAYS = "always"  # use sparingly


@dataclass
class FileType:
    r"""Represents a file type recognized by TopMark.

    A *file type* describes how TopMark recognizes files on disk and whether they
    are eligible for header processing. Recognition can be based on filename
    extension, exact filename, regex pattern, and optionally **file content** via
    :attr:`content_matcher`.

    Attributes:
        name: Internal identifier of the file type (e.g. ``"python"``).
        extensions: List of filename extensions associated with this type. Values
            should include the leading dot (e.g. ``.py``) or be consistent with the
            matcher used elsewhere in TopMark.
        filenames: Exact filenames or tail subpaths to match. If a value contains a
            path separator (``/`` or ``\\``), it is matched against the *tail* of the
            path (e.g. ``".vscode/settings.json"``). Otherwise, it must equal the
            basename exactly (e.g. ``"Makefile"``).
        patterns: Regular expressions evaluated against the basename (see
            :func:`re.fullmatch`). Useful for families of files that don't share a
            simple extension.
        description: Human‑readable description of the file type.
        skip_processing: When ``True``, the pipeline **recognizes** files of this
            type but intentionally **skips header processing** (e.g. JSON without
            comments, LICENSE files). This lets discovery work while keeping writes
            disabled by design.
        content_matcher: Optional callable ``(Path) -> bool`` that performs
            *content-based* recognition when name-based heuristics are
            ambiguous. TopMark calls this **last** in :meth:`matches` after
            testing extensions, filenames, and patterns. The callable should be
            fast, side‑effect free, and return ``True`` if the file is of this
            type. It must **not** raise; exceptions are caught and treated as
            non‑matches.
        content_gate: Gate that controls when the content matcher is consulted.
        header_policy: Optional :class:`FileTypeHeaderPolicy` that tunes placement
            (e.g., shebang handling) and scanning windows around the expected
            insertion anchor.

    Content‑based recognition (example)
    ----------------------------------
    A practical use case is differentiating *commented JSON* (CJSON) from plain
    JSON. File names like ``config.json`` might be CJSON (supports line comments)
    and thus can carry TopMark headers. You can provide a *CJSON* file type with a
    ``content_matcher`` that inspects the file for comment tokens (e.g. ``//`` or
    ``/* ... */``) while avoiding naïve false positives:

    >> def looks_like_cjson(path: Path) -> bool:
    >>     try:
    >>         text = path.read_text(encoding="utf-8", errors="ignore")
    >>     except OSError:
    >>         return False
    >>     # Heuristics: allow // or /* */ outside of strings (simple check)
    >>     return "//" in text or "/*" in text

    Registering such a file type makes TopMark **recognize** these files; pairing
    it with a suitable header processor makes them **supported** for processing.

    Notes:
        * :meth:`matches` first tries extensions, filenames, and regex patterns.
          Only if those fail and :attr:`content_matcher` is set will it call the
          matcher to decide.
        * Content matchers should read a small portion of the file where possible
          to remain fast on large trees. The current implementation leaves that
          policy to the callable to keep the base class simple.
    """

    name: str
    extensions: list[str]
    filenames: list[str]
    patterns: list[str]
    description: str
    # When True, TopMark recognizes this file type but will skip header processing.
    # Useful for formats that do not support comments (e.g., JSON), marker files, or LICENSE texts.
    skip_processing: bool = False
    # Call-back for checking the file type based on the file contents rather than the file name
    content_matcher: Callable[[Path], bool] | None = None
    # Gate defining when the matcher should trigger a match
    content_gate: ContentGate = ContentGate.NEVER
    header_policy: FileTypeHeaderPolicy | None = None

    # Compiled regex patterns (cached)
    _compiled_patterns: list[re.Pattern[str]] | None = None

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

        # Regex patterns against basename (cached)
        if self.patterns:
            if self._compiled_patterns is None:
                try:
                    self._compiled_patterns = [re.compile(p) for p in self.patterns]
                except re.error:
                    self._compiled_patterns = []
            for regex in self._compiled_patterns:
                if regex.fullmatch(path.name):
                    return True
        if self.content_matcher:
            try:
                return self.content_matcher(path)
            except Exception:
                return False
        return False

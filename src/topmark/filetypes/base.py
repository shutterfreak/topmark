# topmark:header:start
#
#   project      : TopMark
#   file         : base.py
#   file_relpath : src/topmark/filetypes/base.py
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

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Final, Protocol, TypedDict, runtime_checkable

from topmark.config.logging import TopmarkLogger, get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.filetypes.policy import FileTypeHeaderPolicy

logger: TopmarkLogger = get_logger(__name__)


class ContentGate(Enum):
    """Policy that controls *when* a `FileType.content_matcher` may run.

    Use a gate to prevent accidental matches (e.g., Markdown containing `//`).
    Most overlay types like JSON-with-comments should use `IF_EXTENSION` so that
    content probing only occurs when the file already looks like the family by
    extension.

    Attributes:
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


@runtime_checkable
class ContentMatcher(Protocol):
    """Protocol for content-based file type matchers.

    A content matcher is a callable that inspects a file's contents to determine
    if it matches a specific file type. This is useful for file types that cannot
    be reliably identified by name alone. The matcher should be fast, side-effect
    free, and return True if the file is of the expected type.
    """

    def __call__(self, path: Path) -> bool:
        """Check if the file at `path` matches the expected type.

        Args:
            path (Path): The path to the file to check.

        Returns:
            bool: True if the file matches the expected type, False otherwise.

        """
        ...


class InsertCapability(Enum):
    """Advisory on whether a header insertion is advisable in the current context.

    Attributes:
        UNEVALUATED: No checker result yet.
        OK: Insertion is advisable.
        SKIP_UNSUPPORTED_CONTENT: Insertion should be skipped because the file
            content is not suitable (e.g., XML prolog-only files).
        SKIP_POLICY: Insertion should be skipped due to policy (e.g., file type
            configured to skip processing).
        SKIP_READONLY: Insertion should be skipped because the file is read-only
            (future use; not implemented yet).
        SKIP_IDEMPOTENCE_RISK: Skip because we cannot guarantee insert→strip idempotence
            (e.g., insertion would reflow a physical line or introduce ambiguous
            blank-line padding).
        SKIP_OTHER: Insertion should be skipped for other reasons (e.g., pre-insert
            checks failed).
    """

    UNEVALUATED = "unevaluated"  # no checker result yet
    OK = "ok"
    SKIP_UNSUPPORTED_CONTENT = "skip_unsupported_content"  # e.g., XML prolog-only
    SKIP_POLICY = "skip_policy"  # e.g., policy says no
    SKIP_READONLY = "skip_readonly"  # future: fs flags
    SKIP_IDEMPOTENCE_RISK = (
        "skip_idempotence_risk"  # e.g., would introduce reflow which might break idempotence
    )
    SKIP_OTHER = "skip_other"


class InsertCheckResult(TypedDict, total=False):
    """Result of a pre-insert check.

    Attributes:
        capability (InsertCapability): Advisory on whether insertion is OK
            or should be skipped (and why).
        reason (str, optional): Human-readable explanation for the advisory.
        origin (str): Origin of the result
    """

    capability: InsertCapability
    reason: str
    origin: str


@runtime_checkable
class PreInsertContextView(Protocol):
    """Minimal view of ProcessingContext for pre-insert checkers.

    This protocol defines the minimal set of attributes that a ProcessingContext
    must have to be used by pre-insert checkers. It allows checkers to be defined
    without depending on the full ProcessingContext class.
    """

    # The minimal attributes checkers need; add more if needed later
    file_lines: list[str] | None
    newline_style: str
    header_processor: Any  # concrete checker can cast to its processor class if needed
    file_type: "FileType | None"


@runtime_checkable
class InsertChecker(Protocol):
    """Protocol for pre-insert checkers associated with a FileType.

    A pre-insert checker is a callable that inspects the current processing context
    before a header insertion is attempted. It can advise whether insertion is
    advisable, should be skipped, or is outright disallowed.
    The checker receives a minimal view of the ProcessingContext to avoid
    unnecessary dependencies.
    """

    def __call__(self, ctx: PreInsertContextView) -> InsertCheckResult:
        """Check if insertion is advisable in the given context.

        Args:
            ctx (PreInsertContextView): The current minimal processing context.

        Returns:
            InsertCheckResult: A dictionary with:
                * `capability` (InsertCapability): Advisory on whether insertion is OK
                  or should be skipped (and why).
                * `reason` (str, optional): Human-readable explanation for the advisory.
        """
        ...


@dataclass
class FileType:
    r"""Represents a file type recognized by TopMark.

    A *file type* describes how TopMark recognizes files on disk and whether they
    are eligible for header processing. Recognition can be based on filename
    extension, exact filename, regex pattern, and optionally **file content** via
    `content_matcher`.

    Attributes:
        name (str): Internal identifier of the file type (e.g. ``"python"``).
        extensions (list[str]): List of filename extensions associated with this type. Values
            should include the leading dot (e.g. ``.py``) or be consistent with the
            matcher used elsewhere in TopMark.
        filenames (list[str]): Exact filenames or tail subpaths to match. If a value contains a
            path separator (``/`` or ``\\``), it is matched against the *tail* of the
            path (e.g. ``".vscode/settings.json"``). Otherwise, it must equal the
            basename exactly (e.g. ``"Makefile"``).
        patterns (list[str]): Regular expressions evaluated against the basename (see
            `re.fullmatch`). Useful for families of files that don't share a
            simple extension.
        description (str): Human‑readable description of the file type.
        skip_processing (bool): When ``True``, the pipeline **recognizes** files of this
            type but intentionally **skips header processing** (e.g. JSON without
            comments, LICENSE files). This lets discovery work while keeping writes
            disabled by design.
        content_matcher (ContentMatcher | None): Optional content matcher
            that performs *content-based* recognition when name-based heuristics are
            ambiguous. TopMark calls this **last** in `matches` after
            testing extensions, filenames, and patterns. The callable should be
            fast, side‑effect free, and return ``True`` if the file is of this
            type. It must **not** raise; exceptions are caught and treated as
            non‑matches.
        content_gate (ContentGate): Gate that controls when the content matcher is consulted.
        header_policy (FileTypeHeaderPolicy | None): Optional `FileTypeHeaderPolicy`
            that tunes placement (e.g., shebang handling) and scanning windows around the
            expected insertion anchor.
        pre_insert_checker (InsertChecker | None): Optional pre-insert checker:
            “may we add a TopMark header here?”

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
        * `matches` first tries extensions, filenames, and regex patterns.
          Only if those fail and `content_matcher` is set will it call the
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
    content_matcher: ContentMatcher | None = None
    # Gate defining when the matcher should trigger a match
    content_gate: ContentGate = ContentGate.NEVER
    header_policy: FileTypeHeaderPolicy | None = None
    # Optional pre-insert checker: “may we add a TopMark header here?”
    pre_insert_checker: InsertChecker | None = None

    # Compiled regex patterns (cached)
    _compiled_patterns: list[re.Pattern[str]] | None = None

    def matches(self, path: Path) -> bool:
        """Determine if the file type matches the given file path.

        This method must be implemented by subclasses to define matching logic.

        Args:
            path (Path): The path to the file to check.

        Returns:
            bool: True if the file matches this file type, False otherwise.
        """
        # Track which name rule (if any) matched; used for content gating.
        matched_by: str | None = None

        # 1) Extension match (simple suffix)
        if self.extensions and path.suffix in self.extensions:
            matched_by = "extension"
        else:
            # 2) Filenames: support exact basename or tail subpath matches
            #    - "settings.json" matches only if basename == "settings.json"
            #    - ".vscode/settings.json" matches
            #      if path.as_posix().endswith(".vscode/settings.json")
            if self.filenames:
                basename: str = path.name
                posix: str = path.as_posix()
                for fname in self.filenames:
                    if "/" in fname or "\\" in fname:
                        if posix.endswith(fname):
                            matched_by = "filename"
                            break
                    else:
                        if basename == fname:
                            matched_by = "filename"
                            break

            # 3) Regex patterns against basename (cached)
            if matched_by is None and self.patterns:
                if self._compiled_patterns is None:
                    try:
                        self._compiled_patterns = [re.compile(p) for p in self.patterns]
                    except re.error:
                        self._compiled_patterns = []
                for regex in self._compiled_patterns:
                    if regex.fullmatch(path.name):
                        matched_by = "pattern"
                        break

        # If any name rule matched and no content matcher is defined, we're done.
        if matched_by is not None and self.content_matcher is None:
            return True

        # If no name rule matched and no content matcher is defined, no match.
        if matched_by is None and self.content_matcher is None:
            return False

        # Evaluate whether the content matcher is *allowed* to run, based on the gate.
        gate: Final[ContentGate] = self.content_gate
        allow_by_gate: bool
        if gate is ContentGate.NEVER:
            allow_by_gate = False
        elif gate is ContentGate.IF_EXTENSION:
            allow_by_gate = matched_by == "extension"
        elif gate is ContentGate.IF_FILENAME:
            allow_by_gate = matched_by == "filename"
        elif gate is ContentGate.IF_PATTERN:
            allow_by_gate = matched_by == "pattern"
        elif gate is ContentGate.IF_ANY_NAME_RULE:
            allow_by_gate = matched_by is not None
        elif gate is ContentGate.IF_NONE:
            # Permit content probing only if *no* name rules exist for this type.
            allow_by_gate = not (self.extensions or self.filenames or self.patterns)
        elif gate is ContentGate.ALWAYS:
            allow_by_gate = True
        else:
            allow_by_gate = False  # safety default

        # If gate disallows probing, return the name-rule result.
        if not allow_by_gate:
            return matched_by is not None

        # Gate allows probing: consult the content matcher.
        try:
            return bool(self.content_matcher(path))  # type: ignore[misc]
        except Exception:
            return False

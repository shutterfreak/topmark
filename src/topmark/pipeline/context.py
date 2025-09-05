# topmark:header:start
#
#   file         : context.py
#   file_relpath : src/topmark/pipeline/context.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Context for header processing in the Topmark pipeline."""

from __future__ import (
    annotations,  # Enables forward references (optional in 3.12+ but good practice)
)

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, cast

from yachalk import chalk

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from topmark.config import Config
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


class BaseStatus(Enum):
    """Base class for status enums in the Topmark pipeline.

    This class serves as a common base for all status enums representing different
    phases of the header processing pipeline (e.g., file, header, generation, comparison, write).
    It provides shared utilities, such as computing the maximum value length for pretty-printing.

    Usage:
        Subclass this class to define specific statuses for each pipeline phase.
    """

    @cached_property
    def value_length(self) -> int:
        """Maximum length of the enum *value* strings for this enum type.

        Note:
            This is effectively a class-level property cached per enum member the
            first time it is accessed. Access ``SomeStatus.ANY.value_length`` to get
            the max width for ``SomeStatus``.

        Returns:
            int: The length of the longest enum value string in the subclass.
        """
        return max(len(member.value) for member in type(self))


class FileStatus(BaseStatus):
    """Represents the status of file processing in the Topmark pipeline.

    Used to indicate the result of file-level operations such as type resolution,
    exclusion, or file readability.
    """

    PENDING = "pending"
    RESOLVED = "resolved"
    EMPTY_FILE = "empty file"
    SKIPPED_NOT_FOUND = "skipped (file not found)"
    SKIPPED_FILE_ERROR = "skipped (error reading file)"
    SKIPPED_NOT_TEXT_FILE = "skipped (not a text file)"
    SKIPPED_NO_LINE_END = "skipped (no line end)"
    SKIPPED_POLICY_BOM_BEFORE_SHEBANG = "skipped (policy: BOM before shebang)"
    UNREADABLE = "unreadable"
    SKIPPED_UNSUPPORTED = "skipped (unsupported file type)"
    SKIPPED_NO_HEADER_PROCESSOR = "skipped (no header processor)"
    SKIPPED_KNOWN_NO_HEADERS = "skipped (known type: headers not supported)"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this file status.

        Returns:
            Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                FileStatus.PENDING: chalk.gray,
                FileStatus.RESOLVED: chalk.green,
                FileStatus.EMPTY_FILE: chalk.yellow,
                FileStatus.SKIPPED_NOT_FOUND: chalk.red,
                FileStatus.SKIPPED_FILE_ERROR: chalk.red_bright,
                FileStatus.SKIPPED_NOT_TEXT_FILE: chalk.red,
                FileStatus.SKIPPED_NO_LINE_END: chalk.red,
                FileStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG: chalk.red,
                FileStatus.UNREADABLE: chalk.red_bright,
                FileStatus.SKIPPED_UNSUPPORTED: chalk.yellow,
                FileStatus.SKIPPED_NO_HEADER_PROCESSOR: chalk.red,
                FileStatus.SKIPPED_KNOWN_NO_HEADERS: chalk.yellow,
            }[self],
        )


class HeaderStatus(BaseStatus):
    """Represents the status of header processing for a file in the pipeline.

    Used to indicate detection, parsing, and validation results for the file header.
    """

    PENDING = "pending"
    MISSING = "missing"
    DETECTED = "detected"
    MALFORMED = "malformed"
    EMPTY = "empty"
    ERRORED = "errored"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this header status.

        Returns:
            Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                HeaderStatus.PENDING: chalk.gray,
                HeaderStatus.MISSING: chalk.blue,
                HeaderStatus.DETECTED: chalk.green,
                HeaderStatus.MALFORMED: chalk.red_bright,
                HeaderStatus.EMPTY: chalk.yellow_bright,
                HeaderStatus.ERRORED: chalk.red_bright,
            }[self],
        )


class GenerationStatus(BaseStatus):
    """Represents the status of header generation in the pipeline.

    Used to indicate whether a new header was generated, rendered,
    or if required fields are missing.
    """

    PENDING = "pending"
    GENERATED = "generated"
    NO_FIELDS = "no fields"
    RENDERED = "rendered"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this generation status.

        Returns:
            Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                GenerationStatus.PENDING: chalk.gray,
                GenerationStatus.GENERATED: chalk.green,
                GenerationStatus.NO_FIELDS: chalk.yellow_bright,
                GenerationStatus.RENDERED: chalk.blue,
            }[self],
        )


class ComparisonStatus(BaseStatus):
    """Represents the status of comparing the current and expected header in the pipeline.

    Used to indicate if the header has changed, is unchanged, or cannot be compared.
    """

    PENDING = "pending"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    CANNOT_COMPARE = "can't compare"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this comparison status.

        Returns:
            Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                ComparisonStatus.PENDING: chalk.gray,
                ComparisonStatus.CHANGED: chalk.red,
                ComparisonStatus.UNCHANGED: chalk.green,
                ComparisonStatus.CANNOT_COMPARE: chalk.yellow_bright,
            }[self],
        )


class StripStatus(BaseStatus):
    """Represents the status of header stripping in the pipeline.

    This axis is orthogonal to scanner detection and write outcomes:
      - Scanner (HeaderStatus) tells us whether a header exists in the original file.
      - StripStatus tells us whether we prepared/performed a removal.
      - WriteStatus records the final write outcome (e.g., REMOVED on apply).
    """

    PENDING = "pending"
    NOT_NEEDED = "not needed"  # no header present to remove
    READY = "ready"  # removal prepared (updated_file_lines computed)
    FAILED = "failed"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this strip status.

        Returns:
            Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                StripStatus.PENDING: chalk.gray,
                StripStatus.NOT_NEEDED: chalk.blue,
                StripStatus.READY: chalk.green,
                StripStatus.FAILED: chalk.red_bright,
            }[self],
        )


class WriteStatus(BaseStatus):
    """Represents the status of the header write operation in the pipeline.

    Used to indicate whether the header was written, previewed, skipped, or failed.
    """

    PENDING = "pending"
    PREVIEWED = "previewed"
    WRITTEN = "written"
    SKIPPED = "skipped"
    FAILED = "failed"
    REPLACED = "replaced"
    INSERTED = "inserted"
    REMOVED = "removed"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this write status.

        Returns:
            Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                WriteStatus.PENDING: chalk.gray,
                WriteStatus.PREVIEWED: chalk.blue,
                WriteStatus.WRITTEN: chalk.green,
                WriteStatus.SKIPPED: chalk.yellow,
                WriteStatus.FAILED: chalk.red_bright,
                WriteStatus.REPLACED: chalk.green,
                WriteStatus.INSERTED: chalk.green_bright,
                WriteStatus.REMOVED: chalk.yellow_bright,
            }[self],
        )


@dataclass
class HeaderProcessingStatus:
    """Tracks the status of each processing phase for a single file.

    Fields correspond to each pipeline phase: file, header, generation, comparison, write.
    """

    file: FileStatus = FileStatus.PENDING  # Status of file-level processing
    header: HeaderStatus = HeaderStatus.PENDING  # Status of header detection/parsing
    generation: GenerationStatus = GenerationStatus.PENDING  # Status of header generation/rendering
    comparison: ComparisonStatus = ComparisonStatus.PENDING  # Status of header comparison
    write: WriteStatus = WriteStatus.PENDING  # Status of writing the header
    strip: StripStatus = StripStatus.PENDING  # Status of header stripping lifecycle


@dataclass
class ProcessingContext:
    """Context for header processing in the pipeline.

    This class holds all necessary information for processing a file's header,
    including the file path, configuration, detected header state, and derived
    header fields. It is used to pass data between different stages of the
    header processing pipeline.

    Attributes:
        path (Path): The file path to process.
        config (Config): The configuration for processing.
        file_type (FileType | None): The resolved file type, if applicable.
        status (HeaderProcessingStatus): Processing status for each pipeline phase.
        header_processor (HeaderProcessor | None): The header processor instance for this file.
        file_lines (list[str] | None): The full original file content as list of lines.
        leading_bom (bool): True when the original file began with a UTF-8 BOM
            ("\ufeff"). The reader sets this and strips the BOM from memory; the
            updater re-attaches it to the final output.
        newline_style: str: The newline stile in the file (``LF``, ``CR``, ``CRLF``).
        ends_with_newline: bool | None: True if the file ends with a newline.
        existing_header_range (tuple[int, int] | None): The (start, end) line numbers
            of the existing header.
        existing_header_block (str | None): The text block of the existing header.
        existing_header_lines (list[str] | None): Raw lines of the existing header from the file.
        existing_header_dict (dict[str, str] | None): Parsed fields from the existing header.
        builtin_fields (dict[str, str] | None): Built-in/derived fields
            based on the file and config.
        expected_header_block (str | None): The fully formatted expected header text.
        expected_header_lines (list[str] | None): Raw lines of the expected header.
        expected_header_dict (dict[str, str] | None): Final rendered fields before formatting.
        updated_file_lines: list[str] | None: Updated file content as a list of lines
        header_diff: str | None: Unified diff (patch) for patching (updating) the header
        diagnostics (list[str]): Any warnings or errors encountered during processing.
    """

    # 📁 1. File input context
    path: Path  # The file path to process (absolute or relative to working directory)
    config: "Config"  # Active config at time of processing
    file_type: "FileType | None" = None  # Resolved file type (e.g., PythonFileType)
    status: HeaderProcessingStatus = field(default_factory=HeaderProcessingStatus)
    header_processor: "HeaderProcessor | None" = (
        None  # HeaderProcessor instance for this file type, if applicable
    )
    file_lines: list[str] | None = None  # Original file content as a list of lines
    leading_bom: bool = False  # True if original file began with a UTF-8 BOM
    has_shebang: bool = False  # True if the first line starts with '#!' (post-BOM normalization)
    newline_style: str = "\n"  # Newline style (default = "\n")
    ends_with_newline: bool | None = None  # True if file ends with a newline sequence

    # 🔍 2. Existing header (detected from original file)
    existing_header_range: tuple[int, int] | None = (
        None  # (start_line, end_line) of detected header
    )
    existing_header_block: str | None = None  # Text block of the detected header
    existing_header_lines: list[str] | None = None  # Raw lines of the detected header
    existing_header_dict: dict[str, str] | None = None  # Parsed fields from the detected header

    # 🧮 3. Derived and expected header state (from config + file path)
    builtin_fields: dict[str, str] | None = (
        None  # Built-in/derived fields, e.g. {"file": ..., "file_relpath": ...}
    )
    expected_header_block: str | None = None  # Fully formatted header text to be written
    expected_header_lines: list[str] | None = None  # Raw lines of the expected header
    expected_header_dict: dict[str, str] | None = None  # Final rendered fields before formatting

    # 4. Updated file and resulting diff
    updated_file_lines: list[str] | None = None  # Updated file content as a list of lines
    header_diff: str | None = None  # Unified diff (patch) for patching (updating) the header

    # Processing diagnostics: warnings/errors collected during processing
    diagnostics: list[str] = field(default_factory=lambda: [])

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable representation of this processing result.

        The schema is stable for CLI/CI consumption and avoids color/formatting.
        """
        return {
            "path": str(self.path),
            "file_type": (self.file_type.name if self.file_type else None),
            "status": {
                "file": self.status.file.name,
                "header": self.status.header.name,
                "generation": self.status.generation.name,
                "comparison": self.status.comparison.name,
                "write": self.status.write.name,
                "strip": self.status.strip.name,
            },
            "existing_header_range": self.existing_header_range,
            "has_diff": bool(self.header_diff),
            "diagnostics": list(self.diagnostics),
            # Heuristic: treat MISSING or CHANGED as a would-change indicator
            "would_change": (
                self.status.header is HeaderStatus.MISSING
                or self.status.comparison is ComparisonStatus.CHANGED
            ),
        }

    def format_summary(self) -> str:
        """Return the current human-readable per-file summary string.

        TODO: refine the rendering.
        """
        result: str = f"{self.path}: "
        if not self.file_type or self.status.file != FileStatus.RESOLVED:
            result += (
                f"{chalk.dim(self.file_type.name if self.file_type else '<unknown>')} - "
                f"{self.status.file.color('file ' + self.status.file.value)}"
            )
            return result

        result += (
            f"{chalk.dim(self.file_type.name)} - "
            f"{self.status.file.color('file ' + self.status.file.value)}"
        )
        result += f", {self.status.header.color('current header: ' + self.status.header.value)}"
        result += f", {self.status.generation.color('new header: ' + self.status.generation.value)}"
        result += f", {self.status.comparison.color('result: ' + self.status.comparison.value)}"
        result += f", {self.status.strip.color('strip: ' + self.status.strip.value)}"
        return result

    @property
    def summary(self) -> str:
        """Return a formatted summary string of the processing status for this file."""
        return self.format_summary()

    @classmethod
    def bootstrap(cls, *, path: Path, config: Config) -> ProcessingContext:
        """Create a fresh context with no derived state."""
        return cls(path=path, config=config)

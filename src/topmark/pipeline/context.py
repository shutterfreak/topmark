# topmark:header:start
#
#   project      : TopMark
#   file         : context.py
#   file_relpath : src/topmark/pipeline/context.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Context for header processing in the Topmark pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, cast

from yachalk import chalk

from topmark.config.policy import Policy, effective_policy
from topmark.filetypes.base import InsertCapability

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from topmark.config import Config
    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor

    from .views import BuilderView, DiffView, FileImageView, HeaderView, RenderView, UpdatedView


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


class FsStatus(BaseStatus):
    """Represents the status of file system checks in the pipeline.

    Used to indicate the result of existence and permission checks.
    """

    PENDING = "pending"
    OK = "ok"
    EMPTY = "empty file"
    NOT_FOUND = "not found"
    NO_READ_PERMISSION = "no read permission"
    UNREADABLE = "read error"
    NO_WRITE_PERMISSION = "no write permission"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this file system status.

        Returns:
            Callable[[str], str]: Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                FsStatus.PENDING: chalk.gray,
                FsStatus.OK: chalk.green,
                FsStatus.EMPTY: chalk.yellow,
                FsStatus.NOT_FOUND: chalk.red,
                FsStatus.NO_READ_PERMISSION: chalk.red_bright,
                FsStatus.UNREADABLE: chalk.red_bright,
                FsStatus.NO_WRITE_PERMISSION: chalk.red_bright,
            }[self],
        )


class ResolveStatus(BaseStatus):
    """Represents the status of file type resolution in the pipeline.

    Used to indicate whether the file type was successfully resolved or not.
    """

    PENDING = "pending"
    RESOLVED = "resolved"
    TYPE_RESOLVED_HEADERS_UNSUPPORTED = "known file type, headers not supported"
    TYPE_RESOLVED_NO_PROCESSOR_REGISTERED = "known file type, no header processor"
    UNSUPPORTED = "unsupported file type"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this resolve status.

        Returns:
            Callable[[str], str]: Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                ResolveStatus.PENDING: chalk.gray,
                ResolveStatus.RESOLVED: chalk.green,
                ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED: chalk.yellow,
                ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED: chalk.red,
                ResolveStatus.UNSUPPORTED: chalk.yellow,
            }[self],
        )


class ContentStatus(BaseStatus):
    """Represents the status of file content checks in the pipeline."""

    PENDING = "pending"
    OK = "ok"
    SKIPPED_NOT_TEXT_FILE = "not a text file"
    SKIPPED_MIXED_LINE_ENDINGS = "mixed line endings"
    SKIPPED_POLICY_BOM_BEFORE_SHEBANG = "BOM before shebang"
    UNREADABLE = "unreadable"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this content status.

        Returns:
            Callable[[str], str]: Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                ContentStatus.PENDING: chalk.gray,
                ContentStatus.OK: chalk.green,
                ContentStatus.SKIPPED_NOT_TEXT_FILE: chalk.red,
                ContentStatus.SKIPPED_MIXED_LINE_ENDINGS: chalk.red,
                ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG: chalk.red,
                ContentStatus.UNREADABLE: chalk.red_bright,
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
    MALFORMED_ALL_FIELDS = "malformed (all fields invalid)"
    MALFORMED_SOME_FIELDS = "malformed (some fields invalid)"
    EMPTY = "empty"
    ERRORED = "errored"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this header status.

        Returns:
            Callable[[str], str]: Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                HeaderStatus.PENDING: chalk.gray,
                HeaderStatus.MISSING: chalk.blue,
                HeaderStatus.DETECTED: chalk.green,
                HeaderStatus.MALFORMED: chalk.red_bright,
                HeaderStatus.MALFORMED_ALL_FIELDS: chalk.red_bright,
                HeaderStatus.MALFORMED_SOME_FIELDS: chalk.red_bright,
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
            Callable[[str], str]: Function to colorize a string for this status.
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
    SKIPPED = "skipped"
    CANNOT_COMPARE = "can't compare"

    @property
    def color(self) -> Callable[[str], str]:
        """Get the chalk color renderer associated with this comparison status.

        Returns:
            Callable[[str], str]: Function to colorize a string for this status.
        """
        return cast(
            "Callable[[str], str]",
            {
                ComparisonStatus.PENDING: chalk.gray,
                ComparisonStatus.CHANGED: chalk.red,
                ComparisonStatus.UNCHANGED: chalk.green,
                ComparisonStatus.SKIPPED: chalk.yellow,
                ComparisonStatus.CANNOT_COMPARE: chalk.red_bright,
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
            Callable[[str], str]: Function to colorize a string for this status.
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
            Callable[[str], str]: Function to colorize a string for this status.
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


# --- Gating helpers (replace the existing block with the definitions below) ---


def allow_empty_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if the file is empty and the effective policy allows header insertions.

    This checks the resolved per-type effective policy (global overlaid by per-type).
    """
    # If you expose a cached effective policy, use that; else compute via `effective_policy(...)`.
    # Assuming `ctx.file_type` is set when resolve == RESOLVED.
    try:
        eff: Policy = effective_policy(ctx.config, ctx.file_type.name if ctx.file_type else None)
    except Exception:
        # Be conservative if we cannot resolve type/policy here.
        return False
    return ctx.status.fs.name == "EMPTY" and eff.allow_header_in_empty_files is True


# --- Step gatekeeping ------------------------------------------------------


def may_proceed_to_sniffer(ctx: "ProcessingContext") -> bool:
    """Determine if processing can proceed to the sniffer step.

    Processing can proceed if:
      - The file was successfully resolved (ctx.status.resolve is RESOLVED)
      - A file type is present (ctx.file_type is not None)

    Args:
        ctx (ProcessingContext): The processing context for the current file.

    Returns:
        bool: True if processing can proceed to the sniffer step, False otherwise.
    """
    return ctx.status.resolve == ResolveStatus.RESOLVED and ctx.file_type is not None


def may_proceed_to_reader(ctx: "ProcessingContext") -> bool:
    """Determine if processing can proceed to the read step.

    Processing can proceed if:
      - The file was successfully resolved (ctx.status.resolve is RESOLVED)
      - A file type is present (ctx.file_type is not None)
      - A header processor is available (ctx.header_processor is not None)

    Note:
        The file system status (`ctx.status.fs`) is not strictly required here,
        to allow tests to skip the sniffer and invoke the reader directly. In such
        cases, the reader is the definitive authority for content checks (existence,
        permissions, binary/text, etc).

    Args:
        ctx (ProcessingContext): The processing context for the current file.

    Returns:
        bool: True if processing can proceed to the read step, False otherwise.
    """
    return (
        ctx.status.resolve == ResolveStatus.RESOLVED
        # and ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}
        and ctx.file_type is not None
        and ctx.header_processor is not None
    )


def may_proceed_to_scanner(ctx: ProcessingContext) -> bool:
    """Determine if processing can proceed to the scan step.

    Processing can proceed if:
      - The file was successfully resolved (ctx.status.resolve is RESOLVED)
      - The file type was resolved (ctx.file_type is not None)
      - A header processor is available (ctx.header_processor is not None)
    """
    return (
        ctx.status.resolve == ResolveStatus.RESOLVED
        and ctx.file_type is not None
        and ctx.header_processor is not None
    )


def may_proceed_to_builder(ctx: ProcessingContext) -> bool:
    """Determine if processing can proceed to the build step.

    Processing can proceed if:
      - The file was successfully resolved (ctx.status.resolve is RESOLVED)
      - A header processor is available (ctx.header_processor is not None)
      - The file image is available (the file image is available via `ctx.image`).

    Args:
        ctx (ProcessingContext): The processing context for the current file.

    Returns:
        bool: True if processing can proceed to the build step, False otherwise.
    """
    return (
        ctx.status.resolve == ResolveStatus.RESOLVED
        and ctx.file_type is not None
        and ctx.header_processor is not None
        # builder does not need the original image; it can run on empty files
        and (
            ctx.status.content == ContentStatus.OK
            or allow_empty_by_policy(ctx)  # Enable empty+policy path
        )
    )


def may_proceed_to_patcher(ctx: ProcessingContext) -> bool:
    """Determine if processing can proceed to the patcher step.

    Processing can proceed if:
      - The comparison step was performed (ctx.status.comparison is CHANGED or UNCHANGED)

    Args:
        ctx (ProcessingContext): The processing context for the current file.

    Returns:
        bool: True if processing can proceed to the patcher step, False otherwise.
    """
    return ctx.status.comparison in {
        ComparisonStatus.CHANGED,
        ComparisonStatus.UNCHANGED,
    }


def may_proceed_to_renderer(ctx: ProcessingContext) -> bool:
    """Determine if processing can proceed to the render step.

    Processing can proceed if:
      - The header was successfully generated (ctx.status.generation is RENDERED or GENERATED)

    Args:
        ctx (ProcessingContext): The processing context for the current file.

    Returns:
        bool: True if processing can proceed to the render step, False otherwise.
    """
    return (
        ctx.status.resolve == ResolveStatus.RESOLVED
        and ctx.file_type is not None
        and ctx.header_processor is not None
        and ctx.status.generation
        in {
            GenerationStatus.GENERATED,
            GenerationStatus.NO_FIELDS,
        }
        or allow_empty_by_policy(ctx)  # Allow render when empty+policy applies
    )


def may_proceed_to_comparer(ctx: "ProcessingContext") -> bool:
    """TODO Google-style docstring with type annotations."""
    return (
        ctx.status.resolve == ResolveStatus.RESOLVED
        and ctx.file_type is not None
        and ctx.header_processor is not None
        and (
            ctx.status.generation
            in {
                GenerationStatus.GENERATED,
                GenerationStatus.NO_FIELDS,
            }
            or allow_empty_by_policy(ctx)  # Allow render when empty+policy applies
            or (ctx.updated is not None and ctx.updated.lines is not None)
        )
    )


def may_proceed_to_updater(ctx: "ProcessingContext") -> bool:
    """TODO Google-style docstring with type annotations."""
    if ctx.status.resolve != ResolveStatus.RESOLVED:
        return False
    # Strip fast-path
    if ctx.status.strip == StripStatus.READY:
        return True
    # Normal update: content OK or empty+policy allowed
    if ctx.status.content == ContentStatus.OK or allow_empty_by_policy(ctx):
        return ctx.status.comparison == ComparisonStatus.CHANGED or (
            ctx.render is not None and ctx.render.lines is not None
        )
    return False


def may_proceed_to_writer(ctx: "ProcessingContext") -> bool:
    """Return `True` if the writer step may write to the sink.

    Conditions (all must hold):
        * `ctx.can_change is True` (authoritative feasibility/safety guard).
        * Intent is present:
            - Check mode: missing header **or** comparison is `CHANGED`.
            - Strip mode: `StripStatus.READY`.
        * Policy permits add/update (policy does **not** govern strip intent).
        * Updater selected a concrete write (`INSERTED` / `REPLACED` / `REMOVED`).

    Args:
        ctx (ProcessingContext): The processing context.

    Returns:
        bool: `True` if the writer should execute; otherwise `False`.
    """
    # add/update intent (check mode)
    would_add_or_update: bool = (
        ctx.status.header == HeaderStatus.MISSING
        or ctx.status.comparison == ComparisonStatus.CHANGED
    )
    # strip intent (strip mode)
    would_strip: bool = ctx.status.strip == StripStatus.READY

    # policy doesn’t govern stripping; it only affects add/update
    policy_allows: bool = (
        (ctx.permitted_by_policy is not False) or would_strip  # policy doesn’t govern strip
    )

    return (
        ctx.can_change is True  # Authoritative guard
        # and ctx.status.resolve == ResolveStatus.RESOLVED
        # and ctx.status.fs == FsStatus.OK
        and (would_add_or_update or would_strip)
        and policy_allows
        and ctx.status.write
        in {
            WriteStatus.INSERTED,
            WriteStatus.REPLACED,
            WriteStatus.REMOVED,
        }
    )


# --- Diagnostics support ------------------------------------------------------
class DiagnosticLevel(Enum):
    """Severity levels for diagnostics collected during processing.

    Levels map to terminal colors and are ordered by importance: ERROR > WARNING > INFO.
    This enum is **internal**; the public API exposes string literals.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def color(self) -> Callable[[str], str]:
        """Return the `yachalk` color function associated with this severity level.

        Intended for human-readable output only; machine formats should not use colors.

        Returns:
            Callable[[str], str]: The `yachalk` color function associated with this severity level.
        """
        return cast(
            "Callable[[str], str]",
            {
                DiagnosticLevel.INFO: chalk.blue,
                DiagnosticLevel.WARNING: chalk.yellow,
                DiagnosticLevel.ERROR: chalk.red_bright,
            }[self],
        )


@dataclass(frozen=True)
class Diagnostic:
    """Internal structured diagnostic with a severity level and message.

    Note:
        This type is **not** part of the public API surface. Conversions to
        `PublicDiagnostic` happen at the API boundary.
    """

    level: DiagnosticLevel
    message: str


@dataclass
class HeaderProcessingStatus:
    """Tracks the status of each processing phase for a single file.

    Fields correspond to each pipeline phase: file, header, generation, comparison, write.
    """

    # File system status (existence, permissions, binary):
    fs: FsStatus = FsStatus.PENDING
    # File type resolution status:
    resolve: ResolveStatus = ResolveStatus.PENDING
    # File content status (BOM, shebang, mixed newlines, readability):
    content: ContentStatus = ContentStatus.PENDING

    # Header-level axes
    header: HeaderStatus = HeaderStatus.PENDING  # Status of header detection/parsing
    generation: GenerationStatus = GenerationStatus.PENDING  # Status of header generation/rendering
    comparison: ComparisonStatus = ComparisonStatus.PENDING  # Status of header comparison
    write: WriteStatus = WriteStatus.PENDING  # Status of writing the header
    strip: StripStatus = StripStatus.PENDING  # Status of header stripping lifecycle

    def reset(self) -> None:
        """Set all status fields to PENDING."""
        self.fs = FsStatus.PENDING
        self.resolve = ResolveStatus.PENDING
        self.content = ContentStatus.PENDING
        self.header = HeaderStatus.PENDING
        self.generation = GenerationStatus.PENDING
        self.comparison = ComparisonStatus.PENDING
        self.strip = StripStatus.PENDING
        self.write = WriteStatus.PENDING


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
        leading_bom (bool): True when the original file began with a UTF-8 BOM
            ("\ufeff"). The reader sets this and strips the BOM from memory; the
            updater re-attaches it to the final output.
        has_shebang (bool): True if the first line starts with '#!' (post-BOM normalization).
        newline_hist (dict[str, int]): Histogram of newline styles found in the file.
        dominant_newline (str | None): Dominant newline style detected in the file.
        dominance_ratio (float | None): Dominance ratio of the dominant newline style.
        mixed_newlines (bool | None): True if mixed newline styles were found in the file.
        newline_style (str): The newline style in the file (``LF``, ``CR``, ``CRLF``).
        ends_with_newline (bool | None): True if the file ends with a newline.
        pre_insert_capability (InsertCapability): Advisory from the sniffer about
            pre-insert checks (e.g. spacers, empty body), defaults to UNEVALUATED.
        pre_insert_reason (str | None): Reason why insertion may be problematic.
        pre_insert_origin (str | None): Origin of the pre-insertion diagnostic.
        diagnostics (list[Diagnostic]): Warnings or errors encountered during processing.
        image (FileImageView | None): Snapshot-oriented view of the file contents for reuse
            across phases.
        header (HeaderView | None): Structured header view produced by the scan phase.
        build (BuilderView | None): Field dictionaries produced by the builder step.
        render (RenderView | None): View capturing the rendered header output.
        updated (UpdatedView | None): View of the post-processing file image.
        diff (DiffView | None): Diff view describing header changes for reporting.
    """

    # 📁 1. File input context
    path: Path  # The file path to process (absolute or relative to working directory)
    config: "Config"  # Active config at time of processing
    file_type: "FileType | None" = None  # Resolved file type (e.g., PythonFileType)
    status: HeaderProcessingStatus = field(default_factory=HeaderProcessingStatus)
    header_processor: "HeaderProcessor | None" = (
        None  # HeaderProcessor instance for this file type, if applicable
    )

    leading_bom: bool = False  # True if original file began with a UTF-8 BOM
    has_shebang: bool = False  # True if the first line starts with '#!' (post-BOM normalization)

    newline_hist: dict[str, int] = field(default_factory=lambda: {})
    dominant_newline: str | None = None
    dominance_ratio: float | None = None
    mixed_newlines: bool | None = None

    newline_style: str = "\n"  # Newline style (default = "\n")
    ends_with_newline: bool | None = None  # True if file ends with a newline sequence

    # Advisory from sniffer about pre-insert checks (e.g. spacers, empty body)
    pre_insert_capability: InsertCapability = InsertCapability.UNEVALUATED
    pre_insert_reason: str | None = None
    pre_insert_origin: str | None = None
    # # 🔍 2. Existing header (detected from original file)
    # existing_header_range: tuple[int, int] | None = (
    #     None  # (start_line, end_line) of detected header
    # )
    # existing_header_block: str | None = None  # Text block of the detected header
    # existing_header_lines: list[str] | None = None  # Raw lines of the detected header
    # existing_header_dict: dict[str, str] | None = None  # Parsed fields from the detected header

    # # 🧮 3. Derived and expected header state (from config + file path)
    # builtin_fields: dict[str, str] | None = (
    #     None  # Built-in/derived fields, e.g. {"file": ..., "file_relpath": ...}
    # )
    # expected_header_block: str | None = None  # Fully formatted header text to be written
    # expected_header_lines: list[str] | None = None  # Raw lines of the expected header
    # expected_header_dict: dict[str, str] | None = None  # Final rendered fields before formatting

    # # 4. Updated file and resulting diff
    # updated_file_lines: list[str] | None = None  # Updated file content as a list of lines
    # header_diff: str | None = None  # Unified diff (patch) for patching (updating) the header

    # Processing diagnostics: warnings/errors collected during processing
    diagnostics: list[Diagnostic] = field(default_factory=list[Diagnostic])

    # View-based properties
    image: FileImageView | None = None  # File image view
    header: HeaderView | None = None  # File header view
    build: BuilderView | None = None  # New file header build view
    render: RenderView | None = None  # New file header render view
    updated: UpdatedView | None = None  # New file updated view
    diff: DiffView | None = None  # File diff view

    @property
    def would_change(self) -> bool | None:
        """Return whether a change *would* occur (tri-state).

        Returns:
            bool | None: ``True`` if a change is intended (e.g., comparison is
                CHANGED, a header is missing, or the strip step prepared/attempted
                a removal), ``False`` if definitively no change (e.g., UNCHANGED or
                strip NOT_NEEDED), and ``None`` when indeterminate because the
                comparison was skipped/pending and the strip step did not run.
        """
        # Strip intent takes precedence: READY means we intend to remove, and
        # FAILED still represents an intent (feasibility is handled by can_change).
        if self.status.strip in {StripStatus.READY, StripStatus.FAILED}:
            return True
        # Default pipeline intents
        if self.status.header == HeaderStatus.MISSING:
            return True
        if self.status.comparison == ComparisonStatus.CHANGED:
            return True
        if (
            self.status.comparison == ComparisonStatus.UNCHANGED
            or self.status.strip == StripStatus.NOT_NEEDED
        ):
            return False
        # Anything else (PENDING, SKIPPED, CANNOT_COMPARE with no strip decision)
        return None

    @property
    def can_change(self) -> bool:
        """Return whether a change *can* be applied safely.

        This reflects operational feasibility (filesystem/resolve status) and
        structural safety, with a policy-based allowance for inserting into empty files.
        """
        # baseline feasibility + structural safety
        feasible: bool = (
            self.status.resolve == ResolveStatus.RESOLVED
            # if strip preparation failed, we can’t change via strip:
            and self.status.strip != StripStatus.FAILED
            # malformed headers block safe mutation in the default pipeline:
            and self.status.header
            not in {
                HeaderStatus.MALFORMED,
                HeaderStatus.MALFORMED_ALL_FIELDS,
                HeaderStatus.MALFORMED_SOME_FIELDS,
            }
        )

        if not feasible:
            return False

        # Filesystem feasibility:
        # - OK files: allowed
        # - EMPTY files: allowed if per-type policy permits insertion into empty files
        if self.status.fs == FsStatus.OK:
            return True
        if self.status.fs == FsStatus.EMPTY and allow_empty_by_policy(self):
            return True

        return False

    @property
    def permitted_by_policy(self) -> bool | None:
        """Whether policy allows the intended type of change (tri-state).

        Returns:
            bool | None:
                - True  : policy allows the intended change (insert/replace/strip)
                - False : policy forbids it (e.g., add_only forbids replace)
                - None  : indeterminate (no clear intent yet)
        """
        # Strip isn’t governed by add_only/update_only
        if self.status.strip in {StripStatus.READY, StripStatus.FAILED}:
            return True

        # No clear intent yet → unknown
        if self.status.header not in {
            HeaderStatus.MISSING,
            HeaderStatus.DETECTED,
        } and self.status.comparison not in {ComparisonStatus.CHANGED, ComparisonStatus.UNCHANGED}:
            return None

        pol: Policy = effective_policy(
            self.config,
            (getattr(self.file_type, "id", None) or getattr(self.file_type, "name", None))
            if self.file_type
            else None,
        )

        # Insert path (missing header)
        if self.status.header == HeaderStatus.MISSING:
            return not pol.update_only  # forbidden when update-only

        # Replace path (existing but different)
        if self.status.comparison == ComparisonStatus.CHANGED:
            return not pol.add_only  # forbidden when add-only

        # Unchanged or no-op
        return True

    @property
    def would_add_or_update(self) -> bool:
        """Intent for check/apply: True if we'd insert or replace a header."""
        return (
            self.status.header == HeaderStatus.MISSING
            or self.status.comparison == ComparisonStatus.CHANGED
        )

    @property
    def effective_would_add_or_update(self) -> bool:
        """True iff add/update is intended, feasible, and allowed by policy."""
        return (
            self.would_add_or_update
            and self.can_change is True
            and (self.permitted_by_policy is not False)
        )

    @property
    def would_strip(self) -> bool:
        """Intent for strip: True if a removal would occur."""
        return self.status.strip == StripStatus.READY

    @property
    def effective_would_strip(self) -> bool:
        """True iff a strip is intended and feasible."""
        # Policy doesn’t block strip; feasibility is in can_change
        return self.would_strip and self.can_change is True

    # @property
    # def effective_would_change(self) -> bool:
    #     """Generic “some kind of change” view (fine for summaries, not for exit codes)."""
    #     return (
    #         (
    #             self.would_add_or_update
    #             or self.would_strip
    #             or self.status.strip == StripStatus.FAILED
    #         )
    #         and self.can_change is True
    #         and (self.permitted_by_policy is not False)
    #     )

    def iter_file_lines(self) -> Iterable[str]:
        """Iterate the current file image without materializing.

        This accessor hides the underlying representation (list-backed, mmap-backed,
        or generator-based) and returns an iterator over logical lines with original
        newline sequences preserved.

        Returns:
            Iterable[str]: An iterator over the file's lines. If no image is present,
            an empty iterator is returned.
        """
        if self.image is not None:
            return self.image.iter_lines()
        return iter(())  # empty

    def file_line_count(self) -> int:
        """Return the number of logical lines without materializing.

        Returns:
            int: Total number of lines in the current image, or ``0`` if no image
            is present.
        """
        if self.image is not None:
            return self.image.line_count()
        return 0

    def to_dict(self) -> dict[str, object]:
        """Return a machine-readable representation of this processing result.

        The schema is stable for CLI/CI consumption and avoids color/formatting.
        Uses view-based properties (header/build/render/updated/diff).
        """
        header_dict: dict[str, object] | None
        if self.header is None:
            header_dict = None
        else:
            header_dict = {
                "range": self.header.range,
                "fields": (self.header.mapping or {}),
                "success_count": self.header.success_count,
                "error_count": self.header.error_count,
                # do not include raw block text by default to keep payload lean
            }

        build_dict: dict[str, object] | None
        if self.build is None:
            build_dict = None
        else:
            build_dict = {
                "builtins": (self.build.builtins or {}),
                "selected": (self.build.selected or {}),
            }

        render_dict: dict[str, object] | None
        if self.render is None:
            render_dict = None
        else:
            # keep output concise; expose counts rather than full text
            line_count: int = len(self.render.lines) if (self.render.lines is not None) else 0
            render_dict = {
                "has_lines": self.render.lines is not None,
                "line_count": line_count,
            }

        updated_dict: dict[str, object] | None
        if self.updated is None:
            updated_dict = None
        else:
            # updated.lines may be an Iterable; avoid materializing to count
            updated_dict = {
                "has_lines": self.updated.lines is not None,
            }

        diff_dict: dict[str, object] | None
        if self.diff is None:
            diff_dict = None
        else:
            diff_dict = {
                "has_diff": bool(self.diff.text),
            }

        return {
            "path": str(self.path),
            "file_type": (self.file_type.name if self.file_type else None),
            "status": {
                "fs": self.status.fs.name,
                "resolve": self.status.resolve.name,
                "content": self.status.content.name,
                "header": self.status.header.name,
                "generation": self.status.generation.name,
                "comparison": self.status.comparison.name,
                "write": self.status.write.name,
                "strip": self.status.strip.name,
            },
            "header": header_dict,
            "build": build_dict,
            "render": render_dict,
            "updated": updated_dict,
            "diff": diff_dict,
            "diagnostics": [
                {"level": d.level.value, "message": d.message} for d in self.diagnostics
            ],
            "diagnostic_counts": {
                "info": sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.INFO),
                "warning": sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.WARNING),
                "error": sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.ERROR),
            },
            "pre_insert_check": {
                "capability": self.pre_insert_capability.name,
                "reason": self.pre_insert_reason,
                "origin": self.pre_insert_origin,
            },
            "outcome": {
                "would_change": self.would_change,
                "can_change": self.can_change,
                "permitted_by_policy": self.permitted_by_policy,
                "check": {
                    "would_add_or_update": self.would_add_or_update,
                    "effective_would_add_or_update": self.effective_would_add_or_update,
                },
                "strip": {
                    "would_strip": self.would_strip,
                    "effective_would_strip": self.effective_would_strip,
                },
                # "effective_would_change": self.effective_would_change,
            },
        }

    def format_summary(self) -> str:
        """Return a concise, human‑readable one‑liner for this file.

        The summary is aligned with TopMark's pipeline phases and mirrors what
        comparable tools (e.g., *ruff*, *black*, *prettier*) surface: a clear
        primary outcome plus a few terse hints.

        Rendering rules:
          1. Primary bucket comes from
             [`topmark.cli_shared.utils.classify_outcome`][topmark.cli_shared.utils.classify_outcome].
             This ensures stable wording across commands/pipelines.
          2. If a write outcome is known (e.g., PREVIEWED/WRITTEN/INSERTED/REMOVED),
             append it as a trailing hint.
          3. If there is a diff but no write outcome (e.g., check/summary with
             `--diff`), append a "diff" hint.
          4. If diagnostics exist, append the diagnostic count as a hint.

        Verbose per‑line diagnostics are emitted only when Config.verbosity_level >= 1
        (treats None as 0).

        Examples (colors omitted here):
            path/to/file.py: python – would insert header - previewed
            path/to/file.py: python – up-to-date
            path/to/file.py: python – would strip header - diff - 2 issues
        """
        # Local import to avoid import cycles at module import time
        from topmark.cli_shared.utils import classify_outcome

        verbosity_level: int = self.config.verbosity_level or 0

        parts: list[str] = [f"{self.path}:"]

        # File type (dim), or <unknown> if resolution failed
        if self.file_type is not None:
            parts.append(chalk.dim(self.file_type.name))
        else:
            parts.append(chalk.dim("<unknown>"))

        # Primary bucket/label with color
        key: str
        label: str
        color_fn: Callable[[str], str]
        key, label, color_fn = classify_outcome(self)
        parts.append("\u2013")  # en dash separator
        parts.append(color_fn(label))

        if key != "ok":
            # Secondary hints: write status > diff marker > diagnostics

            if self.status.write != WriteStatus.PENDING:
                parts.append("-")
                parts.append(self.status.write.color(self.status.write.value))
            elif self.diff and self.diff.text:
                parts.append("-")
                parts.append(chalk.yellow("diff"))

        diag_show_hint: str = ""
        if self.diagnostics:
            n_info: int = sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.INFO)
            n_warn: int = sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.WARNING)
            n_err: int = sum(1 for d in self.diagnostics if d.level == DiagnosticLevel.ERROR)
            parts.append("-")
            # Compose a compact triage summary like "1 error, 2 warnings"
            triage: list[str] = []
            if verbosity_level <= 0:
                diag_show_hint = chalk.dim.italic(" (use '-v' to view)")
            if n_err:
                triage.append(chalk.red_bright(f"{n_err} error" + ("s" if n_err != 1 else "")))
            if n_warn:
                triage.append(chalk.yellow(f"{n_warn} warning" + ("s" if n_warn != 1 else "")))
            if n_info and not (n_err or n_warn):
                # Only show infos when there are no higher severities
                triage.append(chalk.blue(f"{n_info} info" + ("s" if n_info != 1 else "")))
            parts.append(", ".join(triage) if triage else chalk.blue("info"))

        result: str = " ".join(parts) + diag_show_hint

        # Optional verbose diagnostic listing (gated by verbosity level)
        if self.diagnostics and verbosity_level > 0:
            details: list[str] = []
            for d in self.diagnostics:
                prefix: str = {
                    DiagnosticLevel.ERROR: chalk.red_bright("error"),
                    DiagnosticLevel.WARNING: chalk.yellow("warning"),
                    DiagnosticLevel.INFO: chalk.blue("info"),
                }[d.level]
                details.append(f"  [{prefix}] {d.message}")
            result += "\n" + "\n".join(details)

        return result

    @property
    def summary(self) -> str:
        """Return a formatted summary string of the processing status for this file."""
        return self.format_summary()

    @classmethod
    def bootstrap(cls, *, path: Path, config: Config) -> ProcessingContext:
        """Create a fresh context with no derived state."""
        return cls(path=path, config=config)

    # --- Convenience helpers -------------------------------------------------
    def add_info(self, message: str) -> None:
        """Add an `info` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.INFO, message))

    def add_warning(self, message: str) -> None:
        """Add an `warning` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.WARNING, message))

    def add_error(self, message: str) -> None:
        """Add an `error` diagnostic to the processing context.

        Args:
            message (str): The diagnostic message.
        """
        self.diagnostics.append(Diagnostic(DiagnosticLevel.ERROR, message))

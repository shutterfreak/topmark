# topmark:header:start
#
#   project      : TopMark
#   file         : policy.py
#   file_relpath : src/topmark/pipeline/context/policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Policy helpers for interpreting configuration in the pipeline context.

This module centralizes helpers that interpret the effective
[Policy][topmark.config.policy.Policy] in the context of a single file.
Functions here operate on a
[ProcessingContext][topmark.pipeline.context.model.ProcessingContext]
instance to decide whether certain operations (for example, inserting into
empty files or tolerating mixed newlines) are permitted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import Policy
from topmark.core.logging import TopmarkLogger
from topmark.core.logging import get_logger
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus

if TYPE_CHECKING:
    from topmark.config.policy import Policy
    from topmark.pipeline.context.status import ProcessingStatus


logger: TopmarkLogger = get_logger(__name__)


class PolicyContext(Protocol):
    """Minimum context surface required by policy helpers."""

    @property
    def status(self) -> ProcessingStatus:
        """Current aggregated pipeline status for this file."""
        ...

    def get_effective_policy(self) -> Policy:
        """Return the effective policy for this processing context."""
        ...

    @property
    def is_effectively_empty(self) -> bool:
        """Whether the file image is effectively empty.

        Returns whether the decoded, BOM-stripped text image contains **no
        non-whitespace characters**. Newlines and other whitespace are allowed.
        This is the broad notion of “empty” used for most policy decisions.
        """
        ...

    @property
    def is_logically_empty(self) -> bool:
        """Whether the file is “logically empty”.

        Returns whether the file is “logically empty”: after BOM stripping,
        it contains optional horizontal whitespace and **at most one** trailing
        newline sequence (LF/CRLF/CR), and nothing else. This is a stricter subset
        of `is_effectively_empty` and is useful to preserve stable round-trips for
        files that are effectively placeholders.
        """
        ...

    @property
    def is_empty_like(self) -> bool:
        """Whether a file image is "empty-like"."""
        ...


# ---- Classification helpers ----


def is_empty_for_insert(ctx: PolicyContext) -> bool:
    """Return whether this file should be treated as "empty" for *insertion* decisions.

    This helper interprets the effective per-type policy setting
    ``Policy.empty_insert_mode`` and maps it onto the file's observed state.

    The distinction matters because TopMark may need to preserve stable round-trips:

    - A *true empty* file (0 bytes) is represented by ``FsStatus.EMPTY``.
    - A file can be *logically empty* (BOM stripped, optional whitespace, optional single
      trailing newline) even when it is not 0 bytes.
    - A file can be *effectively empty* (no non-whitespace characters) while containing
      multiple blank lines.

    The selected mode controls which of these categories is considered "empty" when
    deciding whether inserting a header is allowed.

    Args:
        ctx: Processing context (or compatible protocol) providing filesystem status and
            decoded image emptiness flags.

    Returns:
        True if the current file qualifies as empty under the configured insertion mode.

    Notes:
        - This predicate is only about *classification* of emptiness for insert gating.
          It does not check whether insertion is allowed; use
          `allow_insert_into_empty_like` for that.
        - ``FsStatus.EMPTY`` is always treated as empty, regardless of mode.
    """
    policy: Policy = ctx.get_effective_policy()
    mode: EmptyInsertMode = policy.empty_insert_mode
    if mode == EmptyInsertMode.BYTES_EMPTY:
        return ctx.status.fs == FsStatus.EMPTY
    if mode == EmptyInsertMode.LOGICAL_EMPTY:
        return ctx.is_logically_empty or ctx.status.fs == FsStatus.EMPTY
    # EmptyInsertMode.WHITESPACE_EMPTY
    return ctx.is_effectively_empty or ctx.status.fs == FsStatus.EMPTY


def is_empty_for_insert_unchanged_by_default(ctx: PolicyContext) -> bool:
    """Return True when an insertion-empty file should default to `UNCHANGED`.

    This helper is for *bucketing/reporting*, not mutation.

    It captures the default policy interpretation for files that are classified
    as "empty for insertion":

    - If the file counts as empty under `is_empty_for_insert(ctx)`, and
    - policy does *not* allow inserting into such files,

    then TopMark should generally treat the file as compliant / unchanged rather
    than as "missing header".

    This avoids surprising "would insert" or "missing header" outcomes for
    placeholder files such as:

    - true 0-byte files
    - BOM-only files
    - newline-only files
    - other empty-like images covered by the configured `EmptyInsertMode`

    The actual definition of "empty" is delegated to `is_empty_for_insert(ctx)`,
    so this helper automatically obeys the effective `EmptyInsertMode`
    (`bytes_empty`, `logical_empty`, or `whitespace_empty`).

    Args:
        ctx: Processing context (or compatible protocol).

    Returns:
        True if the file is classified as empty-for-insert and policy does not
        allow inserting into such files; otherwise False.

    Notes:
        - Use this in outcome bucketing and summaries.
        - Mutation steps should instead use `allow_insert_into_empty_like(ctx)`.
    """
    # First determine whether the current file belongs to the configured
    # "empty for insertion" class.
    if not is_empty_for_insert(ctx):
        return False

    # If the file is empty-for-insert but policy does not permit insertion into
    # that class, it should be treated as compliant / unchanged by default.
    return not allow_insert_into_empty_like(ctx)


# ---- Policy permission helpers ----


def allow_insert_into_empty_like(ctx: PolicyContext) -> bool:
    """Return True if policy permits inserting a header into an empty-like file.

    This is the primary policy gate used by planner/updater when a file has no
    meaningful body content.

    The decision is a conjunction of:

    1) whether the file is considered *empty for insert* (see
       `is_empty_for_insert`), and
    2) whether the effective policy enables insertion into empty files
       (``Policy.allow_header_in_empty_files``).

    Because this helper delegates classification to `is_empty_for_insert`, it
    automatically obeys the configured ``EmptyInsertMode`` (`bytes_empty`,
    `logical_empty`, or `whitespace_empty`).

    Args:
        ctx: Processing context (or compatible protocol).

    Returns:
        True if insertion is allowed for this file given its empty-like state and the
        effective policy.

    Guidance:
        - Use this in *mutation* steps (planner/updater) when deciding whether
          an insert/update is allowed to proceed.
        - Do **not** use it to skip reading/analysis steps; those should be governed by
          filesystem/content feasibility (e.g., unreadable/binary/mixed-newlines).
    """
    policy: Policy | None = ctx.get_effective_policy()

    return is_empty_for_insert(ctx) and bool(policy.allow_header_in_empty_files)


def allow_empty_header(ctx: PolicyContext) -> bool:
    """Return True if the effective policy allows empty header insertion.

    This helper inspects the effective per-type policy (global configuration
    overlaid by per-type overrides) and reports whether an empty rendered
    header is considered acceptable.

    Args:
        ctx: Processing context containing status and configuration.

    Returns:
        `True` if policy allows rendering an empty header when there are no fields,
        `False` otherwise.
    """
    policy: Policy | None = ctx.get_effective_policy()

    return policy.render_empty_header_when_no_fields


def allow_content_reflow(ctx: PolicyContext) -> bool:
    """Return True if the effective policy allows content reflow.

    This covers transformations that may adjust layout or whitespace around
    the header region and are controlled by the ``allow_reflow`` flag.

    Args:
        ctx: Processing context containing status and configuration.

    Returns:
        bool: True if policy allows reflowing content around the header,
        False otherwise.
    """
    policy: Policy | None = ctx.get_effective_policy()

    return policy.allow_reflow


def allow_mixed_line_endings(ctx: PolicyContext) -> bool:
    """Return True if policy allows proceeding despite mixed line endings.

    This helper is used by early pipeline steps (e.g., ReaderStep) when the
    sniffer detected mixed line endings (`FsStatus.MIXED_LINE_ENDINGS`) and
    the project policy has opted into tolerating them.

    Policy fields:
      - If the effective `Policy` defines `ignore_mixed_line_endings` and it is True,
        we allow proceeding on `MIXED_LINE_ENDINGS`.

    Notes:
      - This function is forward-compatible: it uses `getattr(...)` so it returns
        False for unknown fields on older Policy versions (safe default).
      - We *always* allow when `FsStatus` is already OK/EMPTY; for EMPTY, your
        existing `allow_insert_into_empty_like()` governs header insertion later.

    Args:
        ctx: Processing context containing filesystem status and configuration.

    Returns:
        `True` if we may proceed despite mixed line endings,
        `False` otherwise.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    policy: Policy | None = ctx.get_effective_policy()

    if ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(policy, "ignore_mixed_line_endings", False))

    # All other FS states should not be skipped by policy here.
    return False


def allow_bom_before_shebang(ctx: PolicyContext) -> bool:
    """Return True if policy allows proceeding despite a BOM before the shebang.

    This helper is used by early pipeline steps (e.g., ReaderStep) when the
    sniffer detected a BOM before the shebang (`FsStatus.BOM_BEFORE_SHEBANG`)
    and the project policy has opted into tolerating it.

    Policy fields:
      - If the effective `Policy` defines `ignore_bom_before_shebang` and it is True,
        we allow proceeding on `BOM_BEFORE_SHEBANG`.

    Notes:
      - This function is forward-compatible: it uses `getattr(...)` so it returns
        False for unknown fields on older Policy versions (safe default).
      - We *always* allow when `FsStatus` is already OK/EMPTY; for EMPTY, your
        existing `allow_insert_into_empty_like()` governs header insertion later.

    Args:
        ctx: Processing context containing filesystem status and configuration.

    Returns:
        `True` if we may proceed despite a BOM before the shebang,
        `False` otherwise.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    policy: Policy | None = ctx.get_effective_policy()

    if ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(policy, "ignore_bom_before_shebang", False))

    # All other FS states should not be skipped by policy here.
    return False


# ---- Mutation intent / feasibility / pipeline decision logic ----


def check_permitted_by_policy(ctx: PolicyContext) -> bool | None:
    """Whether policy allows the intended type of change (tri-state).

    Args:
        ctx: Processing context for the current file.

    Returns:
        - True  : policy allows the intended change (insert/replace)
        - False : policy forbids it (e.g., add_only forbids replace)
        - None  : indeterminate (no clear intent yet)
    """
    pol: Policy | None = ctx.get_effective_policy()
    pol_check_add_only: bool = pol.add_only if pol else False
    pol_check_update_only: bool = pol.update_only if pol else False

    if ctx.status.strip != StripStatus.PENDING:
        # StripperStep did run
        return None

    if ctx.status.header == HeaderStatus.PENDING:
        # ScannerStep did not run
        return None

    # Insert path (missing header)
    if pol_check_add_only:
        if (
            ctx.status.header
            in {
                HeaderStatus.DETECTED,
                HeaderStatus.EMPTY,
                # HeaderStatus.MALFORMED_ALL_FIELDS,
                # HeaderStatus.MALFORMED_SOME_FIELDS,
            }
            # and ctx.status.comparison == ComparisonStatus.CHANGED
        ):
            logger.debug(
                "permitted_by_policy: header: %s, comparison: %s "
                "-- pol_check_add_only: %s, will return False",
                ctx.status.header,
                ctx.status.comparison,
                pol_check_add_only,
            )
            return False  # forbidden when add-only
        else:
            logger.debug(
                "permitted_by_policy: header: %s, comparison: %s "
                "-- pol_check_add_only: %s, will return True",
                ctx.status.header,
                ctx.status.comparison,
                pol_check_add_only,
            )
            return True

    # Replace path (existing but different)
    if pol_check_update_only:
        if (
            ctx.status.header == HeaderStatus.MISSING
            # and ctx.status.comparison == ComparisonStatus.CHANGED
        ):
            logger.debug(
                "permitted_by_policy: header: %s, comparison: %s "
                "-- pol_check_update_only: %s, will return False",
                ctx.status.header,
                ctx.status.comparison,
                pol_check_update_only,
            )
            return False  # forbidden when update-only
        else:
            logger.debug(
                "permitted_by_policy: header: %s, comparison: %s "
                "-- pol_check_update_only: %s, will return True",
                ctx.status.header,
                ctx.status.comparison,
                pol_check_update_only,
            )
            return True

    # No clear intent yet → unknown
    if ctx.status.header not in {
        HeaderStatus.MISSING,
        HeaderStatus.DETECTED,
    } and ctx.status.comparison not in {
        ComparisonStatus.CHANGED,
        ComparisonStatus.UNCHANGED,
    }:
        logger.debug(
            "permitted_by_policy: header: %s, comparison: %s -- will return None",
            ctx.status.header,
            ctx.status.comparison,
        )
        return None

    logger.debug(
        "permitted_by_policy: header: %s, comparison: %s -- PROCEED",
        ctx.status.header,
        ctx.status.comparison,
    )

    # Unchanged or no-op
    return True


def would_change(ctx: PolicyContext) -> bool | None:
    """Return whether a change *would* occur (tri-state).

    Args:
        ctx: Processing context for the current file.

    Returns:
        ``True`` if a change is intended (e.g., comparison is CHANGED, a header is missing,
        or the strip step prepared/attempted a removal), ``False`` if definitively no change
        (e.g., UNCHANGED or strip NOT_NEEDED), and ``None`` when indeterminate because the
        comparison was skipped/pending and the strip step did not run.
    """
    # Strip intent takes precedence: READY means we intend to remove, and
    # FAILED still represents an intent (feasibility is handled by can_change).
    if ctx.status.strip in {StripStatus.READY, StripStatus.FAILED}:
        return True
    # Default pipeline intents
    if ctx.status.header == HeaderStatus.MISSING:
        return True
    if ctx.status.comparison == ComparisonStatus.CHANGED:
        return True
    if (
        ctx.status.comparison == ComparisonStatus.UNCHANGED
        or ctx.status.strip == StripStatus.NOT_NEEDED
    ):
        return False
    # Anything else (PENDING, SKIPPED, CANNOT_COMPARE with no strip decision)
    return None


def can_change(ctx: PolicyContext) -> bool:
    """Return whether a mutation can be applied safely for this file.

    This helper answers a narrow question:

    *If the pipeline intends to mutate this file, is that mutation structurally
    and operationally allowed to proceed?*

    It combines three categories of checks:

    1) **Baseline feasibility**
       The file must have resolved successfully, strip preparation must not have
       failed, and the header state must not be one of the malformed states that
       block safe mutation.

    2) **Normal files**
       For ordinary files (`FsStatus.OK`), mutation is allowed once baseline
       feasibility is satisfied.

    3) **Empty / empty-like files**
       For files that are considered “empty for insert”, mutation is allowed only
       when policy explicitly permits inserting into such files. Importantly,
       emptiness classification is delegated to `is_empty_for_insert(ctx)`, which
       obeys the configured `EmptyInsertMode`.

    This means:
    - true 0-byte files may be mutable if policy allows it
    - logically empty placeholders may be mutable if policy allows it
    - whitespace-only files may be mutable if policy allows it
      (depending on `EmptyInsertMode`)

    Args:
        ctx: Processing context for the current file.

    Returns:
        True if a mutation is structurally and operationally safe to apply,
        otherwise False.
    """
    # --- 1) Baseline feasibility -------------------------------------------------
    #
    # These checks are independent of "empty-like" policy semantics.
    # If any of them fail, the pipeline should not attempt mutation at all.
    feasible: bool = (
        ctx.status.resolve == ResolveStatus.RESOLVED
        # if strip preparation failed, we can’t change via strip:
        and ctx.status.strip != StripStatus.FAILED
        # malformed headers block safe mutation in the default pipeline:
        and ctx.status.header
        not in {
            HeaderStatus.MALFORMED,
            HeaderStatus.MALFORMED_ALL_FIELDS,
            HeaderStatus.MALFORMED_SOME_FIELDS,
        }
    )
    if not feasible:
        return False

    # --- 2) Normal files ---------------------------------------------------------
    #
    # For regular decoded files, baseline feasibility is enough.
    if ctx.status.fs == FsStatus.OK and not is_empty_for_insert(ctx):
        return True

    # --- 3) Empty / empty-like files --------------------------------------------
    #
    # If this file is considered "empty for insert" under the active policy mode,
    # we may only mutate it when insertion into empty-like files is explicitly
    # allowed.
    if is_empty_for_insert(ctx):
        return allow_insert_into_empty_like(ctx)

    # Any remaining filesystem states are not considered safely mutable here.
    return False


def would_add_or_update(ctx: PolicyContext) -> bool:
    """Intent for check/apply: True if we'd insert or replace a header.

    Args:
        ctx: Processing context for the current file.

    Returns:
        `True` if a change is structurally and operationally safe,
        `False` otherwise.
    """
    return (
        ctx.status.header == HeaderStatus.MISSING
        or ctx.status.comparison == ComparisonStatus.CHANGED
    )


def effective_would_add_or_update(ctx: PolicyContext) -> bool:
    """True iff add/update is intended, feasible, and allowed by policy.

    Args:
        ctx: Processing context for the current file.

    Returns:
        `True` if a change is structurally and operationally safe,
        `False` otherwise.
    """
    return (
        would_add_or_update(ctx)
        and can_change(ctx) is True
        and (check_permitted_by_policy(ctx) is not False)
    )


def would_strip(ctx: PolicyContext) -> bool:
    """Intent for strip: True if a removal would occur.

    Args:
        ctx: Processing context for the current file.

    Returns:
        `True` if a change is structurally and operationally safe,
        `False` otherwise.
    """
    return ctx.status.strip == StripStatus.READY


def effective_would_strip(ctx: PolicyContext) -> bool:
    """True iff a strip is intended and feasible.

    Args:
        ctx: Processing context for the current file.

    Returns:
        `True` if a change is structurally and operationally safe,
        `False` otherwise.
    """
    # Policy doesn’t block strip; feasibility is in can_change
    return would_strip(ctx) and can_change(ctx) is True

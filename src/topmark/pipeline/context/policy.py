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

from typing import TYPE_CHECKING

from topmark.config.logging import TopmarkLogger, get_logger

from ..status import (
    ComparisonStatus,
    FsStatus,
    HeaderStatus,
    ResolveStatus,
    StripStatus,
)

if TYPE_CHECKING:
    from topmark.config.policy import Policy

    from .model import ProcessingContext

logger: TopmarkLogger = get_logger(__name__)


def allow_empty_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if the file is empty and policy allows header insertion.

    This helper inspects the effective per-type policy (global configuration
    overlaid by per-type overrides) and combines it with the current
    filesystem status of the context.

    Args:
        ctx (ProcessingContext): Processing context containing status and
            configuration.

    Returns:
        bool: True if the file is empty and policy permits inserting a header
        into empty files, False otherwise.
    """
    # If you expose a cached effective policy, use that; else compute via `effective_policy(...)`.
    # Assuming `ctx.file_type` is set when resolve == RESOLVED.

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    return ctx.status.fs == FsStatus.EMPTY and eff.allow_header_in_empty_files is True


def allow_empty_header_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if the effective policy allows empty header insertion.

    This helper inspects the effective per-type policy (global configuration
    overlaid by per-type overrides) and reports whether an empty rendered
    header is considered acceptable.

    Args:
        ctx (ProcessingContext): Processing context containing status and
            configuration.

    Returns:
        bool: True if policy allows rendering an empty header when there are
        no fields, False otherwise.
    """
    # If you expose a cached effective policy, use that; else compute via `effective_policy(...)`.
    # Assuming `ctx.file_type` is set when resolve == RESOLVED.
    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    return eff.render_empty_header_when_no_fields


def allow_content_reflow_by_policy(ctx: "ProcessingContext") -> bool:
    """Return True if the effective policy allows content reflow.

    This covers transformations that may adjust layout or whitespace around
    the header region and are controlled by the ``allow_reflow`` flag.

    Args:
        ctx (ProcessingContext): Processing context containing status and
            configuration.

    Returns:
        bool: True if policy allows reflowing content around the header,
        False otherwise.
    """
    # If you expose a cached effective policy, use that; else compute via `effective_policy(...)`.
    # Assuming `ctx.file_type` is set when resolve == RESOLVED.
    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    return eff.allow_reflow


def allows_mixed_line_endings_by_policy(ctx: "ProcessingContext") -> bool:
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
        existing `allow_empty_by_policy()` governs header insertion later.

    Args:
        ctx (ProcessingContext): Processing context containing filesystem
            status and configuration.

    Returns:
        bool: True if we may proceed despite mixed line endings, False
        otherwise.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    if ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_mixed_line_endings", False))

    # All other FS states should not be skipped by policy here.
    return False


def allows_bom_before_shebang_by_policy(ctx: "ProcessingContext") -> bool:
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
        existing `allow_empty_by_policy()` governs header insertion later.

    Args:
        ctx (ProcessingContext): Processing context containing filesystem
            status and configuration.

    Returns:
        bool: True if we may proceed despite a BOM before the shebang, False
        otherwise.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    if ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_bom_before_shebang", False))

    # All other FS states should not be skipped by policy here.
    return False


def policy_allows_fs_skip(ctx: "ProcessingContext") -> bool:
    """Return True if policy allows proceeding despite soft FS violations.

    This helper is used by early pipeline steps (e.g., ReaderStep) to continue
    when Sniffer detected *soft* file-system issues that a project might choose
    to tolerate. Hard errors (e.g., not found, unreadable, binary) must remain
    terminal and are not bypassed here.

    Soft violations considered:
      - FsStatus.BOM_BEFORE_SHEBANG
      - FsStatus.MIXED_LINE_ENDINGS

    Policy fields:
      - If the effective `Policy` defines `ignore_bom_before_shebang` and it is True,
        we allow proceeding on `BOM_BEFORE_SHEBANG`.
      - If the effective `Policy` defines `ignore_mixed_line_endings` and it is True,
        we allow proceeding on `MIXED_LINE_ENDINGS`.

    Notes:
      - This function is forward-compatible: it uses `getattr(...)` so it returns
        False for unknown fields on older Policy versions (safe default).
      - We *always* allow when `FsStatus` is already OK/EMPTY; for EMPTY, your
        existing `allow_empty_by_policy()` governs header insertion later.

    Args:
        ctx (ProcessingContext): Processing context containing filesystem
            status and configuration.

    Returns:
        bool: True if we may proceed despite a soft filesystem violation,
        False otherwise.
    """
    # Always OK to proceed if FS is healthy or empty (read can still run).
    if ctx.status.fs in {FsStatus.OK, FsStatus.EMPTY}:
        return True

    eff: Policy | None = ctx.get_effective_policy()
    if eff is None:
        return False

    if ctx.status.fs == FsStatus.BOM_BEFORE_SHEBANG:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_bom_before_shebang", False))

    if ctx.status.fs == FsStatus.MIXED_LINE_ENDINGS:
        # Newer policies may provide this flag; default False if absent.
        return bool(getattr(eff, "ignore_mixed_line_endings", False))

    # All other FS states should not be skipped by policy here.
    return False


def check_permitted_by_policy(ctx: "ProcessingContext") -> bool | None:
    """Whether policy allows the intended type of change (tri-state).

    Args:
        ctx (ProcessingContext): Processing context for the current file.

    Returns:
        bool | None:
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


def would_change(ctx: "ProcessingContext") -> bool | None:
    """Return whether a change *would* occur (tri-state).

    Args:
        ctx (ProcessingContext): Processing context for the current file.

    Returns:
        bool | None: ``True`` if a change is intended (e.g., comparison is
            CHANGED, a header is missing, or the strip step prepared/attempted
            a removal), ``False`` if definitively no change (e.g., UNCHANGED or
            strip NOT_NEEDED), and ``None`` when indeterminate because the
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


def can_change(ctx: "ProcessingContext") -> bool:
    """Return whether a change *can* be applied safely.

    This reflects operational feasibility (filesystem/resolve status) and
    structural safety, with a policy-based allowance for inserting headers
    into empty files.

    Args:
        ctx (ProcessingContext): Processing context for the current file.

    Returns:
        bool: True if a change is structurally and operationally safe, False
        otherwise.
    """
    # baseline feasibility + structural safety
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

    # Filesystem feasibility:
    # - OK files: allowed
    # - EMPTY files: allowed if per-type policy permits insertion into empty files
    if ctx.status.fs == FsStatus.OK:
        return True
    if ctx.status.fs == FsStatus.EMPTY and allow_empty_by_policy(ctx):
        return True

    return False


def would_add_or_update(ctx: "ProcessingContext") -> bool:
    """Intent for check/apply: True if we'd insert or replace a header.

    Args:
        ctx (ProcessingContext): Processing context for the current file.

    Returns:
        bool: True if a change is structurally and operationally safe, False
        otherwise.
    """
    return (
        ctx.status.header == HeaderStatus.MISSING
        or ctx.status.comparison == ComparisonStatus.CHANGED
    )


def effective_would_add_or_update(ctx: "ProcessingContext") -> bool:
    """True iff add/update is intended, feasible, and allowed by policy.

    Args:
        ctx (ProcessingContext): Processing context for the current file.

    Returns:
        bool: True if a change is structurally and operationally safe, False
        otherwise.
    """
    return (
        would_add_or_update(ctx)
        and can_change(ctx) is True
        and (check_permitted_by_policy(ctx) is not False)
    )


def would_strip(ctx: "ProcessingContext") -> bool:
    """Intent for strip: True if a removal would occur.

    Args:
        ctx (ProcessingContext): Processing context for the current file.

    Returns:
        bool: True if a change is structurally and operationally safe, False
        otherwise.
    """
    return ctx.status.strip == StripStatus.READY


def effective_would_strip(ctx: "ProcessingContext") -> bool:
    """True iff a strip is intended and feasible.

    Args:
        ctx (ProcessingContext): Processing context for the current file.

    Returns:
        bool: True if a change is structurally and operationally safe, False
        otherwise.
    """
    # Policy doesn’t block strip; feasibility is in can_change
    return would_strip(ctx) and can_change(ctx) is True

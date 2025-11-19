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

from topmark.pipeline.status import FsStatus

if TYPE_CHECKING:
    from topmark.config.policy import Policy
    from topmark.pipeline.context.model import ProcessingContext


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
    """Return True if policy allows proceeding despite soft FS violations.

    This helper is used by early pipeline steps (e.g., ReaderStep) to continue
    when Sniffer detected *soft* file-system issues that a project might choose
    to tolerate. Hard errors (e.g., not found, unreadable, binary) must remain
    terminal and are not bypassed here.

    Soft violations considered:
      - FsStatus.BOM_BEFORE_SHEBANG
      - FsStatus.MIXED_LINE_ENDINGS

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
    """Return True if policy allows proceeding despite soft FS violations.

    This helper is used by early pipeline steps (e.g., ReaderStep) to continue
    when Sniffer detected *soft* file-system issues that a project might choose
    to tolerate. Hard errors (e.g., not found, unreadable, binary) must remain
    terminal and are not bypassed here.

    Soft violations considered:
      - FsStatus.BOM_BEFORE_SHEBANG

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

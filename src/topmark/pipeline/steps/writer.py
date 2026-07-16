# topmark:header:start
#
#   project      : TopMark
#   file         : writer.py
#   file_relpath : src/topmark/pipeline/steps/writer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Writer step for committing updated content to a sink.

This step is the canonical place where TopMark writes results to a destination
(filesystem or stdout). Dry-run pipelines do not execute this step. It avoids
implementation drift between the CLI and public API.

This step is responsible for the final I/O after all other steps have computed
`ctx.views.updated` and selected the intended `PlanStatus` (INSERTED, REPLACED, REMOVED,
or PREVIEWED for stdout output). File and stdout sinks stream from repeatable updated
content via `ProcessingContext.iter_updated_lines()` instead of requiring an eagerly
materialized updated-line list.
It also applies policy gates (e.g., header mutation mode) so that command-line intent
and config policies are centralized here.

Sinks
-----
- InplaceFileSink: writes in-place to the file path.
- AtomicFileSink: writes through a same-directory temporary file and atomically replaces the target.
  POSIX-only durability and permission helpers such as `os.fchmod()` and `os.O_DIRECTORY` are used
  only when available; Windows falls back to best-effort path-based permission handling and skips
  directory `fsync()`.
- StdoutSink: streams the updated content to stdout (stdin-content mode).

The step respects
[`WriterStep.may_proceed()`][topmark.pipeline.steps.writer.WriterStep.may_proceed]
and the tri-state intent/feasibility via `ProcessingContext.would_change`
and `ProcessingContext.can_change`.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import stat
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol

from topmark.config.policy import HeaderMutationMode
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.core.logging import get_logger
from topmark.pipeline.context.policy import can_change
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.status import PlanStatus
from topmark.pipeline.status import WriteStatus
from topmark.pipeline.steps.base import BaseStep
from topmark.pipeline.views import ViewSlot

if TYPE_CHECKING:
    from pathlib import Path
    from typing import BinaryIO

    from topmark.config.policy import FrozenPolicy
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.views import UpdatedView


logger: TopmarkLogger = get_logger(__name__)


# --- DRY helpers for writer sinks ---
def _has_updated_lines(
    ctx: ProcessingContext,
) -> bool:
    """Return whether an updated image exists without materializing it.

    Args:
        ctx: Processing context.

    Returns:
        True when the context holds updated content, otherwise False.
    """
    uv: UpdatedView | None = ctx.views.updated
    return uv is not None and uv.lines is not None


def _write_encoded_lines(
    *,
    ctx: ProcessingContext,
    file: BinaryIO,
) -> int:
    """Stream updated lines to a binary file object.

    Args:
        ctx: Processing context containing repeatable updated content.
        file: Binary file object to receive UTF-8 encoded lines.

    Returns:
        Number of UTF-8 bytes written.
    """
    bytes_written: int = 0
    for line in ctx.iter_updated_lines():
        encoded: bytes = line.encode("utf-8")
        file.write(encoded)
        bytes_written += len(encoded)
    return bytes_written


def _write_stdout_lines(
    ctx: ProcessingContext,
) -> int:
    """Stream updated lines to standard output.

    Args:
        ctx: Processing context containing repeatable updated content.

    Returns:
        Number of UTF-8 bytes emitted.
    """
    bytes_written: int = 0
    for line in ctx.iter_updated_lines():
        bytes_written += len(line.encode("utf-8"))
        sys.stdout.write(line)
    return bytes_written


class WriteSink(Protocol):
    """Behavioral protocol for writer-step sinks.

    Sink implementations encapsulate the final destination-specific I/O for a
    processing context, such as writing to disk or emitting to stdout. The protocol
    intentionally exposes only behavior and does not require shared sink state.
    """

    def write(
        self,
        *,
        ctx: ProcessingContext,
    ) -> WriteResult:
        """Write the updated content for ``ctx`` to the target sink.

        Implementations perform the final write operation for a processed file,
        such as writing to disk or emitting to stdout.

        Args:
            ctx: Context that holds updated content and write status.

        Returns:
            Structured result indicating the write status and byte count when
            the sink can report one.
        """
        ...


@dataclass(frozen=True, kw_only=True, slots=True)
class WriteResult:
    """Structured result of a writer sink operation.

    Attributes:
        status: Final status reported by the sink.
        bytes_written: Number of bytes written when reported by the sink. Stdout
            reports emitted UTF-8 bytes; file sinks currently report zero after
            successful writes.
    """

    status: WriteStatus
    bytes_written: int = 0


class StdoutSink:
    """Standard-output sink (stdin-content mode)."""

    def write(
        self,
        *,
        ctx: ProcessingContext,
    ) -> WriteResult:
        """Emit updated content to standard output.

        This sink is used when the CLI/API is configured to read a single file's
        content from STDIN and emit the updated result to STDOUT.

        Args:
            ctx: Processing context containing the updated lines.

        Returns:
            ``WRITTEN`` with the number of UTF-8 bytes printed when content is available;
            otherwise ``SKIPPED`` with zero bytes written.
        """
        if not _has_updated_lines(ctx):
            logger.debug(
                "StdoutSink: ctx.views.updated not defined or ctx.views.updated.lines not defined: "
                "nothing to do"
            )
            return WriteResult(status=WriteStatus.SKIPPED, bytes_written=0)

        try:
            size: int = _write_stdout_lines(ctx)
        except (OSError, UnicodeError) as e:
            ctx.diagnostics.add_error(f"Stdout write failed: {e}")
            return WriteResult(status=WriteStatus.FAILED, bytes_written=0)
        return WriteResult(status=WriteStatus.WRITTEN, bytes_written=size)


class InplaceFileSink(WriteSink):
    """Write updated content by truncating the original file and writing in place.

    Pros:
        - Keeps inode identity stable.
        - Minimal I/O.
    Cons:
        - Risk of partial/truncated files on crash.
        - Live readers may observe mid-write changes.
    """

    def write(
        self,
        *,
        ctx: ProcessingContext,
    ) -> WriteResult:
        """Write updated content directly into the original file (in-place).

        Opens the file in binary write mode, truncates its contents, and streams
        `ctx.iter_updated_lines()` to the target file. This operation preserves the
        inode identity but may leave a truncated file if the process is interrupted
        mid-write.

        Args:
            ctx: The active processing context, expected to provide repeatable updated
                content through `ctx.iter_updated_lines()`.

        Returns:
            Structured write result containing `WriteStatus.WRITTEN` on success,
            or `WriteStatus.FAILED` after recording diagnostic information on error.
        """
        path: Path = ctx.path
        try:
            # Preserve mode; other metadata handled best-effort.
            try:
                st_mode: int = path.stat().st_mode
                mode: int | None = stat.S_IMODE(st_mode)
            except OSError:
                mode = None

            with path.open("wb") as f:
                _write_encoded_lines(ctx=ctx, file=f)
                f.flush()
                os.fsync(f.fileno())
            if mode is not None:
                # Best-effort: preserve original permissions.
                with contextlib.suppress(OSError):
                    path.chmod(mode)
            return WriteResult(status=WriteStatus.WRITTEN)
        except (OSError, UnicodeError) as e:
            ctx.diagnostics.add_error(f"In-place write failed: {e}")
            return WriteResult(status=WriteStatus.FAILED)


class AtomicFileSink(WriteSink):
    """Write updated content to a temp file and atomically replace the target.

    This sink writes to a temporary file in the **same directory** as the
    target, `fsync()`s it, then calls `os.replace()` to atomically swap it in.

    Permission preservation and directory durability are best-effort and platform-aware:
    POSIX uses `os.fchmod()` and directory `fsync()` when available, while Windows falls back to
    path-based `chmod()` and skips directory `fsync()` because `os.fchmod` and `os.O_DIRECTORY` are
    not exposed there.

    Pros:
        - Atomic visibility; crash-safe (old file remains until replace).
    Cons:
        - New inode/ID on POSIX; slightly more I/O.
        - Directory `fsync()` is POSIX-only and therefore skipped on Windows.
    """

    def write(
        self,
        *,
        ctx: ProcessingContext,
    ) -> WriteResult:
        """Atomically replace the target file by writing to a temp file first.

        Streams `ctx.iter_updated_lines()` to a temporary file in the same directory,
        calls `os.fsync()` to ensure durability, and performs `os.replace()` to
        atomically swap it in place. The operation guarantees that readers will
        either see the old file or the complete new file, never a partial write.

        Args:
            ctx: The active processing context, expected to provide repeatable updated
                content through `ctx.iter_updated_lines()`.

        Returns:
            Structured write result with `WriteStatus.WRITTEN` on success, or
            `WriteStatus.FAILED` after recording diagnostic information on error.
        """
        path: Path = ctx.path
        dirpath: Path = path.parent
        # Generate a hidden, per-process, per-file temp name.
        tmp: Path = dirpath / f".{path.name}.topmark.tmp-{os.getpid()}-{secrets.token_hex(4)}"
        try:
            # Read original metadata for later re-apply (best-effort)
            try:
                st: os.stat_result | None = path.stat()
                mode: int | None = stat.S_IMODE(st.st_mode) if st else None
            except OSError:
                st = None
                mode = None

            with tmp.open("wb") as f:
                # Apply permissions early to reduce race windows.
                if mode is not None:
                    fchmod = getattr(os, "fchmod", None)
                    if fchmod is not None:
                        try:
                            # Try to apply permissions to the open file descriptor (fchmod).
                            # This is ideal: no race window, applies before rename.
                            fchmod(f.fileno(), mode)
                        except OSError:
                            # Fallback behavior: if fchmod fails, try chmod(tmp).
                            with contextlib.suppress(OSError):
                                tmp.chmod(mode)
                    else:
                        # Windows does not expose os.fchmod. Apply permissions to the temporary path
                        # directly as a best-effort fallback.
                        with contextlib.suppress(OSError):
                            tmp.chmod(mode)
                _write_encoded_lines(ctx=ctx, file=f)
                f.flush()
                os.fsync(f.fileno())

            tmp.replace(path)

            # Try to fsync the directory for durability (POSIX only).
            o_directory: int | None = getattr(os, "O_DIRECTORY", None)
            if o_directory is not None:
                try:
                    dir_fd: int = os.open(str(dirpath), o_directory)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    # Best-effort durability; ignore on platforms/filesystems that don't support it.
                    logger.debug("AtomicFileSink: directory fsync not supported", exc_info=True)
            else:
                logger.debug("AtomicFileSink: directory fsync not available on this platform")

            return WriteResult(status=WriteStatus.WRITTEN)
        except (OSError, UnicodeError) as e:
            # Best-effort cleanup of the temp file
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                logger.debug("AtomicFileSink: failed to clean up temp file %s", tmp, exc_info=True)
            ctx.diagnostics.add_error(f"Atomic write failed: {e}")
            return WriteResult(status=WriteStatus.FAILED)


def _select_sink(
    ctx: ProcessingContext,
) -> WriteSink:
    """Pick the appropriate sink for this write operation.

    Selection rules:
      * If `ctx.run_options.output_target == OutputTarget.STDOUT` → `StdoutSink`
        (emit updated content to standard output). This path ignores `apply_changes`
        because it does not mutate the filesystem.
      * Else (target is an apply-mode file operation), select the file sink by strategy:
          - `FileWriteStrategy.INPLACE` → `InplaceFileSink`
          - `FileWriteStrategy.ATOMIC` or no strategy → `AtomicFileSink` (default)

    Notes:
      * Output target is configured and set at config resolution.
      * The *destination* (stdout vs file) is orthogonal to the *write strategy*.
      * `WriterStep.may_proceed()` rejects non-apply file operations before sink selection.
      * `apply_changes` is ignored for stdout because stdout does not mutate the source file.
    """
    # Destination: stdout takes precedence and ignores apply_changes.
    if ctx.run_options.output_target == OutputTarget.STDOUT:
        logger.info("--> Writer selected StdoutSink")
        return StdoutSink()

    # Apply to file using the configured strategy (default: atomic).
    if ctx.run_options.file_write_strategy == FileWriteStrategy.INPLACE:
        # In-place writer (faster)
        logger.info("--> Writer selected InplaceFileSink")
        return InplaceFileSink()
    # Default (True, None): atomic writer (safer)
    logger.info("--> Writer selected AtomicFileSink (default)")
    return AtomicFileSink()


class WriterStep(BaseStep):
    """Commit updated content to a filesystem or stdout sink.

    Applies policy gates and the intended write action (insert/replace/remove)
    to produce a final write result. Performs the only I/O in the pipeline.

    Axes written:
      - write

    Sets:
      - WriteStatus: {PENDING, WRITTEN, SKIPPED, FAILED}
    """

    def __init__(self) -> None:
        super().__init__(
            name=self.__class__.__name__,
            primary_axis=Axis.WRITE,
            axes_written=(Axis.WRITE,),
            consumes_views=frozenset(
                {
                    ViewSlot.UPDATED,
                }
            ),
        )

    def may_proceed(
        self,
        ctx: ProcessingContext,
    ) -> bool:
        """Return True if the writer is allowed to commit changes.

        The writer should only run when the pipeline is not halted and an updated
        image exists. Stdout accepts preview or concrete plan states independently
        of filesystem feasibility. File output additionally requires apply mode, a
        concrete ``INSERTED``/``REPLACED``/``REMOVED`` plan, and
        ``can_change(ctx) is True``.

        Policy and intent have already been enforced by the updater. Re-checking
        header/comparison/strip intent here can drift from the authoritative
        ``UpdateStatus`` and cause double-gating, so we avoid it.

        Args:
            ctx: The processing context for the current file.

        Returns:
            True if processing can proceed to the write step, False otherwise.
        """
        if ctx.is_halted:
            return False

        # Require an updated image.
        updated_view: UpdatedView | None = ctx.views.updated
        updated_view_exists: bool = updated_view is not None and updated_view.lines is not None
        if not updated_view_exists:
            return False

        # STDOUT target is non-mutating. Allow emitting updated content even when
        # `apply_changes` is False (preview) and even when filesystem feasibility
        # would block an on-disk write.
        if ctx.run_options.output_target == OutputTarget.STDOUT:
            return ctx.status.plan in {
                PlanStatus.PREVIEWED,
                PlanStatus.INSERTED,
                PlanStatus.REPLACED,
                PlanStatus.REMOVED,
            }

        # File target: only write when the caller explicitly enabled apply mode.
        if not ctx.run_options.apply_changes:
            return False

        # Only execute when updater produced a concrete write operation.
        if ctx.status.plan not in {
            PlanStatus.INSERTED,
            PlanStatus.REPLACED,
            PlanStatus.REMOVED,
        }:
            return False

        return can_change(ctx) is True

    def run(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Writer step: commit updates to the selected sink.

        This step executes only when `may_proceed()` returns `True`. It consumes the
        planner-owned updated image without normalizing BOM or final-newline policy.

        Args:
            ctx: The processing context with update intent.

        Mutations:
            Updates `ctx.status.write` and may append diagnostics when policy or
            sink failures prevent writing.
        """
        logger.debug("ctx: %s", ctx)

        # --- Policy enforcement (centralized + file-type-specific when configured) ---
        pol: FrozenPolicy = ctx.get_effective_policy()

        # Only gate insert/replace (check mode) - strip/removal is not governed by add/update.
        if (
            ctx.status.plan == PlanStatus.INSERTED
            and pol.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY
        ):
            ctx.status.write = WriteStatus.SKIPPED
            ctx.diagnostics.add_info("Skipped by policy: header_mutation_mode=update_only")
            return

        if (
            ctx.status.plan == PlanStatus.REPLACED
            and pol.header_mutation_mode == HeaderMutationMode.ADD_ONLY
        ):
            ctx.status.write = WriteStatus.SKIPPED
            ctx.diagnostics.add_info("Skipped by policy: header_mutation_mode=add_only")
            return

        sink: WriteSink = _select_sink(ctx)
        result: WriteResult = sink.write(ctx=ctx)

        # Update write status:
        ctx.status.write = result.status

    def hint(
        self,
        ctx: ProcessingContext,
    ) -> None:
        """Attach write hints (non-binding).

        Args:
            ctx: The processing context.

        Raises:
            RuntimeError: If the context contains an unexpected write status value.
        """
        st: WriteStatus = ctx.status.write

        match st:
            # May proceed to next step (always):
            case WriteStatus.WRITTEN:
                ctx.hint(
                    axis=Axis.WRITE,
                    code=KnownCode.WRITE_WRITTEN,
                    cluster=Cluster.CHANGED,
                    message="changes written",
                )
            case WriteStatus.SKIPPED:
                if ctx.status.plan in {PlanStatus.INSERTED, PlanStatus.REPLACED}:
                    msg: str = "write skipped (policy)"
                else:
                    msg = "write skipped"
                ctx.hint(
                    axis=Axis.WRITE,
                    code=KnownCode.WRITE_SKIPPED,
                    cluster=Cluster.SKIPPED,
                    message=msg,
                )

            # Stop processing:
            case WriteStatus.FAILED:
                ctx.hint(
                    axis=Axis.WRITE,
                    code=KnownCode.WRITE_FAILED,
                    cluster=Cluster.ERROR,
                    message="write failed",
                    terminal=True,
                )

            # States owned outside this step:
            case WriteStatus.PENDING:  # pragma: no cover - BaseStep owns pending-state handling.
                # BaseStep.__call__() handles PENDING state (step did not complete)
                pass

            case _:  # pragma: no cover - exhaustive enum guard for untyped callers.
                raise RuntimeError(f"Unexpected WriteStatus found: {st!r}")

# topmark:header:start
#
#   project      : TopMark
#   file         : conftest.py
#   file_relpath : tests/pipeline/conftest.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared test utilities for TopMark header processors.

This module provides helpers used across processor tests to derive canonical
TopMark header preamble and postamble lines directly from the registered
`HeaderProcessor` for a given file path. By querying the processor for its
rendered block structure, tests avoid hard-coding comment syntax (e.g., HTML
block comments vs. pound-style line comments) and remain resilient to future
formatting changes.

Key utilities:
  * BlockSignatures: TypedDict capturing the canonical header block lines.
  * expected_block_lines_for(path, newline): Renders preamble/postamble lines
    using the processor’s configured block/line prefixes and returns them as
    single-line strings (newlines stripped) for straightforward assertions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import NotRequired, Required, TypedDict

from topmark.config.policy import PolicyRegistry, make_policy_registry
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.pipelines import CHECK_PATCH_PIPELINE, CHECK_SUMMMARY_PIPELINE
from topmark.pipeline.processors import get_processor_for_file, register_all_processors
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.status import ContentStatus, FsStatus, ResolveStatus
from topmark.pipeline.steps.builder import BuilderStep
from topmark.pipeline.steps.comparer import ComparerStep
from topmark.pipeline.steps.patcher import PatcherStep
from topmark.pipeline.steps.planner import PlannerStep
from topmark.pipeline.steps.reader import ReaderStep
from topmark.pipeline.steps.renderer import RendererStep
from topmark.pipeline.steps.resolver import ResolverStep
from topmark.pipeline.steps.scanner import ScannerStep
from topmark.pipeline.steps.sniffer import SnifferStep
from topmark.pipeline.steps.stripper import StripperStep
from topmark.pipeline.steps.writer import WriterStep
from topmark.pipeline.views import ListFileImageView

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from topmark.config import Config
    from topmark.pipeline.processors.base import HeaderProcessor
    from topmark.pipeline.protocols import Step


def run_resolver(ctx: ProcessingContext) -> ProcessingContext:
    """Run the ResolverStep."""
    return ResolverStep()(ctx)


def run_sniffer(ctx: ProcessingContext) -> ProcessingContext:
    """Run the SnifferStep."""
    return SnifferStep()(ctx)


def run_reader(ctx: ProcessingContext) -> ProcessingContext:
    """Run the ReaderStep."""
    return ReaderStep()(ctx)


def run_scanner(ctx: ProcessingContext) -> ProcessingContext:
    """Run the ScannerStep."""
    return ScannerStep()(ctx)


def run_builder(ctx: ProcessingContext) -> ProcessingContext:
    """Run the BuilderStep."""
    return BuilderStep()(ctx)


def run_renderer(ctx: ProcessingContext) -> ProcessingContext:
    """Run the RendererStep."""
    return RendererStep()(ctx)


def run_planner(ctx: ProcessingContext) -> ProcessingContext:
    """Run the PlannerStep."""
    return PlannerStep()(ctx)


def run_comparer(ctx: ProcessingContext) -> ProcessingContext:
    """Run the ComparerStep."""
    return ComparerStep()(ctx)


def run_patcher(ctx: ProcessingContext) -> ProcessingContext:
    """Run the PatcherStep."""
    return PatcherStep()(ctx)


def run_stripper(ctx: ProcessingContext) -> ProcessingContext:
    """Run the StripperStep."""
    return StripperStep()(ctx)


def run_writer(ctx: ProcessingContext) -> ProcessingContext:
    """Run the WriterStep."""
    return WriterStep()(ctx)


def make_pipeline_context(path: Path, cfg: Config) -> ProcessingContext:
    """Return a ProcessingContext seeded with a PolicyRegistry for a given path."""
    policy_registry: PolicyRegistry = make_policy_registry(cfg)
    return ProcessingContext.bootstrap(
        path=path,
        config=cfg,
        policy_registry_override=policy_registry,
    )


def make_context_from_text(
    text: str,
    *,
    cfg: Config,
    path: Path,
) -> ProcessingContext:
    r"""Bootstrap a context in a post-reader state from in-memory text.

    This helper is intended for pipeline tests that want to exercise the
    scanner/builder/planner/renderer/comparer/patcher steps without going
    through the full resolver/sniffer/reader chain on disk.

    The helper:
      * Creates a fresh ProcessingContext via ``ProcessingContext.bootstrap``.
      * Resolves and attaches the appropriate ``HeaderProcessor`` using the
        normal test-time registry helpers.
      * Marks ``resolve/fs/content`` axes as successfully completed.
      * Installs a ``ListFileImageView`` backed by ``text.splitlines(keepends=True)``.
      * Sets a simple newline style (``"\\n"``) and ``ends_with_newline`` flag.

    Notes:
        This is a **test-only** utility. It deliberately skips real I/O and
        does not attempt to mirror all side effects of SnifferStep/ReaderStep
        (e.g. BOM-before-shebang and mixed-newline policies). Tests that care
        about those details should continue to go through the real steps on
        temporary files.

    Args:
        text: In-memory file contents to expose via ``ctx.views.image``.
        cfg: Frozen configuration snapshot used to bootstrap the context.
        path: Synthetic path used for the context and processor lookup.

    Returns:
        A context suitable for running post-reader steps.
    """
    ctx: ProcessingContext = make_pipeline_context(path=path, cfg=cfg)

    # Resolve and attach processor/file type using the normal registry helper.
    proc: HeaderProcessor | None = get_processor_for_file(path=path)
    assert proc is not None, f"Expected a registered HeaderProcessor for test path {path!s}"
    ctx.header_processor = proc
    ctx.file_type = proc.file_type
    ctx.status.resolve = ResolveStatus.RESOLVED

    # Simulate ReaderStep output: image view and basic newline metadata.
    lines: list[str] = text.splitlines(keepends=True)
    ctx.views.image = ListFileImageView(lines)

    ctx.status.fs = FsStatus.OK
    ctx.status.content = ContentStatus.OK

    # Minimal newline metadata sufficient for most builder/render tests.
    ctx.newline_style = "\n"
    ctx.ends_with_newline = text.endswith("\n")

    return ctx


# --- Newline normalization helper for test output ---
def coerce_newlines(
    lines: list[str],
    target_nl: str,
    ends_with_newline: bool | None,
) -> list[str]:
    """Normalize all line terminators to ``target_nl`` and ensure final newline presence.

    Each element in ``lines`` is expected to be keepends=True style.
    """
    if not lines:
        return lines
    out: list[str] = []
    # Normalize all but the last line
    for ln in lines[:-1]:
        core: str = (
            ln[:-2]
            if ln.endswith("\r\n")
            else (ln[:-1] if ln.endswith("\n") or ln.endswith("\r") else ln)
        )
        out.append(core + target_nl)
    # Last line: respect ends_with_newline if provided
    last: str = lines[-1]
    core_last: str = (
        last[:-2]
        if last.endswith("\r\n")
        else (last[:-1] if last.endswith("\n") or last.endswith("\r") else last)
    )
    if ends_with_newline is None:
        # Preserve as-is but convert style if it had a terminator
        if last.endswith(("\r\n", "\n", "\r")):
            out.append(core_last + target_nl)
        else:
            out.append(core_last)
    else:
        out.append(core_last + target_nl if ends_with_newline else core_last)
    return out


@pytest.fixture(scope="module", autouse=True)
def register_processors_for_this_package() -> None:
    """Ensure all header processors are registered for processor tests.

    Using an autouse, module-scoped fixture here avoids repeating the same
    registration fixture in each test module under ``tests/pipeline/processors``.
    """
    register_all_processors()


def materialize_image_lines(ctx: ProcessingContext) -> list[str]:
    """Return the current file image lines as a concrete list for test assertions.

    Converts the possibly lazy iterator from ``ctx.views.image.iter_lines()`` into a list
    without altering the ProcessingContext. Safe for test-only use.
    """
    if not ctx.views.image:
        return []
    # `iter_lines()` always yields keepends=True lines
    return list(ctx.views.image.iter_lines())


def materialize_updated_lines(ctx: ProcessingContext) -> list[str]:
    """Return updated file lines as a concrete list for test assertions.

    Converts the possibly lazy iterable in ``ctx.views.updated.lines`` into a list
    without altering the ProcessingContext. Safe for test-only use.
    """
    if not ctx.views.updated or ctx.views.updated.lines is None:
        return []
    seq: Sequence[str] | Iterable[str] = ctx.views.updated.lines
    return seq if isinstance(seq, list) else list(seq)


# --- Class-based step runner helpers (tests) ---
def run_steps(ctx: ProcessingContext, steps: list[Step] | tuple[Step, ...]) -> ProcessingContext:
    """Run a list of class-based steps against a context and return it.

    This helper mirrors the engine's simple sequential execution. It does not     short-circuit on
    `may_proceed()`—each step enforces its own gating, as in production.
    """
    for step in steps:
        step(ctx)
    return ctx


# Common step chains used by tests
SCAN_STEPS: list[Step] = [
    ResolverStep(),
    SnifferStep(),
    ReaderStep(),
    ScannerStep(),
]
STRIP_STEPS: list[Step] = SCAN_STEPS + [
    StripperStep(),
    PlannerStep(),
]
CHECK_COMPARE_STEPS: list[Step] = SCAN_STEPS + [
    RendererStep(),
    ComparerStep(),
]
# For insert/update tests that render and compare before updating, test modules
# can extend SCAN_STEPS with Builder/Renderer/Comparer if needed.


def run_insert(path: Path, cfg: Config) -> ProcessingContext:
    """Run a minimal insert/update flow for tests using class-based steps.

    This helper executes the discovery stages (resolve/sniff/read/scan) and
    then runs the updater. Tests that need rendering/compare can extend this
    chain in their own modules.

    Args:
        path: File to modify.
        cfg: TopMark configuration used for rendering.

    Returns:
        The updated ``ProcessingContext`` with ``updated_file_lines`` set.
    """
    ctx: ProcessingContext = make_pipeline_context(path=path, cfg=cfg)
    run_steps(ctx, CHECK_SUMMMARY_PIPELINE + (PlannerStep(),))

    return ctx


def run_insert_diff(path: Path, cfg: Config) -> ProcessingContext:
    """Run a minimal insert/update flow for tests using class-based steps.

    This helper executes the discovery stages (resolve/sniff/read/scan) and
    then runs the updater. Tests that need rendering/compare can extend this
    chain in their own modules.

    Args:
        path: File to modify.
        cfg: TopMark configuration used for rendering.

    Returns:
        The updated ``ProcessingContext`` with ``updated_file_lines`` set.
    """
    ctx: ProcessingContext = make_pipeline_context(path=path, cfg=cfg)
    run_steps(ctx, CHECK_PATCH_PIPELINE + (PlannerStep(),))

    return ctx


def run_strip(path: Path, cfg: Config) -> ProcessingContext:
    """Run a strip flow (resolve → sniff → read → scan → strip → update).

    Args:
        path: File to modify.
        cfg: TopMark configuration (not used for stripping, but kept for symmetry).

    Returns:
        The updated ``ProcessingContext`` with ``updated_file_lines`` set to the stripped content.
    """
    ctx: ProcessingContext = make_pipeline_context(path=path, cfg=cfg)
    run_steps(ctx, STRIP_STEPS)
    return ctx


def run_scan(path: Path, cfg: Config) -> ProcessingContext:
    """Run just the discovery/scan steps to populate header and content views."""
    ctx: ProcessingContext = make_pipeline_context(path=path, cfg=cfg)
    run_steps(ctx, SCAN_STEPS)
    return ctx


def find_line(lines: list[str], needle: str) -> int:
    """Return the index of the first line equal to ``needle``.

    Comparison strips trailing newline characters to be newline-style agnostic.

    Args:
        lines: Sequence of lines (each typically ending with a newline).
        needle: The exact content to match (no trailing newline).

    Returns:
        Zero-based index of the first matching line.

    Raises:
        AssertionError: If ``needle`` is not found.
    """
    for i, ln in enumerate(lines):
        if ln.rstrip("\r\n") == needle:
            return i
    raise AssertionError(f"Line not found: {needle!r}\n\n" + "".join(lines))


# --- Helper for canonical TopMark block signatures for test assertions ---


class BlockSignatures(TypedDict, total=False):
    """Canonical TopMark header block lines for assertions in tests.

    All values are single lines (no trailing newline). Optional keys are
    present only when the processor defines block wrappers.
    """

    block_open: NotRequired[str]
    start_line: Required[str]
    blank_after_start: Required[str]  # Might become configurable
    blank_before_end: Required[str]  # Might become configurable
    end_line: Required[str]
    block_close: NotRequired[str]


def expected_block_lines_for(path: Path, newline: str = "\n") -> BlockSignatures:
    """Return the rendered preamble/postamble lines for the file’s processor.

    The returned strings match exactly what the processor would render for the
    preamble (block open, start marker, intentional blank) and postamble
    (intentional blank, end marker, block close). Newlines are stripped so the
    values can be compared to ``ctx.updated_file_lines`` using equality after
    ``rstrip()``.

    Args:
        path: Path to the file under test; used to resolve the processor.
        newline: Newline style to use when rendering test expectations.

    Returns:
        A dict with canonical single-line strings suitable for assertions.
    """
    # Ensure processors are registered and resolve the appropriate one
    proc: HeaderProcessor | None = get_processor_for_file(path)
    if proc is None:
        register_all_processors()
        proc = get_processor_for_file(path)
    assert proc is not None, f"No header processor found for {path}"

    pre: list[str] = proc.render_preamble_lines(newline_style=newline)
    post: list[str] = proc.render_postamble_lines(newline_style=newline)

    def strip_nl(s: str) -> str:
        return s.rstrip("\r\n")

    # Choose indices depending on block prefix presence
    if proc.block_prefix:
        start_idx = 1
        blank_after_idx = 2
    else:
        start_idx = 0
        blank_after_idx = 1

    # Choose indices depending on block suffix presence
    if proc.block_suffix:
        blank_before_end_idx = 0
        end_line_idx = 1
    else:
        blank_before_end_idx = 0
        end_line_idx = 1

    out: BlockSignatures = {
        "start_line": strip_nl(pre[start_idx]),
        "blank_after_start": strip_nl(pre[blank_after_idx]),
        "blank_before_end": strip_nl(post[blank_before_end_idx]),
        "end_line": strip_nl(post[end_line_idx]),
    }
    if proc.block_prefix:
        out["block_open"] = strip_nl(pre[0])
    if proc.block_suffix:
        out["block_close"] = strip_nl(post[-1])

    return out

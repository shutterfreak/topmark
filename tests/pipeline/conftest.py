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

from typing_extensions import NotRequired, Required, TypedDict

from tests.conftest import fixture
from topmark.pipeline.context import ProcessingContext
from topmark.pipeline.processors import get_processor_for_file, register_all_processors
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.steps import reader, resolver, scanner, sniffer, updater

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config import Config
    from topmark.pipeline.processors.base import HeaderProcessor


# --- Newline normalization helper for test output ---
def _coerce_newlines(
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


@fixture(scope="module", autouse=True)
def register_processors_for_this_package() -> None:
    """Ensure all header processors are registered for processor tests.

    Using an autouse, module-scoped fixture here avoids repeating the same
    registration fixture in each test module under ``tests/pipeline/processors``.
    """
    register_all_processors()


def run_insert(path: Path, cfg: Config) -> ProcessingContext:
    """Insert a TopMark header by running the minimal pipeline for insertion.

    Steps:
      1. bootstrap `ProcessingContext`
      2. `resolver.resolve()` → choose FileType and HeaderProcessor
      3. `sniffer.sniff()` → early/cheap policy checks (existence, binary, BOM/shebang,
         newline histogram)
      4. `reader.read()` → load `file_lines`, precise newline/BOM/shebang flags
      5. `scanner.scan()` → detect existing TopMark header bounds
      6. `renderer.render()` → compute expected header lines for current file
      7. `updater.update()` → apply insert/update in-memory

    Args:
        path (Path): File to modify.
        cfg (Config): TopMark configuration used for rendering.

    Returns:
        ProcessingContext: The updated ``ProcessingContext`` with ``updated_file_lines`` set.
    """
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=path, config=cfg)

    # Run resolver first so ctx.file_type and ctx.header_processor are set based on
    # the registry and file path. Policies like shebang handling depend on this.
    ctx = resolver.resolve(ctx)

    # Run sniffer to perform early/cheap policy checks:
    #   - existence, permissions, empty file
    #   - fast binary/NUL check
    #   - BOM/shebang ordering and policy
    #   - quick newline histogram (mixed-newlines policy)
    ctx = sniffer.sniff(ctx)

    # Run the reader to populate file_lines, ends_with_newline, and detect
    # newline style (LF/CRLF/CR) and BOM/shebang precisely.
    ctx = reader.read(ctx)

    assert ctx.newline_style, "run_insert(): Newline style MUST NOT be empty"
    newline: str = ctx.newline_style or "\n"

    # Scan for existing TopMark header using processor-specific bounds logic
    ctx = scanner.scan(ctx)

    # We deliberately call renderer.render() directly, as builder is internal and
    # not required for test orchestration—renderer suffices for expected header lines.
    # Ensure we have a processor (resolver should have set it). Fall back to registry lookup.
    processor: HeaderProcessor | None = ctx.header_processor or get_processor_for_file(path)
    assert processor is not None, "No header processor for file"
    ctx.header_processor = processor

    # Render header with the detected newline style so header lines match file endings.
    header_values: dict[str, str] = {field: "" for field in cfg.header_fields}

    # Preserve pre-prefix indentation (spaces/tabs before the prefix) when
    # replacing an existing header block, so nested JSONC headers stay aligned.
    header_indent_override: str | None = None
    if ctx.existing_header_range is not None and ctx.file_lines:
        start_idx: int
        _end_idx: int
        start_idx, _end_idx = ctx.existing_header_range
        first_line: str = ctx.file_lines[start_idx]
        leading_ws: str = first_line[: len(first_line) - len(first_line.lstrip())]
        if leading_ws and first_line.lstrip().startswith(processor.line_prefix):
            header_indent_override = leading_ws

    ctx.expected_header_lines = processor.render_header_lines(
        header_values,
        cfg,
        newline,
        header_indent_override=header_indent_override,
    )

    # If scanner did not find a header, attempt a lightweight signature-based
    # detection to support tests that directly call the updater with crafted content.
    if ctx.existing_header_range is None:
        try:
            sig: BlockSignatures = expected_block_lines_for(path, newline=newline)
            start_idx = find_line(ctx.file_lines or [], sig["start_line"])
            end_idx: int = find_line(ctx.file_lines or [], sig["end_line"])
            ctx.existing_header_range = (start_idx, end_idx)
        except AssertionError:
            ctx.existing_header_range = None

    # Call the updater step directly
    ctx = updater.update(ctx)
    assert ctx.updated_file_lines is not None
    # Normalize newlines for consistent test output
    ctx.updated_file_lines = _coerce_newlines(
        ctx.updated_file_lines or [],
        target_nl=ctx.newline_style or "\n",
        ends_with_newline=ctx.ends_with_newline,
    )
    return ctx


def find_line(lines: list[str], needle: str) -> int:
    """Return the index of the first line equal to ``needle``.

    Comparison strips trailing newline characters to be newline-style agnostic.

    Args:
        lines (list[str]): Sequence of lines (each typically ending with a newline).
        needle (str): The exact content to match (no trailing newline).

    Returns:
        int: Zero-based index of the first matching line.

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
        path (Path): Path to the file under test; used to resolve the processor.
        newline (str): Newline style to use when rendering test expectations.

    Returns:
        BlockSignatures: A dict with canonical single-line strings suitable for assertions.
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

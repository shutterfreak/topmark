# topmark:header:start
#
#   project      : TopMark
#   file         : test_patcher.py
#   file_relpath : tests/pipeline/steps/test_patcher.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Patcher step generates CRLF-preserving diffs; render_patch shows explicit EOLs.

This test bypasses console/capture entirely: it drives the pipeline to the
patcher step, inspects `ctx.header_diff`, and runs `render_patch()` on it to
assert CRLF semantics (or explicit `\\r\\n` markers) deterministically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.pipeline.conftest import (
    make_pipeline_context,
    run_builder,
    run_comparer,
    run_patcher,
    run_planner,
    run_reader,
    run_renderer,
    run_resolver,
    run_scanner,
)
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext


def _run_to_patcher(file: Path, cfg: Config) -> ProcessingContext:
    """Drive the v2 pipeline up to `patcher.patch()` and return the ctx."""
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    ctx = run_resolver(ctx)
    ctx = run_reader(ctx)
    ctx = run_scanner(ctx)
    ctx = run_builder(ctx)
    ctx = run_renderer(ctx)
    ctx = run_planner(ctx)  # produce updated_file_lines for the diff
    ctx = run_comparer(ctx)  # compare using updated image
    ctx = run_patcher(ctx)
    return ctx


def test_patcher_diff_preserves_crlf_and_render_markers(tmp_path: Path) -> None:
    r"""CRLF-seeded file → diff lines use CRLF; render_patch shows \\r\\n markers."""
    path: Path = tmp_path / "a.ts"
    # Ensure file content is CRLF-seeded.
    with path.open("w", encoding="utf-8", newline="\r\n") as fp:
        # Add a syntactically valid TopMark header field (key:value)
        fp.write(
            f"// {TOPMARK_START_MARKER}\n// test:header\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n"
        )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = _run_to_patcher(path, cfg)

    # We expect a change (strip/replace) to have produced a diff.
    diff_text: str = (ctx.views.diff.text if ctx.views.diff else "") or ""
    assert diff_text, "Expected non-empty unified diff from patcher"

    # The raw diff is produced with lineterm = ctx.newline_style.
    # If reader detected CRLF, ensure the diff contains CRLF in hunk lines.
    if ctx.newline_style == "\r\n":
        assert "\r\n" in diff_text, "Raw diff should contain CRLF line terminators"

    # Pass a list of lines to preserve native EOLs; when given a single string,
    # render_patch would lose CRLF markers due to splitlines() default behavior.
    rendered: str = render_patch(
        patch=diff_text.splitlines(keepends=True),
        color=False,
    )
    # Depending on render_patch implementation, CRLF may be preserved as literal
    # `\r\n` or displayed via explicit markers.
    assert (
        ("\r\n" in rendered)
        or ("\\r\\n" in rendered)
        or ("␍␊" in rendered)
        or ("CRLF" in rendered.upper())
    )
    assert "\n\r" not in rendered  # avoid flipped sequence

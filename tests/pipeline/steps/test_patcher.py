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

from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.context import ProcessingContext
from topmark.pipeline.steps import (
    builder,
    comparer,
    patcher,
    reader,
    renderer,
    resolver,
    scanner,
    updater,
)
from topmark.utils.diff import render_patch

if TYPE_CHECKING:
    from pathlib import Path


def _run_to_patcher(path: Path, cfg: Config) -> ProcessingContext:
    """Drive the v2 pipeline up to `patcher.patch()` and return the ctx."""
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=path, config=cfg)
    ctx = resolver.resolve(ctx)
    ctx = reader.read(ctx)
    ctx = scanner.scan(ctx)
    ctx = builder.build(ctx)
    ctx = renderer.render(ctx)
    ctx = updater.update(ctx)  # produce updated_file_lines for the diff
    ctx = comparer.compare(ctx)  # compare using updated image
    ctx = patcher.patch(ctx)
    return ctx


def test_patcher_diff_preserves_crlf_and_render_markers(tmp_path: Path) -> None:
    r"""CRLF-seeded file → diff lines use CRLF; render_patch shows \\r\\n markers."""
    f: Path = tmp_path / "a.ts"
    # Ensure file content is CRLF-seeded.
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        # Add a syntactically valid TopMark header field (key:value)
        fp.write(
            f"// {TOPMARK_START_MARKER}\n// test:header\n// {TOPMARK_END_MARKER}\nconsole.log(1)\n"
        )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = _run_to_patcher(f, cfg)

    # We expect a change (strip/replace) to have produced a diff.
    diff_text: str = (ctx.diff.text if ctx.diff else "") or ""
    assert diff_text, "Expected non-empty unified diff from patcher"

    # The raw diff is produced with lineterm = ctx.newline_style.
    # If reader detected CRLF, ensure the diff contains CRLF in hunk lines.
    if ctx.newline_style == "\r\n":
        assert "\r\n" in diff_text, "Raw diff should contain CRLF line terminators"

    # Pass a list of lines to preserve native EOLs; when given a single string,
    # render_patch would lose CRLF markers due to splitlines() default behavior.
    rendered: str = render_patch(diff_text.splitlines(keepends=True))
    assert ("\\r\\n" in rendered) or ("␍␊" in rendered) or ("CRLF" in rendered.upper())
    assert "\n\r" not in rendered  # avoid flipped sequence

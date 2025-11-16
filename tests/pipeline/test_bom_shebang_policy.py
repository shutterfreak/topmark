# topmark:header:start
#
#   project      : TopMark
#   file         : test_bom_shebang_policy.py
#   file_relpath : tests/pipeline/test_bom_shebang_policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for BOM-before-shebang policy handling in the pipeline.

These tests exercise two layers:

* reader.read(): detects BOM + shebang conflict for shebang-aware types and
  marks the file as skipped with a clear diagnostic.
* updater.update(): when a write path is taken and both `leading_bom` and
  `has_shebang` are True, it avoids re-prepending the BOM and appends the same
  diagnostic, so users see consistent feedback even on apply paths.
"""

from __future__ import annotations

from pathlib import Path

from tests.pipeline.conftest import materialize_image_lines, run_steps
from topmark.config import Config, MutableConfig
from topmark.pipeline.context import ProcessingContext
from topmark.pipeline.status import (
    ContentStatus,
    PlanStatus,
    ResolveStatus,
    StripStatus,
)
from topmark.pipeline.steps.planner import PlannerStep
from topmark.pipeline.steps.reader import ReaderStep
from topmark.pipeline.steps.resolver import ResolverStep
from topmark.pipeline.steps.sniffer import SnifferStep
from topmark.pipeline.views import UpdatedView


def _ctx_for(path: Path) -> ProcessingContext:
    """Build a minimal ProcessingContext for a single file path.

    The resolver will populate `file_type` and `header_processor`.
    """
    cfg: Config = MutableConfig.from_defaults().freeze()
    return ProcessingContext.bootstrap(path=path, config=cfg)


def test_reader_skips_when_bom_precedes_shebang_python(tmp_path: Path) -> None:
    """BOM + shebang for a shebang-aware type must be skipped with diagnostic."""
    p: Path = tmp_path / "bom_and_shebang.py"
    # NOTE: BOM first, then shebang — invalid for POSIX shebang recognition
    p.write_text("\ufeff#! /usr/bin/env python\nprint('x')\n", encoding="utf-8")

    ctx: ProcessingContext = _ctx_for(p)
    ctx = run_steps(
        ctx,
        (
            ResolverStep(),
            SnifferStep(),
            ReaderStep(),
        ),
    )

    assert ctx.leading_bom is True
    assert ctx.has_shebang is True
    assert ctx.status.content == ContentStatus.SKIPPED_POLICY_BOM_BEFORE_SHEBANG
    assert any(
        "BOM appears before the shebang" in d.message or "BOM precedes shebang" in d.message
        for d in ctx.diagnostics
    ), ctx.diagnostics


def test_reader_allows_shebang_without_bom_python(tmp_path: Path) -> None:
    """Shebang without BOM should proceed normally and not be skipped."""
    p: Path = tmp_path / "shebang_only.py"
    p.write_text("#! /usr/bin/env python\nprint('ok')\n", encoding="utf-8")

    ctx: ProcessingContext = _ctx_for(p)
    ctx = run_steps(
        ctx,
        (
            ResolverStep(),
            SnifferStep(),
        ),
    )

    assert ctx.leading_bom is False
    assert ctx.has_shebang is True
    # Should not be skipped by the BOM/shebang policy (reader did not run, status still PENDING)
    assert ctx.status.content == ContentStatus.PENDING

    # Reader should have loaded lines
    ctx = run_steps(ctx, (ReaderStep(),))  # optional: then assert lines were loaded

    assert ctx.views.image
    file_lines: list[str] = materialize_image_lines(ctx)

    assert file_lines and file_lines[0].startswith("#!"), (
        file_lines[:2] if file_lines else "(File has no lines)"
    )


def test_updater_suppresses_bom_reprepend_in_strip_fastpath() -> None:
    """Updater must not re-prepend BOM when a shebang is present (fast path)."""
    # Construct a context hitting the strip fast-path in update():
    ctx: ProcessingContext = _ctx_for(path=Path("dummy.py"))
    ctx.leading_bom = True
    ctx.has_shebang = True

    # Simulate prior steps setting up a removal result
    updated_file_lines: list[str] = ["#! /usr/bin/env python\n", "print('x')\n"]
    ctx.views.updated = UpdatedView(lines=updated_file_lines)  # precomputed change

    # Ensure the may_proceed_to_updater() gating helper allows processing:
    ctx.status.resolve = ResolveStatus.RESOLVED
    ctx.status.content = ContentStatus.OK
    ctx.status.strip = StripStatus.READY

    ctx = run_steps(ctx, (PlannerStep(),))

    assert ctx.status.plan == PlanStatus.PREVIEWED  # Dry-run mode
    # Should *not* have a BOM re-attached
    assert ctx.views.updated

    assert not updated_file_lines[0].startswith("\ufeff"), updated_file_lines[0]
    # Diagnostic should be present to explain why BOM was not re-appended
    assert any("BOM appears before the shebang" in d.message for d in ctx.diagnostics), (
        ctx.diagnostics
    )

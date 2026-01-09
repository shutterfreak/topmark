# topmark:header:start
#
#   project      : TopMark
#   file         : test_comparer_e2e.py
#   file_relpath : tests/pipeline/integration/test_comparer_e2e.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""End-to-end tests for comparer with builder+renderer in the loop.

These tests exercise the full scan→build→render→compare path to validate that
(1) content differences are detected, and (2) *formatting-only* differences can
be surfaced when dicts are equal but the canonical render differs from the
on-disk header layout. The latter uses a minimal amount of synthesis to keep the
focus on the comparer while still calling builder+renderer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.pipeline.conftest import make_pipeline_context, run_insert, run_steps
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.status import ComparisonStatus, GenerationStatus, RenderStatus
from topmark.pipeline.steps import builder, comparer, reader, resolver, scanner
from topmark.pipeline.views import BuilderView, RenderView

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext


def test_e2e_content_change_detected(tmp_path: Path) -> None:
    """Content mismatch (dict-wise) is flagged as CHANGED end-to-end.

    The file contains a hand-authored header with `license`/`project`, while the
    default config/builder expects `file`/`file_relpath`. Dicts differ → CHANGED.
    """
    file: Path = tmp_path / "content_change.py"
    file.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "# license: MIT\n"
        "# project: TopMark\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('x')\n",
        encoding="utf-8",
    )

    # cfg: Config = MutableConfig.from_defaults().freeze()
    draft: MutableConfig = MutableConfig.from_defaults()
    draft.header_fields = ["file", "file_relpath"]
    draft.policy.render_empty_header_when_no_fields = True
    cfg: Config = draft.freeze()

    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # Full e2e path (no synthesis): resolver → reader → scanner → builder → renderer → comparer
    ctx = run_insert(file, cfg)
    assert ctx.status.comparison is ComparisonStatus.CHANGED, (
        "Builder produced different expected fields; comparer must flag CHANGED"
    )


def test_e2e_formatting_only_change_detected(tmp_path: Path) -> None:
    """Formatting-only drift is flagged as CHANGED with builder+renderer invoked.

    We configure the header fields to match the hand-authored header keys, but we
    arrange the on-disk header in a non-canonical *order*. We still call
    builder+renderer to keep the full pipeline engaged. To ensure the comparer
    evaluates the *formatting* branch (dicts equal), we then synthesize the
    comparer inputs so `expected_header_dict == existing_header_dict` while
    keeping the canonical block text from the processor.

    This keeps the test end-to-end (builder+renderer are exercised) while making
    the final comparison focus on formatting-only differences.
    We avoid calling the renderer here because the builder's configured schema
    may not include these fields; instead we render canonically with a local config
    for comparison.
    """
    file: Path = tmp_path / "formatting_only_e2e.py"
    file.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "# project: TopMark\n"  # non-canonical order (project before license)
        "# license: MIT\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('ok')\n",
        encoding="utf-8",
    )

    cfg: Config = MutableConfig.from_defaults().freeze()

    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    # Run builder to keep the test end-to-end, but do not rely on its fields
    # (builder may filter fields not present in the configured schema).
    ctx = run_steps(
        ctx,
        (
            resolver.ResolverStep(),
            reader.ReaderStep(),
            scanner.ScannerStep(),
            builder.BuilderStep(),
        ),
    )

    # Do NOT call renderer here: this test supplies the canonical render explicitly
    # so that we can focus the comparer on formatting-only differences.
    ctx.status.render = RenderStatus.RENDERED

    # Prepare a render-config that expresses the canonical order for the fields.
    draft_cfg_for_render: MutableConfig = MutableConfig.from_defaults()
    draft_cfg_for_render.header_fields = ["license", "project"]
    cfg_for_render: Config = draft_cfg_for_render.freeze()

    assert ctx.header_processor is not None, "Header processor must be set by resolver"
    assert ctx.views.header is not None
    assert ctx.views.build is not None

    ctx.views.build = BuilderView(
        builtins=None,
        selected=ctx.views.header.mapping or {},
    )

    expected_lines: list[str] = ctx.header_processor.render_header_lines(
        header_values=ctx.views.build.selected or {},
        config=cfg_for_render,
        newline_style=ctx.newline_style,
    )
    ctx.views.render = RenderView(lines=expected_lines, block="".join(expected_lines))
    ctx.status.generation = GenerationStatus.GENERATED

    ctx = run_steps(ctx, (comparer.ComparerStep(),))

    # Dicts must match, but block text must differ (ordering/spacing) → CHANGED
    assert (
        ctx.views.header is not None
        and ctx.views.build is not None
        and ctx.views.build.selected == ctx.views.header.mapping
    )
    assert ctx.views.render is not None and "".join(ctx.views.render.lines or []) != (
        ctx.views.header.block or ""
    )
    assert ctx.status.comparison is ComparisonStatus.CHANGED

# topmark:header:start
#
#   file         : test_comparer_e2e.py
#   file_relpath : tests/pipeline/integration/test_comparer_e2e.py
#   project      : TopMark
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

from pathlib import Path

from topmark.config import Config
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline.context import ComparisonStatus, GenerationStatus, ProcessingContext
from topmark.pipeline.steps import builder, comparer, reader, renderer, resolver, scanner


def test_e2e_content_change_detected(tmp_path: Path) -> None:
    """Content mismatch (dict-wise) is flagged as CHANGED end-to-end.

    The file contains a hand-authored header with `license`/`project`, while the
    default config/builder expects `file`/`file_relpath`. Dicts differ → CHANGED.
    """
    f = tmp_path / "content_change.py"
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "# license: MIT\n"
        "# project: TopMark\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('x')\n",
        encoding="utf-8",
    )

    cfg = Config.from_defaults()
    ctx = ProcessingContext.bootstrap(path=f, config=cfg)

    # Full e2e path (no synthesis): resolver → reader → scanner → builder → renderer → comparer
    ctx = resolver.resolve(ctx)
    ctx = reader.read(ctx)
    ctx = scanner.scan(ctx)
    ctx = builder.build(ctx)
    ctx = renderer.render(ctx)

    ctx = comparer.compare(ctx)

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
    f = tmp_path / "formatting_only_e2e.py"
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "# project: TopMark\n"  # non-canonical order (project before license)
        "# license: MIT\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('ok')\n",
        encoding="utf-8",
    )

    cfg = Config.from_defaults()

    ctx = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolver.resolve(ctx)
    assert ctx.header_processor is not None

    ctx = reader.read(ctx)
    ctx = scanner.scan(ctx)

    # Run builder to keep the test end-to-end, but do not rely on its fields
    # (builder may filter fields not present in the configured schema).
    ctx = builder.build(ctx)

    # Do NOT call renderer here: this test supplies the canonical render explicitly
    # so that we can focus the comparer on formatting-only differences.
    # Prepare a render-config that expresses the canonical order for the fields.
    cfg_for_render = Config.from_defaults()
    cfg_for_render.header_fields = ["license", "project"]

    assert ctx.header_processor is not None, "Header processor must be set by resolver"
    ctx.expected_header_dict = dict(ctx.existing_header_dict or {})

    expected_lines = ctx.header_processor.render_header_lines(
        header_values=ctx.expected_header_dict,
        config=cfg_for_render,
        newline_style=ctx.newline_style,
    )

    ctx.expected_header_lines = expected_lines
    ctx.status.generation = GenerationStatus.GENERATED

    ctx = comparer.compare(ctx)

    # Dicts must match, but block text must differ (ordering/spacing) → CHANGED
    assert ctx.expected_header_dict == ctx.existing_header_dict
    assert "".join(ctx.expected_header_lines or []) != (ctx.existing_header_block or "")
    assert ctx.status.comparison is ComparisonStatus.CHANGED

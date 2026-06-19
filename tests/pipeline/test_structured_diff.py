# topmark:header:start
#
#   project      : TopMark
#   file         : test_structured_diff.py
#   file_relpath : tests/pipeline/test_structured_diff.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Regression tests for structured unified-diff rendering."""

from __future__ import annotations

import difflib

import pytest

from topmark.pipeline.structured_diff import render_structured_unified_diff
from topmark.pipeline.views import PlanEditKind
from topmark.pipeline.views import PlannedEdit
from topmark.pipeline.views import infer_single_planned_edit


def _assert_structured_diff_matches_difflib(
    *,
    original_lines: list[str],
    updated_lines: list[str],
    kind: PlanEditKind,
    lineterm: str = "\n",
) -> None:
    """Assert that a structured one-splice diff matches `difflib` output."""
    edit: PlannedEdit | None = infer_single_planned_edit(
        kind=kind,
        original_lines=original_lines,
        updated_lines=updated_lines,
    )
    assert edit is not None

    structured_lines: list[str] | None = render_structured_unified_diff(
        original_lines=original_lines,
        edit=edit,
        fromfile="sample.py (current)",
        tofile="sample.py (updated)",
        fromfiledate="old-date",
        tofiledate="new-date",
        lineterm=lineterm,
        context=3,
    )
    difflib_lines: list[str] = list(
        difflib.unified_diff(
            original_lines,
            updated_lines,
            fromfile="sample.py (current)",
            tofile="sample.py (updated)",
            fromfiledate="old-date",
            tofiledate="new-date",
            lineterm=lineterm,
            n=3,
        )
    )

    assert structured_lines == difflib_lines


@pytest.mark.parametrize(
    ("original_lines", "updated_lines", "kind"),
    [
        pytest.param(
            [],
            ["header\n"],
            PlanEditKind.INSERT,
            id="insert-empty-file",
        ),
        pytest.param(
            ["body\n"],
            ["header\n", "body\n"],
            PlanEditKind.INSERT,
            id="insert-bof",
        ),
        pytest.param(
            ["#!/usr/bin/env python\n", "body\n"],
            ["#!/usr/bin/env python\n", "header\n", "body\n"],
            PlanEditKind.INSERT,
            id="insert-after-shebang",
        ),
        pytest.param(
            ["old header\n", "body\n"],
            ["new header\n", "body\n"],
            PlanEditKind.REPLACE,
            id="replace-header",
        ),
        pytest.param(
            ["header\n", "body\n"],
            ["body\n"],
            PlanEditKind.REMOVE,
            id="remove-header",
        ),
        pytest.param(
            ["old"],
            ["new"],
            PlanEditKind.REPLACE,
            id="replace-no-final-newline",
        ),
    ],
)
def test_structured_unified_diff_matches_difflib_for_single_splice(
    original_lines: list[str],
    updated_lines: list[str],
    kind: PlanEditKind,
) -> None:
    """Single-splice structured diffs should exactly match `difflib` output."""
    _assert_structured_diff_matches_difflib(
        original_lines=original_lines,
        updated_lines=updated_lines,
        kind=kind,
    )


def test_structured_unified_diff_matches_difflib_for_crlf_control_lines() -> None:
    """Structured diffs should preserve the requested diff control-line terminator."""
    _assert_structured_diff_matches_difflib(
        original_lines=["old\r\n", "body\r\n"],
        updated_lines=["new\r\n", "body\r\n"],
        kind=PlanEditKind.REPLACE,
        lineterm="\r\n",
    )


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=-1,
                old_end=0,
                new_lines=("header\n",),
            ),
            id="negative-start",
        ),
        pytest.param(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=1,
                old_end=0,
                new_lines=("header\n",),
            ),
            id="end-before-start",
        ),
        pytest.param(
            PlannedEdit(
                kind=PlanEditKind.REPLACE,
                old_start=0,
                old_end=2,
                new_lines=("header\n",),
            ),
            id="end-beyond-original-lines",
        ),
    ],
)
def test_structured_unified_diff_rejects_invalid_edit_ranges(
    edit: PlannedEdit,
) -> None:
    """Invalid edit ranges should not produce structured diffs."""
    diff_lines: list[str] | None = render_structured_unified_diff(
        original_lines=["body\n"],
        edit=edit,
        fromfile="sample.py (current)",
        tofile="sample.py (updated)",
        fromfiledate="old-date",
        tofiledate="new-date",
        lineterm="\n",
        context=3,
    )

    assert diff_lines is None


def test_structured_unified_diff_rejects_negative_context() -> None:
    """Negative context windows should not produce structured diffs."""
    diff_lines: list[str] | None = render_structured_unified_diff(
        original_lines=["body\n"],
        edit=PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=("header\n",),
        ),
        fromfile="sample.py (current)",
        tofile="sample.py (updated)",
        fromfiledate="old-date",
        tofiledate="new-date",
        lineterm="\n",
        context=-1,
    )

    assert diff_lines is None


def test_structured_unified_diff_returns_empty_diff_for_noop_edit() -> None:
    """A zero-length edit without replacement lines should produce no diff."""
    diff_lines: list[str] | None = render_structured_unified_diff(
        original_lines=["body\n"],
        edit=PlannedEdit(
            kind=PlanEditKind.INSERT,
            old_start=0,
            old_end=0,
            new_lines=(),
        ),
        fromfile="sample.py (current)",
        tofile="sample.py (updated)",
        fromfiledate="old-date",
        tofiledate="new-date",
        lineterm="\n",
        context=3,
    )

    assert diff_lines == []


def test_infer_single_planned_edit_returns_none_for_identical_images() -> None:
    """Identical images should not infer a planned edit."""
    edit: PlannedEdit | None = infer_single_planned_edit(
        kind=PlanEditKind.REPLACE,
        original_lines=["same\n", "body\n"],
        updated_lines=["same\n", "body\n"],
    )

    assert edit is None

# topmark:header:start
#
#   project      : TopMark
#   file         : test_view_pruning.py
#   file_relpath : tests/pipeline/test_view_pruning.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for pipeline view-pruning lifecycle helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.pipeline.pipelines import Pipeline
from topmark.pipeline.views import BuilderView
from topmark.pipeline.views import DiffView
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import RenderView
from topmark.pipeline.views import UpdatedView
from topmark.pipeline.views import Views
from topmark.pipeline.views import ViewSlot

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step


def test_release_consumed_keeps_views_needed_by_remaining_steps() -> None:
    """The lifecycle helper must not release payloads with downstream consumers."""
    header_mapping: Mapping[str, str] = {
        "project": "TopMark",
    }
    build_mapping: Mapping[str, str] = {
        "project": "TopMark",
    }
    views = Views(
        image=ListFileImageView(
            ["print('hello')\n"],
        ),
        header=HeaderView(
            range=(0, 4),
            lines=["# topmark:header:start\n"],
            block="# topmark:header:start\n",
            mapping=header_mapping,
        ),
        build=BuilderView(
            builtins=build_mapping,
            selected=build_mapping,
        ),
        render=RenderView(
            lines=["# rendered\n"],
            block="# rendered\n",
        ),
        updated=UpdatedView(
            lines=["# rendered\n", "print('hello')\n"],
        ),
        diff=DiffView(
            text="--- current\n+++ updated\n",
        ),
    )

    views.release_consumed(
        remaining_view_consumers={
            ViewSlot.IMAGE,
            ViewSlot.HEADER,
            ViewSlot.BUILD,
            ViewSlot.RENDER,
            ViewSlot.UPDATED,
        },
        keep_diff_view=True,
    )

    assert views.image is not None
    assert views.image.line_count() == 1
    assert views.header is not None
    assert views.header.lines is not None
    assert views.header.block is not None
    assert views.header.mapping is not None
    assert views.build is not None
    assert views.build.selected is not None
    assert views.render is not None
    assert views.render.lines is not None
    assert views.updated is not None
    assert views.updated.lines is not None
    assert views.diff is not None
    assert views.diff.text is not None


def test_release_consumed_releases_payloads_not_needed_before_writer() -> None:
    """Only the updated image and requested diff need to survive before the writer."""
    header_mapping: Mapping[str, str] = {"project": "TopMark"}
    build_mapping: Mapping[str, str] = {"project": "TopMark"}
    views = Views(
        image=ListFileImageView(
            ["print('hello')\n"],
        ),
        header=HeaderView(
            range=(0, 4),
            lines=["# topmark:header:start\n"],
            block="# topmark:header:start\n",
            mapping=header_mapping,
        ),
        build=BuilderView(
            builtins=build_mapping,
            selected=build_mapping,
        ),
        render=RenderView(
            lines=["# rendered\n"],
            block="# rendered\n",
        ),
        updated=UpdatedView(
            lines=["# rendered\n", "print('hello')\n"],
        ),
        diff=DiffView(
            text="--- current\n+++ updated\n",
        ),
    )

    views.release_consumed(
        remaining_view_consumers={ViewSlot.UPDATED},
        keep_diff_view=True,
    )

    assert views.image is not None
    assert views.image.line_count() == 0
    assert views.header is not None
    assert views.header.lines is None
    assert views.header.block is None
    assert views.header.mapping is None
    assert views.build is not None
    assert views.build.selected is None
    assert views.render is not None
    assert views.render.lines is None
    assert views.updated is not None
    assert views.updated.lines is not None
    assert views.diff is not None
    assert views.diff.text is not None


def test_release_consumed_releases_diff_unless_caller_keeps_it() -> None:
    """Diff payloads are retained only when explicitly requested."""
    views = Views(diff=DiffView(text="--- current\n+++ updated\n"))

    views.release_consumed(
        remaining_view_consumers=set(),
        keep_diff_view=False,
    )

    assert views.diff is not None
    assert views.diff.text is None


def test_pipeline_steps_declare_expected_view_consumers() -> None:
    """Verify the expected consumes_views declarations used by lifecycle pruning.

    The step implementations remain the source of truth via their
    ``consumes_views`` declarations. This test intentionally mirrors the
    current contract so that view-pruning behavior changes require an
    explicit test update and review.
    """
    expected_by_step_name: dict[str, frozenset[ViewSlot]] = {
        "ReaderStep": frozenset(),
        "ResolverStep": frozenset(),
        "SnifferStep": frozenset(),
        "ScannerStep": frozenset(
            {
                ViewSlot.IMAGE,
            }
        ),
        "BuilderStep": frozenset(),
        "RendererStep": frozenset(
            {
                ViewSlot.IMAGE,
                ViewSlot.HEADER,
                ViewSlot.BUILD,
            }
        ),
        "ComparerStep": frozenset(
            {
                ViewSlot.IMAGE,
                ViewSlot.HEADER,
                ViewSlot.BUILD,
                ViewSlot.RENDER,
                ViewSlot.UPDATED,
            }
        ),
        "PlannerStep": frozenset(
            {
                ViewSlot.IMAGE,
                ViewSlot.HEADER,
                ViewSlot.RENDER,
                ViewSlot.UPDATED,
                ViewSlot.EDIT,
            }
        ),
        "StripperStep": frozenset(
            {
                ViewSlot.IMAGE,
                ViewSlot.HEADER,
                ViewSlot.EDIT,
            }
        ),
        "PatcherStep": frozenset(
            {
                ViewSlot.IMAGE,
                ViewSlot.UPDATED,
                ViewSlot.EDIT,
            }
        ),
        "WriterStep": frozenset(
            {
                ViewSlot.UPDATED,
            }
        ),
    }

    steps_by_name: dict[str, Step[ProcessingContext]] = {
        step.name: step
        for step in (
            *Pipeline.CHECK_APPLY_PATCH.steps,
            *Pipeline.STRIP_APPLY_PATCH.steps,
        )
    }

    assert set(steps_by_name) == set(expected_by_step_name)
    for step_name, expected_consumers in expected_by_step_name.items():
        assert steps_by_name[step_name].consumes_views == expected_consumers


def test_release_all_releases_diff_payload() -> None:
    """Views.release_all() releases all payloads, including diff payload."""
    views = Views(diff=DiffView(text="--- current\n+++ updated\n"))

    views.release_all()

    assert views.diff is not None
    assert views.diff.text is None

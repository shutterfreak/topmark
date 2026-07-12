# topmark:header:start
#
#   project      : TopMark
#   file         : test_model.py
#   file_relpath : tests/pipeline/context/test_model.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for processing-context state and view accessors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.policy import FrozenPolicy
from topmark.config.policy import PolicyRegistry
from topmark.filetypes.model import FileType
from topmark.pipeline.context.model import HaltState
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.context.status import ProcessingStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.steps.patcher import PatcherStep
from topmark.pipeline.steps.reader import ReaderStep
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import UpdatedView
from topmark.pipeline.views import compose_updated_content

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig


def test_context_bootstrap_starts_with_independent_default_state(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Fresh contexts should not share mutable status, diagnostics, or views."""
    first: ProcessingContext = make_pipeline_context(
        tmp_path / "first.py",
        default_frozen_config,
    )
    second: ProcessingContext = make_pipeline_context(
        tmp_path / "second.py",
        default_frozen_config,
    )

    assert first.status == ProcessingStatus()
    assert first.halt_state is None
    assert first.is_halted is False
    assert first.steps == []
    assert list(first.diagnostics) == []
    assert list(first.diagnostic_hints) == []

    first.status.fs = FsStatus.EMPTY
    first.steps.append(ReaderStep())
    first.request_halt("test-halt", first.steps[0])

    assert second.status == ProcessingStatus()
    assert second.steps == []
    assert second.halt_state is None
    assert second.is_halted is False


def test_request_halt_records_stable_reason_and_step_name(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """A graceful halt should retain its machine reason and originating step."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "halt.py",
        default_frozen_config,
    )
    step = ReaderStep()

    context.request_halt("reader-policy", step)

    assert context.is_halted is True
    assert context.halt_state == HaltState(
        reason_code="reader-policy",
        step_name="ReaderStep",
    )


def test_image_accessors_return_empty_values_without_an_image(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Absent or released image payloads should be safe to query repeatedly."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "image.py",
        default_frozen_config,
    )

    assert list(context.iter_image_lines()) == []
    assert context.materialize_image_lines() == []
    assert context.image_line_count() == 0

    context.views.image = ListFileImageView(["first\n", "second"])

    assert list(context.iter_image_lines()) == ["first\n", "second"]
    assert context.materialize_image_lines() == ["first\n", "second"]
    assert context.image_line_count() == 2

    context.views.image.release()

    assert list(context.iter_image_lines()) == []
    assert context.materialize_image_lines() == []
    assert context.image_line_count() == 0


def test_updated_accessors_support_absent_released_and_lazy_content(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Updated accessors should preserve safe empties and repeatable lazy content."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "updated.py",
        default_frozen_config,
    )

    assert list(context.iter_updated_lines()) == []
    assert context.materialize_updated_lines() == []

    context.views.updated = UpdatedView(lines=None)

    assert list(context.iter_updated_lines()) == []
    assert context.materialize_updated_lines() == []

    context.views.updated.lines = compose_updated_content(
        ["prefix\n"],
        ["header\n"],
        ["body\n"],
    )

    assert list(context.iter_updated_lines()) == [
        "prefix\n",
        "header\n",
        "body\n",
    ]
    assert context.materialize_updated_lines() == [
        "prefix\n",
        "header\n",
        "body\n",
    ]
    assert list(context.iter_updated_lines()) == [
        "prefix\n",
        "header\n",
        "body\n",
    ]

    context.views.updated.release()

    assert list(context.iter_updated_lines()) == []
    assert context.materialize_updated_lines() == []


def test_get_effective_policy_uses_global_and_qualified_type_policies(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Context policy lookup should use the resolved file type's qualified key."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "policy.py",
        default_frozen_config,
    )
    global_policy = FrozenPolicy(allow_content_probe=False)
    python_policy = FrozenPolicy(allow_content_probe=True)
    context.policy_registry = PolicyRegistry(
        global_policy=global_policy,
        by_type={"topmark:python": python_policy},
    )

    assert context.get_effective_policy() is global_policy

    context.file_type = FileType(
        local_key="python",
        namespace="topmark",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        description="Python source",
    )

    assert context.get_effective_policy() is python_policy


def test_step_axes_exposes_declared_axis_values(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Step-axis projection should expose ordered, stable enum values."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "axes.py",
        default_frozen_config,
    )
    context.steps.extend([ReaderStep(), PatcherStep()])

    assert context.step_axes == {
        "ReaderStep": ["content"],
        "PatcherStep": ["comparison", "patch"],
    }


def test_bootstrap_preserves_explicit_policy_registry(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Bootstrap should retain an explicitly supplied policy registry by identity."""
    seeded_context: ProcessingContext = make_pipeline_context(
        tmp_path / "seed.py",
        default_frozen_config,
    )
    registry = PolicyRegistry(
        global_policy=FrozenPolicy(),
        by_type={},
    )

    context: ProcessingContext = ProcessingContext.bootstrap(
        path=tmp_path / "override.py",
        config=default_frozen_config,
        run_options=seeded_context.run_options,
        policy_registry_override=registry,
    )

    assert context.policy_registry is registry

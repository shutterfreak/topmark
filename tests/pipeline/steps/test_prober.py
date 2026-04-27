# topmark:header:start
#
#   project      : TopMark
#   file         : test_prober.py
#   file_relpath : tests/pipeline/steps/test_prober.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for the ProberStep pipeline step.

These tests validate that ProberStep correctly populates the resolution
probe, sets resolve status, and halts the pipeline appropriately without
invoking further steps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.registry import make_file_type
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps.prober import ProberStep
from topmark.processors.base import HeaderProcessor
from topmark.resolution.probe import ResolutionProbeStatus

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import EffectiveRegistries
    from topmark.config.model import Config
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import ProcessingContext


def _run_prober(ctx: ProcessingContext) -> ProcessingContext:
    """Run the ProberStep on a context and return it."""
    step = ProberStep()
    step(ctx)
    return ctx


def _make_context(path: Path) -> ProcessingContext:
    """Create a processing context with default frozen config.

    Args:
        path: Path to seed the processing context with.

    Returns:
        Processing context ready for direct pipeline-step execution.
    """
    cfg: Config = mutable_config_from_defaults().freeze()
    return make_pipeline_context(path=path, cfg=cfg)


def test_prober_step_resolves_supported_file(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Supported files should populate probe, file_type and processor."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    py_ft: FileType = make_file_type(local_key="python", extensions=[".py"])
    filetypes: dict[str, FileType] = {"python": py_ft}
    processors: dict[str, HeaderProcessor] = {"python": HeaderProcessor()}

    with effective_registries(filetypes, processors):
        ctx: ProcessingContext = _make_context(file)
        ctx = _run_prober(ctx)

    assert ctx.resolution_probe is not None
    assert ctx.resolution_probe.status == ResolutionProbeStatus.RESOLVED
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type is not None
    assert ctx.header_processor is not None
    assert ctx.halt_state is not None


def test_prober_step_handles_unsupported_file(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Unsupported files should halt with UNSUPPORTED status."""
    file: Path = tmp_path / "example.unknown"
    file.write_text("data\n", encoding="utf-8")

    with effective_registries({}, {}):
        ctx: ProcessingContext = _make_context(file)
        ctx = _run_prober(ctx)

    assert ctx.resolution_probe is not None
    assert ctx.resolution_probe.status == ResolutionProbeStatus.UNSUPPORTED
    assert ctx.status.resolve == ResolveStatus.UNSUPPORTED
    assert ctx.file_type is None
    assert ctx.header_processor is None
    assert ctx.halt_state is not None


def test_prober_step_handles_missing_processor(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Files with file type but no processor should report NO_PROCESSOR."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    py_ft: FileType = make_file_type(local_key="python", extensions=[".py"])
    filetypes: dict[str, FileType] = {"python": py_ft}

    # No processor registered
    with effective_registries(filetypes, {}):
        ctx: ProcessingContext = _make_context(file)
        ctx = _run_prober(ctx)

    assert ctx.resolution_probe is not None
    assert ctx.resolution_probe.status == ResolutionProbeStatus.NO_PROCESSOR
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
    assert ctx.file_type is not None
    assert ctx.header_processor is None
    assert ctx.halt_state is not None

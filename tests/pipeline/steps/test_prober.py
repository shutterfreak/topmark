# topmark:header:start
#
#   project      : TopMark
#   file         : test_prober.py
#   file_relpath : tests/pipeline/steps/test_prober.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Contract tests for the resolution-only `ProberStep`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.diagnostic.model import DiagnosticLevel
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.hints import Axis
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.steps import resolver as resolver_module
from topmark.pipeline.steps.prober import ProberStep
from topmark.processors.base import HeaderProcessor
from topmark.resolution.filetypes import probe_resolution_for_path
from topmark.resolution.probe import ResolutionProbeStatus
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    import pytest

    from tests.conftest import EffectiveRegistries
    from topmark.config.model import FrozenConfig
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import HaltState
    from topmark.resolution.probe import ResolutionProbeResult


def _run_prober(ctx: ProcessingContext) -> ProcessingContext:
    """Run the public ProberStep lifecycle on a context."""
    return ProberStep()(ctx)


def _make_context(path: Path) -> ProcessingContext:
    """Create a processing context representing a read-only probe run."""
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    return ProcessingContext.bootstrap(
        path=path,
        config=cfg,
        run_options=RunOptions(
            pipeline_kind="probe",
            apply_changes=False,
        ),
    )


def test_prober_step_declares_resolution_only_lifecycle_contract(tmp_path: Path) -> None:
    """Probing owns only resolution and is unconditionally eligible to run."""
    ctx: ProcessingContext = _make_context(tmp_path / "source.py")
    step = ProberStep()

    assert step.primary_axis == Axis.RESOLVE
    assert step.axes_written == (Axis.RESOLVE,)
    assert step.consumes_views == frozenset()
    assert step.may_proceed(ctx) is True


def test_prober_step_resolves_and_requests_successful_completion_halt(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Successful probing mirrors canonical bindings and halts as complete."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    file_type: FileType = make_file_type(local_key="python", extensions=[".py"])
    processor = HeaderProcessor()

    with effective_registries({"python": file_type}, {"python": processor}):
        original_ctx: ProcessingContext = _make_context(file)
        ctx: ProcessingContext = _run_prober(original_ctx)

    assert ctx is original_ctx
    assert len(ctx.steps) == 1
    assert isinstance(ctx.steps[0], ProberStep)
    assert ctx.resolution_probe is not None
    assert ctx.resolution_probe.status == ResolutionProbeStatus.RESOLVED
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type is file_type
    assert ctx.resolution_probe.selected_processor is not None
    assert ctx.header_processor is not None
    assert (
        ctx.header_processor.qualified_key == ctx.resolution_probe.selected_processor.qualified_key
    )
    assert ctx.header_processor.file_type is file_type
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "ProberStep"
    assert ctx.halt_state.reason_code == "Resolution probe completed."
    assert ctx.halt_state.reason_code != "ProberStep did not set state."
    assert ctx.diagnostics.items == []
    assert ctx.diagnostic_hints.items == []


def test_prober_step_preserves_unsupported_resolution_details(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Unsupported probing retains the shared helper's diagnostic and halt."""
    file: Path = tmp_path / "example.unknown"
    file.write_text("data\n", encoding="utf-8")

    with effective_registries({}, {}):
        original_ctx: ProcessingContext = _make_context(file)
        ctx: ProcessingContext = _run_prober(original_ctx)

    reason = "No file type associated with this file."
    assert ctx is original_ctx
    assert len(ctx.steps) == 1
    assert isinstance(ctx.steps[0], ProberStep)
    assert ctx.resolution_probe is not None
    assert ctx.resolution_probe.status == ResolutionProbeStatus.UNSUPPORTED
    assert ctx.status.resolve == ResolveStatus.UNSUPPORTED
    assert ctx.file_type is None
    assert ctx.header_processor is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "ProberStep"
    assert ctx.halt_state.reason_code == reason
    assert ctx.halt_state.reason_code != "Resolution probe completed."
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, reason),
    ]
    assert ctx.diagnostic_hints.items == []


def test_prober_step_preserves_no_processor_resolution_details(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """An unbound known type retains the shared helper's diagnostic and halt."""
    file: Path = tmp_path / "example.py"
    file.write_text("print('hello')\n", encoding="utf-8")

    file_type: FileType = make_file_type(local_key="python", extensions=[".py"])

    with effective_registries({"python": file_type}, {}):
        original_ctx: ProcessingContext = _make_context(file)
        ctx: ProcessingContext = _run_prober(original_ctx)

    reason = "No header processor registered for file type 'python'."
    assert ctx is original_ctx
    assert len(ctx.steps) == 1
    assert isinstance(ctx.steps[0], ProberStep)
    assert ctx.resolution_probe is not None
    assert ctx.resolution_probe.status == ResolutionProbeStatus.NO_PROCESSOR
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
    assert ctx.file_type is file_type
    assert ctx.header_processor is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "ProberStep"
    assert ctx.halt_state.reason_code == reason
    assert ctx.halt_state.reason_code != "Resolution probe completed."
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, reason),
    ]
    assert ctx.diagnostic_hints.items == []


def test_prober_step_preserves_header_unsupported_precedence(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Header-unsupported state takes precedence over an unbound processor."""
    file: Path = tmp_path / "README.md"
    file.write_text("# Documentation\n", encoding="utf-8")

    file_type: FileType = make_file_type(
        local_key="docs",
        extensions=[".md"],
        skip_processing=True,
    )

    with effective_registries({"docs": file_type}, {}):
        original_ctx: ProcessingContext = _make_context(file)
        ctx: ProcessingContext = _run_prober(original_ctx)

    reason = (
        "File type 'docs' (namespace: pytest) recognized; "
        "headers are not supported for this format."
    )
    assert ctx is original_ctx
    assert len(ctx.steps) == 1
    assert isinstance(ctx.steps[0], ProberStep)
    assert ctx.resolution_probe is not None
    assert ctx.resolution_probe.status == ResolutionProbeStatus.NO_PROCESSOR
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED
    assert ctx.file_type is file_type
    assert ctx.header_processor is None
    assert ctx.halt_state is not None
    assert ctx.halt_state.step_name == "ProberStep"
    assert ctx.halt_state.reason_code == reason
    assert ctx.halt_state.reason_code != "Resolution probe completed."
    assert [(item.level, item.message) for item in ctx.diagnostics.items] == [
        (DiagnosticLevel.INFO, reason),
    ]
    assert ctx.diagnostic_hints.items == []


def test_prober_reuses_authoritative_context_probe(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prober delegates without replacing an existing shared probe snapshot."""
    file: Path = tmp_path / "source.py"
    file_type: FileType = make_file_type(local_key="python", extensions=[".py"])
    processor = HeaderProcessor()

    with effective_registries({"python": file_type}, {"python": processor}):
        ctx: ProcessingContext = _make_context(file)
        probe: ResolutionProbeResult = probe_resolution_for_path(file)
        ctx.resolution_probe = probe

        def fail_if_recomputed(
            path: Path,
            *,
            include_file_types: Collection[str] | None = None,
            exclude_file_types: Collection[str] | None = None,
        ) -> ResolutionProbeResult:
            del path, include_file_types, exclude_file_types
            raise AssertionError("existing resolution probe was recomputed")

        monkeypatch.setattr(resolver_module, "probe_resolution_for_path", fail_if_recomputed)
        result: ProcessingContext = _run_prober(ctx)

    assert result is ctx
    assert ctx.resolution_probe is probe
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type is file_type
    assert ctx.header_processor is not None
    assert ctx.halt_state is not None
    assert ctx.halt_state.reason_code == "Resolution probe completed."
    assert ctx.diagnostic_hints.items == []


def test_prober_hint_is_noop_and_preserves_halt_state(tmp_path: Path) -> None:
    """Probe output, not a generic resolver hint, explains the resolution."""
    ctx: ProcessingContext = _make_context(tmp_path / "source.py")
    step = ProberStep()
    ctx.request_halt(reason="existing probe halt", at_step=step)
    halt_state: HaltState | None = ctx.halt_state

    step.hint(ctx)

    assert ctx.halt_state is halt_state
    assert ctx.diagnostic_hints.items == []

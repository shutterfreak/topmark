# topmark:header:start
#
#   project      : TopMark
#   file         : test_renderer.py
#   file_relpath : tests/pipeline/steps/test_renderer.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Direct contracts for the renderer pipeline step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import run_renderer
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.pipeline.hints import Axis
from topmark.pipeline.status import GenerationStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import RenderStatus
from topmark.pipeline.steps.renderer import RendererStep
from topmark.pipeline.views import BuilderView
from topmark.pipeline.views import HeaderView
from topmark.pipeline.views import ListFileImageView
from topmark.pipeline.views import RenderView
from topmark.pipeline.views import ViewSlot
from topmark.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.processors.base import RuntimeConfigLike


@dataclass(frozen=True, kw_only=True, slots=True)
class RenderCall:
    """Arguments passed across the renderer-to-processor boundary."""

    header_values: Mapping[str, str]
    config: RuntimeConfigLike
    newline_style: str
    header_indent_override: str | None


class RecordingProcessor(HeaderProcessor):
    """Deterministic processor double that records renderer-owned arguments."""

    namespace = "tests"
    local_key = "recording-renderer"
    line_prefix = "//"

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[RenderCall] = []

    def render_header_lines(
        self,
        header_values: Mapping[str, str],
        config: RuntimeConfigLike,
        newline_style: str,
        block_prefix_override: str | None = None,
        block_suffix_override: str | None = None,
        line_prefix_override: str | None = None,
        line_suffix_override: str | None = None,
        line_indent_override: str | None = None,
        header_indent_override: str | None = None,
    ) -> list[str]:
        """Record the orchestration arguments and return fixed rendered lines."""
        assert block_prefix_override is None
        assert block_suffix_override is None
        assert line_prefix_override is None
        assert line_suffix_override is None
        assert line_indent_override is None
        self.calls.append(
            RenderCall(
                header_values=header_values,
                config=config,
                newline_style=newline_style,
                header_indent_override=header_indent_override,
            )
        )
        return ["<rendered>\r\n", "</rendered>\r\n"]


def _renderer_config(
    *,
    header_fields: list[str],
    allow_empty_header: bool = False,
) -> FrozenConfig:
    """Return a coherent effective config with explicit renderer inputs."""
    config: MutableConfig = mutable_config_from_defaults()
    config.header_fields = header_fields
    config.policy.render_empty_header_when_no_fields = allow_empty_header
    return config.freeze()


def _renderer_context(
    path: Path,
    cfg: FrozenConfig,
    *,
    generation: GenerationStatus,
    selected: Mapping[str, str] | None,
    image_lines: list[str] | None = None,
) -> tuple[ProcessingContext, RecordingProcessor]:
    """Return a coherent unhalted context at the builder-to-renderer boundary."""
    ctx: ProcessingContext = make_pipeline_context(path, cfg)
    processor = RecordingProcessor()
    ctx.header_processor = processor
    ctx.status.generation = generation
    ctx.status.header = HeaderStatus.MISSING
    if selected is not None:
        ctx.views.build = BuilderView(builtins={"unused": "builtin"}, selected=selected)
    if image_lines is not None:
        ctx.views.image = ListFileImageView(image_lines)
    return ctx, processor


def test_renderer_declares_render_axis_and_consumed_views() -> None:
    """Renderer writes only render state and declares every view it reads."""
    step = RendererStep()

    assert step.primary_axis is Axis.RENDER
    assert step.axes_written == (Axis.RENDER,)
    assert step.consumes_views == frozenset({ViewSlot.IMAGE, ViewSlot.HEADER, ViewSlot.BUILD})


def test_renderer_passes_selected_fields_config_and_newline_to_processor(tmp_path: Path) -> None:
    """Generated fields cross the processor boundary unchanged and are captured exactly."""
    cfg: FrozenConfig = _renderer_config(header_fields=["project", "file"])
    selected: dict[str, str] = {"project": "TopMark", "file": "source.py"}
    ctx, processor = _renderer_context(
        tmp_path / "source.py",
        cfg,
        generation=GenerationStatus.GENERATED,
        selected=selected,
    )
    ctx.newline_style = "\r\n"

    run_renderer(ctx)

    assert processor.calls == [
        RenderCall(
            header_values=selected,
            config=cfg,
            newline_style="\r\n",
            header_indent_override=None,
        )
    ]
    assert ctx.status.render is RenderStatus.RENDERED
    assert ctx.views.render == RenderView(
        lines=["<rendered>\r\n", "</rendered>\r\n"],
        block="<rendered>\r\n</rendered>\r\n",
    )
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    assert ctx.diagnostic_hints.items == []


def test_renderer_preserves_existing_pre_prefix_indentation(tmp_path: Path) -> None:
    """Existing spaces and tabs before the active line prefix are handed to the processor."""
    cfg: FrozenConfig = _renderer_config(header_fields=["project"])
    selected: dict[str, str] = {"project": "TopMark"}
    ctx, processor = _renderer_context(
        tmp_path / "source.jsonc",
        cfg,
        generation=GenerationStatus.GENERATED,
        selected=selected,
        image_lines=["{\n", "\t  // topmark:header:start\n", "\t  // topmark:header:end\n"],
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.views.header = HeaderView(
        range=(1, 2),
        lines=["\t  // topmark:header:start\n", "\t  // topmark:header:end\n"],
        block="\t  // topmark:header:start\n\t  // topmark:header:end\n",
        mapping={},
    )

    run_renderer(ctx)

    assert processor.calls == [
        RenderCall(
            header_values=selected,
            config=cfg,
            newline_style="\n",
            header_indent_override="\t  ",
        )
    ]
    assert ctx.status.render is RenderStatus.RENDERED
    assert ctx.halt_state is None


def test_renderer_omits_indent_override_for_unindented_existing_header(tmp_path: Path) -> None:
    """An existing header at column zero does not invent a pre-prefix override."""
    cfg: FrozenConfig = _renderer_config(header_fields=["project"])
    selected: dict[str, str] = {"project": "TopMark"}
    ctx, processor = _renderer_context(
        tmp_path / "source.jsonc",
        cfg,
        generation=GenerationStatus.GENERATED,
        selected=selected,
        image_lines=["// topmark:header:start\n", "// topmark:header:end\n"],
    )
    ctx.status.header = HeaderStatus.DETECTED
    ctx.views.header = HeaderView(
        range=(0, 1),
        lines=["// topmark:header:start\n", "// topmark:header:end\n"],
        block="// topmark:header:start\n// topmark:header:end\n",
        mapping={},
    )

    run_renderer(ctx)

    assert processor.calls[0].header_indent_override is None
    assert ctx.status.render is RenderStatus.RENDERED
    assert ctx.halt_state is None


def test_renderer_renders_markers_only_when_no_fields_are_allowed(tmp_path: Path) -> None:
    """The allowed no-fields policy delegates an empty mapping to the processor."""
    cfg: FrozenConfig = _renderer_config(header_fields=[], allow_empty_header=True)
    ctx, processor = _renderer_context(
        tmp_path / "source.py",
        cfg,
        generation=GenerationStatus.NO_FIELDS,
        selected=None,
    )
    ctx.newline_style = "\r\n"

    run_renderer(ctx)

    assert processor.calls == [
        RenderCall(
            header_values={},
            config=cfg,
            newline_style="\r\n",
            header_indent_override=None,
        )
    ]
    assert ctx.status.render is RenderStatus.RENDERED
    assert ctx.views.render == RenderView(
        lines=["<rendered>\r\n", "</rendered>\r\n"],
        block="<rendered>\r\n</rendered>\r\n",
    )
    assert ctx.diagnostics.items == []
    assert ctx.halt_state is None
    assert ctx.diagnostic_hints.items == []


def test_renderer_skips_denied_no_fields_without_calling_processor(tmp_path: Path) -> None:
    """The denied no-fields policy attaches an empty view and owns the terminal halt."""
    cfg: FrozenConfig = _renderer_config(header_fields=[])
    ctx, processor = _renderer_context(
        tmp_path / "source.py",
        cfg,
        generation=GenerationStatus.NO_FIELDS,
        selected=None,
    )

    run_renderer(ctx)

    assert processor.calls == []
    assert ctx.status.render is RenderStatus.SKIPPED
    assert ctx.views.render == RenderView(lines=None, block=None)
    assert ctx.halt_state is not None
    assert (ctx.halt_state.reason_code, ctx.halt_state.step_name) == (
        "RendererStep skipped.",
        "RendererStep",
    )
    assert ctx.diagnostics.items == []
    assert ctx.diagnostic_hints.items == []


def test_renderer_completes_empty_generated_selection_without_processor_call(
    tmp_path: Path,
) -> None:
    """A reachable all-unknown builder selection remains a coherent empty render."""
    cfg: FrozenConfig = _renderer_config(header_fields=["unknown"])
    ctx, processor = _renderer_context(
        tmp_path / "source.py",
        cfg,
        generation=GenerationStatus.GENERATED,
        selected={},
    )

    run_renderer(ctx)

    assert processor.calls == []
    assert ctx.status.render is RenderStatus.RENDERED
    assert ctx.views.render == RenderView(lines=[], block="")
    assert ctx.halt_state is None
    assert ctx.diagnostic_hints.items == []

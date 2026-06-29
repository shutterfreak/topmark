# topmark:header:start
#
#   project      : TopMark
#   file         : pipeline_memory_baseline.py
#   file_relpath : tools/perf/pipeline_memory_baseline.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Measure memory behavior for TopMark pipeline processing.

The tool generates deterministic benchmark files, runs selected TopMark pipeline
variants against them, and writes JSON plus optional Markdown summaries containing
elapsed time, tracemalloc peaks, RSS observations where available, per-step
samples, and retained-view summaries.

The default scenario and mode suites are intentionally stable. They preserve the
historical baseline lifecycle established by issue #134 so memory evolution can be
compared across later performance work. Optimized lifecycle variants are exposed
as explicit `*_pruned` modes instead of replacing the historical mode names.

The script avoids optional profiling dependencies so it can run in CI and on
fresh source checkouts before the project decides whether heavier tools such as
memray or pympler are warranted.
"""

from __future__ import annotations

# The source-checkout bootstrap below intentionally precedes TopMark imports.
# ruff: noqa: E402
import argparse
import contextlib
import gc
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final
from typing import Literal

# Allow running this tool directly from a source checkout without requiring an
# editable install. The bootstrap must occur before any TopMark imports.
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SRC_ROOT: Final[Path] = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.policy import make_policy_registry
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.engine import PipelineExecutionState
from topmark.pipeline.engine import iter_steps_for_files
from topmark.pipeline.pipelines import select_pipeline
from topmark.pipeline.reduction import iter_processing_results
from topmark.runtime.model import RunOptions

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence
    from resource import struct_rusage

    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.config.policy import PolicyRegistry
    from topmark.core.exit_codes import ExitCode
    from topmark.pipeline.pipelines import PipelineSelection
    from topmark.pipeline.protocols import Step
    from topmark.pipeline.result import ProcessingResult
    from topmark.pipeline.views import ViewSlot


PipelineKind = Literal["check", "strip"]
SuiteName = Literal["smoke", "baseline", "pathological", "repository"]
ScenarioName = Literal[
    "small_1kb_missing_header",
    "small_10kb_existing_header",
    "medium_100kb_missing_header",
    "medium_1mb_missing_header",
    "large_10mb_missing_header",
    "huge_header",
    "huge_diff",
    "insert_near_end",
    "strip_large_header",
    "mixed_newlines",
    "bom_file",
    "repo_many_small_mixed",
]

# ---- Benchmark scenario and suite definitions ----

DEFAULT_SCENARIOS: Final[tuple[ScenarioName, ...]] = (
    "small_1kb_missing_header",
    "small_10kb_existing_header",
    "medium_100kb_missing_header",
    "medium_1mb_missing_header",
    "huge_header",
    "huge_diff",
    "insert_near_end",
    "strip_large_header",
    "mixed_newlines",
    "bom_file",
)
LARGE_SCENARIOS: Final[tuple[ScenarioName, ...]] = ("large_10mb_missing_header",)

# Repository scenarios are opt-in so the default ad-hoc run stays comparable with
# the historical single-file baseline corpus.
REPOSITORY_SCENARIOS: Final[tuple[ScenarioName, ...]] = ("repo_many_small_mixed",)

# ---- Pipeline mode definitions ----
DEFAULT_MODES: Final[tuple[str, ...]] = (
    "check",
    "check_diff",
    "check_apply",
    "check_stdout",
    "strip",
    "strip_diff",
)

# Historical modes intentionally keep the unpruned lifecycle used by the #134
# baseline. Use explicit `*_pruned` variants for #140 lifecycle measurements.
PRUNED_MODES: Final[tuple[str, ...]] = (
    "check_pruned",
    "check_diff_pruned",
    "check_apply_pruned",
    "check_stdout_pruned",
    "strip_pruned",
    "strip_diff_pruned",
)
ALL_MODES: Final[tuple[str, ...]] = DEFAULT_MODES + PRUNED_MODES

# ---- Predefined benchmark suites ----

# Historical suites keep their original mode names to preserve #134 comparability.
# The repository suite is deliberately pruned-only because it measures aggregate
# durable result ownership after volatile view release, not legacy retained views.
SUITE_SCENARIOS: Final[dict[SuiteName, tuple[ScenarioName, ...]]] = {
    "smoke": ("small_1kb_missing_header",),
    "baseline": (
        "small_1kb_missing_header",
        "small_10kb_existing_header",
        "medium_100kb_missing_header",
        "medium_1mb_missing_header",
        "huge_header",
        "huge_diff",
        "insert_near_end",
        "strip_large_header",
        "mixed_newlines",
        "bom_file",
    ),
    "pathological": ("huge_header", "huge_diff", "strip_large_header"),
    "repository": REPOSITORY_SCENARIOS,
}
SUITE_MODES: Final[dict[SuiteName, tuple[str, ...]]] = {
    "smoke": ("check",),
    "baseline": DEFAULT_MODES,
    "pathological": (
        "check",
        "check_diff",
        "strip",
        "strip_diff",
    ),
    "repository": (
        "check_pruned",
        "check_diff_pruned",
        "strip_pruned",
        "strip_diff_pruned",
    ),
}
REPOSITORY_FILE_COUNT: Final[int] = 250
HEADER_LINES: Final[tuple[str, ...]] = (
    "# topmark:header:start\n",
    "#\n",
    "#   project      : TopMarkPerf\n",
    "#   file         : baseline.py\n",
    "#   license      : MIT\n",
    "#   copyright    : (c) 2025 TopMark\n",
    "#\n",
    "# topmark:header:end\n",
)


@dataclass(frozen=True, kw_only=True, slots=True)
class RunDestination:
    """Resolved output destination for a benchmark run."""

    output_file: Path
    output_dir: Path | None
    run_id: str | None


@dataclass(frozen=True, kw_only=True, slots=True)
class Scenario:
    """Generated benchmark scenario description.

    A scenario may point at one file or at a directory tree for repository-scale
    measurements. `size_bytes` and `file_count` are aggregate values for the full
    generated input.
    """

    name: ScenarioName
    path: Path
    size_bytes: int
    description: str
    file_count: int = 1


@dataclass(frozen=True, kw_only=True, slots=True)
class Mode:
    """Pipeline mode to benchmark."""

    name: str
    kind: PipelineKind
    apply: bool
    diff: bool
    output_target: OutputTarget
    prune_views: bool
    emit_diff: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class StepSample:
    """Memory and timing sample captured around one pipeline step."""

    step: str
    elapsed_ns: int
    current_tracemalloc_bytes: int
    peak_tracemalloc_bytes: int
    rss_bytes: int | None
    image_lines: int
    header_lines: int
    render_lines: int
    updated_lines: int
    diff_bytes: int


@dataclass(frozen=True, kw_only=True, slots=True)
class RunMeasurement:
    """Measurement result for one scenario/mode pair.

    Single-file measurements retain step samples and final view-size summaries.
    Repository-scale measurements record aggregate result counts and durable diff
    bytes after reduction, while omitting per-file step samples.
    """

    scenario: str
    mode: str
    file_size_bytes: int
    elapsed_ns: int
    peak_tracemalloc_bytes: int
    final_tracemalloc_bytes: int
    start_rss_bytes: int | None
    end_rss_bytes: int | None
    max_observed_rss_bytes: int | None
    stdout_bytes: int
    input_file_count: int
    result_count: int
    result_diff_bytes: int
    exit_code: int | None
    status: dict[str, str]
    views_before_prune: dict[str, int | bool]
    views_after_prune: dict[str, int | bool]
    steps: list[StepSample]


# ---- Lightweight measurement helpers ----
def _rss_bytes() -> int | None:
    """Return current process max RSS where the platform exposes it.

    Returns:
        RSS in bytes when available, otherwise `None`.
    """
    if sys.platform == "win32":
        return None

    try:
        import resource
    except ImportError:
        return None

    usage: struct_rusage = resource.getrusage(resource.RUSAGE_SELF)
    value = int(usage.ru_maxrss)
    if sys.platform == "darwin":
        return value
    return value * 1024


def _max_optional_rss(*values: int | None) -> int | None:
    """Return the maximum RSS observation when the platform reports RSS."""
    observed: list[int] = [value for value in values if value is not None]
    if not observed:
        return None
    return max(observed)


def _line_count(value: object) -> int:
    """Best-effort count for sequence-like retained view payloads."""
    if value is None:
        return 0
    if hasattr(value, "__len__"):
        return len(value)  # pyright: ignore[reportArgumentType]
    return -1


def _view_sizes(ctx: ProcessingContext) -> dict[str, int | bool]:
    """Return lightweight retained-view size indicators for a context."""
    image_lines: int = ctx.views.image.line_count() if ctx.views.image is not None else 0
    header_lines: int = _line_count(ctx.views.header.lines) if ctx.views.header is not None else 0
    render_lines: int = _line_count(ctx.views.render.lines) if ctx.views.render is not None else 0
    updated_lines: int = (
        _line_count(ctx.views.updated.lines) if ctx.views.updated is not None else 0
    )
    diff_text: str | None = ctx.views.diff.text if ctx.views.diff is not None else None
    return {
        "image_lines": image_lines,
        "header_lines": header_lines,
        "header_block_bytes": len(ctx.views.header.block.encode("utf-8"))
        if ctx.views.header is not None and ctx.views.header.block is not None
        else 0,
        "render_lines": render_lines,
        "render_block_bytes": len(ctx.views.render.block.encode("utf-8"))
        if ctx.views.render is not None and ctx.views.render.block is not None
        else 0,
        "updated_lines": updated_lines,
        "diff_bytes": len(diff_text.encode("utf-8")) if diff_text is not None else 0,
        "has_build_view": ctx.views.build is not None,
    }


def _status_dict(ctx: ProcessingContext) -> dict[str, str]:
    """Return compact final status values for one context."""
    return {
        "resolve": ctx.status.resolve.value,
        "fs": ctx.status.fs.value,
        "content": ctx.status.content.value,
        "header": ctx.status.header.value,
        "generation": ctx.status.generation.value,
        "render": ctx.status.render.value,
        "comparison": ctx.status.comparison.value,
        "strip": ctx.status.strip.value,
        "plan": ctx.status.plan.value,
        "patch": ctx.status.patch.value,
        "write": ctx.status.write.value,
    }


def _format_bytes(value: int | None) -> str:
    """Format bytes as a compact human-readable string."""
    if value is None:
        return "n/a"
    units = ("B", "KiB", "MiB", "GiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{value} B"
        amount /= 1024
    return f"{value} B"


def _format_ms(elapsed_ns: int) -> str:
    """Format nanoseconds as milliseconds."""
    return f"{elapsed_ns / 1_000_000:.2f}"


def _utc_run_id(suite: SuiteName | None) -> str:
    """Return a timestamp-based run identifier."""
    stamp: str = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"{stamp}-{suite}" if suite is not None else stamp


def _read_git_commit() -> str | None:
    """Return the current Git commit when this checkout is inside a Git repository."""
    head: Path = REPO_ROOT / ".git" / "HEAD"
    try:
        ref: str = head.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if ref.startswith("ref: "):
        ref_path: Path = REPO_ROOT / ".git" / ref.removeprefix("ref: ")
        try:
            return ref_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return ref or None


def _write_summary(path: Path, measurements: Sequence[RunMeasurement]) -> None:
    """Write a compact Markdown summary for a benchmark run."""
    lines: list[str] = [
        "# TopMark pipeline memory baseline",
        "",
        "| Scenario | Mode | Files | File size | Image lines | Updated lines | Diff size | "
        "Result diff | Peak traced | Max RSS | Elapsed ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for measurement in measurements:
        lines.append(
            "| "
            f"{measurement.scenario} | "
            f"{measurement.mode} | "
            f"{measurement.input_file_count} | "
            f"{_format_bytes(measurement.file_size_bytes)} | "
            f"{measurement.views_before_prune['image_lines']} | "
            f"{measurement.views_before_prune['updated_lines']} | "
            f"{_format_bytes(int(measurement.views_before_prune['diff_bytes']))} | "
            f"{_format_bytes(measurement.result_diff_bytes)} | "
            f"{_format_bytes(measurement.peak_tracemalloc_bytes)} | "
            f"{_format_bytes(measurement.max_observed_rss_bytes)} | "
            f"{_format_ms(measurement.elapsed_ns)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---- Benchmark input and output setup ----
def _resolve_destination(args: argparse.Namespace, *, suite: SuiteName | None) -> RunDestination:
    """Resolve file and directory destinations for benchmark output."""
    output: Path | None = args.output
    output_dir: Path | None = args.output_dir
    run_id: str | None = args.run_id

    if output is not None and (output_dir is not None or run_id is not None):
        raise ValueError("--output cannot be combined with --output-dir or --run-id")

    if output is not None:
        return RunDestination(output_file=output, output_dir=None, run_id=None)

    if output_dir is None:
        output_dir = Path("artifacts/perf")
    if run_id is None:
        run_id = _utc_run_id(suite)

    run_dir: Path = output_dir / run_id
    if run_dir.exists() and not bool(args.overwrite):
        raise FileExistsError(
            f"Benchmark run directory already exists: {run_dir}. "
            "Choose a different --run-id or pass --overwrite."
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunDestination(output_file=run_dir / "report.json", output_dir=run_dir, run_id=run_id)


def _make_config(root: Path) -> FrozenConfig:
    """Create a minimal benchmark config rooted at `root`."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.files = [str(root)]
    draft.relative_to_raw = str(root)
    draft.relative_to = root
    draft.header_fields = ["project", "file", "license", "copyright"]
    draft.field_values = {
        "project": "TopMarkPerf",
        "license": "MIT",
        "copyright": "(c) 2025 TopMark",
    }
    draft.align_fields = True
    return draft.freeze()


def _write_repeated_body(path: Path, *, target_bytes: int, prefix: str = "print") -> None:
    """Write a deterministic Python-like body of approximately `target_bytes`."""
    line_template: str = f"{prefix}('topmark performance baseline line')\n"
    lines_needed: int = max(1, target_bytes // len(line_template.encode("utf-8")))
    path.write_text(line_template * lines_needed, encoding="utf-8")


def _write_with_header(path: Path, *, body_bytes: int) -> None:
    """Write a deterministic Python file with an existing TopMark header."""
    body_line = "print('existing header baseline body')\n"
    lines_needed: int = max(1, body_bytes // len(body_line.encode("utf-8")))
    path.write_text("".join(HEADER_LINES) + (body_line * lines_needed), encoding="utf-8")


def _write_huge_header(path: Path, *, header_lines: int, body_bytes: int) -> None:
    """Write a file containing a very large detected TopMark header."""
    lines: list[str] = ["# topmark:header:start\n", "#\n"]
    for index in range(header_lines):
        lines.append(f"#   generated_{index:05d} : value {index}\n")
    lines.extend(["#\n", "# topmark:header:end\n"])
    body_line = "print('body after huge header')\n"
    body_count: int = max(1, body_bytes // len(body_line.encode("utf-8")))
    path.write_text("".join(lines) + (body_line * body_count), encoding="utf-8")


def _write_huge_diff(path: Path, *, body_bytes: int) -> None:
    """Write a file with a malformed/outdated header to force a large diff vicinity."""
    body_line = "print('huge diff body line with stable content')\n"
    body_count: int = max(1, body_bytes // len(body_line.encode("utf-8")))
    header: list[str] = [
        "# topmark:header:start\n",
        "#\n",
        "#   project      : OutdatedProject\n",
        "#   file         : old.py\n",
        "#   license      : Proprietary\n",
        "#   copyright    : (c) 1999 Someone Else\n",
        "#\n",
        "# topmark:header:end\n",
    ]
    path.write_text("".join(header) + (body_line * body_count), encoding="utf-8")


def _write_repository_workload(
    root: Path,
    *,
    file_count: int = REPOSITORY_FILE_COUNT,
) -> None:
    """Write the deterministic many-file repository-scale workload.

    The mix intentionally includes missing, current, and outdated headers so the
    repository suite exercises unchanged, insert, replace, and diff-retention paths
    without depending on external fixture data.
    """
    for index in range(file_count):
        package_dir: Path = root / f"package_{index // 25:02d}"
        package_dir.mkdir(parents=True, exist_ok=True)
        path: Path = package_dir / f"module_{index:04d}.py"
        if index % 10 == 0:
            _write_huge_diff(path, body_bytes=24_000)
        elif index % 3 == 0:
            _write_with_header(path, body_bytes=8_000)
        else:
            _write_repeated_body(path, target_bytes=8_000)


def _tree_size_bytes(root: Path) -> int:
    """Return the total size of files below `root`."""
    if root.is_file():
        return root.stat().st_size
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _tree_file_count(root: Path) -> int:
    """Return the number of files below `root`."""
    if root.is_file():
        return 1
    return sum(1 for path in root.rglob("*") if path.is_file())


def build_scenarios(root: Path, *, include_large: bool) -> list[Scenario]:
    """Generate benchmark files and return their scenario descriptors."""
    names: tuple[ScenarioName, ...] = (
        DEFAULT_SCENARIOS + REPOSITORY_SCENARIOS + (LARGE_SCENARIOS if include_large else ())
    )
    scenarios: list[Scenario] = []

    for name in names:
        path: Path = root / f"{name}.py"
        description: str
        match name:
            case "small_1kb_missing_header":
                _write_repeated_body(path, target_bytes=1_024)
                description = "Small file without a header; exercises insertion baseline."
            case "small_10kb_existing_header":
                _write_with_header(path, body_bytes=10_000)
                description = "Small file with an existing header; exercises scan/compare baseline."
            case "medium_100kb_missing_header":
                _write_repeated_body(path, target_bytes=100_000)
                description = "Medium file without a header; captures normal insertion scaling."
            case "medium_1mb_missing_header":
                _write_repeated_body(path, target_bytes=1_000_000)
                description = (
                    "One-megabyte file without a header; captures list-backed image costs."
                )
            case "large_10mb_missing_header":
                _write_repeated_body(path, target_bytes=10_000_000)
                description = "Large file without a header; optional heavier baseline workload."
            case "huge_header":
                _write_huge_header(path, header_lines=10_000, body_bytes=10_000)
                description = "Huge detected header; stresses scanner/header view retention."
            case "huge_diff":
                _write_huge_diff(path, body_bytes=1_000_000)
                description = "Large changed file with outdated header; stresses diff generation."
            case "insert_near_end":
                # Python inserts after shebang/encoding at the top, so use a large body to
                # approximate the retained-image cost of preserving content around insertion.
                _write_repeated_body(path, target_bytes=1_000_000, prefix="value")
                description = "Large insertion workload; approximates insertion composition cost."
            case "strip_large_header":
                _write_huge_header(path, header_lines=10_000, body_bytes=1_000_000)
                description = (
                    "Large strip workload; stresses removed-header and updated-image costs."
                )
            case "repo_many_small_mixed":
                # Repository workloads are directory scenarios. Avoid the default
                # `.py` suffix used by single-file scenarios so aggregate file counts
                # and sizes describe the generated tree rather than a placeholder file.
                path = root / name
                path.mkdir(parents=True, exist_ok=True)
                _write_repository_workload(path)
                description = (
                    "Repository-scale workload with many small Python files, mixing "
                    "missing, current, and outdated headers."
                )
            case "mixed_newlines":
                path.write_bytes(b"print('a')\nprint('b')\r\nprint('c')\n")
                description = "Mixed newline file; should stop before expensive update paths."
            case "bom_file":
                path.write_bytes("\ufeffprint('bom baseline')\n".encode("utf-8"))
                description = (
                    "BOM-bearing file; exercises BOM normalization and retention behavior."
                )
        scenarios.append(
            Scenario(
                name=name,
                path=path,
                size_bytes=_tree_size_bytes(path),
                description=description,
                file_count=_tree_file_count(path),
            )
        )
    return scenarios


# ---- Mode resolution and pipeline execution ----
def _mode_from_name(name: str) -> Mode:
    """Return a configured benchmark mode by name.

    Historical mode names keep `prune_views=False` to preserve comparability with
    the original #134 baseline. Names ending in `_pruned` opt into the #140
    lifecycle policy and make before/after comparisons explicit in reports.
    """
    match name:
        case "check":
            return Mode(
                name=name,
                kind="check",
                apply=False,
                diff=False,
                output_target=OutputTarget.FILE,
                prune_views=False,
                emit_diff=False,
            )
        case "check_diff":
            return Mode(
                name=name,
                kind="check",
                apply=False,
                diff=True,
                output_target=OutputTarget.FILE,
                prune_views=False,
                emit_diff=True,
            )
        case "check_apply":
            return Mode(
                name=name,
                kind="check",
                apply=True,
                diff=False,
                output_target=OutputTarget.FILE,
                prune_views=False,
                emit_diff=False,
            )
        case "check_stdout":
            return Mode(
                name=name,
                kind="check",
                apply=False,
                diff=False,
                output_target=OutputTarget.STDOUT,
                prune_views=False,
                emit_diff=False,
            )
        case "strip":
            return Mode(
                name=name,
                kind="strip",
                apply=False,
                diff=False,
                output_target=OutputTarget.FILE,
                prune_views=False,
                emit_diff=False,
            )
        case "strip_diff":
            return Mode(
                name=name,
                kind="strip",
                apply=False,
                diff=True,
                output_target=OutputTarget.FILE,
                prune_views=False,
                emit_diff=True,
            )
        case "check_pruned":
            return Mode(
                name=name,
                kind="check",
                apply=False,
                diff=False,
                output_target=OutputTarget.FILE,
                prune_views=True,
                emit_diff=False,
            )
        case "check_diff_pruned":
            return Mode(
                name=name,
                kind="check",
                apply=False,
                diff=True,
                output_target=OutputTarget.FILE,
                prune_views=True,
                emit_diff=True,
            )
        case "check_apply_pruned":
            return Mode(
                name=name,
                kind="check",
                apply=True,
                diff=False,
                output_target=OutputTarget.FILE,
                prune_views=True,
                emit_diff=False,
            )
        case "check_stdout_pruned":
            return Mode(
                name=name,
                kind="check",
                apply=False,
                diff=False,
                output_target=OutputTarget.STDOUT,
                prune_views=True,
                emit_diff=False,
            )
        case "strip_pruned":
            return Mode(
                name=name,
                kind="strip",
                apply=False,
                diff=False,
                output_target=OutputTarget.FILE,
                prune_views=True,
                emit_diff=False,
            )
        case "strip_diff_pruned":
            return Mode(
                name=name,
                kind="strip",
                apply=False,
                diff=True,
                output_target=OutputTarget.FILE,
                prune_views=True,
                emit_diff=True,
            )
        case _:
            choices: str = ", ".join(ALL_MODES)
            raise ValueError(f"Unknown mode {name!r}; expected one of: {choices}")


def _run_steps_with_samples(
    *,
    scenario: Scenario,
    mode: Mode,
    config: FrozenConfig,
    policy_registry: PolicyRegistry,
) -> tuple[ProcessingContext, list[StepSample], str]:
    """Run one scenario/mode pair and collect step-level samples."""
    pipeline: PipelineSelection = select_pipeline(
        mode.kind,
        apply=mode.apply,
        diff=mode.diff,
    )
    run_options: RunOptions = RunOptions.from_pipeline_selection(
        selection=pipeline,
        output_target=mode.output_target,
        file_write_strategy=FileWriteStrategy.ATOMIC,
        prune_views=mode.prune_views,
    )
    ctx: ProcessingContext = ProcessingContext.bootstrap(
        path=scenario.path,
        config=config,
        run_options=run_options,
        policy_registry_override=policy_registry,
    )
    steps: tuple[Step[ProcessingContext], ...] = pipeline.steps
    samples: list[StepSample] = []
    stdout_capture = io.StringIO()

    step_count: int = len(steps)
    with contextlib.redirect_stdout(stdout_capture):
        for index, step in enumerate(steps):
            step_start: int = time.perf_counter_ns()
            ctx = step(ctx)
            # Mirror the production runner lifecycle so per-step samples reflect
            # the retained views available to later steps, not only final cleanup.
            if mode.prune_views:
                remaining_view_consumers: set[ViewSlot] = set()
                for remaining_step in steps[index + 1 : step_count]:
                    remaining_view_consumers.update(remaining_step.consumes_views)
                ctx.views.release_consumed(
                    remaining_view_consumers=remaining_view_consumers,
                    keep_diff_view=mode.emit_diff,
                )
            elapsed_ns: int = time.perf_counter_ns() - step_start
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            views: dict[str, int | bool] = _view_sizes(ctx)
            samples.append(
                StepSample(
                    step=step.name,
                    elapsed_ns=elapsed_ns,
                    current_tracemalloc_bytes=current_bytes,
                    peak_tracemalloc_bytes=peak_bytes,
                    rss_bytes=_rss_bytes(),
                    image_lines=int(views["image_lines"]),
                    header_lines=int(views["header_lines"]),
                    render_lines=int(views["render_lines"]),
                    updated_lines=int(views["updated_lines"]),
                    diff_bytes=int(views["diff_bytes"]),
                )
            )

    return ctx, samples, stdout_capture.getvalue()


def _measure_repository_one(
    *,
    scenario: Scenario,
    mode: Mode,
    config: FrozenConfig,
) -> RunMeasurement:
    """Measure one many-file repository scenario/mode pair.

    Repository measurements exercise the production multi-file execution and
    reduction boundary. They intentionally summarize aggregate durable result
    state instead of capturing per-step samples for every file.
    """
    pipeline: PipelineSelection = select_pipeline(
        mode.kind,
        apply=mode.apply,
        diff=mode.diff,
    )
    run_options: RunOptions = RunOptions.from_pipeline_selection(
        selection=pipeline,
        output_target=mode.output_target,
        file_write_strategy=FileWriteStrategy.ATOMIC,
        prune_views=mode.prune_views,
    )
    file_list: list[Path] = sorted(scenario.path.rglob("*.py"))

    gc.collect()
    tracemalloc.start()
    start_rss: int | None = _rss_bytes()
    start_ns: int = time.perf_counter_ns()
    state: PipelineExecutionState = PipelineExecutionState()
    contexts: Iterable[ProcessingContext] = iter_steps_for_files(
        run_options=run_options,
        config=config,
        path_configs=None,
        pipeline=pipeline,
        file_list=file_list,
        state=state,
    )
    # Materialize only durable ProcessingResult snapshots. The reducer releases
    # volatile context views as each file is consumed so this measures retained
    # result ownership rather than full ProcessingContext retention.
    results: tuple[ProcessingResult, ...] = tuple(
        iter_processing_results(contexts, release_views=True)
    )
    elapsed_ns: int = time.perf_counter_ns() - start_ns
    final_bytes, peak_bytes = tracemalloc.get_traced_memory()
    end_rss: int | None = _rss_bytes()
    tracemalloc.stop()

    # Diff text is durable result detail, so aggregate its retained bytes separately
    # from transient per-context diff views used by the single-file measurements.
    result_diff_bytes: int = sum(
        len(result.detail.diff_text.encode("utf-8"))
        for result in results
        if result.detail.diff_text is not None
    )
    max_observed_rss: int | None = _max_optional_rss(start_rss, end_rss)

    return RunMeasurement(
        scenario=scenario.name,
        mode=mode.name,
        file_size_bytes=scenario.size_bytes,
        elapsed_ns=elapsed_ns,
        peak_tracemalloc_bytes=peak_bytes,
        final_tracemalloc_bytes=final_bytes,
        start_rss_bytes=start_rss,
        end_rss_bytes=end_rss,
        max_observed_rss_bytes=max_observed_rss,
        stdout_bytes=0,
        input_file_count=len(file_list),
        result_count=len(results),
        result_diff_bytes=result_diff_bytes,
        exit_code=state.exit_code.value if state.exit_code is not None else None,
        status={},
        views_before_prune={
            "image_lines": 0,
            "header_lines": 0,
            "header_block_bytes": 0,
            "render_lines": 0,
            "render_block_bytes": 0,
            "updated_lines": 0,
            "diff_bytes": 0,
            "has_build_view": False,
        },
        views_after_prune={
            "image_lines": 0,
            "header_lines": 0,
            "header_block_bytes": 0,
            "render_lines": 0,
            "render_block_bytes": 0,
            "updated_lines": 0,
            "diff_bytes": 0,
            "has_build_view": False,
        },
        steps=[],
    )


def _measure_one(
    *,
    scenario: Scenario,
    mode: Mode,
    config: FrozenConfig,
    policy_registry: PolicyRegistry,
) -> RunMeasurement:
    """Measure one scenario/mode pair."""
    if scenario.name == "repo_many_small_mixed":
        return _measure_repository_one(
            scenario=scenario,
            mode=mode,
            config=config,
        )

    gc.collect()
    tracemalloc.start()
    start_rss: int | None = _rss_bytes()
    start_ns: int = time.perf_counter_ns()
    exit_code: ExitCode | None = None

    try:
        ctx, samples, stdout_text = _run_steps_with_samples(
            scenario=scenario,
            mode=mode,
            config=config,
            policy_registry=policy_registry,
        )
    except Exception:
        tracemalloc.stop()
        raise

    elapsed_ns: int = time.perf_counter_ns() - start_ns
    final_bytes, peak_bytes = tracemalloc.get_traced_memory()
    end_rss: int | None = _rss_bytes()
    views_before_prune: dict[str, int | bool] = _view_sizes(ctx)
    ctx.views.release_all()
    views_after_prune: dict[str, int | bool] = _view_sizes(ctx)
    max_sample_rss: int | None = _max_optional_rss(*(sample.rss_bytes for sample in samples))
    max_observed_rss: int | None = _max_optional_rss(start_rss, end_rss, max_sample_rss)
    tracemalloc.stop()

    return RunMeasurement(
        scenario=scenario.name,
        mode=mode.name,
        file_size_bytes=scenario.size_bytes,
        elapsed_ns=elapsed_ns,
        peak_tracemalloc_bytes=peak_bytes,
        final_tracemalloc_bytes=final_bytes,
        start_rss_bytes=start_rss,
        end_rss_bytes=end_rss,
        max_observed_rss_bytes=max_observed_rss,
        stdout_bytes=len(stdout_text.encode("utf-8")),
        input_file_count=scenario.file_count,
        result_count=1,
        result_diff_bytes=int(views_before_prune["diff_bytes"]),
        exit_code=exit_code.value if exit_code is not None else None,
        status=_status_dict(ctx),
        views_before_prune=views_before_prune,
        views_after_prune=views_after_prune,
        steps=samples,
    )


# ---- Subprocess isolation and JSON rehydration helpers ----


def _object_mapping(value: object, *, message: str) -> dict[str, object]:
    """Return a string-keyed object mapping.

    Args:
        value: Candidate JSON object value.
        message: Error message used when `value` is not a JSON object.

    Returns:
        A string-keyed object dictionary.

    Raises:
        TypeError: If `value` is not a JSON object.
    """
    if not is_mapping(value):
        raise TypeError(message)
    return as_object_dict(value)


def _object_list(value: object, *, message: str) -> list[object]:
    """Return an object list.

    Args:
        value: Candidate JSON array value.
        message: Error message used when `value` is not a JSON array.

    Returns:
        A list of JSON-compatible values.

    Raises:
        TypeError: If `value` is not a JSON array.
    """
    if not is_any_list(value):
        raise TypeError(message)
    return list(value)


def _required_int(payload: dict[str, object], key: str) -> int:
    """Return a required integer-compatible payload value.

    Args:
        payload: JSON object payload.
        key: Field name to read from `payload`.

    Returns:
        The selected value converted to `int`.

    Raises:
        TypeError: If the value cannot be converted to `int`.
    """
    value: object = payload[key]
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float | str):
        return int(value)
    raise TypeError(f"payload field {key!r} is not integer-compatible")


def _optional_int(payload: dict[str, object], key: str) -> int | None:
    """Return an optional integer-compatible payload value.

    Args:
        payload: JSON object payload.
        key: Field name to read from `payload`.

    Returns:
        The selected value converted to `int`, or `None` when the payload value is null.

    Raises:
        TypeError: If the non-null value cannot be converted to `int`.
    """
    value: object = payload[key]
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float | str):
        return int(value)
    raise TypeError(f"payload field {key!r} is not integer-compatible")


def _int_bool_mapping(value: object, *, message: str) -> dict[str, int | bool]:
    """Return a JSON object as an integer-or-boolean mapping.

    Args:
        value: Candidate JSON object value.
        message: Error message used when `value` is not a JSON object.

    Returns:
        A string-keyed dictionary containing only integers and booleans.

    Raises:
        TypeError: If `value` is not a JSON object or contains unsupported values.
    """
    payload: dict[str, object] = _object_mapping(value, message=message)
    result: dict[str, int | bool] = {}
    for key, item in payload.items():
        if isinstance(item, bool):
            result[key] = item
        elif isinstance(item, int | float | str):
            result[key] = int(item)
        else:
            raise TypeError(f"payload field {key!r} is not integer-compatible")
    return result


def measurement_from_mapping(payload: dict[str, object]) -> RunMeasurement:
    """Rebuild one [RunMeasurement](RunMeasurement) from JSON-compatible data.

    Args:
        payload: JSON-compatible measurement object payload.

    Returns:
        A reconstructed run measurement.
    """
    steps_payload: list[object] = _object_list(
        payload.get("steps"),
        message="measurement payload is missing a valid steps list",
    )

    steps: list[StepSample] = []
    for step_value in steps_payload:
        step_payload: dict[str, object] = _object_mapping(
            step_value,
            message="measurement step payload must be an object",
        )
        steps.append(
            StepSample(
                step=str(step_payload["step"]),
                elapsed_ns=_required_int(step_payload, "elapsed_ns"),
                current_tracemalloc_bytes=_required_int(
                    step_payload,
                    "current_tracemalloc_bytes",
                ),
                peak_tracemalloc_bytes=_required_int(
                    step_payload,
                    "peak_tracemalloc_bytes",
                ),
                rss_bytes=_optional_int(step_payload, "rss_bytes"),
                image_lines=_required_int(step_payload, "image_lines"),
                header_lines=_required_int(step_payload, "header_lines"),
                render_lines=_required_int(step_payload, "render_lines"),
                updated_lines=_required_int(step_payload, "updated_lines"),
                diff_bytes=_required_int(step_payload, "diff_bytes"),
            )
        )

    status_payload: dict[str, object] = _object_mapping(
        payload.get("status"),
        message="measurement payload is missing a valid status object",
    )
    return RunMeasurement(
        scenario=str(payload["scenario"]),
        mode=str(payload["mode"]),
        file_size_bytes=_required_int(payload, "file_size_bytes"),
        elapsed_ns=_required_int(payload, "elapsed_ns"),
        peak_tracemalloc_bytes=_required_int(payload, "peak_tracemalloc_bytes"),
        final_tracemalloc_bytes=_required_int(payload, "final_tracemalloc_bytes"),
        start_rss_bytes=_optional_int(payload, "start_rss_bytes"),
        end_rss_bytes=_optional_int(payload, "end_rss_bytes"),
        max_observed_rss_bytes=_optional_int(payload, "max_observed_rss_bytes"),
        stdout_bytes=_required_int(payload, "stdout_bytes"),
        input_file_count=_required_int(payload, "input_file_count"),
        result_count=_required_int(payload, "result_count"),
        result_diff_bytes=_required_int(payload, "result_diff_bytes"),
        exit_code=_optional_int(payload, "exit_code"),
        status={str(key): str(value) for key, value in status_payload.items()},
        views_before_prune=_int_bool_mapping(
            payload.get("views_before_prune"),
            message="measurement payload is missing a valid views_before_prune object",
        ),
        views_after_prune=_int_bool_mapping(
            payload.get("views_after_prune"),
            message="measurement payload is missing a valid views_after_prune object",
        ),
        steps=steps,
    )


def _measure_one_subprocess(
    *,
    scenario_name: ScenarioName,
    mode_name: str,
    include_large: bool,
    work_dir: Path,
) -> RunMeasurement:
    """Measure one scenario/mode pair in a fresh Python process for accurate RSS."""
    output: Path = work_dir / f"{scenario_name}-{mode_name}.json"
    command: list[str] = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--single-process",
        "--scenario",
        scenario_name,
        "--mode",
        mode_name,
        "--output",
        output.as_posix(),
    ]
    if include_large:
        command.append("--include-large")
    # The command is constructed from the current Python executable, this script path,
    # and validated argparse choices; no shell is used.
    subprocess.run(command, check=True)  # noqa: S603

    raw_payload: object = json.loads(output.read_text(encoding="utf-8"))
    payload: dict[str, object] = _object_mapping(
        raw_payload, message="subprocess report payload must be an object"
    )
    measurements_payload: list[object] = _object_list(
        payload.get("measurements"),
        message="subprocess report measurements payload must be a list",
    )
    if len(measurements_payload) != 1:
        raise ValueError("subprocess report must contain exactly one measurement")
    measurement_payload: dict[str, object] = _object_mapping(
        measurements_payload[0],
        message="subprocess measurement payload must be an object",
    )
    return measurement_from_mapping(measurement_payload)


def _measure_all_subprocesses(
    *,
    scenarios: Sequence[Scenario],
    modes: Sequence[Mode],
    include_large: bool,
    work_dir: Path,
) -> list[RunMeasurement]:
    """Measure all scenario/mode pairs in subprocesses."""
    measurements: list[RunMeasurement] = []
    for scenario in scenarios:
        for mode in modes:
            measurements.append(
                _measure_one_subprocess(
                    scenario_name=scenario.name,
                    mode_name=mode.name,
                    include_large=include_large,
                    work_dir=work_dir,
                )
            )
    return measurements


def _json_default(value: object) -> object:
    """Serialize dataclass values for JSON output."""
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (Scenario, Mode, StepSample, RunMeasurement, RunDestination)):
        return asdict(value)
    if isinstance(value, OutputTarget):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


# ---- CLI argument parsing and orchestration ----
def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate TopMark pipeline memory/allocation baseline measurements.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to this path instead of stdout.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write a preserved run directory below this path. Defaults to artifacts/perf.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Name for the preserved run directory. Defaults to a UTC timestamp.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing preserved run directory.",
    )
    parser.add_argument(
        "--suite",
        choices=tuple(SUITE_SCENARIOS),
        default=None,
        help="Run a predefined scenario/mode suite instead of specifying every command manually.",
    )
    parser.add_argument(
        "--include-large",
        action="store_true",
        help="Include heavier large-file scenarios that may take longer.",
    )
    parser.add_argument(
        "--mode",
        action="append",
        choices=ALL_MODES,
        help=(
            "Mode to run. May be repeated. Defaults to historical unpruned modes; "
            "use *_pruned modes to measure view-pruning lifecycle behavior explicitly."
        ),
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=DEFAULT_SCENARIOS + REPOSITORY_SCENARIOS + LARGE_SCENARIOS,
        help="Scenario to run. May be repeated. Defaults to the standard scenario set.",
    )
    parser.add_argument(
        "--single-process",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def _select_scenarios(
    scenarios: Iterable[Scenario],
    selected_names: Sequence[str] | None,
) -> list[Scenario]:
    """Filter generated scenarios by optional names."""
    if selected_names is None:
        return list(scenarios)
    selected: set[str] = set(selected_names)
    return [scenario for scenario in scenarios if scenario.name in selected]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark and emit a JSON report."""
    args: argparse.Namespace = _parse_args(sys.argv[1:] if argv is None else argv)
    suite: SuiteName | None = args.suite
    if suite is not None:
        # Suites own both scenario and mode selection so documented benchmark runs
        # remain reproducible even if default ad-hoc selections evolve.
        scenario_names: Sequence[str] | None = SUITE_SCENARIOS[suite]
        mode_names: Sequence[str] = SUITE_MODES[suite]
    else:
        # Keep repository-scale workloads opt-in for ad-hoc runs; the default remains
        # the historical single-file corpus unless callers select the repository suite
        # or the scenario explicitly.
        scenario_names = args.scenario if args.scenario is not None else DEFAULT_SCENARIOS
        mode_names = args.mode if args.mode is not None else DEFAULT_MODES
    modes: list[Mode] = [_mode_from_name(name) for name in mode_names]
    destination: RunDestination = _resolve_destination(args, suite=suite)

    with tempfile.TemporaryDirectory(prefix="topmark-perf-") as tmp:
        root = Path(tmp)
        scenarios: list[Scenario] = _select_scenarios(
            build_scenarios(root, include_large=args.include_large),
            scenario_names,
        )
        if bool(args.single_process):
            config: FrozenConfig = _make_config(root)
            policy_registry: PolicyRegistry = make_policy_registry(config)
            measurements: list[RunMeasurement] = []

            for scenario in scenarios:
                for mode in modes:
                    # Each measurement gets a fresh copy so apply-mode runs do not contaminate
                    # subsequent dry-run or strip measurements for the same logical scenario.
                    isolated: Path = root / f"isolated-{scenario.name}-{mode.name}"
                    if scenario.path.is_dir():
                        shutil.copytree(scenario.path, isolated)
                    else:
                        isolated = isolated.with_suffix(".py")
                        isolated.write_bytes(scenario.path.read_bytes())
                    isolated_scenario = Scenario(
                        name=scenario.name,
                        path=isolated,
                        size_bytes=_tree_size_bytes(isolated),
                        description=scenario.description,
                        file_count=_tree_file_count(isolated),
                    )
                    measurements.append(
                        _measure_one(
                            scenario=isolated_scenario,
                            mode=mode,
                            config=config,
                            policy_registry=policy_registry,
                        )
                    )
        else:
            measurements = _measure_all_subprocesses(
                scenarios=scenarios,
                modes=modes,
                include_large=bool(args.include_large),
                work_dir=root,
            )

        report: dict[str, object] = {
            "schema_version": 1,
            "tool": "tools/perf/pipeline_memory_baseline.py",
            "pid": os.getpid(),
            "python": sys.version,
            "platform": sys.platform,
            "repo_root": REPO_ROOT.as_posix(),
            "git_commit": _read_git_commit(),
            "suite": suite,
            "run_id": destination.run_id,
            "measurement_isolation": "single-process"
            if bool(args.single_process)
            else "subprocess",
            "scenarios": [asdict(scenario) for scenario in scenarios],
            "modes": [asdict(mode) for mode in modes],
            "measurements": measurements,
        }

    payload: str = json.dumps(report, indent=2, default=_json_default)
    destination.output_file.parent.mkdir(parents=True, exist_ok=True)
    destination.output_file.write_text(payload + "\n", encoding="utf-8")
    if destination.output_dir is not None:
        _write_summary(destination.output_dir / "summary.md", measurements)
        manifest: dict[str, int | str | list[str] | None] = {
            "schema_version": 1,
            "run_id": destination.run_id,
            "suite": suite,
            "report": destination.output_file.name,
            "summary": "summary.md",
            "python": sys.version,
            "platform": sys.platform,
            "git_commit": _read_git_commit(),
            "scenarios": [scenario.name for scenario in scenarios],
            "modes": [mode.name for mode in modes],
        }
        (destination.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        print(destination.output_dir.as_posix())
    elif args.output is None:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

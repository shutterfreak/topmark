<!--
topmark:header:start

  project      : TopMark
  file         : performance-baselines.md
  file_relpath : docs/dev/performance-baselines.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Performance baselines

This document describes the memory and allocation baseline methodology established for TopMark Track
B performance work.

The goal of these baselines is to measure current behavior before and after incremental
optimizations. The measurements provide a factual reference for work such as lazy updated-file
composition, iterable-backed views, streaming writes, diff lifecycle improvements, and view-pruning
changes.

______________________________________________________________________

## Scope

The baseline tooling focuses on:

- peak memory usage;
- Python allocation behavior;
- retained view ownership;
- per-step timing;
- diff-generation costs;
- duplicate diff-preview formatting when verbose pipeline logging is enabled;
- updated-file materialization costs.

The tooling is intentionally measurement-only and does not modify pipeline architecture or ownership
semantics.

______________________________________________________________________

## Benchmark tool

The benchmark driver is:

```text
tools/perf/pipeline_memory_baseline.py
```

The script generates synthetic workloads, executes representative pipeline flows, and produces JSON
and Markdown reports.

______________________________________________________________________

## Benchmark suites

Three suites are currently defined.

### Smoke

Minimal validation suite used to confirm that the benchmark tooling is operational.

```sh
python tools/perf/pipeline_memory_baseline.py \
    --suite smoke \
    --run-id initial-smoke-baseline
```

### Pathological

Exercises expected memory hotspots.

Examples include:

- huge headers;
- large diffs;
- large strip operations.

```sh
python tools/perf/pipeline_memory_baseline.py \
    --suite pathological \
    --run-id initial-pathological-baseline
```

### Baseline

Comprehensive suite covering representative workloads.

```sh
python tools/perf/pipeline_memory_baseline.py \
    --suite baseline \
    --run-id initial-baseline-suite
```

A convenience target is also available:

```sh
make perf-baseline
```

which executes:

```sh
python tools/perf/pipeline_memory_baseline.py --suite baseline
```

______________________________________________________________________

## Output layout

Benchmark outputs are written below:

```text
artifacts/perf/
```

The directory is intentionally ignored by Git.

A preserved benchmark run has the following structure:

```text
artifacts/perf/<run-id>/
├── manifest.json
├── report.json
└── summary.md
```

Where:

- `manifest.json` contains environment metadata;
- `report.json` contains full measurement data;
- `summary.md` contains a human-readable summary table.

Benchmark outputs are not committed to the repository. Only the tooling, documentation, and
conclusions derived from the measurements are version controlled.

______________________________________________________________________

## Measurement methodology

### Traced allocations

The benchmark tool uses Python's built-in `tracemalloc` module to collect:

- peak traced allocations;
- final traced allocations;
- allocation growth throughout pipeline execution.

### RSS measurements

Resident Set Size (RSS) measurements are collected using platform-specific process statistics.

Each scenario/mode pair is executed in a dedicated subprocess.

This isolation is important because RSS measurements are typically reported as a process high-water
mark. Running all scenarios inside a single Python process would make later measurements inherit
memory peaks from earlier measurements.

The benchmark report therefore records:

```text
measurement_isolation = "subprocess"
```

for the canonical baseline runs.

### Platform support

RSS measurements currently rely on platform-specific process statistics.

- Linux: RSS measurements are collected and reported.
- macOS: RSS measurements are collected and reported.
- Windows: RSS measurements are currently reported as unavailable (`None`).

The benchmark framework continues to collect tracemalloc-based allocation metrics on Windows, but
RSS values are omitted because the current implementation intentionally avoids introducing
additional platform-specific dependencies solely for benchmark tooling.

As a result, Windows benchmark runs remain useful for allocation analysis and relative comparisons,
but RSS-based comparisons should be performed using Linux or macOS baseline runs.

### Retained views

The benchmark tool records lightweight ownership indicators including:

- image line counts;
- header line counts;
- rendered line counts;
- updated line counts;
- diff sizes;
- retained views before pruning;
- retained views after pruning.

The `views_before_prune` measurement captures the final retained volatile views after pipeline
execution. The `views_after_prune` measurement then explicitly releases all remaining volatile views
from the benchmark context. This mirrors the durable-result lifecycle introduced during GitHub issue
148: `ProcessingResult` owns durable snapshots such as rendered diff text after reduction, while
`ProcessingContext` views remain volatile execution state and may be released once snapshotting has
completed.

______________________________________________________________________

## Baseline scenarios

The current benchmark corpus includes:

### Small workloads

- 1 KB file without header
- 10 KB file with header

### Medium workloads

- 100 KB file without header
- 1 MB file without header

### Pathological workloads

- huge header
- huge diff
- insertion-oriented workload
- large strip workload
- mixed newline file
- BOM file

These scenarios were selected to exercise the primary materialization and retention points
identified during the pipeline ownership audit.

### Scope of current measurements

The current benchmark corpus consists exclusively of single-file workloads.

Each measurement represents:

```text
one generated file
× one pipeline mode
× one isolated Python subprocess
```

The baseline results therefore characterize per-file pipeline behavior and materialization costs.

The current benchmark suite does not attempt to measure:

- repository-scale traversal;
- many-file batch execution;
- cumulative `ProcessingContext` retention across files;
- aggregate JSON or NDJSON serialization costs;
- repeated small-file scaling behavior;
- whole-run memory growth across large file sets.

Those concerns may warrant additional benchmark suites in future performance work if optimization
efforts extend beyond per-file pipeline processing.

______________________________________________________________________

## Initial findings

The initial baseline measurements support the conclusions from the ownership audit.

### Baseline results (GitHub issue 134)

The following representative measurements were collected from the canonical baseline runs using
subprocess-isolated RSS measurements.

| Scenario                    | Mode         | Diff size | Peak traced |  Max RSS |
| --------------------------- | ------------ | --------: | ----------: | -------: |
| `small_1kb_missing_header`  | `check`      |       0 B |   374.3 KiB | 44.5 MiB |
| `medium_1mb_missing_header` | `check_diff` |   2.0 MiB |    14.4 MiB | 63.4 MiB |
| `huge_diff`                 | `strip_diff` |   1.9 MiB |    13.5 MiB | 62.8 MiB |
| `strip_large_header`        | `strip_diff` |   2.3 MiB |    21.9 MiB | 80.1 MiB |

The largest measured workload was `strip_large_header` in `strip_diff` mode. This scenario combines
a very large detected header, updated-file generation, and diff creation, making it a useful
upper-bound reference for current pipeline behavior.

Observed hotspots include:

1. diff generation and retention;
1. updated-file materialization;
1. large header scanning and ownership;
1. original file image materialization.

The largest measured cases were associated with diff-heavy workloads and large strip operations. In
particular, `strip_large_header` / `strip_diff` produced the highest observed peak traced allocation
(~21.9 MiB) and RSS (~80 MiB).

### Follow-up measurements (GitHub issue 140)

GitHub issue 140 introduced incremental consumed-view pruning between pipeline steps when pruning is
enabled.

To preserve longitudinal comparability with the GitHub issue 134 baseline, the benchmark tool
continues to use the historical unpruned mode names in its predefined suites. Explicit `_pruned`
mode variants were added for measuring lifecycle improvements without changing the original baseline
reference points.

The benchmark harness mirrors the production between-step pruning lifecycle during step sampling
whenever a pruned mode is used, so retained-view measurements reflect the views that remain
available to downstream pipeline steps. Final volatile-view release is measured separately after the
run so it remains distinct from runner-owned between-step pruning and reduction-owned durable
snapshotting.

Representative issue 140 measurements collected using the explicit pruned benchmark modes were:

These measurements were collected using the explicit pruned benchmark modes introduced by GitHub
issue 140. The original GitHub issue 134 baseline measurements remain reproducible through the
historical mode names and predefined benchmark suites.

| Scenario             | Mode                | Peak traced change | RSS change |
| -------------------- | ------------------- | -----------------: | ---------: |
| `huge_header`        | `check_diff_pruned` |            -33.6 % |     -8.3 % |
| `huge_header`        | `strip_diff_pruned` |            -32.9 % |     -4.0 % |
| `strip_large_header` | `check_diff_pruned` |            -14.7 % |     -1.9 % |
| `strip_large_header` | `strip_diff_pruned` |             -8.1 % |     +0.1 % |

The strongest improvements were observed in header-heavy workloads where multiple transient views
(image content, detected headers, rendered headers, and updated content) would otherwise coexist for
longer periods.

For example, `huge_header` improved by roughly 33% in peak traced allocations in both
`check_diff_pruned` and `strip_diff_pruned` modes, with corresponding RSS reductions of roughly 4%
to 8% on the measured platform.

The largest pathological diff workload (`strip_large_header` / `strip_diff_pruned`) showed a more
modest improvement of roughly 8% in peak traced allocations and essentially unchanged RSS. This is
consistent with the ownership audit and baseline findings: the remaining dominant costs in that
scenario are updated-file materialization and diff generation rather than retention of consumed
header-related views.

These figures should be treated as directional rather than hard thresholds because memory
measurements are platform-, allocator-, and workload-sensitive.

The GitHub issue 140 results therefore validate that earlier release of consumed views is a
worthwhile low-risk optimization, while also confirming that the largest remaining memory
opportunities lie in later roadmap items focused on diff generation and updated-file ownership.

- diff lifecycle management (GitHub issue 138);
- updated-file ownership and composition (GitHub issues 135, 136, and 137);
- view release timing and pruning (GitHub issue 140, completed and measured as a baseline-preserving
  optimization).

### Follow-up measurements (GitHub issue 138)

GitHub issue 138 audited diff-generation materialization and retention behavior. The implemented
change was intentionally narrow: avoid constructing a duplicate formatted diff preview when INFO
logging is not enabled.

The issue 138 measurements were collected using the same explicit `_pruned` benchmark modes used for
the GitHub issue 140 follow-up measurements, allowing direct comparison against the already pruned
lifecycle baseline.

Representative changes relative to the GitHub issue 140 results were:

| Scenario             | Mode                | Peak traced change | RSS change |
| -------------------- | ------------------- | -----------------: | ---------: |
| `huge_diff`          | `strip_diff_pruned` |            -34.5 % |    -13.4 % |
| `strip_large_header` | `strip_diff_pruned` |            -35.4 % |    -19.5 % |

The largest improvements were observed specifically in diff-producing workloads. Non-diff modes and
header-oriented workloads remained effectively unchanged, which is consistent with the scope of the
optimization.

In particular, `huge_diff` and `strip_large_header` in `strip_diff_pruned` mode showed substantial
reductions in both peak traced allocations and RSS. These results are consistent with the conclusion
that duplicate formatting of large unified diffs represented a measurable transient allocation cost
even after the view-pruning improvements introduced by GitHub issue 140.

For historical tracking, the issue 138 results can also be compared against the original GitHub
issue 134 baseline measurements. This shows the cumulative effect of the Track B optimizations
implemented so far.

| Scenario             | Baseline mode | Current mode        | Peak traced change | RSS change |
| -------------------- | ------------- | ------------------- | -----------------: | ---------: |
| `huge_diff`          | `strip_diff`  | `strip_diff_pruned` |            -31.2 % |     -8.8 % |
| `strip_large_header` | `strip_diff`  | `strip_diff_pruned` |            -37.8 % |    -15.5 % |

Relative to the original GitHub issue 134 baseline, the combined effect of incremental view pruning
(GitHub issue 140) and reduced diff-preview duplication (GitHub issue 138) produces substantially
larger improvements than either optimization in isolation.

The measurements also reinforce the broader findings from GitHub issues 133, 134, and 140:

- diff generation remains one of the largest memory hotspots in the pipeline;
- updated-file materialization and diff generation still dominate the largest pathological cases;
- lifecycle pruning and reduced duplication are complementary optimizations;
- future work in GitHub issues 135, 136, and 137 remains the primary opportunity for additional
  memory reductions.

These figures should be treated as directional rather than hard thresholds because memory
measurements remain platform-, allocator-, and workload-sensitive.

### Lazy updated-content composition follow-up (GitHub issues 135 and 136)

GitHub issues 135 and 136 introduced a repeatable updated-content abstraction for pipeline-generated
updated views. The implementation is intentionally narrow: replacement planning can now retain a
segment-backed composition of the original prefix, rendered header, and original suffix instead of
retaining one eager updated-file list.

The updated-view contract now rejects arbitrary one-shot iterables in favor of repeatable updated
content or materialized sequences. This preserves current CLI and API behavior while making the
pipeline ownership model more explicit: pipeline-generated lazy content must be repeatable so
comparer, patcher, and writer can consume updated content independently.

The issue 135 and 136 measurements were collected using the same explicit `_pruned` benchmark modes
used for the GitHub issue 140 and GitHub issue 138 follow-up measurements. Representative changes
relative to the GitHub issue 138 results were:

| Scenario             | Mode                | Peak traced change | RSS change |
| -------------------- | ------------------- | -----------------: | ---------: |
| `huge_diff`          | `strip_diff_pruned` |             +1.8 % |     +0.1 % |
| `strip_large_header` | `strip_diff_pruned` |             +1.9 % |     +0.4 % |
| `huge_header`        | `check_diff_pruned` |              0.0 % |     +0.3 % |
| `strip_large_header` | `check_diff_pruned` |             +3.7 % |     +5.0 % |

These results should be interpreted as effectively flat rather than as a regression. The measured
pathological workloads remain dominated by comparison, patch generation, scanner/header ownership,
or current consumers that still materialize updated lines when required by existing behavior.

A follow-up materialization audit after the issue 135 and 136 changes did not identify an obvious
additional low-risk optimization that belonged in the same change set. The remaining relevant
materialization points are primarily:

- comparison, where old and updated line sequences are currently materialized for equality checks;
- patch generation, where updated lines and unified diff output are materialized;
- writer sinks and stdout handling, which remain the focus of GitHub issue 137;
- scanner/header extraction and processor-local normalization paths.

For historical tracking, the issue 135 and 136 results can also be compared against the original
GitHub issue 134 baseline measurements. This shows the cumulative effect of the Track B
optimizations implemented so far.

| Scenario             | Baseline mode | Current mode        | Peak traced change | RSS change |
| -------------------- | ------------- | ------------------- | -----------------: | ---------: |
| `huge_header`        | `check_diff`  | `check_diff_pruned` |            -37.2 % |     -9.0 % |
| `huge_header`        | `strip_diff`  | `strip_diff_pruned` |            -38.6 % |     -5.5 % |
| `huge_diff`          | `strip_diff`  | `strip_diff_pruned` |            -33.3 % |    -16.8 % |
| `strip_large_header` | `strip_diff`  | `strip_diff_pruned` |            -39.5 % |    -19.1 % |

Relative to the original GitHub issue 134 baseline, the cumulative Track B improvements remain
substantial. The largest measured reductions are still attributable to earlier release of consumed
views and reduced duplicate diff-preview formatting, while the issue 135 and 136 work primarily
improves the architecture and ownership contract for updated content.

The measurements confirm that lazy updated-content composition is now in place, but they also show
that the current pathological benchmark set does not expose a large additional memory win from this
change alone. This is consistent with the benchmark design: the largest measured cases still require
comparison or unified diff generation, both of which continue to materialize updated content or diff
text.

### Stream updated content through WriterStep (GitHub issue 137)

GitHub issue 137 completed the writer-owned part of that follow-up by keeping file sinks streaming
through `ctx.iter_updated_lines()` and changing the STDOUT sink to emit updated content line by line
while accounting for UTF-8 bytes incrementally. This removes the remaining writer-local eager
updated-line materialization without changing comparison, patch generation, or broader stdout
presentation behavior. Further diff-generation redesign and stdout rendering/materialization work
should remain separate so that benchmark comparisons stay attributable to one architectural change
at a time.

Benchmark results after GitHub issue 137 were effectively flat relative to the previous checkpoint
(GitHub issues 140, 138, 135 and 136). This was expected because the remaining writer-local
materialization occurred only in STDOUT emission paths, while the pathological benchmark scenarios
remain dominated by comparison, patch generation, diff retention, scanner ownership, and file-image
ownership. The change therefore improves ownership clarity and removes the final writer-local eager
updated-line materialization without producing a measurable benchmark shift in the current benchmark
suite.

Relative to the
[lazy updated-content composition follow-up (GitHub issues 135 and 136)](#lazy-updated-content-composition-follow-up-github-issues-135-and-136):

| Scenario           | Mode              | Peak traced | RSS   |
| ------------------ | ----------------- | ----------- | ----- |
| huge_diff          | strip_diff_pruned | ~0.0%       | 0.0%  |
| strip_large_header | strip_diff_pruned | ~0.0%       | -0.6% |
| huge_header        | check_diff_pruned | 0.0%        | -0.4% |

The results are interpreted as effectively flat.

Follow-up:

- stdout presentation outside writer-owned updated-content emission, which remains the focus of
  GitHub issue 139;

### Structured diff backend follow-up (GitHub issue 167)

GitHub issue 167 evaluated whether structured edit metadata can become the primary diff-generation
backend for current TopMark pipeline mutations. The current planner and stripper mutation paths emit
exactly one contiguous `PlannedEdit` for the implemented update operations: header replacement,
header insertion, and header removal. `EditView` keeps a tuple of edits as deliberate
future-proofing, but current processors do not produce multiple independent file mutations from one
pipeline action.

Patch generation now prefers the structured unified-diff renderer when `EditView` contains exactly
one edit and applying that edit to the original image reproduces the already-computed updated image.
`difflib.unified_diff()` remains available as a fallback for missing, invalid, or future multi-edit
metadata. This preserves the existing unified-diff output contract while avoiding generic sequence
diffing on the common single-splice paths.

Representative pathological measurements after the change were:

| Scenario             | Mode                | Peak traced |  Max RSS |
| -------------------- | ------------------- | ----------: | -------: |
| `huge_diff`          | `strip_diff_pruned` |     4.35 MB | 46.90 MB |
| `strip_large_header` | `strip_diff_pruned` |     6.37 MB | 52.80 MB |
| `huge_header`        | `check_diff_pruned` |     3.21 MB | 47.12 MB |
| `strip_large_header` | `check_diff_pruned` |     7.26 MB | 54.00 MB |

The structured backend reduces the algorithmic work needed to produce patch lines for common
single-splice mutations, but it does not remove the larger ownership boundaries that still dominate
these workloads: comparison materializes current and updated lines before patching, and patch views
still retain unified diff text for downstream reporting. The benchmark impact should therefore be
interpreted as modest and workload-sensitive rather than as a broad memory step-change.

The benchmark tool remains adequate for this class of change because the pathological
`*_diff_pruned` modes exercise context retention, view pruning, diff retention, and repository-scale
execution through the same durable-result pipeline used by the CLI and API. Its main limitation is
that it measures retained process allocations and RSS around complete per-file processing; it does
not isolate the diff algorithm's short-lived internal allocations from earlier comparison and
updated image materialization.

### Stdout rendering and end-to-end output architecture audits (GitHub issues 139 and 147)

GitHub issue 139 audited stdout rendering after the writer-owned streaming work. The audit found
that writer STDOUT emission already streams updated content, and that the remaining stdout and
presentation ownership is concentrated in human report rendering and machine-readable output
serialization rather than in file-content writing. No implementation was justified because the
current benchmark scenarios did not show stdout presentation as a meaningful contributor.

GitHub issue 147 extended that audit to the end-to-end CLI, API, reporting, and machine-output
architecture. The current ownership map is:

- command orchestration keeps the ordered `ProcessingContext` result list for exit-code precedence,
  missing-input synthesis, reduction, and probe rendering, while check/strip human and machine
  output render from durable `ProcessingResult` snapshots after reduction;
- public API `check()` and `strip()` result packaging now consumes durable `ProcessingResult`
  snapshots after reduction for report filtering, summaries, diagnostics, write counts, and public
  diff exposure;
- check/strip machine-readable output now serializes durable `ProcessingResult` snapshots after
  reduction for per-file JSON/NDJSON detail output and apply-explicit summary classification;
- human TEXT and Markdown renderers build a filtered `view_results` list for per-file presentation
  and then render one complete output string from small presentation fragments;
- JSON machine output builds a complete envelope and serializes it as one pretty-printed JSON
  document, as required by the existing machine-output contract;
- NDJSON machine output already streams record strings from iterator-based serializers after the
  command has completed result collection;
- public API entry points assemble immutable DTO tuples and summary dictionaries because their
  contract is an in-memory return value, not a streaming sink;
- patch previews still depend on the diff view produced by patch generation, which remains a known
  algorithm-level materialization point rather than a presentation-only concern.

The realistic streaming alternatives were evaluated as follows:

| Candidate                                                  | Compatibility impact                                                                                                         | Expected benchmark relevance                                                        | Recommendation                    |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------- |
| Streaming NDJSON record emission during pipeline execution | Would complicate ordering, error precedence, and synthetic missing/filtered results                                          | Low unless repositories contain very large numbers of files                         | Do not implement now              |
| Incremental JSON generation                                | Would preserve less of the existing pretty JSON/envelope contract and still needs full result knowledge for summaries/errors | Low in current file-size-oriented benchmarks                                        | Do not implement now              |
| Sink-oriented human report rendering                       | Would replace simple string renderers with writer/sink plumbing while retaining the same filtered result list                | Low; current evidence points to file views, diff generation, and comparison instead | Do not implement now              |
| Lazy patch preview rendering                               | Potentially useful only if diff generation itself becomes lazy                                                               | Not separable from the known diff-generation ownership point                        | Keep as future diff-work input    |
| Streaming public API results                               | Would be a new API contract rather than an internal optimization                                                             | Not applicable to current CLI benchmark comparability                               | Defer unless API users request it |

The audit therefore does not recommend an end-to-end streaming-output redesign for the current Track
B scope. The existing architecture is already partially streaming where it is low-risk and
contract-compatible: updated-content writing streams through `WriterStep`, and NDJSON serialization
streams records from iterators. The remaining output materialization is intentional and tied to
stable CLI/API contracts. Converting those layers to sinks or incremental emitters would add
substantial orchestration complexity while leaving the historically measured hotspots largely
unchanged.

This conclusion is consistent with the GitHub issue 139 finding that stdout presentation is not a
benchmark-dominant contributor, and with the GitHub issue 141 finding that replacing the
authoritative file-image representation would not provide a realistic measurable improvement under
the current benchmark evidence. Track B should therefore treat end-to-end output streaming as
evaluated but not currently warranted.

### Streaming-oriented reduction architecture follow-up (GitHub issue 165)

GitHub issue 165 introduced streaming-capable execution and reduction seams while preserving the
existing batch-oriented public API, CLI, presentation, and machine-output contracts. The new
internal ownership path is:

```text
iter_steps_for_files()
    -> ProcessingContext
    -> iter_processing_results()
    -> ProcessingResult
    -> run_pipeline_results()
```

The implementation makes the engine able to yield per-file mutable processing contexts and makes the
reduction layer able to snapshot each context into a durable `ProcessingResult` before releasing
context-owned volatile views. Normal check and strip API orchestration uses the result-oriented
runtime adapter. Probe API orchestration now uses the same durable-result runtime shape for real
file-backed probe results and synthetic missing or filtered probe results, while preserving the
existing public probe DTO contract. CLI probe output still materializes an ordered durable result
tuple before rendering so exit-code precedence, machine-output schemas, and human output ordering
remain unchanged, but it no longer retains source contexts or context-owned volatile views after
reduction.

This change primarily improves ownership clarity and context lifetime boundaries. It is not expected
to materially change the existing single-file benchmark results because the current benchmark corpus
still measures one generated file per isolated subprocess, and public API/CLI outputs continue to
materialize ordered result collections for summaries, exit-code selection, and stable output
contracts.

The most relevant performance implication is therefore lifecycle-local rather than benchmark-wide:
per-file reduction can now release volatile views immediately after durable snapshotting when
callers do not retain source contexts. Measuring whether this reduces peak memory for
repository-scale runs would require a future many-file benchmark suite, because the current
scenarios do not measure cumulative `ProcessingContext` retention across large file sets.

For the current baseline corpus, the expected result is effectively flat peak traced allocations and
RSS. The issue 165 smoke baseline was regenerated after the probe-result adapter work. The run
remained consistent with the expected flat profile for the current single-file benchmark corpus:
`small_1kb_missing_header` in `check` mode measured about 412.3 KiB peak traced allocation and 43.9
MiB max RSS. The result is informational rather than a new canonical baseline because the changed
code path is probe orchestration, while the current benchmark corpus exercises check/strip
processing paths. Any future streaming-output or public iterator API work should be benchmarked
separately so memory changes remain attributable to a specific architectural layer.

______________________________________________________________________

## Known caveats

RSS availability is platform-dependent. Canonical RSS baselines are currently generated on Linux and
macOS. Windows runs record allocation metrics but may report RSS values as unavailable.

The benchmark corpus is synthetic.

The workloads are designed to provide repeatable measurements and stress representative pipeline
behavior. They are not intended to model every real-world repository.

The benchmark results should therefore be interpreted as comparative baselines rather than absolute
production-memory guarantees.

______________________________________________________________________

## Related issues

- GitHub issue 133: Audit pipeline materialization points and memory ownership
- GitHub issue 134: Establish memory and allocation baselines for pipeline processing
- GitHub issue 135: Design lazy updated-file composition for pipeline updates
- GitHub issue 136: Implement iterable-backed UpdatedView generation
- GitHub issue 137: Stream updated content through WriterStep
- GitHub issue 138: Audit diff-generation materialization and retention behavior
- GitHub issue 139: Audit stdout rendering and output materialization behavior
- GitHub issue 140: Review view-pruning lifecycle and memory-release opportunities
- GitHub issue 141: Evaluate alternative FileImageView implementations
- GitHub issue 147: Design end-to-end streaming output architecture for CLI and machine formats
- GitHub issue 165: Evaluate streaming-oriented reduction and incremental reporting architecture

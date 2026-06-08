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

The goal of these baselines is to measure current behavior before introducing optimizations. The
measurements provide a factual reference for future work such as lazy updated-file composition,
iterable-backed views, streaming writes, diff lifecycle improvements, and view-pruning changes.

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

The benchmark harness mirrors the production pruning lifecycle during step sampling whenever a
pruned mode is used, so retained-view measurements reflect the views that remain available to
downstream pipeline steps rather than only final cleanup behavior.

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
- GitHub issue 140: Review view-pruning lifecycle and memory-release opportunities
- GitHub issue 141: Evaluate alternative FileImageView implementations

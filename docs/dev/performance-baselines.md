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

### Baseline results (issue #134)

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

The measurements therefore suggest that future optimization work should pay particular attention to:

- diff lifecycle management (#138);
- updated-file ownership and composition (#135, #136, #137);
- view release timing and pruning (#140).

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

- #133 Audit pipeline materialization points and memory ownership
- #134 Establish memory and allocation baselines for pipeline processing
- #135 Design lazy updated-file composition for pipeline updates
- #136 Implement iterable-backed UpdatedView generation
- #137 Stream updated content through WriterStep
- #138 Audit diff-generation materialization and retention behavior
- #140 Review view-pruning lifecycle and memory-release opportunities
- #141 Evaluate alternative FileImageView implementations

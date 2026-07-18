<!--
topmark:header:start

  project      : TopMark
  file         : public.md
  file_relpath : docs/api/public.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Public API reference (%%TOPMARK_VERSION%%)

These pages are generated using [mkdocstrings](https://mkdocstrings.github.io/) from the TopMark
source code.

The API reference complements the higher-level usage guides:

- [Installation](../install.md)
- [Pre-commit integration](../usage/pre-commit.md)
- [Header placement rules](../usage/header-placement.md)
- [Supported file types](../usage/generated/filetypes.md)
- [Supported header processors](../usage/generated/processors.md)

Use this section if you need details on functions, classes, or constants available in TopMark.

{% include-markdown "\_snippets/terminology.md" %}

{% include-markdown "\_snippets/output-contract.md" %}

> [!NOTE]
>
> For programmatic use, prefer the Python API or JSON/NDJSON output rather than parsing
> TEXT/Markdown.

## Stable public API

### Version metadata

Use `topmark.api.get_version_text()` for the canonical runtime PEP 440 string. Use
`topmark.api.get_version_info(semver=...)` when an integration also needs the effective format or
conversion context. Its immutable `VersionInfo` result has three stable fields:

- `version_text`: the selected version string;
- `version_format`: `"pep440"` or `"semver"`;
- `err`: the retained conversion exception, or `None`.

When SemVer-compatible output is requested but the installed package version is outside TopMark's
supported conversion subset, `get_version_info()` returns the original PEP 440 string with
`version_format="pep440"` and retains the `ValueError` in `err`. The `topmark.version` package owns
this internal domain behavior but is not a barrel-style public import surface; integrations should
continue importing these helpers and `VersionInfo` from `topmark.api`.

### Streaming event contracts

TopMark exposes public event DTOs and streaming entry points for integrations that want to consume
ordered processing results incrementally while preserving the existing batch APIs. The streaming
entry points are additive compatibility extensions rather than replacements for the batch-oriented
API. `stream_check()` and `stream_strip()` emit `ContentStreamEvent` values, while `stream_probe()`
emits `ProbeStreamEvent` values. The batch `check()`, `strip()`, and `probe()` functions continue to
return `RunResult` and `ProbeRunResult`.

The public stream model has three event phases:

1. `RunStartedEvent` announces the command and selected-file count.
1. `FileResultEvent` or `ProbeFileResultEvent` carries the public DTO for one processed file.
1. `RunCompletedEvent` carries final summary, error, write, skip, and diagnostic aggregates.

The stream events intentionally do not expose internal `ProcessingContext` or `ProcessingResult`
objects. File-result events carry the same public DTOs used by the batch APIs, and run-completed
events carry the same public summary, error, skip, write, and diagnostic aggregate semantics. This
keeps the streaming surface aligned with the existing public compatibility policy while allowing
internal execution, presentation, machine-readable output, CLI orchestration, public stream APIs,
and batch collectors to share the same durable-result event model without changing the documented
API contracts.

The streaming APIs preserve deterministic event ordering: one `RunStartedEvent`, then zero or more
file-result events in the same order as the corresponding batch result view, then one
`RunCompletedEvent`. Report-scope filtering for `stream_check()` and `stream_strip()` matches the
corresponding batch API call, so filtered-out files are reflected in the final `skipped` count
rather than emitted as file-result events.

Internally, TopMark uses durable-result stream collectors and machine-/presentation-output stream
adapters to keep batch APIs, machine-readable output, human TEXT/Markdown presentation, and CLI
command orchestration aligned on the same ordering and result-ownership semantics. Those internal
adapters are implementation details and do not expand the public compatibility surface. JSON output
remains a complete-envelope compatibility format, but the documented envelope is reconstructed from
ordered durable-result stream events before emission. This keeps JSON compatible with existing
machine-readable output consumers while aligning its implementation with the same durable-result
streaming core used by NDJSON, human presentation, public stream APIs, and batch collectors.

### Configuration via mappings

Public API functions accept either a plain mapping (mirroring the TOML structure) or an immutable
\[`FrozenConfig`\][topmark.config.model.FrozenConfig].

Internally, TopMark merges mapping input into mutable runtime configuration state and immediately
\[`freeze()`s\][topmark.config.model.MutableConfig.freeze] it into an immutable runtime snapshot
before execution. This prevents accidental mutation and keeps results deterministic.

The mapping mirrors the layered TopMark configuration fragment plus TOML-source-local sections such
as `[config]` and `[writer]`. Source-local options such as `[config].root` and `strict` can also be
provided via the `config` key in the mapping, for example:

```python
config = {
    "config": {
        "root": True,
        "strict": False,
    },
    # ... other sections like "fields", "header", "policy", etc.
}
```

{% include-markdown "\_snippets/config-strictness.md" %}

Note that `strict` is not a layered configuration field. It is resolved from `[config]` /
`[tool.topmark.config]`-shaped input during configuration loading and influences staged
config-loading validation behavior. API helpers such as
\[`ensure_config_valid(...)`\][topmark.api.runtime.ensure_config_valid] apply this effective
strictness (including optional overrides) when validating a config across staged config-loading
validation:

- TOML-source diagnostics
- merged-config diagnostics
- runtime-applicability diagnostics

These options are resolved separately from layered
\[`FrozenConfig`\][topmark.config.model.FrozenConfig] values and do not participate in layered
configuration merging.

Internally, TopMark first performs whole-source TOML-style validation of these sections (unknown
keys, malformed section shapes, etc.), then deserializes only the layered configuration fragment
into the final immutable \[`FrozenConfig`\][topmark.config.model.FrozenConfig] snapshot, and finally
evaluates effective validity across staged config-loading validation. A flattened compatibility
diagnostics view remains available for reporting and exception payloads, derived from the staged
validation logs. This is why sections like `[config]` and `[writer]` can influence loading and
runtime behavior without becoming layered configuration fields.

This distinction is also visible when inspecting configuration via
[`topmark config dump --show-layers`](../usage/commands/config/dump.md): source-local TOML fragments
are preserved per layer (for example under `[[layers]].toml.*` in human output or
`config_provenance.layers[].toml` in machine-readable output), while the final immutable
\[`FrozenConfig`\][topmark.config.model.FrozenConfig] represents only the flattened effective
runtime configuration used during execution.

Pipeline selection is resolved separately from layered configuration. Public API helpers such as
\[`check()`\][topmark.api.commands.pipeline.check],
\[`strip()`\][topmark.api.commands.pipeline.strip], and
\[`probe()`\][topmark.api.commands.pipeline.probe] first select an executable pipeline definition
from the pipeline catalogue based on command intent and runtime flags. The selected pipeline then
contributes execution intent (pipeline kind, mutation mode, and diff-view preservation) to durable
runtime options before processing begins.

```python
from topmark import api

config = {
    "config": {
        "root": False,
        "strict": False,
    },
    "fields": {
        "project": "TopMark",
        "license": "MIT",
    },
    "header": {
        "fields": [
            "file",
            "project",
            "license",
        ]
    },
    "formatting": {
        "align_fields": True,
    },
    "files": {
        "include_file_types": ["topmark:python"],
        "exclude_patterns": [".venv"],
    },
    "policy_by_type": {
        "topmark:python": {
            "allow_header_in_empty_files": True,
        },
    }
}

run: api.RunResult = api.check(
    ["src"],
    config=config,
    diff=True,
    report="actionable",
)
```

API overlays, TOML configuration, CLI filters, and effective runtime policy resolution all share
identical file-type identity semantics. Local identifiers such as `"python"` are also accepted when
unambiguous. Internally, TopMark normalizes identifiers to canonical qualified keys such as
`"topmark:python"` before filtering, resolution, policy evaluation, and binding lookup.

Public API execution follows the same architecture as the CLI: immutable configuration, pipeline
selection, runtime-option construction, processing-context execution, reduction into durable
results, and final report rendering. Internal pipeline-selection objects and execution contexts are
intentionally not part of the public API surface.

Public API execution also uses the same documented filesystem-identity semantics as the CLI.
Existing filesystem inputs undergo filesystem-identity evaluation before pipeline execution.
Multiple path spellings that resolve to the same target, such as a symlink and its target, may
therefore be normalized to a single selected processing path and reported as a single result for the
resolved processing target. The selected processing path is the public result identity used by API
file results; original invocation spellings are not guaranteed to be preserved.

Hard-link policy is evaluated separately from path-spelling normalization. If multiple selected
processing paths refer to the same filesystem object through hard links, the public API preserves
one result per selected path and reports each affected path as an unsupported, policy-blocked
processing target. TopMark does not select a source, target, winner, or loser path from the
hard-link group.

For the public API, the returned view is controlled via
`report="all" | "actionable" | "noncompliant"`. This replaces the older `skip_compliant` /
`skip_unsupported` booleans.

{% include-markdown "\_snippets/api-internal-overrides.md" %}

See also:

- [Configuration](../usage/configuration.md)
- [Filtering](../usage/filtering.md)
- [Policies](../usage/policies.md)

### Resolution diagnostics and probe API

For programmatic inspection of file-type and processor resolution, use the high-level probe API:

```python
from topmark import api

result: api.ProbeRunResult = api.probe(["README.md"])

for fr in result.files:
    print(fr.path, fr.status, fr.reason)
    if fr.selected_file_type:
        print("selected:", fr.selected_file_type, fr.selected_processor)
    for c in fr.candidates:
        print(" -", c.file_type, c.rank, c.selected, c.matched_by)
```

Unlike content-processing APIs, probe execution always selects the dedicated read-only probe
pipeline. It does not perform header generation, mutation planning, comparison, patch generation, or
writing.

The probe API is read-only and returns stable JSON-friendly DTOs:

- \[`ProbeRunResult`\][topmark.api.types.ProbeRunResult] → aggregate results and summary
- \[`ProbeFileResult`\][topmark.api.types.ProbeFileResult] → one entry per input path (including
  missing or filtered inputs)
- \[`ProbeCandidateInfo`\][topmark.api.types.ProbeCandidateInfo] → normalized candidate information

Candidates are returned in resolver order (best match first).

For inputs that reach normal probing, `ProbeFileResult.path` reports the selected processing path,
not necessarily the original invocation spelling. Missing and filtered explicit inputs still report
explicit diagnostic input paths because they did not become normal processing paths. Hard-linked
processing targets remain separate probe results and are reported as unsupported with the stable
reason string `hard_link_duplicate`.

Unlike \[`check()`\][topmark.api.commands.pipeline.check] and
\[`strip()`\][topmark.api.commands.pipeline.strip],
\[`probe()`\][topmark.api.commands.pipeline.probe] does not perform content processing or mutation
planning. It only explains how inputs resolve to file types and processors.

Design guarantees:

- No exposure of internal enums, pipeline contexts, or registry objects
- `status` and `reason` are plain strings stable across the 1.x series
- `score` is explanatory only and not part of the compatibility contract; use `selected`, `rank`,
  and `matched_by`
- Explicit input paths are always returned, even if they are filtered or missing
- Hard-linked selected processing paths remain separate results and do not collapse to a preferred
  source, target, winner, or loser path

#### Missing and filtered inputs

The probe API explains inputs across the full discovery lifecycle:

- Missing explicit paths → `status="error"`
- Filtered explicit inputs → `status="filtered"` with reasons such as:
  - `excluded_by_path_filter`
  - `excluded_by_file_type_filter`
  - `excluded_by_discovery_filter`

This mirrors [`topmark probe`](../usage/commands/probe.md) (CLI) behavior and provides full
explainability without exposing resolver internals.

When an input does become a normal processing path, symlink spelling is not preserved in the result
path. This keeps public API results aligned with header metadata generation and machine-readable CLI
output.

Hard-link policy is a processing-target eligibility check rather than path normalization. If
multiple selected processing paths are hard links to the same filesystem object, each affected path
remains visible in public API results and is reported as unsupported.

#### Low-level probe helper

For direct path-based resolution (without discovery context), you may still use:

```python
from topmark.resolution.filetypes import probe_resolution_for_path

probe = probe_resolution_for_path("README.md")
```

This returns a \[`ResolutionProbeResult`\][topmark.resolution.probe.ResolutionProbeResult] exposing
candidate file types, scores, match signals, and the selected processor. It is the canonical
path-based resolution surface for advanced integrations.

Prefer \[`topmark.api.probe()`\][topmark.api.probe] for all public, semver-stable integrations.

The probe API is part of the stable 1.x public API surface and machine-readable compatibility
contract.

### Configuration resolution and provenance model

Internally, TopMark resolves TOML sources into a layered configuration model before producing the
final immutable \[`FrozenConfig`\][topmark.config.model.FrozenConfig] snapshot used by the public
API.

This process follows:

1. TOML sources (defaults, user, project, `--config`)
1. Layered configuration merging by precedence
1. Staged config-loading validation
1. Freeze into immutable \[`FrozenConfig`\][topmark.config.model.FrozenConfig]
1. Runtime overlays (API call arguments such as `diff`, `report`, etc.)

For processing APIs, pipeline selection occurs after configuration resolution and before runtime
execution. The selected pipeline definition is not part of the public compatibility contract; public
results expose stable outcome and reporting data rather than internal execution-planning objects.

File-backed TOML sources use configuration-source identity based on the resolved configuration-file
target. If a configuration file is reached through a symlink, provenance and applicability are based
on the resolved target rather than the symlink spelling.

Configuration-source identity is distinct from processing-target identity. Hard-link processing
policy applies to runtime filesystem-processing commands and public API helpers, but it does not
affect configuration loading, layered provenance, applicability evaluation, or configuration-source
selection. Conversely, configuration-source identity does not determine which runtime processing
paths enter pipeline execution.

The public API operates only on the flattened immutable
\[`FrozenConfig`\][topmark.config.model.FrozenConfig]. Staged validation logs are not exposed
directly; only their flattened compatibility view is used at reporting and API boundaries.

Internally, TopMark resolves TOML sources, validates each whole-source TOML fragment, builds merged
mutable runtime configuration state, and evaluates effective validity across staged config-loading
validation before freezing into or validating against an immutable
\[`FrozenConfig`\][topmark.config.model.FrozenConfig]. Advanced users can inspect the
TOML-resolution and draft-building portion of this process via
\[`resolve_toml_sources_and_build_mutable_config()`\][topmark.config.resolution.bridge.resolve_toml_sources_and_build_mutable_config].

### Recognized and supported file types

- File types are identified by their **file type identifier**.
- A file type is **recognized** if its *file type identifier* exists in
  \[`FileTypeRegistry`\][topmark.registry.filetypes.FileTypeRegistry].
- A file type is **supported** if it is recognized **and** has an effective binding in
  \[`BindingRegistry`\][topmark.registry.bindings.BindingRegistry] to a registered processor
  definition in \[`HeaderProcessorRegistry`\][topmark.registry.processors.HeaderProcessorRegistry].
- A file may be *recognized* but still *unbound* (and therefore not supported). In that case:
  - it participates in discovery and filtering
  - it may appear in results depending on the selected `report` scope
  - no header insertion or removal is attempted

File type identifiers may be provided either as a local identifier (`"python"`) or as a qualified
identifier (`"topmark:python"`).

Internally, TopMark normalizes identifiers to canonical qualified keys before filtering, resolution,
policy evaluation, and binding lookup.

Registry-facing APIs resolve identifiers using
\[`FileTypeRegistry.resolve_filetype_id(...)`\][topmark.registry.filetypes.FileTypeRegistry.resolve_filetype_id],
which returns the corresponding \[`FileType`\][topmark.filetypes.model.FileType] instance from the
effective composed registry.

Local identifiers are accepted only when they remain unambiguous in the composed registry. If
multiple file types share the same local identifier, callers must use the qualified
`"namespace:name"` form.

For a detailed explanation of the registry model and identity semantics, see
[Registry model](../dev/registry-model.md).

For resolution diagnostics, use
\[`probe_resolution_for_path()`\][topmark.resolution.filetypes.probe_resolution_for_path] (see
\[`topmark.resolution.filetypes.probe_resolution_for_path`\][topmark.resolution.filetypes.probe_resolution_for_path]).
This function returns a \[`ResolutionProbeResult`\][topmark.resolution.probe.ResolutionProbeResult]
exposing candidate file types, scores, match signals, and the selected processor. It is the
canonical path-based resolution surface for 1.0.

### Registries, bindings, and runtime extensibility

TopMark exposes read-only registry inspection through the stable
\[`Registry`\][topmark.registry.registry.Registry] facade.

The facade represents the effective composed runtime registry view of:

- registered file types
- registered header processors
- effective file type to processor bindings

Examples:

```python
from topmark.registry.registry import Registry

for ft in Registry.filetypes().values():
    print(ft.qualified_key)
```

```python
from topmark.registry.registry import Registry

for binding in Registry.bindings():
    print(binding.file_type_key, binding.processor_key)
```

Most public integrations should treat the registry facade as introspection-only and prefer the
high-level \[`topmark.api`\][topmark.api] execution helpers.

Public integrations should likewise treat pipeline selection and execution planning as internal
implementation details. The supported compatibility boundary is the documented API DTOs,
machine-readable output contracts, immutable configuration model, and registry-inspection surfaces.

Advanced registry concepts, including registry layers, runtime overlays, bindings, qualified/local
identity semantics, and runtime extension examples, are documented in
[Registry model](../dev/registry-model.md).

Registry state can also be inspected from the CLI:

- [`topmark registry`](../usage/commands/registry.md)
- [`topmark registry filetypes`](../usage/commands/registry/filetypes.md)
- [`topmark registry processors`](../usage/commands/registry/processors.md)
- [`topmark registry bindings`](../usage/commands/registry/bindings.md)

For resolution diagnostics, prefer:

- \[`topmark.api.probe()`\][topmark.api.probe]
- [`topmark probe`](../usage/commands/probe.md)

______________________________________________________________________

**Stability note:** See [API stability and snapshot policy](../dev/api-stability.md) for how TopMark
protects the stable public API surface across supported Python versions, including the
[identity-domain compatibility boundaries](../dev/api-stability.md#identity-domain-compatibility-boundaries)
shared by public API results, machine-readable output, configuration provenance, and documented
processing-target behavior.

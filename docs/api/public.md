<!--
topmark:header:start

  project      : TopMark
  file         : public.md
  file_relpath : docs/api/public.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# API Reference (%%TOPMARK_VERSION%%)

These pages are auto‑generated using [mkdocstrings](https://mkdocstrings.github.io/), pulling
docstrings directly from the TopMark source code.

The API reference complements the higher‑level usage guides:

- [Installation](../install.md)
- [Pre‑commit integration](../usage/pre-commit.md)
- [Header placement rules](../usage/header-placement.md)
- [Supported file types](../usage/generated/filetypes.md)
- [Supported header processors](../usage/generated/processors.md)

Use this section if you need details on functions, classes, or constants available in TopMark.

{% include-markdown "\_snippets/output-contract.md" %}

> [!NOTE]
>
> For programmatic use, prefer the Python API or JSON/NDJSON output rather than parsing
> TEXT/Markdown.

## Public API (stable)

### Configuration via mappings (immutable at runtime)

Public API functions accept either a plain **mapping** (that mirrors the TOML structure) or a frozen
\[`Config`\][topmark.config.model.Config]. Internally, TopMark merges your input into a **mutable
builder** and immediately \[`freeze()`s\][topmark.config.model.MutableConfig.freeze] it into an
immutable snapshot before running, which prevents accidental mutation and keeps results
deterministic.

The mapping mirrors the **layered TopMark config fragment** plus TOML-source-local sections such as
`[config]` and `[writer]`. Source-local options such as `[config].root` and `strict_config_checking`
can also be provided via the `config` key in the mapping, for example:

```python
config = {
    "config": {
        "root": True,
        "strict_config_checking": False,
    },
    # ... other sections like "fields", "header", "policy", etc.
}
```

Note that `strict_config_checking` is not a layered \[`Config`\][topmark.config.model.Config] field.
It is resolved from `[config]` / `[tool.topmark.config]`-shaped input during configuration loading
and influences validation behavior. API helpers such as
\[`ensure_config_valid(...)`\][topmark.api.runtime.ensure_config_valid] apply this effective
strictness (including optional overrides) when validating a config across staged
config-loading/preflight validation:

- TOML-source diagnostics
- merged-config diagnostics
- runtime-applicability diagnostics

These options are resolved separately from layered \[`Config`\][topmark.config.model.Config] values
and do not participate in layered config merging.

Internally, TopMark first performs whole-source TOML-style validation of these sections (unknown
keys, malformed section shapes, etc.), then deserializes only the layered fragment into the final
immutable \[`Config`\][topmark.config.model.Config] snapshot, and finally evaluates effective
validity across staged config-loading/preflight validation. A flattened compatibility diagnostics
view remains available for reporting and exception payloads, derived from the staged validation
logs. This is why sections like `[config]` and `[writer]` can influence loading/runtime behavior
without becoming layered \[`Config`\][topmark.config.model.Config] fields.

This distinction is also visible when inspecting configuration via
[`topmark config dump --show-layers`](../usage/commands/config/dump.md): source-local TOML fragments
are preserved per layer (for example under `[[layers]].toml.*` in human output or
`config_provenance.layers[].toml` in machine output), while the final immutable
\[`Config`\][topmark.config.model.Config] represents only the flattened effective configuration used
at runtime.

```python
from topmark import api

config = {
    "config": {
        "root": False,
        "strict_config_checking": False,
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
        "include_file_types": ["python"],
        "exclude_patterns": [".venv"],
    },
    "policy_by_type": {
        "python": {
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

For the public API, the returned view is controlled via
`report="all" | "actionable" | "noncompliant"`. This replaces the older `skip_compliant` /
`skip_unsupported` booleans.

{% include-markdown "\_snippets/api-internal-overrides.md" %}

### Resolution diagnostics (probe API)

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

The probe API is **read-only** and returns stable, JSON-friendly DTOs:

- \[`ProbeRunResult`\][topmark.api.types.ProbeRunResult] → aggregate results and summary
- \[`ProbeFileResult`\][topmark.api.types.ProbeFileResult] → one entry per input path (including
  missing or filtered inputs)
- \[`ProbeCandidateInfo`\][topmark.api.types.ProbeCandidateInfo] → normalized candidate information

Candidates are returned in resolver order (best match first).

Unlike \[`check()`\][topmark.api.commands.pipeline.check] and
\[`strip()`\][topmark.api.commands.pipeline.strip],
\[`probe()`\][topmark.api.commands.pipeline.probe] does not perform any content processing or
mutation planning. It only explains how inputs resolve to file types and processors.

Design guarantees:

- No exposure of internal enums, pipeline contexts, or registry objects
- `status` and `reason` are **plain strings** (stable across 1.x)
- `score` is **explanatory only** and not part of the stability contract; use `selected`, `rank`,
  and `matched_by`
- Explicit input paths are always returned, even if they are filtered or missing

#### Missing and filtered inputs

The probe API explains inputs across the full discovery lifecycle:

- Missing explicit paths → `status="error"`
- Filtered explicit inputs → `status="filtered"` with reasons such as:
  - `excluded_by_path_filter`
  - `excluded_by_file_type_filter`
  - `excluded_by_discovery_filter`

This mirrors [`topmark probe`](../usage/commands/probe.md) (CLI) behavior and provides full
explainability without exposing resolver internals.

#### Low-level probe helper (advanced)

For direct path-based resolution (without discovery context), you may still use:

```python
from topmark.resolution.filetypes import probe_resolution_for_path

probe = probe_resolution_for_path("README.md")
```

This returns a \[`ResolutionProbeResult`\][topmark.resolution.probe.ResolutionProbeResult] with
internal enums and full resolution evidence. It is **not part of the stable public API surface** and
should only be used for advanced debugging or internal integrations.

Prefer \[`topmark.api.probe()`\][topmark.api.probe] for all public, semver-stable integrations.

The probe API is part of the stable 1.x public API surface.

### Configuration resolution and provenance

Internally, TopMark resolves TOML sources into a layered configuration model before producing the
final immutable \[`Config`\][topmark.config.model.Config] snapshot used by the public API.

This process follows:

1. TOML sources (defaults, user, project, `--config`)
1. Layered config (merged by precedence)
1. Staged config-loading/preflight validation
1. Freeze into effective immutable \[`Config`\][topmark.config.model.Config]
1. Runtime overlays (API call arguments such as `diff`, `report`, etc.)

The public API only operates on the flattened immutable \[`Config`\][topmark.config.model.Config].
Staged validation logs are not exposed directly; only their flattened compatibility view is used at
reporting and API boundaries.

Internally, TopMark resolves TOML sources, validates each whole-source TOML fragment, builds a
merged mutable config draft, and evaluates effective validity across staged config-loading/preflight
validation before freezing into or validating against an immutable
\[`Config`\][topmark.config.model.Config]. Advanced users can inspect the TOML-resolution and
draft-building portion of this process via
\[`resolve_toml_sources_and_build_config_draft()`\][topmark.config.resolution.bridge.resolve_toml_sources_and_build_config_draft].

### Recognized vs supported file types

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

File type identifiers may be provided either as an unqualified name (`"python"`) or as a qualified
identifier (`"topmark:python"`). Internally, TopMark resolves these identifiers using
`FileTypeRegistry.resolve_filetype_id(...)`, which returns the corresponding
\[`FileType`\][topmark.filetypes.model.FileType] instance used by the runtime registries.

Unqualified identifiers are only safe when they remain unique in the composed registry. If multiple
file types share the same unqualified name, callers must use the qualified `"namespace:name"` form.

For resolution diagnostics, use
\[`probe_resolution_for_path()`\][topmark.resolution.filetypes.probe_resolution_for_path] (see
\[`topmark.resolution.filetypes.probe_resolution_for_path`\][topmark.resolution.filetypes.probe_resolution_for_path]).
This function returns a \[`ResolutionProbeResult`\][topmark.resolution.probe.ResolutionProbeResult]
exposing candidate file types, scores, match signals, and the selected processor, and is the
canonical path-based resolution surface for 1.0.

### Registries, bindings, and extensibility

TopMark exposes **read-only** registries for file types and header processors via the stable facade
in \[`topmark.registry.registry.Registry`\][topmark.registry.registry.Registry]. These registries
represent the **effective composed view** (internal base registries + overlays − removals) and are
returned as immutable `Mapping` views (backed by `MappingProxyType`).

These registry objects are **not part of the \[`topmark.api`\][topmark.api] stability contract**;
the supported programmatic API is defined exclusively by the symbols exported in
\[`topmark.api.__all__`\][topmark.api].

Identity registries (\[`FileTypeRegistry`\][topmark.registry.filetypes.FileTypeRegistry],
\[`HeaderProcessorRegistry`\][topmark.registry.processors.HeaderProcessorRegistry]) and the
relationship registry (\[`BindingRegistry`\][topmark.registry.bindings.BindingRegistry]) are
advanced APIs. The stable \[`Registry`\][topmark.registry.registry.Registry] façade remains the
preferred entry point for public read operations and cross-registry coordination.

The registry model has been refactored into three explicit layers with clear responsibilities:

- \[`FileTypeRegistry`\]\[topmark.registry.filetypes.FileTypeRegistry\]: manages file type
  identities (namespace, local key, qualified key)
- \[`HeaderProcessorRegistry`\]\[topmark.registry.processors.HeaderProcessorRegistry\]: manages
  processor identities (namespace, local key, qualified key)
- \[`BindingRegistry`\]\[topmark.registry.bindings.BindingRegistry\]: manages relationships between
  file types and processors (bindings)

The \[`Registry`\][topmark.registry.registry.Registry] facade composes these layers and provides
convenience read-only accessors such as:

- `Registry.filetypes()` → effective file type mapping
- `Registry.processors_by_qualified_key()` → processor definitions by qualified key
- `Registry.bindings()` → effective bindings

This separation ensures that identity and relationships remain decoupled, and avoids implicit side
effects when registering or binding components.

Most users should interact with registries through this facade and treat them as
**introspection-only**.

Resolution of file types and processors is now probe-driven in 1.0. Instead of using ad-hoc helpers,
callers should rely on
\[`probe_resolution_for_path()`\][topmark.resolution.filetypes.probe_resolution_for_path] and then
use the registry facade to inspect or resolve processors from the selected file type.

If you need dynamic extensions at runtime (typically in plugins or tests), use the advanced
registries in \[`topmark.registry`\][topmark.registry] directly and keep the steps explicit:

```python
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

# Register file type identity
FileTypeRegistry.register(ft)

# Register processor identity
proc_def = HeaderProcessorRegistry.register(
    processor_class=MyProcessor,
)

# Bind file type to processor
BindingRegistry.bind(
    file_type_key=ft.qualified_key,
    processor_key=proc_def.qualified_key,
)
```

For cleanup, reverse the same steps explicitly:

- `BindingRegistry.unbind(ft.qualified_key)`
- `HeaderProcessorRegistry.unregister(proc_def.qualified_key)`
- `FileTypeRegistry.unregister(ft.qualified_key)`

Note that all mutation helpers operate on **overlay state only**. They do not mutate the built-in
registry definitions and are intended for runtime extensions (e.g. plugins or tests).

These mutation helpers apply **overlay-only changes**: they do not mutate the internal base
registries used to construct the effective views. Overlays are process-local and thread-safe (via an
internal lock). In tests, prefer wrapping mutations in `try/finally` to ensure cleanup.

Overlay mutations automatically invalidate composed registry caches; callers do not need to manage
cache lifetimes explicitly.

When registering processors against file types, prefer qualified file type identifiers such as
`"topmark:python"` or `"my_plugin:django_html"` once multiple namespaces are in play. Unqualified
names remain supported for compatibility, but may become ambiguous.

For long-term or redistributable extensions, prefer publishing a plugin using the
\[`topmark.filetypes`\][topmark.filetypes] entry point group.

See the generated API reference:

- [`topmark.api`](../api/reference/topmark.api.md)
- [`topmark.registry`](../api/reference/topmark.registry.md)

______________________________________________________________________

**Stability note:** See [API Stability](../dev/api-stability.md) for how we guard the public surface
with a JSON snapshot across supported Python versions.

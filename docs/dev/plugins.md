<!--
topmark:header:start

  project      : TopMark
  file         : plugins.md
  file_relpath : docs/dev/plugins.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Plugins and extensibility

TopMark supports extensibility via **plugins** that provide:

1. **File types** (definitions of how TopMark recognizes files), and optionally
1. **Header processors** (implementations that can detect/insert/update/strip headers for those file
   types).

This page documents the supported plugin extension points for TopMark 1.x.

{% include-markdown "\_snippets/terminology.md" %}

For the lower-level registry architecture, composed registry views, bindings, overlays, and identity
semantics, see [Registry model](registry-model.md).

See also:

- [Registry model](registry-model.md)
- [Resolver model](resolution.md)
- [Registry CLI commands](../usage/commands/registry.md)
- [Registry file types command](../usage/commands/registry/filetypes.md)
- [Registry processors command](../usage/commands/registry/processors.md)
- [Registry bindings command](../usage/commands/registry/bindings.md)
- [Configuration](../usage/configuration.md)

______________________________________________________________________

## Conceptual model

Plugins extend TopMark by contributing file type definitions and, for advanced integrations, runtime
processor overlay registrations.

The detailed registry architecture is documented in [Registry model](registry-model.md). In short:

- file type plugins are loaded through the `topmark.filetypes` entry point group;
- built-in processors are defined by TopMark's internal binding inventory;
- advanced processor integrations use runtime overlays;
- CLI and API execution use the effective composed runtime registry view.

Plugin authors should treat qualified file type identifiers, such as `my_plugin:my_lang`, as the
stable reference once custom namespaces are involved.

______________________________________________________________________

## Extension points

### File types (recommended plugin surface)

File types are discovered through Python entry points. TopMark loads:

- **built-in file types** from a small set of internal modules, and
- **plugin file types** from the entry point group:
  - **Entry point group:** \[`topmark.filetypes`\][topmark.filetypes]

A plugin contributes one or more \[`FileType`\][topmark.filetypes.model.FileType] objects through
that entry point.

**When loaded:** lazily, when TopMark first performs file-type resolution.

______________________________________________________________________

### Header processors (advanced / internal-facing)

Built-in header processors are declared explicitly in TopMark's internal processor binding inventory
and instantiated when the base processor registry is constructed.

Advanced integrations and tests may still register additional processor classes at runtime through
\[`topmark.registry.registry.Registry`\][topmark.registry.registry.Registry] or
\[`topmark.registry.processors.HeaderProcessorRegistry`\][topmark.registry.processors.HeaderProcessorRegistry].
These registrations are applied as overlay-only mutations layered on top of the immutable internal
base registry.

______________________________________________________________________

## Registration order and runtime overlays

TopMark uses explicit base registries plus overlay registries:

- base file types are loaded from built-ins and file-type entry points;
- base processors are constructed from explicit built-in bindings;
- runtime additions and removals are applied as overlays via
  \[`topmark.registry.*`\][topmark.registry].

This means plugin-defined file types must still be available before a processor class is registered
against them, but processor registration no longer depends on module import order or decorator side
effects. Path-based file type selection is performed by the shared scoring resolver in
\[`topmark.resolution.filetypes`\][topmark.resolution.filetypes]. The formal selection and ambiguity
policy is documented in [`resolution.md`](resolution.md).

______________________________________________________________________

## Writing a FileType plugin

### File type identity: name and namespace

Every \[`FileType`\][topmark.filetypes.model.FileType] has two identity components:

- `namespace`: identifies the producer, such as `topmark`, `acme`, or `my_plugin`
- `name`: the local file type key within that namespace

TopMark reserves the namespace `topmark` (the internal constant
\[`TOPMARK_NAMESPACE`\][topmark.core.constants.TOPMARK_NAMESPACE]) for built-in file types.

**Plugin guidance:**

- Set `namespace` to your package or organization identifier, for example `"acme"` or
  `"my_company"`.
- Choose a clear local `name`, for example `"django_html"` or `"my_lang"`.
- Use qualified file type identities, such as `"acme:django_html"`, in shared configuration,
  processor bindings, and documentation.

Note: `namespace` is **mandatory** for both file types and processors. The built-in namespace
`topmark` is reserved for TopMark-provided types.

TopMark normalizes file type identifiers to canonical qualified keys of the form
`<namespace>:<name>`.

TopMark accepts both:

- local identifiers such as `"python"`, when unambiguous;
- qualified identifiers such as `"topmark:python"` or `"acme:django_html"`.

Local identifiers are accepted only when unambiguous in the effective composed registry. If multiple
file types share the same local identifier, callers must use the qualified form.

Registry-facing APIs resolve identifiers through
\[`FileTypeRegistry.resolve_filetype_id(...)`\][topmark.registry.filetypes.FileTypeRegistry.resolve_filetype_id].

For the complete identity contract, see
[Registry model](registry-model.md#qualified-vs-local-identifiers).

### 1) Create a provider function

Create a module that returns an iterable of \[`FileType`\][topmark.filetypes.model.FileType]
objects.

Example:

```python
# my_topmark_plugin/filetypes.py
from __future__ import annotations

from topmark.filetypes.model import FileType

def provide_filetypes() -> list[FileType]:
    return [
        FileType(
            name="my_lang",
            namespace="my_plugin",
            extensions=[".mylang"],
            filenames=[],
            patterns=[],
            description="MyLang source files",
            skip_processing=False,
        )
    ]
```

### Using the FileType factory (recommended)

TopMark provides a small helper factory that simplifies constructing multiple file types that share
the same namespace.

```python
from topmark.filetypes.factory import make_filetype_factory

make_my_ft = make_filetype_factory(namespace="my_plugin")

MY_FILETYPE = make_my_ft(
    name="my_lang",
    description="MyLang source files",
    extensions=[".mylang"],
)
```

This avoids repeating the namespace argument and ensures that all
\[`FileType`\][topmark.filetypes.model.FileType] instances created by the plugin share the correct
identity.

The factory only constructs \[`FileType`\][topmark.filetypes.model.FileType] objects.

Registration still happens when TopMark loads file types through the
\[`topmark.filetypes`\][topmark.filetypes] entry point group.

### 2) Register the entry point

In your plugin's `pyproject.toml`:

```toml
[project.entry-points."topmark.filetypes"]
my_topmark_plugin = "my_topmark_plugin.filetypes:provide_filetypes"
```

This registers your file type provider so TopMark can discover it.

File types are loaded lazily when TopMark first resolves file types during configuration or pipeline
execution.

______________________________________________________________________

## Writing a HeaderProcessor plugin (advanced)

Header processor plugins use advanced runtime-overlay registration semantics rather than entry-point
discovery.

A processor class must define a stable processor identity:

- `namespace`: identifies the producer
- `key`: local processor identifier within that namespace

The qualified processor identity is `<namespace>:<key>`.

To register a processor class for a file type at runtime, use the composed registry layer:

```python
# my_topmark_plugin/processors.py
from __future__ import annotations

from topmark.processors.base import HeaderProcessor
from topmark.registry.registry import Registry


class MyLangHeaderProcessor(HeaderProcessor):
    """Example processor for MyLang."""
    namespace = "my_plugin"
    key = "my_lang"

    # Implement required HeaderProcessor methods here
    ...


Registry.register_processor("my_plugin:my_lang", MyLangHeaderProcessor)
```

At registration time, TopMark resolves the file type identifier through the composed runtime file
type registry and then binds the processor to that resolved
\[`FileType`\][topmark.filetypes.model.FileType] object. Qualified identifiers are recommended
because a local file type identifier may become ambiguous once multiple namespaces define similarly
named file types.

Important:

- file type registration must happen before processor registration;
- runtime processor registrations are overlay-only and do not mutate immutable built-in base
  registry data;
- processor bindings should use canonical qualified file type identifiers for deterministic
  behavior.

______________________________________________________________________

## Runtime processor registration flow

Unlike file types, processor classes are not discovered from entry points. They are registered
explicitly through the runtime registry API when needed.

A typical advanced integration flow is:

1. expose file types through the \[`topmark.filetypes`\][topmark.filetypes] entry point group;
1. let TopMark discover those file types lazily;
1. register processor classes explicitly through
   \[`HeaderProcessorRegistry.register(...)`\][topmark.registry.processors.HeaderProcessorRegistry.register],
   \[`Registry.bind(...)`\][topmark.registry.registry.Registry.bind], or
   \[`HeaderProcessorRegistry.register(...)`\][topmark.registry.processors.HeaderProcessorRegistry.register]
   during controlled initialization.

This keeps built-in registry construction deterministic and avoids module-import side effects.

______________________________________________________________________

## Recommended plugin scope for TopMark 1.x

For most integrations, providing **FileType plugins only** is sufficient.

Header processor plugins are more advanced because they rely on runtime overlay registration and
explicit processor bindings.

Unless you need custom header parsing or formatting logic, prefer defining custom file types that
reuse existing processors.

______________________________________________________________________

## Troubleshooting

### "Unknown file type" during processor registration

Cause: the processor registration target does not resolve through the composed file type registry.

Fix:

- Ensure the plugin file type (including its `namespace` and unique `name`) is registered via the
  \[`topmark.filetypes`\][topmark.filetypes] entry point.
- Ensure file type discovery occurs before calling
  \[`Registry.bind(...)`\][topmark.registry.registry.Registry.bind].
- Prefer qualified file type identifiers such as `"my_plugin:my_lang"` when registering processors.

### "Ambiguous file type identifier" during processor registration

Cause: an unqualified file type identifier such as `"python"` or `"html"` matched more than one file
type in the composed registry.

Fix:

- Retry with a qualified identifier such as `"topmark:html"` or `"my_plugin:django_html"`.
- Use qualified identifiers consistently in shared configuration, processor bindings, and plugin
  documentation.

### Duplicate processor registration

TopMark rejects duplicate overlay registrations targeting the same effective file type binding.

If you see an error indicating that a processor is already registered for a file type, decide on an
explicit overlay strategy first, for example:

- unregister the existing overlay and then register the replacement;
- leave the existing processor in place;
- fail fast and require the caller to choose a policy explicitly.

______________________________________________________________________

## Relevant internal modules

These modules are useful for advanced TopMark integrations and registry extensions:

- \[`topmark.filetypes.instances`\][topmark.filetypes.instances] - base file type discovery
- \[`topmark.processors.instances`\][topmark.processors.instances] - base processor binding
  inventory and registry construction
- \[`topmark.resolution.filetypes`\][topmark.resolution.filetypes] - shared scoring-based path
  resolver
- \[`topmark.registry.filetypes`\][topmark.registry.filetypes] - composed file type registry view
  and identifier resolution
- \[`topmark.registry.processors`\][topmark.registry.processors] - composed processor registry view
  and overlay mutations
- \[`topmark.registry.registry`\][topmark.registry.registry] - stable higher-level registry facade
- \[`topmark.registry.bindings`\][topmark.registry.bindings] - composed binding registry and overlay
  mutations

These composed registries provide effective runtime views that combine base registrations with
runtime overlays and removals.

______________________________________________________________________

## See also

- [`Registry model`](./registry-model.md) - detailed registry layers, bindings, overlays, and
  identifier semantics
- [`Terminology and Canonical Vocabulary`](../terminology.md) - canonical identifier, overlay,
  applicability, and machine-readable terminology
- [`Architecture`](./architecture.md) - high-level overview of registries and runtime composition
- [`registry.md`](../usage/commands/registry.md) - CLI-facing registry inspection commands
- [`Resolution model`](./resolution.md) - file-type scoring and ambiguity policy

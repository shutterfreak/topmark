<!--
topmark:header:start

  project      : TopMark
  file         : api-stability.md
  file_relpath : docs/dev/api-stability.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# API stability and snapshot policy

TopMark maintains a stable public 1.x Python API across all supported Python versions (3.10-3.14)
using a JSON-based snapshot test.

The snapshot system protects the documented public execution surface exposed through `topmark.api`,
helping downstream users rely on stable symbols, signatures, and machine-readable behavior contracts
across releases.

{% include-markdown "\_snippets/terminology.md" %}

See also:

- [Public API](../api/public.md)
- [Registry model](registry-model.md)
- [Terminology and Canonical Vocabulary](../terminology.md)
- [Machine-readable output](../usage/machine-output.md)
- [Machine-readable format conventions](machine-formats.md)
- [Configuration discovery, precedence, and policy](../configuration/index.md)
- [Resolution](resolution.md)
  - [Filesystem identity and processing paths](resolution.md#filesystem-identity-and-processing-paths)
- [Release Process](release-process.md)
- [Test and validation architecture](../ci/test-validation.md)

______________________________________________________________________

## Scope of this document

This page documents:

- the stable public API boundary;
- API snapshot generation and validation;
- compatibility expectations across supported Python versions;
- relationships between API stability, machine-readable output, configuration behavior, and
  release/versioning policy.

It also explains which TopMark subsystems are intentionally excluded from the public stability
contract.

______________________________________________________________________

## Public API Contract

TopMark defines its **stable programmatic API** as the set of symbols exported by
`topmark.api.__all__`.

In practice this means:

- Anything exported from \[`topmark.api`\][topmark.api] is considered part of the stable public 1.x
  API surface.
- Symbols not exported via `topmark.api.__all__` are **internal implementation details** and may
  change without notice.
- Registry internals (`topmark.registry.*`) are documented for maintainers and advanced integrations
  but are **not part of the stable snapshot compatibility contract**.

The API snapshot test therefore derives its reference surface directly from `topmark.api.__all__`
and verifies that this public façade remains stable across Python versions.

This boundary intentionally separates:

- stable user-facing execution APIs;
- stable machine-readable output contracts;
- stable configuration and file type identity semantics;
- stable documented processing-target behavior;
- evolving registry internals and overlay helpers.

### Identity-domain compatibility boundaries

TopMark documents several identity domains that intentionally share vocabulary but have separate
compatibility boundaries:

| Domain                         | Stable compatibility surface                                                                                                                                                                                                   | Flexible implementation detail                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Processing-target identity     | Public/API/CLI results are based on selected processing paths after filesystem-identity evaluation. Header metadata and processing machine output use that selected processing path.                                           | The internal data structures and helper functions used to choose the selected processing path.        |
| Configuration-source identity  | File-backed TOML provenance, precedence, and applicability are based on resolved configuration-file targets. Synthetic sources use stable labels.                                                                              | The staged config-loading objects and merge-building machinery.                                       |
| Workspace/config discovery     | Project-chain configuration discovery resolves the selected anchor before walking upward, so symlinked CWD and input-anchor spellings discover configuration from the resolved target chain.                                   | The internal helper structure used to choose and traverse discovery anchors.                          |
| Registry identity              | Canonical qualified identifiers such as `topmark:python`, `qualified_key`, `file_type_key`, and `processor_key` are stable machine-readable/public behavior.                                                                   | Registry composition internals, overlay mutation helpers, and scoring implementation details.         |
| Path serialization             | Machine-readable filesystem path fields use POSIX `/` separators and report selected processing paths, not invocation spellings.                                                                                               | Human-facing path formatting and presentation labels.                                                 |
| Filesystem-identity evaluation | Documented outcomes are stable: equivalent symlink spellings collapse to selected processing paths, and selected hard-linked processing targets are reported as unsupported policy-blocked results without selecting a winner. | Low-level platform probes, cache shape, and implementation helpers used to detect equivalent objects. |

______________________________________________________________________

## What the snapshot covers

The snapshot captures the **stable programmatic API exposed via \[`topmark.api`\][topmark.api]**,
including:

- `from topmark import api`: all entries defined in `api.__all__`
- Public API command functions (e.g. \[`check`\][topmark.api.commands.pipeline.check],
  \[`strip`\][topmark.api.commands.pipeline.strip],
  \[`probe`\][topmark.api.commands.pipeline.probe],
  \[`list_filetypes`\][topmark.api.commands.registry.list_filetypes],
  \[`list_processors`\][topmark.api.commands.registry.list_processors], version helpers)
- Public result and metadata types exported by \[`topmark.api`\][topmark.api]
- Enum and class structure normalization for cross-version consistency:
  - Enums → `"<enum>"`
  - Classes → `"<class>"`
  - Functions → real signatures are preserved

This includes stable read-only diagnostic APIs such as \[`topmark.api.probe()`\][topmark.api.probe]
in addition to content-processing commands.

The snapshot intentionally **does not include internal registries or implementation modules**. Only
the public façade defined by `topmark.api.__all__` is considered part of the stable surface.

Overlay state and internal registries are intentionally excluded from the snapshot; only symbols and
signatures exported via \[`topmark.api`\][topmark.api] are tracked.

Configuration layering objects and TOML source resolution machinery are internal implementation
details and are not part of the public API symbol contract. The documented configuration-source
identity behavior exposed through provenance, applicability, and machine-readable output is part of
the supported behavior contract.

Canonical file type identity semantics are part of the stable public behavior contract shared
across:

- CLI filtering;
- TOML configuration;
- API overlays;
- resolution and filtering;
- machine-readable output.

The comparison is deterministic across Python versions by normalizing class representations and
ordering.

______________________________________________________________________

## Stability boundaries

TopMark intentionally separates:

- stable execution APIs;
- stable machine-readable output contracts;
- stable configuration and filtering behavior contracts;
- evolving internal orchestration and registry internals.

The snapshot protects the stable public surface exposed through `topmark.api`, while allowing
controlled internal refactoring and pipeline evolution.

______________________________________________________________________

## Running the API stability tests

You can verify API stability via either **nox** or **make**.

### Quick local check (current interpreter only)

```bash
make api-snapshot-dev
```

This runs the API snapshot test once using your active Python interpreter.

### Full matrix check (across all supported Pythons)

```bash
make api-snapshot
```

This executes the snapshot tests for all supported Python versions defined in the `nox` matrix
(3.10-3.14). It corresponds to running:

```bash
nox -s api_snapshot
```

### Regenerate snapshot (when public API changes intentionally)

```bash
make api-snapshot-update
```

This regenerates the file `tests/api/public_api_snapshot.json` via `tools/api_snapshot.py`, shows
the diff, and instructs you to commit the updated snapshot if the public API changed.

### Ensure snapshot is clean (CI gate)

```bash
make api-snapshot-ensure-clean
```

Fails if the current working tree differs from the committed snapshot - useful in CI to detect
unintended API drift.

These commands map directly to the validation tooling documented in:

- [Test and validation architecture](../ci/test-validation.md)
- [CI workflow](../ci/ci-workflow.md)

______________________________________________________________________

## Relationship to machine-readable output

The API snapshot protects importable Python symbols and signatures exposed through `topmark.api`.
Machine-readable output stability is tracked separately through documented JSON and NDJSON
contracts.

Stable machine-readable contracts include canonical identifiers such as:

- `qualified_key`
- `file_type_key`
- `processor_key`

These identifiers are intentionally shared across:

- CLI filtering;
- TOML configuration;
- API overlays;
- resolution and filtering;
- machine-readable output.

See also:

- [Machine-readable output](../usage/machine-output.md)
- [Machine-readable format conventions](machine-formats.md)

______________________________________________________________________

## Stability policy

- **Automatic validation:** Every PR and CI run verifies that the public API matches the committed
  snapshot.

- **If the snapshot test fails:**

  1. **Unintentional change:** fix or revert the code to match the current public API.
  1. **Intentional change:** regenerate the snapshot (`make api-snapshot-update`), commit the new
     snapshot, and add a corresponding entry to `CHANGELOG.md`. Package versioning is derived from
     Git tags via `setuptools-scm`, so no manual version bump is performed in `pyproject.toml`.

**Registry note:** Registry access for integrations is provided via the read-only façade in
\[`topmark.registry.registry.Registry`\][topmark.registry.registry.Registry].

The registry system itself is intentionally versioned more flexibly than the stable
\[`topmark.api`\][topmark.api] execution surface.

Registry internals, overlay mutation helpers, and composed registry implementation details may
evolve independently as long as:

- the documented public API remains stable;
- documented machine-readable output contracts remain stable;
- canonical identifier semantics remain stable.
- **Supported Python range:** 3.10-3.14 (`nox` matrix). Future Python minor releases will be added
  once validated by CI and release tooling.
- **File under version control:**\
  `tests/api/public_api_snapshot.json` must always be checked in and tracked.

______________________________________________________________________

## Implementation notes

- The snapshot test is implemented in `tests/api/test_public_api_snapshot.py`.
- The generator logic lives in `tools/api_snapshot.py`.
- Normalization ensures consistent diffing across OSes and Python builds.
- Canonical file type identity normalization ensures stable file type handling across configuration,
  resolver, registry, and machine-readable output boundaries.
- The snapshot is derived from `topmark.api.__all__`, ensuring the stable façade remains small and
  explicitly defined.
- Internal helpers such as
  \[`topmark.filetypes.instances.get_base_file_type_registry`\][topmark.filetypes.instances.get_base_file_type_registry]
  and
  \[`topmark.processors.instances.get_base_header_processor_registry`\][topmark.processors.instances.get_base_header_processor_registry]
  are not part of the public API and may change without notice.

______________________________________________________________________

## Relationship to release versioning

Intentional public API changes should:

1. update the snapshot;
1. update `CHANGELOG.md`;
1. align with the intended release-version and compatibility semantics.

TopMark derives package versions from Git tags through `setuptools-scm`.

Public API evolution, snapshot updates, changelog entries, and release tags together form the
historical record of API evolution.

See also:

- [Release Process](release-process.md)
- [CI & Validation](../ci/index.md)

______________________________________________________________________

## Non-goals

The snapshot contract intentionally does not guarantee stability for:

- internal registry composition details;
- overlay mutation helpers;
- internal runtime-configuration construction structure;
- internal resolver scoring heuristics;
- private helper modules outside \[`topmark.api`\][topmark.api].

Only documented public APIs and machine-readable output contracts are considered part of the stable
1.x compatibility surface.

______________________________________________________________________

## Practical workflow

1. Modify or extend the TopMark public API surface.

1. Run:

   ```bash
   make api-snapshot-dev
   ```

   If it fails due to expected changes:

1. Regenerate snapshot:

   ```bash
   make api-snapshot-update
   ```

1. Commit the updated `tests/api/public_api_snapshot.json`.

1. Update `CHANGELOG.md` accordingly.

1. When preparing a release, create the appropriate Git tag for the intended version (for example
   `v1.0.0a1`, `v1.0.0rc1`, or `v1.0.0`).

______________________________________________________________________

## Related pages

- [Public API](../api/public.md)
- [Registry model](registry-model.md)
- [Terminology and Canonical Vocabulary](../terminology.md)
- [Machine-readable output](../usage/machine-output.md)
- [Machine-readable format conventions](machine-formats.md)
- [Release Process](release-process.md)
- [Test and validation architecture](../ci/test-validation.md)

**Summary:**

TopMark separates stable public execution APIs, machine-readable output contracts, and canonical
identifier semantics from more flexible internal registry and orchestration details.

The snapshot system protects the documented stable public surface while still allowing controlled
internal evolution under the project's Git-tag-driven release and versioning model.

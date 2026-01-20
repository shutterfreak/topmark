<!--
topmark:header:start

  project      : TopMark
  file         : api-stability.md
  file_relpath : docs/dev/api-stability.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# API Stability & Snapshot Policy

TopMark enforces a **stable public API** across all supported Python versions (**3.10–3.14**) using a JSON-based snapshot test.\
This ensures that downstream users can rely on consistent function signatures and symbols across releases.

______________________________________________________________________

## 🧩 What’s Covered

The snapshot captures public-facing API symbols and their structure, including:

- `from topmark import api`: all entries defined in `api.__all__`
- `Registry.filetypes`, `Registry.processors`, and `Registry.bindings` method signatures (stable registry facade)
- `FileTypeRegistry` / `HeaderProcessorRegistry` symbols and signatures when exported via `topmark.registry` (advanced, but still snapshot-tracked)
- Enum and class structure normalization for cross-version consistency:
  - Enums → `"<enum>"`
  - Classes → `"<class>"`
  - Functions → real signatures are preserved

Overlay state is intentionally excluded from the snapshot; only symbols and signatures are tracked.

The comparison is deterministic across Python versions by normalizing class representations and ordering.

______________________________________________________________________

## 🔍 Running the API Stability Tests

You can verify API stability via either **tox** or **make**.

### Quick local check (current interpreter only)

```bash
make api-snapshot-dev
```

This runs the API snapshot test once using your active Python interpreter.

### Full matrix check (across all supported Pythons)

```bash
make api-snapshot
```

This executes the snapshot tests for all Python versions defined in the tox matrix (3.10–3.14).\
It corresponds to running:

```bash
tox -m api-check
```

### Regenerate snapshot (when public API changes intentionally)

```bash
make api-snapshot-update
```

This regenerates the file `tests/api/public_api_snapshot.json` via `tools/api_snapshot.py`, showing the diff and instructing you to commit and update the version if the API changed.

### Ensure snapshot is clean (CI gate)

```bash
make api-snapshot-ensure-clean
```

Fails if the current working tree differs from the committed snapshot — useful in CI to detect unintended API drift.

______________________________________________________________________

## TOML I/O and tomlkit internals

The helper `topmark.config.io.nest_toml_under_section` uses `tomlkit`’s
`TOMLDocument` and its `.body` layout to preserve comments and whitespace
when nesting an existing document under a dotted section (for example
`tool.topmark` when generating a `pyproject.toml` block).

This function is intentionally covered by focused tests
(see `tests/config/test_io.py`) so that changes in tomlkit’s internal
representation (e.g. how comments or whitespace nodes are stored) are
caught early. If a future tomlkit release breaks these tests, the
expected behavior here is the reference: preamble and postamble comments
must be preserved, and the nested document must remain valid TOML.

______________________________________________________________________

## Config sanitization and invariants

The method `MutableConfig.sanitize()` in `topmark.config.model` is the
central place to enforce invariants on configuration values before they
are frozen into an immutable `Config`.

Current rules are intentionally conservative (for example, rejecting
glob-like paths in `include_from` / `exclude_from` / `files_from`), but
this method is expected to grow stricter over time. New checks should:

- Prefer emitting diagnostics (warnings or errors) over raising
  exceptions where possible.
- Use `Config.diagnostics` to surface problems to the CLI and JSON/NDJSON
  machine output.
- Avoid changing the *shape* of the public config API; instead, treat
  sanitization as validating and annotating existing fields.

If downstream tools rely on exact error messages or the absence of
diagnostics, they should be treated as internal integrations rather than
stable public API.

______________________________________________________________________

## 🧱 Policy

- **Automatic validation:**\
  Every PR and CI run verifies that the public API matches the committed snapshot.

- **If the snapshot test fails:**

  1. **Unintentional change:** fix or revert the code to match the current public API.
  1. **Intentional change:** regenerate the snapshot (`make api-snapshot-update`), commit the new snapshot, and **bump the version** in `pyproject.toml`.\
     Also add a corresponding entry to the `CHANGELOG.md`.

**Registry note:**
Registry access for integrations is expected to go through `topmark.registry.Registry` (read-only facade). The advanced registries (`FileTypeRegistry`, `HeaderProcessorRegistry`) are supported for tests and plugins via overlay registration, but changes to their public signatures are still tracked by the snapshot.

- **Supported Python range:** 3.10–3.14 (tox matrix).\
  Future minor Python releases will be added once supported by CI.

- **File under version control:**\
  `tests/api/public_api_snapshot.json` must always be checked in and tracked.

______________________________________________________________________

## ⚙️ Implementation Notes

- The snapshot test is implemented in `tests/api/test_public_api_snapshot.py`.
- The generator logic lives in `tools/api_snapshot.py`.
- Normalization ensures consistent diffing across OSes and Python builds.
- The snapshot intentionally treats `topmark.registry.Registry` as the stable entry point for registry introspection; internal base registries under `topmark.filetypes.*` are not part of the public surface.
- Advanced registries are snapshot-tracked for signatures, not behavior.
- Internal helpers such as `get_base_file_type_registry()` and `get_base_header_processor_registry()` are not part of the public API and may change without notice

______________________________________________________________________

## ✅ Practical Workflow

1. Modify or extend the TopMark public API.

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

1. Bump the version in `pyproject.toml`.

1. Update `CHANGELOG.md` accordingly.

______________________________________________________________________

**Summary:**\
The API snapshot system protects TopMark’s public interface from unintended breakage while still allowing controlled evolution under semantic versioning.

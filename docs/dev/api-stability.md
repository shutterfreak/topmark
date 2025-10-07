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
- `Registry.filetypes`, `Registry.processors`, and `Registry.bindings` method signatures
- Enum and class structure normalization for cross-version consistency:
  - Enums → `"<enum>"`
  - Classes → `"<class>"`
  - Functions → real signatures are preserved

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

## 🧱 Policy

- **Automatic validation:**\
  Every PR and CI run verifies that the public API matches the committed snapshot.

- **If the snapshot test fails:**

  1. **Unintentional change:** fix or revert the code to match the current public API.
  1. **Intentional change:** regenerate the snapshot (`make api-snapshot-update`), commit the new snapshot, and **bump the version** in `pyproject.toml`.\
     Also add a corresponding entry to the `CHANGELOG.md`.

- **Supported Python range:** 3.10–3.14 (tox matrix).\
  Future minor Python releases will be added once supported by CI.

- **File under version control:**\
  `tests/api/public_api_snapshot.json` must always be checked in and tracked.

______________________________________________________________________

## ⚙️ Implementation Notes

- The snapshot test is implemented in `tests/api/test_public_api_snapshot.py`.
- The generator logic lives in `tools/api_snapshot.py`.
- Normalization ensures consistent diffing across OSes and Python builds.

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

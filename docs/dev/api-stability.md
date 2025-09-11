<!--
topmark:header:start

  file         : api-stability.md
  file_relpath : docs/dev/api-stability.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# API Stability & Snapshot Test

TopMark enforces a stable public API across Python 3.10–3.13 using a JSON snapshot.

## What’s covered

- `from topmark import api`: symbols in `api.__all__`
- `Registry.filetypes`, `Registry.processors`, `Registry.bindings` method signatures

To avoid CPython version drift, class/enum constructors are normalized in the test:

- Enums → `"<enum>"`
- Other classes → `"<class>"`
- Functions/callables keep real signatures

## (Re)generating the snapshot

Use the Make target to refresh the snapshot when you intentionally change the public API:

```bash
make public-api-update
```

This runs `tools/api_snapshot.py` to write `tests/api/public_api_snapshot.json`. Commit the file
along with a version bump and a CHANGELOG entry.

## Policy

- If the snapshot test fails, either:
  - You unintentionally changed the public API → revert or adjust the change; or
  - You intentionally changed it → update the snapshot **and** bump the version; add a CHANGELOG
    entry.
- The snapshot must pass on Python 3.10–3.13 (tox matrix).
- Keep `tests/api/public_api_snapshot.json` under version control.

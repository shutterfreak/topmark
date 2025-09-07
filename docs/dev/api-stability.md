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

Use the snippet below to refresh `tests/api/public_api_snapshot.json` when you *intentionally*
change the public API (and bump the version):

```bash
python - <<'PY'
from topmark import api
from topmark.registry import Registry
import inspect, json, enum, pathlib

def _sig(obj):
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "<?>"

def _normalize(obj):
    if isinstance(obj, type) and issubclass(obj, enum.Enum):
        return "<enum>"
    if inspect.isclass(obj):
        return "<class>"
    return _sig(obj)

exported = {name: _normalize(getattr(api, name)) for name in sorted(api.__all__)}
exported["Registry.filetypes"]   = _sig(Registry.filetypes)
exported["Registry.processors"]  = _sig(Registry.processors)
exported["Registry.bindings"]    = _sig(Registry.bindings)

path = pathlib.Path("tests/api/public_api_snapshot.json")
path.write_text(json.dumps(exported, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Wrote {path}")
PY
```

## Policy

- If the snapshot test fails, either:
  - You unintentionally changed the public API → revert or adjust the change; or
  - You intentionally changed it → update the snapshot **and** bump the version; add a CHANGELOG
    entry.
- The snapshot must pass on Python 3.10–3.13 (tox matrix).
- Keep `tests/api/public_api_snapshot.json` under version control.

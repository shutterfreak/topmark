# topmark:header:start
#
#   file         : test_public_api_snapshot.py
#   file_relpath : tests/api/test_public_api_snapshot.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

r"""Optional public API snapshot test.

This test enforces that public function/Facade signatures do not change
without updating a committed baseline *and* bumping the version.

It intentionally **skips** if the baseline file is missing, so day-to-day
dev doesn’t fail. Before a release, generate and commit the baseline.

How to generate the baseline:
    >>> python - <<'PY'
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
    exported["Registry.filetypes"] = _sig(Registry.filetypes)
    exported["Registry.processors"] = _sig(Registry.processors)
    exported["Registry.bindings"] = _sig(Registry.bindings)

    path = pathlib.Path("tests/api/public_api_snapshot.json")
    path.write_text(json.dumps(exported, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
    PY
    # Save output to tests/api/public_api_snapshot.json and commit it.
"""

from __future__ import annotations

import enum
import inspect
import json
import os
from typing import Any, Callable

import pytest

from topmark import api
from topmark.registry import Registry

BASELINE_PATH = os.path.join("tests", "api", "public_api_snapshot.json")


def _sig(obj: Callable[..., Any] | type) -> str:
    """Return a stable signature string for callables.

    We intentionally *don’t* include constructor signatures of classes in the
    snapshot because those vary across Python versions (e.g., ``Enum`` gained
    parameters between 3.10 and 3.11). For classes, we return a stable token.
    """
    # Treat classes (including Enums) as opaque for snapshot purposes.
    if inspect.isclass(obj):
        try:
            if issubclass(obj, enum.Enum):
                return "<enum>"
        except Exception:
            # obj may not be a proper class or issubclass may fail; fall back
            pass
        return "<class>"

    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "<?>"


def _collect() -> dict[str, str]:
    exported: dict[str, str] = {name: _sig(getattr(api, name)) for name in sorted(api.__all__)}
    exported["Registry.filetypes"] = _sig(Registry.filetypes)
    exported["Registry.processors"] = _sig(Registry.processors)
    exported["Registry.bindings"] = _sig(Registry.bindings)
    return exported


@pytest.mark.skipif(
    not os.path.exists(BASELINE_PATH), reason="Baseline missing; generate before release"
)
def test_public_api_snapshot_matches_baseline() -> None:
    """Current public API signatures match the committed baseline JSON."""
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    assert _collect() == baseline, "Public API changed. Update baseline and bump version."

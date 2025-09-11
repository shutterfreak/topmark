# topmark:header:start
#
#   file         : api_snapshot.py
#   file_relpath : tools/api_snapshot.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end
"""Utilities to snapshot TopMark's public API.

Captures callable signatures for symbols exposed by ``topmark.api`` and the
facade methods on ``Registry``. Used by the public API snapshot test and
the Makefile targets.
"""

from __future__ import annotations

import enum
import inspect
import json
import os
import typing

from topmark import api
from topmark.registry import Registry


def _sig(obj: typing.Any) -> str:
    """Return a stable textual signature for a callable-like object.

    Args:
        obj (typing.Any): Object that may be a callable or class.

    Returns:
        str: A compact string representing the call signature, or ``"<?>"`` if
            the signature cannot be determined.
    """
    # Normalize typing.Any consistently across Python versions (3.10 differs)
    # In 3.10, Any is not a class and inspect.signature(Any) yields '(*args, **kwds)'.
    # We map it to '<class>' to keep a stable cross-version snapshot that matches newer Pythons.
    if obj is typing.Any:
        return "<class>"

    try:
        if inspect.isclass(obj):
            # Use __init__ signature for classes
            sig: inspect.Signature = inspect.signature(obj.__init__)
        else:
            sig = inspect.signature(obj)
        return str(sig)
    except (ValueError, TypeError):
        return "<?>"


def _normalize(obj: typing.Any) -> str:
    """Normalize objects for snapshotting.

    Classes (including ``Enum`` subclasses) are treated as opaque to avoid
    Python-version-specific constructor diffs.

    Args:
        obj (typing.Any): Object to normalize.

    Returns:
        str: ``"<enum>"`` for ``Enum`` subclasses, ``"<class>"`` for other classes,
            otherwise the object's call signature string.
    """
    # Prefer isinstance(obj, type) instead of inspect.isclass to satisfy type checkers
    if isinstance(obj, type) and issubclass(obj, enum.Enum):
        return "<enum>"
    if isinstance(obj, type):
        return "<class>"
    return _sig(obj)


def collect_snapshot() -> dict[str, str]:
    """Collect the current public API snapshot data.

    Returns:
        dict[str, str]: A mapping (as a plain ``dict``) from exported symbol name
        to a normalized signature token. Only symbols explicitly exported by ``topmark.api``
        (via ``__all__``) are included, plus a curated subset of facade methods
        on ``Registry`` to keep the snapshot narrowly focused and stable.
    """
    snapshot: dict[str, str] = {}

    # Snapshot only symbols explicitly exported by topmark.api
    api_exports = getattr(api, "__all__", None)
    if api_exports is None:
        # Fallback: public-looking names (best-effort), but prefer __all__ when present
        api_exports = tuple(n for n in dir(api) if not n.startswith("_"))
    for name in sorted(api_exports):
        obj = getattr(api, name)
        snapshot[name] = _normalize(obj)

    # Snapshot a curated set of Registry facades (match historical baseline)
    for name in ("filetypes", "processors", "bindings"):
        obj = getattr(Registry, name)
        snapshot[f"Registry.{name}"] = _sig(obj)

    return snapshot


def write_snapshot(path: str) -> None:
    """Write the public API snapshot JSON to ``path``.

    Args:
        path (str): Destination file path for the JSON snapshot.
    """
    snapshot: typing.Mapping[str, str] = collect_snapshot()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate TopMark public API snapshot JSON",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="tests/api/public_api_snapshot.json",
        help="Output path for the snapshot JSON (default: tests/api/public_api_snapshot.json)",
    )
    args = parser.parse_args()
    write_snapshot(args.path)

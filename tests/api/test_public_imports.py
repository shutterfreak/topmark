# topmark:header:start
#
#   project      : TopMark
#   file         : test_public_imports.py
#   file_relpath : tests/api/test_public_imports.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Smoke tests for public imports and __all__ (Google-style)."""

from __future__ import annotations

import inspect
import types


def test_api_all_contains_expected_symbols() -> None:
    """__all__ exposes the expected stable symbols (at least this subset)."""
    from topmark import api

    # At minimum these should be present; the full list is allowed to grow.

    expected_methods: set[str] = {
        "check",
        "probe",
        "strip",
        "list_filetypes",
        "list_processors",
        "get_version_info",
        "get_version_text",
    }
    expected_types: set[str] = {
        "ProbeCandidateInfo",
        "ProbeFileResult",
        "ProbeRunResult",
        "FileResult",
        "RunResult",
    }
    exported: set[str] = set(api.__all__)
    missing: set[str] = (expected_methods | expected_types) - exported
    assert not missing, f"Missing from api.__all__: {sorted(missing)}; have: {sorted(exported)}"


def test_api_symbols_are_callable_types_or_type_aliases() -> None:
    """Every exported symbol is callable, a type/class, or a runtime type alias value."""
    from topmark import api

    # Ensure __all__ exists and is an iterable of strings
    assert hasattr(api, "__all__")
    assert all(isinstance(n, str) for n in api.__all__)

    for name in api.__all__:
        obj = getattr(api, name)
        # Functions are callable, DTOs are classes, and exported PEP 604 union
        # aliases are runtime types.UnionType values.
        assert callable(obj) or inspect.isclass(obj) or isinstance(obj, types.UnionType)

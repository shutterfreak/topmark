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


def test_api_all_contains_expected_symbols() -> None:
    """__all__ exposes the expected stable symbols (at least this subset)."""
    from topmark import api

    # At minimum these should be present; the full list is allowed to grow.

    expected_methods: set[str] = {
        "check",
        "strip",
        "list_filetypes",
        "list_processors",
        "get_version_info",
        "get_version_text",
    }
    exported: set[str] = set(api.__all__)
    missing: set[str] = expected_methods - exported
    assert not missing, f"Missing from api.__all__: {sorted(missing)}; have: {sorted(exported)}"


def test_api_symbols_are_callable_or_types() -> None:
    """Every exported symbol is either callable or a type/class."""
    from topmark import api

    # Ensure __all__ exists and is an iterable of strings
    assert hasattr(api, "__all__")
    assert all(isinstance(n, str) for n in api.__all__)

    for name in api.__all__:
        obj = getattr(api, name)
        # functions are callable; types may not be
        assert callable(obj) or inspect.isclass(obj)

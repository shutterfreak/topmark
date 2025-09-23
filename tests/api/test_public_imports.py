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

    expected: set[str] = {"check", "strip", "get_filetype_info", "get_processor_info", "version"}
    exported: set[str] = set(api.__all__)
    missing: set[str] = expected - exported
    assert not missing, f"Missing from api.__all__: {sorted(missing)}; have: {sorted(exported)}"


def test_public_imports() -> None:  # noqa: F811
    """Public modules import cleanly without raising."""
    from topmark import api  # noqa: F401
    from topmark.registry import Registry  # noqa: F401

    # Mark as used so static analyzers don't complain:
    assert api is not None
    assert Registry is not None


def test_api_symbols_are_callable_or_types() -> None:
    """Every exported symbol is either callable or a type/class."""
    from topmark import api

    for name in api.__all__:
        obj = getattr(api, name)
        # functions are callable; types may not be
        assert callable(obj) or inspect.isclass(obj)

# topmark:header:start
#
#   project      : TopMark
#   file         : introspection.py
#   file_relpath : src/topmark/utils/introspection.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Markdown utilities for TopMark."""

from __future__ import annotations

from inspect import getmodule
from typing import Any

from topmark.config.logging import TopmarkLogger, get_logger

logger: TopmarkLogger = get_logger(__name__)


def format_callable_pretty(obj: Any) -> str:
    """Return a human-friendly (module.qualname) for any callable.

    Handles functions, bound methods, callable instances, and partials. Falls
    back to the callable's class name when needed, and uses ``inspect.getmodule``
    as a last resort to resolve the module name.

    Args:
        obj: The callable object to describe.

    Returns:
        A string like ``"(package.module.QualifiedName)"`` or ``"(QualifiedName)"``
        if the module cannot be resolved.
    """
    mod_name: str | None = getattr(obj, "__module__", None)
    call_name: str | None = getattr(obj, "__qualname__", None)

    if call_name is None:
        call_name = getattr(obj, "__name__", None)
    if call_name is None:
        call_name = type(obj).__name__

    if not mod_name:
        mod = getmodule(obj)
        if mod is not None and getattr(mod, "__name__", None):
            mod_name = mod.__name__

    return f"({mod_name}.{call_name})" if mod_name else f"({call_name})"

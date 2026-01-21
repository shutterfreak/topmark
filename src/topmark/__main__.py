# topmark:header:start
#
#   project      : TopMark
#   file         : __main__.py
#   file_relpath : src/topmark/__main__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Module entry point for running TopMark via ``python -m topmark``.

This module allows invoking the TopMark CLI using the Python module execution
mechanism, equivalent to running the ``topmark`` console script.

It delegates directly to :func:`topmark.cli.main.cli`, ensuring a single,
authoritative CLI entry point regardless of how TopMark is launched.

Examples:
    Run TopMark using the module interface::

        python -m topmark check .
"""

from __future__ import annotations

from topmark.cli.main import cli

if __name__ == "__main__":
    # We call the Click group directly
    cli()

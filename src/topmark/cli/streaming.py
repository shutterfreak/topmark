# topmark:header:start
#
#   project      : TopMark
#   file         : streaming.py
#   file_relpath : src/topmark/cli/streaming.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI stream-emission helpers.

This module contains small command-layer helpers for payload streams whose
ownership must remain explicit. It intentionally sits above the low-level
console abstraction: helpers here describe CLI output intent, while
`topmark.cli.console` describes concrete console behavior.
"""

from __future__ import annotations

import click


def emit_stdout_payload(payload: str, *, nl: bool = True) -> None:
    """Emit a command payload that intentionally owns STDOUT.

    Use this for payload text that must be written to STDOUT independently of
    the human report console, such as unified diff output. Do not use it for
    diagnostics, warnings, status messages, or machine-output emitters that
    already receive an explicit console.

    Args:
        payload: Payload text to emit. Empty strings are ignored.
        nl: Whether Click should append a trailing newline.
    """
    if payload:
        click.echo(payload, nl=nl)

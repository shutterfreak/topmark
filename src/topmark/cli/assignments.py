# topmark:header:start
#
#   project      : TopMark
#   file         : assignments.py
#   file_relpath : src/topmark/cli/assignments.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared token-order handling for CLI file-type rules."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
import rich_click

from topmark.cli.keys import CliOpt
from topmark.cli.state import bootstrap_cli_state
from topmark.config.assignments import parse_file_type_rules
from topmark.config.resolution.synthetic import CLI_ASSIGNMENT_SOURCE
from topmark.diagnostic.model import MutableDiagnosticLog

if TYPE_CHECKING:
    from topmark.cli.state import TopmarkCliState
    from topmark.config.assignments import FileTypeRule


def parse_assignment_value(
    value: str,
) -> dict[str, object]:
    """Split exactly one type from a verbatim pattern suffix.

    Use only the first assignment delimiter and leave the complete remaining
    pattern untouched for shared configuration validation.

    Args:
        value: One TYPE=GLOB option value.

    Returns:
        Structured assignment for shared configuration validation.

    Raises:
        ValueError: If either side or the delimiter is absent.
    """
    target, delimiter, pattern = value.partition("=")
    if not delimiter or not target or not pattern:
        raise ValueError("Expected TYPE=GLOB with a nonempty type and pattern")
    return {
        "file_type": target,
        "patterns": [pattern],
    }


class AssignmentCommand(
    rich_click.RichCommand,
):
    """Retain interleaving before Click groups repeated option values."""

    def parse_args(
        self,
        ctx: click.Context,
        args: list[str],
    ) -> list[str]:
        """Parse Click arguments and retain one ordered sequence of rule tokens.

        Capture actual option occurrences before Click groups repeated values.
        Respect other option values and the end-of-options delimiter, then use
        the shared configuration validator for both rule variants.

        Args:
            ctx: Invocation context.
            args: Original argument tokens.

        Returns:
            Unconsumed positional arguments from Click.

        Raises:
            click.BadParameter: If a rule is malformed or references an invalid type.
        """
        raw: list[dict[str, object]] = []
        options: dict[str, click.Option] = {
            name: p
            for p in self.get_params(ctx)
            if isinstance(p, click.Option)
            for name in (*p.opts, *p.secondary_opts)
        }
        index = 0
        while index < len(args):
            argument: str = args[index]
            if argument == "--":
                break
            name, separator, value = argument.partition("=")
            option: click.Option | None = options.get(name)
            if option is None and argument.startswith("-") and not argument.startswith("--"):
                for offset, char in enumerate(argument[1:], start=1):
                    short_option: click.Option | None = options.get("-" + char)
                    if short_option is None:
                        break  # Click reports unknown flags.
                    if not short_option.is_flag and not short_option.count:
                        if offset == len(argument) - 1:
                            index += short_option.nargs
                        break
            if option is not None and not option.is_flag and not option.count:
                if not separator:
                    if index + option.nargs >= len(args):
                        break  # Click provides its normal missing-value diagnostic.
                    value = args[index + 1]
                    index += option.nargs
                if name in (CliOpt.ASSIGN_FILETYPE, CliOpt.INFER_FILETYPE):
                    try:
                        raw.append(
                            parse_assignment_value(value)
                            if name == CliOpt.ASSIGN_FILETYPE
                            else {"action": "infer", "patterns": [value]}
                        )
                    except ValueError as exc:
                        raise click.BadParameter(str(exc), param_hint=name) from exc
            index += 1
        result: list[str] = super().parse_args(ctx, args)
        diagnostics = MutableDiagnosticLog()
        rules: list[FileTypeRule] = parse_file_type_rules(
            raw,
            base=Path.cwd().resolve(),
            source=CLI_ASSIGNMENT_SOURCE,
            scope=None,
            diagnostics=diagnostics,
        )
        if diagnostics.stats().n_error:
            raise click.BadParameter(
                "; ".join(d.message for d in diagnostics.freeze()),
                param_hint="--assign-filetype/--infer-filetype",
            )
        state: TopmarkCliState = bootstrap_cli_state(ctx)
        state.file_type_rules = tuple(rules)
        state.file_type_rule_diagnostics = diagnostics.freeze()
        return result


def cli_file_type_rules(
    ctx: click.Context,
) -> list[FileTypeRule]:
    """Return the validated invocation rule sequence.

    Read the invocation-local values captured during argument parsing without
    consulting project configuration or mutating registry state.

    Args:
        ctx: Invocation context holding parsed rule values.

    Returns:
        Ordered CLI rules.
    """
    return list(bootstrap_cli_state(ctx).file_type_rules)

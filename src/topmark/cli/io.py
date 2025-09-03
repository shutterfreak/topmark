# topmark:header:start
#
#   file         : io.py
#   file_relpath : src/topmark/cli/io.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""STDIN handling utilities for Click commands.

This module intentionally focuses only on normalizing STDIN usage for the CLI:
- List mode: consume newline-delimited paths from STDIN.
- Content mode: materialize STDIN bytes as a temporary file path.

Higher-level concerns like config building or file discovery are handled elsewhere.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal, NamedTuple

if TYPE_CHECKING:
    import click

from topmark.cli.errors import TopmarkUsageError
from topmark.cli.options import (
    extract_stdin_for_from_options,
    split_nonempty_lines,
    strip_dash_sentinels,
)

# Keep this module narrowly scoped to STDIN handling only.


class StdinMode(str, Enum):
    """How STDIN was interpreted by consume_stdin()."""

    NONE = "none"  # No STDIN was consumed (TTY or empty)
    LIST = "list"  # STDIN contained a list of paths (one per line)
    CONTENT = "content"  # STDIN contained file content (written to a temp file)


class StdinResult(NamedTuple):
    """Result of consuming STDIN for CLI commands that support it.

    Attributes:
        mode: How STDIN was interpreted:
              - "none": no STDIN was consumed (stdin is a TTY or empty)
              - "list": STDIN contained a list of paths (one per line)
              - "content": STDIN contained file content (written to a temp file)
        paths: In "list" mode, the parsed paths. In "content", a single temp path.
        temp_path: The temp file created for "content" mode; otherwise None.
        errors: Non-fatal errors/warnings (strings) collected during processing.
    """

    mode: StdinMode
    paths: list[Path]
    temp_path: Path | None
    errors: list[str]


def consume_stdin(
    *,
    expect: Literal["auto", "list", "content"] = "auto",
    stdin_filename: str | None = None,
    encoding: str = "utf-8",
) -> StdinResult:
    """Consume STDIN if present and return a normalized result.

    If `stdin_filename` is provided (or `expect="content"`), STDIN is treated
    as the contents of a single file which is written to a temporary path.
    The returned `paths` will contain exactly that temp path and `mode == "content"`.

    Otherwise (default), STDIN is treated as a list of paths, one per line.
    Empty lines and lines starting with '#' are ignored. `mode == "list"`.

    If STDIN is a TTY or empty, returns `mode == "none"`.

    Args:
        expect: Force interpretation of STDIN ("list" or "content"), or "auto".
        stdin_filename: Target filename to use when interpreting STDIN as file
                        content. If omitted in content mode, a default name is used.
        encoding: Text encoding for reading and writing.

    Returns:
        StdinResult struct describing what (if anything) was consumed.
    """
    # If no data is piped, do nothing.
    if not sys.stdin or sys.stdin.isatty():
        return StdinResult(mode=StdinMode.NONE, paths=[], temp_path=None, errors=[])

    data = sys.stdin.read()
    if data == "":
        return StdinResult(mode=StdinMode.NONE, paths=[], temp_path=None, errors=[])

    # Decide interpretation
    force_content = expect == "content" or stdin_filename is not None
    if force_content:
        # Treat as a single file's content written to a temp file.
        # We use NamedTemporaryFile(delete=False) to hand back a stable path.
        # We do not delete it here; caller cleans up if needed.
        try:
            # Create temp file with a sensible suffix/name if provided
            suffix = ""
            if stdin_filename and "." in stdin_filename:
                suffix = "." + stdin_filename.rsplit(".", 1)[-1]

            tmp = tempfile.NamedTemporaryFile(prefix="topmark-stdin-", suffix=suffix, delete=False)
            temp_path = Path(tmp.name)
            with tmp:
                tmp.write(data.encode(encoding))
            return StdinResult(
                mode=StdinMode.CONTENT, paths=[temp_path], temp_path=temp_path, errors=[]
            )
        except OSError as exc:
            return StdinResult(
                mode=StdinMode.NONE,
                paths=[],
                temp_path=None,
                errors=[f"#ERROR: failed to create temp file for STDIN content: {exc}"],
            )

    # Default/forced list mode: parse as list of paths (one per line)
    lines = [ln.strip() for ln in data.splitlines()]
    paths = [Path(ln) for ln in lines if ln and not ln.startswith("#")]
    return StdinResult(mode=StdinMode.LIST, paths=paths, temp_path=None, errors=[])


def merge_cli_paths_with_stdin(
    cli_paths: Iterable[str],
    stdin_result: StdinResult,
) -> list[Path]:
    """Merge CLI-provided paths with STDIN, with predictable semantics.

    Rules:
      - mode == "none": just return CLI paths.
      - mode == "list": return CLI paths + list from STDIN (in that order).
      - mode == "content": ignore CLI paths and return the single temp file path.

    This keeps command bodies small and avoids subtle drift across subcommands.

    Note: Do not use this to feed data for --files-from -, --include-from -, or --exclude-from -;
    those options expect the STDIN lines to be routed into their respective option lists
    instead of positional PATHS.
    """
    cli = [Path(p) for p in cli_paths]

    if stdin_result.mode == "none":
        return cli

    if stdin_result.mode == "list":
        return [*cli, *stdin_result.paths]

    # "content" mode
    return list(stdin_result.paths)


@dataclass(frozen=True)
class InputPlan:
    """Normalized inputs for building a Config and file list.

    Attributes:
        stdin_mode: True when reading a single file’s *content* from STDIN via "-".
        temp_path: Temporary file path used in content-on-STDIN mode; None otherwise.
        paths: Positional PATH arguments after normalization (and/or from --files-from -).
        include_patterns: Include glob patterns after merging CLI and include-from.
        exclude_patterns: Exclude glob patterns after merging CLI and exclude-from.
        files_from: File paths to read additional candidate paths from (no '-' sentinels).
        include_from: File paths to read include patterns from (no '-' sentinels).
        exclude_from: File paths to read exclude patterns from (no '-' sentinels).
    """

    stdin_mode: bool  # True if reading a single file’s content from STDIN ("-")
    temp_path: Path | None  # Temp file path for STDIN content mode, or None
    paths: list[str]  # Positional PATH arguments (normalized)
    include_patterns: list[str]  # Include glob patterns (after merging CLI/include-from)
    exclude_patterns: list[str]  # Exclude glob patterns (after merging CLI/exclude-from)
    files_from: list[str]  # Files to read candidate paths from (no '-' sentinels)
    include_from: list[str]  # Files to read include patterns from (no '-' sentinels)
    exclude_from: list[str]  # Files to read exclude patterns from (no '-' sentinels)


def plan_cli_inputs(
    *,
    ctx: click.Context,
    files_from: Iterable[str],
    include_from: Iterable[str],
    exclude_from: Iterable[str],
    include_patterns: Iterable[str],
    exclude_patterns: Iterable[str],
    stdin_filename: str | None,
    allow_empty_paths: bool = False,
) -> InputPlan:
    """Normalize CLI args and STDIN into a plan, with strict guards.

    Args:
        ctx: Click context.
        files_from: Iterable of files to read candidate paths from (may include '-').
        include_from: Iterable of files to read include patterns from (may include '-').
        exclude_from: Iterable of files to read exclude patterns from (may include '-').
        include_patterns: Iterable of include glob patterns.
        exclude_patterns: Iterable of exclude glob patterns.
        stdin_filename: Optional assumed filename when reading content from STDIN.
        allow_empty_paths: If True, do not raise an error if no paths are provided.
            (Used for commands like dump-config that are file-agnostic.)

    Raises:
        TopmarkUsageError: If mixing content '-' with any ...-from '-' option.
        TopmarkUsageError: If using '-' as a PATH without --stdin-filename.
        TopmarkUsageError: If no input is provided (unless allow_empty_paths is True).

    Returns:
        InputPlan: The normalized input plan for config and file discovery.
    """
    raw_args = list(ctx.args)

    # detect content mode
    stdin_mode = raw_args == ["-"]

    # route list-on-STDIN to one of the ...-from options
    files_from_text, include_from_text, exclude_from_text = extract_stdin_for_from_options(
        files_from, include_from, exclude_from
    )

    # forbid mixing content mode with ...-from - usage
    if stdin_mode and any(
        t is not None for t in (files_from_text, include_from_text, exclude_from_text)
    ):
        raise TopmarkUsageError(
            "Cannot combine '-' (content on STDIN) with "
            "--files-from - / --include-from - / --exclude-from -."
        )

    paths: list[str] = []
    inc = list(include_patterns)
    exc = list(exclude_patterns)
    temp_path: Path | None = None

    if stdin_mode:
        if not stdin_filename:
            raise TopmarkUsageError(
                "--stdin-filename is required when using '-' to read from STDIN."
            )
        res = consume_stdin(expect="content", stdin_filename=stdin_filename)
        if res.mode != "content" or not res.paths:
            raise TopmarkUsageError("No data received on STDIN while '-' was specified.")
        temp_path = res.paths[0]
        paths = [str(temp_path)]
        files_from, include_from, exclude_from = strip_dash_sentinels(
            files_from, include_from, exclude_from
        )
    else:
        # ...-from routing (list mode)
        if files_from_text is not None:
            paths.extend(split_nonempty_lines(files_from_text))

        if raw_args:
            if "-" in raw_args:
                raise TopmarkUsageError(
                    "'-' is only valid as the sole PATH to read content from STDIN. "
                    "Use --files-from - to read a list of paths from STDIN."
                )
            paths.extend(raw_args)

        if include_from_text is not None:
            inc += split_nonempty_lines(include_from_text)
        if exclude_from_text is not None:
            exc += split_nonempty_lines(exclude_from_text)

        files_from, include_from, exclude_from = strip_dash_sentinels(
            files_from, include_from, exclude_from
        )

    if not paths and not allow_empty_paths:
        raise TopmarkUsageError(
            f"Error: No arguments provided. Try 'topmark {ctx.command.name} FILE'"
        )

    return InputPlan(
        stdin_mode=stdin_mode,
        temp_path=temp_path,
        paths=paths,
        include_patterns=inc,
        exclude_patterns=exc,
        files_from=list(files_from),
        include_from=list(include_from),
        exclude_from=list(exclude_from),
    )

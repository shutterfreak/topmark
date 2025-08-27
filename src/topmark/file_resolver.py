# topmark:header:start
#
#   file         : file_resolver.py
#   file_relpath : src/topmark/file_resolver.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""
Resolve input files for TopMark based on config, paths, and filters.

This module expands positional arguments and stdin‑provided paths, applies
include/exclude patterns (including patterns loaded from files), and filters
by registered file types. Globs are expanded relative to the current working
directory. The result is a deterministic, sorted list of files to process.
"""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from .config import Config
from .config.logging import get_logger
from .filetypes.base import FileType
from .filetypes.instances import get_file_type_registry

logger = get_logger(__name__)


def load_patterns_from_file(file_path: str | Path) -> list[str]:
    """Load non‑empty, non‑comment patterns from a text file.

    Lines that are empty or start with ``#`` are ignored. Whitespace is trimmed
    from each non‑ignored line. If the file cannot be read, an empty list is returned.

    Args:
      file_path (str | Path): Path to the file containing one pattern per line.

    Returns:
        A list of patterns as strings.
    """
    try:
        # Skip empty lines and commented-out lines
        return [
            line.strip()
            for line in Path(file_path).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except FileNotFoundError as e:
        logger.error("Cannot read patterns from '%s': %s", file_path, e)
        return []


def resolve_file_list(config: Config, *, stdin_stream: TextIO | None = None) -> list[Path]:
    """Return the list of input files derived from configuration and filters.

    The resolver:
      1. Collects base paths from positional arguments, stdin (when enabled), or
         ``config_files`` as a last resort.
      2. Expands base paths: files are added directly; directories are traversed
         recursively; globs are expanded relative to the current working directory.
      3. Applies include patterns (and patterns loaded from ``include_from`` files),
         merging their matches into the candidate set.
      4. Applies exclude patterns (and patterns from ``exclude_from`` files) using
         Git‑wildmatch semantics via :mod:`pathspec`.
      5. Optionally filters by configured file types.

    Args:
      config (Config): Configuration values influencing path collection and filters.
      stdin_stream (TextIO | None): Optional stream to read file paths from when
        ``config.stdin`` is ``True``. Defaults to :data:`sys.stdin`.

    Returns:
      list[Path]: Sorted list of files selected for processing.
    """
    logger.debug("resolve_file_list(): config: %s", config)

    positional_paths = config.files if hasattr(config, "files") else []
    stdin = config.stdin if hasattr(config, "stdin") else False
    include_patterns = config.include_patterns if hasattr(config, "include_patterns") else []
    include_file = config.include_from if hasattr(config, "include_from") else None
    exclude_patterns = config.exclude_patterns if hasattr(config, "exclude_patterns") else []
    exclude_file = config.exclude_from if hasattr(config, "exclude_from") else None
    config_files = config.config_files if hasattr(config, "config_files") else []
    file_types: set[str] = config.file_types if hasattr(config, "file_types") else set()

    logger.trace(
        """\
    positional_paths: %s
    stdin: %s
    include_patterns: %s
    include_file: %s
    exclude_patterns: %s
    exclude_file: %s
    config_files: %s
    file_type_list: %s
    config: %s
""",
        positional_paths,
        stdin,
        include_patterns,
        include_file,
        exclude_patterns,
        exclude_file,
        config_files,
        file_types,
        config,
    )

    def expand_path(p: Path) -> list[Path]:
        # Glob patterns are expanded relative to CWD (Black‑style args).
        if "*" in str(p):
            return list(Path(".").rglob(str(p)))
        # If the path is a directory, recursively include all files and subdirectories
        elif p.is_dir():
            return list(p.rglob("*"))
        # If the path is a file, return it as a single-item list
        elif p.is_file():
            return [p]
        # Otherwise, return empty list (path does not exist or is unsupported)
        return []

    # Step 1: Determine base input paths
    if stdin:
        # Read paths from stdin if configured (favor a provided Click stream)
        stream = stdin_stream if stdin_stream is not None else sys.stdin
        try:
            raw = stream.read()
            lines = [] if raw is None else raw.splitlines()
            input_paths = [Path(line.strip()) for line in lines if line.strip()]
        except Exception as e:
            logger.debug(
                "stdin read failed, treating as no input: %s: %r",
                type(e).__name__,
                e,
            )
            input_paths = []
    elif positional_paths:
        # Use positional paths if provided
        input_paths = [Path(p) for p in positional_paths]
    elif config_files:
        # Use config files as input paths if no positional paths or stdin
        input_paths = [Path(p) for p in config_files]
    else:
        input_paths = []

    # Step 2: Expand base paths into a set of files (and directories initially)
    all_files: set[Path] = set()
    for path in input_paths:
        all_files.update(expand_path(path))

    # Step 3: Expand includes by adding files matching include patterns and files from include files
    combined_include_patterns = list(include_patterns or [])
    if include_file:
        for f in include_file:
            # Load patterns from include files and add them to the include list
            combined_include_patterns += load_patterns_from_file(f)

            # TODO check here if files exist?

    for pattern in combined_include_patterns:
        # Add files matching include patterns relative to current directory
        all_files.update(Path(".").rglob(pattern))

    # Step 4: Apply exclusions by building a PathSpec matcher from exclude patterns and files
    combined_exclude_patterns = list(exclude_patterns or [])
    if exclude_file:
        for f in exclude_file:
            # Load patterns from exclude files and add them to the exclude list
            combined_exclude_patterns += load_patterns_from_file(f)

            # TODO check here if files exist?

    def is_excluded_factory(patterns: list[str]) -> Callable[[Path], bool]:
        spec = PathSpec.from_lines(GitWildMatchPattern, patterns)
        return lambda path: spec.match_file(path.as_posix())

    is_excluded = is_excluded_factory(combined_exclude_patterns)

    # Keep only files (drop directories) and apply exclusions.
    filtered_files = {f for f in all_files if f.is_file() and not is_excluded(f)}

    # Step 6: Log and skip files with unknown types (commented out - consider cleanup or refactor)
    # skipped = []
    # kept = []
    # for f in filtered_files:
    #     ft = resolve_file_types(f)
    #     if ft is None:
    #         skipped.append(f)
    #     else:
    #         kept.append(f)

    # for s in skipped:
    #     logger.warning(f"Skipped (unknown type): {s}")

    # filtered_files = kept

    # Step 7: Filter files by configured file types if specified
    if file_types:
        registry = get_file_type_registry()
        # Warn about unknown file type names in config
        unknown = sorted(t for t in file_types if t not in registry)
        if unknown:
            logger.warning("Unknown file types specified: %s", ", ".join(unknown))

        # Build the set of selected FileType instances from the registry
        selected_types: list[FileType] = [registry[t] for t in file_types if t in registry]

        def _matches_selected_types(path: Path) -> bool:
            return any(ft.matches(path) for ft in selected_types)

        filtered_files = {f for f in filtered_files if _matches_selected_types(f)}
    logger.trace("Files to process: %d -- %s", len(filtered_files), sorted(filtered_files))
    return sorted(filtered_files)


def resolve_file_types(path: Path) -> list[FileType]:
    """Resolve registered file types that match a path.

    Attempts to match the path against all registered file type matchers and returns
    a list of matching FileType instances. Logs a warning if multiple matches are found.

    Args:
      path (Path): Path to test.

    Returns:
      list[FileType]: Matching file types (may be empty). Logs a warning when
      multiple types match the same path.
    """
    matches: list[FileType] = [ft for ft in get_file_type_registry().values() if ft.matches(path)]
    if len(matches) > 1:
        logger.warning(
            "Ambiguous file type match for: %s (%s)",
            path,
            ", ".join([type(ft).__name__ for ft in matches]),
        )
    return matches


def detect_newline(lines: list[str]) -> str:
    """Detect the newline style used by a sequence of lines.

    Scans the provided lines in order and returns the first encountered newline
    sequence: ``CRLF`` ``LF``, or ``CR``. Falls back to
    ``LF`` when no newline can be inferred (e.g., single line without terminator).

    Args:
      lines (list[str]): Lines from a file, each potentially ending with a newline.

    Returns:
      str: The detected newline sequence (``LF``, ``CR``, or ``CRLF``).
    """
    for ln in lines:
        if ln.endswith("\r\n"):
            return "\r\n"
        if ln.endswith("\n"):
            return "\n"
        if ln.endswith("\r"):
            return "\r"
    return "\n"

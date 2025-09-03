# topmark:header:start
#
#   file         : file_resolver.py
#   file_relpath : src/topmark/file_resolver.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Resolve input files for TopMark based on config, paths, and filters.

This module expands positional arguments and stdin‑provided paths, applies
include/exclude patterns (including patterns loaded from files), and filters
by registered file types. Globs are expanded relative to the current working
directory. The result is a deterministic, sorted list of files to process.
"""

from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from topmark.config import Config
from topmark.config.logging import get_logger
from topmark.filetypes.base import FileType
from topmark.filetypes.instances import get_file_type_registry

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


def resolve_file_list(config: Config) -> list[Path]:
    """Return the list of input files to process, applying candidate expansion and filters.

    The resolver implements these semantics:
      1. **Candidate set**: Expand positional paths (files, directories recursively, and globs).
         If no positional paths are provided, fall back to `config_files`.
         Also, extend with any literal paths read from `--files-from` files
         (added before filtering).
      2. **File-only**: Only files (not directories) are kept for filtering.
      3. **Include intersection**: If any include patterns
         (from `include_patterns` or `include_from` files)
         are given, filter the candidate set to only those files matching *any* include pattern
         (intersection filter).
      4. **Exclude subtraction**: If any exclude patterns
         (from `exclude_patterns` or `exclude_from` files)
         are given, remove any files matching the exclusion patterns from the set.
      5. **File type filter**: If `file_types` is specified, further restrict to files
         matching those types.
      6. Returns a **sorted** list of Path objects for deterministic output.

    Args:
      config (Config): Configuration values influencing path collection and filters.

    Returns:
      list[Path]: Sorted list of files selected for processing.
    """
    logger.debug("resolve_file_list(): config: %s", config)

    positional_paths = config.files if hasattr(config, "files") else []
    include_patterns = config.include_patterns if hasattr(config, "include_patterns") else []
    include_file = config.include_from if hasattr(config, "include_from") else None
    exclude_patterns = config.exclude_patterns if hasattr(config, "exclude_patterns") else []
    exclude_file = config.exclude_from if hasattr(config, "exclude_from") else None
    config_files = config.config_files if hasattr(config, "config_files") else []
    file_types: set[str] = config.file_types if hasattr(config, "file_types") else set()
    files_from = config.files_from if hasattr(config, "files_from") else []

    logger.trace(
        """\
    positional_paths: %s
    include_patterns: %s
    include_file: %s
    exclude_patterns: %s
    exclude_file: %s
    config_files: %s
    file_type_list: %s
    files_from: %s
    config: %s
""",
        positional_paths,
        include_patterns,
        include_file,
        exclude_patterns,
        exclude_file,
        config_files,
        file_types,
        files_from,
        config,
    )

    def expand_path(p: Path) -> list[Path]:
        """Expand a base path into a list of files and directories.

        Handles globs, directories (recursively), and files.
        Globs are expanded relative to the current working directory.

        Args:
            p (Path): Base path to expand.

        Returns:
            list[Path]: List of expanded paths (files and directories).
        """
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

    # Step 1: Build candidate set from positional paths or config_files
    if positional_paths:
        # Use positional paths if provided
        input_paths = [Path(p) for p in positional_paths]
    elif config_files:
        # Use config files as input paths if no positional paths or stdin
        input_paths = [Path(p) for p in config_files]
    else:
        input_paths = []

    # Add paths from files-from (literal, not patterns)
    def _read_paths_from_file(fp: Path) -> list[Path]:
        try:
            text = fp.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("Cannot read file list from '%s' (not found).", fp)
            return []
        except OSError as e:
            logger.error("Cannot read file list from '%s': %s", fp, e)
            return []
        paths: list[Path] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            paths.append(Path(line))
        return paths

    # Merge paths from files-from into the candidate inputs
    for fp in files_from or []:
        input_paths.extend(_read_paths_from_file(Path(fp)))

    # Step 2: Expand base paths into a set of files (and directories initially)
    candidate_set: set[Path] = set()
    unmatched_patterns: list[str] = []
    missing_literals: list[Path] = []

    for raw in input_paths:
        p = Path(raw)
        # Expand
        expanded = expand_path(p)
        candidate_set.update(expanded)

        # Report problems *after* expansion
        if "*" in str(p):
            if not expanded:
                unmatched_patterns.append(str(p))  # glob that matched nothing
        else:
            if not p.exists():
                missing_literals.append(p)  # literal path that doesn't exist

    # Emit warnings once (keeps logs tidy)
    if unmatched_patterns:
        for up in unmatched_patterns:
            logger.warning("No matches for glob pattern: %s", up)
    if missing_literals:
        for ml in missing_literals:
            logger.warning("No such file or directory: %s", ml)

    # Only keep files (drop directories) before filtering
    candidate_set = {p for p in candidate_set if p.is_file()}

    # Step 3: Apply include intersection filter (if any include patterns)
    # Merge include_patterns + include_from patterns
    combined_include_patterns = list(include_patterns or [])
    if include_file:
        for f in include_file:
            # Load patterns from include files and add them to the include list
            combined_include_patterns += load_patterns_from_file(f)
    if combined_include_patterns:
        # Only keep files matching any include pattern (intersection)
        include_spec = PathSpec.from_lines(GitWildMatchPattern, combined_include_patterns)
        candidate_set = {p for p in candidate_set if include_spec.match_file(p.as_posix())}

    # Step 4: Apply exclude subtraction filter (if any exclude patterns)
    combined_exclude_patterns = list(exclude_patterns or [])
    if exclude_file:
        for f in exclude_file:
            # Load patterns from exclude files and add them to the exclude list
            combined_exclude_patterns += load_patterns_from_file(f)
    if combined_exclude_patterns:
        exclude_spec = PathSpec.from_lines(GitWildMatchPattern, combined_exclude_patterns)
        candidate_set = {p for p in candidate_set if not exclude_spec.match_file(p.as_posix())}

    filtered_files = candidate_set

    # Step 5: Filter files by configured file types if specified
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

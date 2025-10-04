# topmark:header:start
#
#   project      : TopMark
#   file         : file_resolver.py
#   file_relpath : src/topmark/file_resolver.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Resolve input files for TopMark based on config, paths, and filters.

This module expands positional arguments and paths read upstream from STDIN
(when provided by the CLI layer), applies include/exclude patterns, and filters
by registered file types. Globs are expanded relative to the current working
directory. The result is a deterministic, sorted list of files to process.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from topmark.config import PatternSource  # runtime use
from topmark.config.logging import TopmarkLogger, get_logger
from topmark.filetypes.base import FileType
from topmark.filetypes.instances import get_file_type_registry

if TYPE_CHECKING:
    from topmark.config import Config, PatternSource
    from topmark.filetypes.base import FileType


logger: TopmarkLogger = get_logger(__name__)


def load_patterns_from_file(source: PatternSource) -> list[str]:
    """Load non-empty, non-comment patterns from a text file.

    The pattern semantics mirror .gitignore: each pattern is later evaluated
    relative to the pattern file's own base directory (``source.base``).

    Args:
        source (PatternSource): Reference to the pattern file and its base.

    Returns:
        list[str]: A list of patterns as strings.
    """
    try:
        text: str = source.path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        logger.error("Cannot read patterns from '%s': %s", source.path, e)
        return []
    except OSError as e:
        logger.error("Cannot read patterns from '%s': %s", source.path, e)
        return []
    patterns: list[str] = []
    for line in text.splitlines():
        s: str = line.strip()
        if not s or s.startswith("#"):
            continue
        patterns.append(s)
    logger.debug("Loaded %d pattern(s) from %s (base=%s)", len(patterns), source.path, source.base)
    return patterns


def _read_paths_from_source(source: PatternSource) -> list[Path]:
    """Read newline-delimited file paths from a list file.

    Relative entries are resolved against the list file's base directory
    (``source.base``).

    Args:
        source (PatternSource): List file reference and its resolution base.

    Returns:
        list[Path]: Absolute paths read from the file (comments/blank lines ignored).
    """
    try:
        text: str = source.path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("Cannot read file list from '%s' (not found).", source.path)
        return []
    except OSError as e:
        logger.error("Cannot read file list from '%s': %s", source.path, e)
        return []
    out: list[Path] = []
    for line in text.splitlines():
        s: str = line.strip()
        if not s or s.startswith("#"):
            continue
        p = Path(s)
        if not p.is_absolute():
            p: Path = (source.base / p).resolve()
        else:
            p = p.resolve()
        out.append(p)
    logger.debug("Loaded %d path(s) from %s (base=%s)", len(out), source.path, source.base)
    return out


def _rel_for_match(path: Path, base: Path) -> str:
    """Return a POSIX-style relative path (or absolute as fallback) for PathSpec matching."""
    try:
        rel: Path = path.resolve().relative_to(base.resolve())
        return rel.as_posix()
    except Exception:
        return path.as_posix()


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

    # Normalize config collections to stable, predictable types.
    # Use getattr with defaults so SimpleNamespace-based test doubles work fine
    positional_paths: tuple[str, ...] = tuple(getattr(config, "files", ()) or ())
    include_patterns: tuple[str, ...] = tuple(getattr(config, "include_patterns", ()) or ())
    include_sources: tuple[PatternSource, ...] = tuple(getattr(config, "include_from", ()) or ())
    exclude_patterns: tuple[str, ...] = tuple(getattr(config, "exclude_patterns", ()) or ())
    exclude_sources: tuple[PatternSource, ...] = tuple(getattr(config, "exclude_from", ()) or ())
    config_files: tuple[str | Path, ...] = tuple(getattr(config, "config_files", ()) or ())
    file_types: frozenset[str] = frozenset(getattr(config, "file_types", ()) or ())
    files_from_sources: tuple[PatternSource, ...] = tuple(getattr(config, "files_from", ()) or ())
    stdin_flag: bool = bool(getattr(config, "stdin", False))
    workspace_root: Path | None = getattr(config, "relative_to", None)
    # Defensive fallback only; in normal operation resolve_config_from_click() sets this.
    if workspace_root is None:
        workspace_root = Path.cwd()

    logger.trace(
        """\
    positional_paths: %s
    include_patterns: %s
    include_sources: %s
    exclude_patterns: %s
    exclude_sources: %s
    config_files: %s
    file_type_list: %s
    files_from_sources: %s
    workspace_root: %s
    stdin_flag: %s
    config: %s
""",
        positional_paths,
        include_patterns,
        include_sources,
        exclude_patterns,
        exclude_sources,
        config_files,
        file_types,
        files_from_sources,
        workspace_root,
        stdin_flag,
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

    # Step 1: Build candidate set from positional paths, or fall back to config_files
    # when there are no positional paths and we’re not using stdin/files-from.

    if len(positional_paths) > 0:
        # Use positional paths if provided
        # NOTE: static code check incorrectly assumes code is unreachable
        input_paths: list[Path] = [Path(p) for p in positional_paths]
    elif not files_from_sources and not stdin_flag:
        # `config_files` are roots/patterns provided by configuration; expand them
        input_paths = [Path(p) for p in config_files]
    else:
        input_paths = []

    logger.debug("Initial input paths: %s", input_paths)
    # Merge paths from files-from into the candidate inputs (resolve relatives vs. source.base)
    for src in files_from_sources or []:
        input_paths.extend(_read_paths_from_source(src))
    logger.debug("Input paths before expansion: %s", input_paths)

    # Step 2: Expand base paths into a set of files (and directories initially)
    candidate_set: set[Path] = set()
    unmatched_patterns: list[str] = []
    missing_literals: list[Path] = []

    for raw in input_paths:
        p = Path(raw)
        # Expand
        expanded: list[Path] = expand_path(p)
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
    any_includes: bool = bool(include_patterns) or bool(include_sources)
    if any_includes:
        kept: set[Path] = set()
        # 3.1 workspace-root include patterns
        if include_patterns:
            # NOTE: static code analysis reports that this branch is unreachable -- CHECK!
            spec_root: PathSpec = PathSpec.from_lines(GitWildMatchPattern, list(include_patterns))
            if workspace_root is not None:
                for p in candidate_set:
                    if spec_root.match_file(_rel_for_match(p, workspace_root)):
                        kept.add(p)
            else:
                for p in candidate_set:
                    if spec_root.match_file(p.as_posix()):
                        kept.add(p)
        # 3.2 include_from sources (each with its own base)
        for src in include_sources:
            pats: list[str] = load_patterns_from_file(src)
            if not pats:
                continue
            spec_src: PathSpec = PathSpec.from_lines(GitWildMatchPattern, pats)
            for p in candidate_set:
                if spec_src.match_file(_rel_for_match(p, src.base)):
                    kept.add(p)
        candidate_set = kept

    # Step 4: Apply exclude subtraction filter (if any exclude patterns/sources)
    any_excludes: bool = bool(exclude_patterns) or bool(exclude_sources)
    if any_excludes:
        kept: set[Path] = set()
        # 4.1 workspace-root exclude patterns
        if exclude_patterns:
            # NOTE: static code analysis reports that this branch is unreachable -- CHECK!
            spec_root = PathSpec.from_lines(GitWildMatchPattern, list(exclude_patterns))
            if workspace_root is not None:
                for p in candidate_set:
                    if not spec_root.match_file(_rel_for_match(p, workspace_root)):
                        kept.add(p)
            else:
                for p in candidate_set:
                    if not spec_root.match_file(p.as_posix()):
                        kept.add(p)
        else:
            kept = set(candidate_set)
        # 4.2 exclude_from sources (each with its own base)
        for src in exclude_sources:
            pats = load_patterns_from_file(src)
            if not pats:
                continue
            spec_src = PathSpec.from_lines(GitWildMatchPattern, pats)
            kept = {p for p in kept if not spec_src.match_file(_rel_for_match(p, src.base))}
        candidate_set = kept

    filtered_files: set[Path] = candidate_set

    # Step 5: Filter files by configured file types if specified
    if file_types:
        registry: dict[str, FileType] = get_file_type_registry()
        # Warn about unknown file type names in config
        unknown: list[str] = sorted(t for t in file_types if t not in registry)
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
    r"""Detect the newline sequence used by the provided lines.

    Scans in order and returns the first encountered newline **sequence**:
    ``\"\\r\\n\"``, ``\"\\n\"``, or ``\"\\r\"``. Falls back to ``\"\\n\"`` when no
    newline can be inferred (e.g., single line without terminator).

    Args:
        lines (list[str]): Lines from a file, each potentially ending with a newline.

    Returns:
        str: One of ``\"\\r\\n\"``, ``\"\\n\"``, or ``\"\\r\"``.
    """
    for ln in lines:
        if ln.endswith("\r\n"):
            return "\r\n"
        if ln.endswith("\n"):
            return "\n"
        if ln.endswith("\r"):
            return "\r"
    return "\n"

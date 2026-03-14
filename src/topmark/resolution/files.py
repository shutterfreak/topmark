# topmark:header:start
#
#   project      : TopMark
#   file         : files.py
#   file_relpath : src/topmark/resolution/files.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Resolve the concrete filesystem inputs that TopMark should process.

This module expands configured or positional paths, applies include/exclude
pattern filters, optionally constrains the candidate set by configured file type
identifiers, and returns a deterministic list of files to process.

Conceptually, this module answers a different question from
[`topmark.resolution.filetypes`][topmark.resolution.filetypes]:

- [`topmark.resolution.files`][topmark.resolution.files] decides which files should be processed;
- [`topmark.resolution.filetypes`][topmark.resolution.filetypes] decides what each file is.

Positional globs are expanded relative to the current working directory (CWD).
Globs declared in configuration files are expanded relative to the directory of
each declaring config file. Paths loaded from `files_from` sources are resolved
against their declaring source base directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from pathspec import PathSpec

from topmark.config.types import PatternSource  # runtime use
from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.logging import TRACE_LEVEL
from topmark.core.logging import get_logger
from topmark.filetypes.model import FileType
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.config.model import Config
    from topmark.config.types import PatternSource
    from topmark.core.logging import TopmarkLogger
    from topmark.filetypes.model import FileType


logger: TopmarkLogger = get_logger(__name__)


def load_patterns_from_file(source: PatternSource) -> list[str]:
    """Load non-empty, non-comment patterns from a text file.

    The pattern semantics mirror .gitignore: each pattern is later evaluated
    relative to the pattern file's own base directory (``source.base``).

    Args:
        source: Reference to the pattern file and its base.

    Returns:
        A list of patterns as strings.
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


def _read_input_paths_from_source(source: PatternSource) -> list[Path]:
    """Read newline-delimited input paths from a list file.

    Relative entries are resolved against the list file's base directory
    (`source.base`). Blank lines and comment lines are ignored.

    Args:
        source: List-file reference and its resolution base.

    Returns:
        Absolute paths read from the file.
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
        p: Path = Path(s)
        p = (source.base / p).resolve() if not p.is_absolute() else p.resolve()
        out.append(p)
    logger.debug("Loaded %d path(s) from %s (base=%s)", len(out), source.path, source.base)
    return out


def _relative_posix_for_match(path: Path, base: Path) -> str:
    """Return a POSIX-style path suitable for PathSpec matching.

    The path is made relative to `base` when possible. If `path` does not lie under `base`, the
    absolute POSIX path is returned instead.

    Args:
        path: Path to test.
        base: Base directory against which the path is relativized.

    Returns:
        POSIX-style relative path for matching, or an absolute POSIX path as a fallback.
    """
    try:
        rel: Path = path.resolve().relative_to(base.resolve())
        return rel.as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _iter_config_base_dirs(config_files: tuple[str | Path, ...]) -> list[Path]:
    """Return parent directories of real config files only.

    Skips non-files (e.g., markers like "<CLI overrides>") and resolves to absolute paths.

    Args:
        config_files: Sequence of config source identifiers (paths or markers like
            "<CLI overrides>").

    Returns:
        Unique parent directories of real config files, resolved to absolute paths.
    """
    bases: list[Path] = []
    for config_file in config_files:
        try:
            p = Path(config_file)
        except TypeError:
            continue
        if p.exists() and p.is_file():
            base: Path = p.resolve().parent
            if base not in bases:
                bases.append(base)
    return bases


def _resolve_configured_file_types(file_type_ids: frozenset[str]) -> list[FileType]:
    """Resolve configured file type identifiers to concrete `FileType` objects.

    Unknown identifiers are ignored with a warning. Ambiguous unqualified
    identifiers are also ignored with a warning so resolution can continue.
    """
    resolved: list[FileType] = []
    for file_type_id in sorted(file_type_ids):
        try:
            file_type: FileType | None = FileTypeRegistry.resolve_filetype_id(file_type_id)
        except AmbiguousFileTypeIdentifierError as err:
            logger.warning("Ambiguous file type identifier in config (ignored): %s", err)
            continue
        if file_type is None:
            logger.warning("Unknown file type identifier in config (ignored): %s", file_type_id)
            continue
        resolved.append(file_type)
    return resolved


def _matches_any_file_type(path: Path, file_types: Sequence[FileType]) -> bool:
    """Return whether `path` matches any of the supplied file types."""
    return any(file_type.matches(path) for file_type in file_types)


def resolve_file_list(config: Config) -> list[Path]:
    """Return the concrete input files to process after expansion and filtering.

    The resolver implements these semantics:
      1. **Candidate set**: Expand positional paths (files, directories recursively, and globs).
         If no positional paths are provided, extend with any literal paths read from
         ``--files-from`` **before filtering**. If the candidate set is still empty and
         include globs are configured, expand those include globs from **both** the current
         working directory (CLI perspective) and each discovered/explicit config file’s
         directory (config perspective) to seed candidates.
      2. **File-only**: Only files (not directories) are kept for filtering.
      3. **Include intersection**: If any include patterns
         (from `include_patterns` or `include_from` files)
         are given, filter the candidate set to only those files matching *any* include pattern
         (intersection filter).
      4. **Exclude subtraction**: If any exclude patterns
         (from `exclude_patterns` or `exclude_from` files)
         are given, remove any files matching the exclusion patterns from the set.
      5. **File type filter**: If `include_file_types` or `exclude_file_types` are specified,
         further restrict to files matching those types.
      6. Returns a **sorted** list of Path objects for deterministic output.

    Args:
        config: Configuration values influencing path collection and filters.

    Returns:
        Sorted list of files selected for processing.
    """
    logger.debug("resolve_file_list(): config: %s", config)

    # Normalize config collections to stable, predictable types.
    positional_paths: tuple[str, ...] = config.files

    include_patterns: tuple[str, ...] = config.include_patterns
    exclude_patterns: tuple[str, ...] = config.exclude_patterns

    include_sources: tuple[PatternSource, ...] = config.include_from
    exclude_sources: tuple[PatternSource, ...] = config.exclude_from

    # Keep the original config-source identifiers so we can derive config-file
    # base directories for include/exclude pattern expansion.
    config_files: tuple[Path | str, ...] = config.config_files

    include_file_types: frozenset[str] = frozenset(config.include_file_types)
    exclude_file_types: frozenset[str] = frozenset(config.exclude_file_types)

    files_from_sources: tuple[PatternSource, ...] = config.files_from

    stdin_flag: bool = config.stdin_mode or False

    workspace_root: Path | None = config.relative_to
    # Defensive fallback only; in normal operation resolve_config_from_click() sets this.
    if workspace_root is None:
        workspace_root = Path.cwd()

    cwd: Path = Path.cwd()

    if logger.isEnabledFor(TRACE_LEVEL):
        logger.trace(
            """\
    positional_paths: %s
    include_patterns: %s
    include_sources: %s
    exclude_patterns: %s
    exclude_sources: %s
    config_files: %s
    include_file_type_list: %s
    exclude_file_type_list: %s
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
            include_file_types,
            exclude_file_types,
            files_from_sources,
            workspace_root,
            stdin_flag,
            config,
        )

    # -------- Precompute exclude specs to allow directory-level pruning --------

    exclude_pattern_spec: PathSpec | None = None
    exclude_pattern_bases: list[Path] = []
    exclude_source_specs: list[tuple[PathSpec, Path]] = []

    if exclude_patterns:
        # Same bases as in Step 4: CWD + config file directories
        exclude_pattern_bases = [cwd.resolve()]
        for base_dir in _iter_config_base_dirs(config_files):
            if base_dir not in exclude_pattern_bases:
                exclude_pattern_bases.append(base_dir)
        exclude_pattern_spec = PathSpec.from_lines(
            "gitignore",
            list(exclude_patterns),
        )

    if exclude_sources:
        # Precompute specs for exclude_from files to prune directories early
        for psrc in exclude_sources:
            pats: list[str] = load_patterns_from_file(psrc)
            if not pats:
                continue
            spec_src: PathSpec = PathSpec.from_lines(
                "gitignore",
                pats,
            )
            exclude_source_specs.append((spec_src, psrc.base))

    def _is_excluded_dir(path: Path) -> bool:
        """Return True if a directory should be pruned during traversal.

        This uses the same PathSpec semantics as the later exclude subtraction step,
        but is applied to directory paths so we can avoid descending into subtrees
        that would be entirely excluded anyway.
        """
        real: Path = path.resolve()

        # 1) Global exclude_patterns against CWD + config dirs
        if exclude_pattern_spec is not None:
            for base in exclude_pattern_bases:
                if exclude_pattern_spec.match_file(_relative_posix_for_match(real, base)):
                    return True

        # 2) exclude_from specs (each with its own base)
        for spec, base in exclude_source_specs:
            if spec.match_file(_relative_posix_for_match(real, base)):
                return True

        return False

    def _expand_path(p: Path) -> list[Path]:
        """Expand a base path into a list of files and directories.

        Handles globs, directories (recursively), and files.
        Globs are expanded relative to the current working directory.

        Args:
            p: Base path to expand.

        Returns:
            List of expanded paths (files and directories).
        """

        def _walk_dir(root: Path) -> list[Path]:
            """Walk a directory tree, pruning excluded subdirectories early."""
            out: list[Path] = []

            # If the root directory itself is excluded, skip its entire subtree.
            if _is_excluded_dir(root):
                logger.debug("Skipping excluded root dir during expansion: %s", root)
                return out

            for dirpath, dirnames, filenames in os.walk(root):
                dirpath_path: Path = Path(dirpath)

                # Prune excluded subdirectories in-place so os.walk never enters them.
                kept_dirnames: list[str] = []
                for name in dirnames:
                    subdir: Path = dirpath_path / name
                    if _is_excluded_dir(subdir):
                        logger.debug("Pruning excluded subdir during expansion: %s", subdir)
                        continue
                    kept_dirnames.append(name)
                dirnames[:] = kept_dirnames

                for fname in filenames:
                    out.append(dirpath_path / fname)

            return out

        # Glob patterns are expanded relative to CWD (Black-style args).
        # Keep this branch exactly as before to preserve Path.rglob semantics.
        if "*" in str(p):
            logger.debug("Processing glob pattern: %s", p)
            return list(Path().rglob(str(p)))
        # If the path is a directory, recursively include all files and subdirectories,
        # but prune directories that are already excluded by config.
        if p.is_dir():
            logger.debug("Processing dir: %s", p)
            path_list: list[Path] = _walk_dir(p)
            logger.debug(
                "Processing dir: %s - returning %d item(s)",
                p,
                len(path_list),
            )
            return path_list
        # If the path is a file, return it as a single-item list
        if p.is_file():
            return [p]
        # Otherwise, return empty list (path does not exist or is unsupported)
        return []

    # Step 1: Build candidate set from positional paths only; do not treat
    # config files as inputs. We'll optionally seed from include globs later.
    if len(positional_paths) > 0:
        # Use positional paths if provided
        # NOTE: This branch is reachable depending on CLI/config inputs;
        # some static analyzers may flag it falsely.
        input_paths: list[Path] = [Path(p) for p in positional_paths]
    else:
        input_paths = []

    logger.debug("Initial input paths: %s", input_paths)
    # Merge paths from files-from into the candidate inputs (resolve relatives vs. source.base)
    for psrc in files_from_sources or []:
        input_paths.extend(_read_input_paths_from_source(psrc))
    logger.debug("Input paths before expansion: %s", input_paths)

    # If there are no explicit inputs (positional or files-from) but include globs
    # were provided, expand them relative to the workspace root to seed candidates.
    if not input_paths and include_patterns:
        # NOTE: This branch is reachable depending on CLI/config inputs;
        # some static analyzers may flag it falsely.
        expanded_from_includes: set[Path] = set()
        # 1) Expand as if patterns came from CLI (CWD)
        for pat in include_patterns:
            for hit in cwd.glob(pat):
                if hit.is_file():
                    expanded_from_includes.add(hit.resolve())
        # 2) Expand as if patterns came from each declaring config file directory
        for base_dir in _iter_config_base_dirs(config_files):
            for pat in include_patterns:
                for hit in base_dir.glob(pat):
                    if hit.is_file():
                        expanded_from_includes.add(hit.resolve())
        if expanded_from_includes:
            input_paths.extend(sorted(expanded_from_includes))
            logger.debug(
                "Expanded include_patterns from CWD and %d config dir(s): %d match(es)",
                len(tuple(config_files)),
                len(expanded_from_includes),
            )

    # Step 2: Expand base paths into a set of files (and directories initially)
    candidate_paths: set[Path] = set()
    unmatched_patterns: list[str] = []
    missing_literals: list[Path] = []

    for raw in input_paths:
        p = Path(raw)
        # Expand
        expanded: list[Path] = _expand_path(p)
        candidate_paths.update(expanded)

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
    candidate_paths = {p for p in candidate_paths if p.is_file()}

    # Step 3: Apply include intersection filter (if any include patterns)
    # Merge include_patterns + include_from patterns
    any_includes: bool = bool(include_patterns) or bool(include_sources)
    if any_includes:
        kept: set[Path] = set()
        # 3.1 include_patterns: evaluate against CWD and each config file directory
        if include_patterns:
            # NOTE: This branch is reachable depending on CLI/config inputs;
            # some static analyzers may flag it falsely.
            spec_root: PathSpec = PathSpec.from_lines(
                "gitignore",
                list(include_patterns),
            )
            bases: list[Path] = [cwd.resolve()]
            # add parent directories of discovered/explicit config files
            for base_dir in _iter_config_base_dirs(config_files):
                if base_dir not in bases:
                    bases.append(base_dir)
            for p in candidate_paths:
                # match if it matches under ANY base
                for base in bases:
                    if spec_root.match_file(_relative_posix_for_match(p, base)):
                        kept.add(p)
                        break
        # 3.2 include_from sources (each with its own base)
        for psrc in include_sources:
            pats: list[str] = load_patterns_from_file(psrc)
            if not pats:
                continue
            spec_src: PathSpec = PathSpec.from_lines(
                "gitignore",
                pats,
            )
            for p in candidate_paths:
                if spec_src.match_file(_relative_posix_for_match(p, psrc.base)):
                    kept.add(p)
        candidate_paths = kept

    # Step 4: Apply exclude subtraction filter (if any exclude patterns/sources)
    any_excludes: bool = bool(exclude_patterns) or bool(exclude_sources)
    if any_excludes:
        kept: set[Path] = set()
        # 4.1 exclude_patterns: evaluate against CWD and each config file directory
        if exclude_patterns:
            # NOTE: This branch is reachable depending on CLI/config inputs;
            # some static analyzers may flag it falsely.
            spec_root = PathSpec.from_lines(
                "gitignore",
                list(exclude_patterns),
            )
            bases = [cwd.resolve()]
            for base_dir in _iter_config_base_dirs(config_files):
                if base_dir not in bases:
                    bases.append(base_dir)
            for p in candidate_paths:
                matched = False
                for base in bases:
                    if spec_root.match_file(_relative_posix_for_match(p, base)):
                        matched = True
                        break
                if not matched:
                    kept.add(p)
        else:
            kept = set(candidate_paths)
        # 4.2 exclude_from sources (each with its own base)
        for psrc in exclude_sources:
            pats = load_patterns_from_file(psrc)
            if not pats:
                continue
            spec_src = PathSpec.from_lines(
                "gitignore",
                pats,
            )
            kept = {
                p for p in kept if not spec_src.match_file(_relative_posix_for_match(p, psrc.base))
            }
        candidate_paths = kept

    filtered_paths: set[Path] = candidate_paths

    # Step 5: Filter files by configured file type identifiers if specified.
    #
    # Config values may contain either unqualified names ("markdown") or
    # qualified identifiers ("topmark:markdown"). Resolve them through the
    # namespace-aware file type registry before applying path-based matching.

    # 5.1: whitelisted file types
    # Invalid entries are handled and reported as Config diagnostic in MutableConfig.sanitize()
    if include_file_types:
        selected_include_types: list[FileType] = _resolve_configured_file_types(include_file_types)

        # Whitelisting:
        filtered_paths = {
            file_path
            for file_path in filtered_paths
            if _matches_any_file_type(file_path, selected_include_types)
        }

    # 5.2: blacklisted file types
    if exclude_file_types:
        selected_exclude_types: list[FileType] = _resolve_configured_file_types(exclude_file_types)

        # Blacklisting:
        filtered_paths = {
            file_path
            for file_path in filtered_paths
            if not _matches_any_file_type(file_path, selected_exclude_types)
        }

    # Step 6 (Finalize): dedupe by real path, prefer CWD-relative presentation
    out_by_real: dict[Path, Path] = {}
    for p in filtered_paths:
        real: Path = p.resolve()
        try:
            rel_to_cwd: Path = real.relative_to(cwd.resolve())
            rep: Path = rel_to_cwd
        except (OSError, ValueError):
            rep = real  # keep absolute if not within CWD
        if real not in out_by_real:
            out_by_real[real] = rep

    result: list[Path] = sorted(out_by_real.values(), key=lambda q: q.as_posix())
    logger.trace("Files to process: %d -- %s", len(result), result)
    return result

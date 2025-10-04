# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/config/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Configuration handling for the TopMark tool.

This module defines the Config dataclass, logic to parse and load TOML-based configuration files,
and utilities to safely extract and coerce typed values from tomlkit Tables.

Supports default configuration generation, CLI overrides, and fallback resolution
from topmark.toml or pyproject.toml.
"""

from __future__ import annotations

import functools
import os

# For runtime type checks, prefer collections.abc
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any, Callable

from topmark.config.io import (
    clean_toml,
    get_bool_value_or_none,
    get_list_value,
    get_string_value,
    get_string_value_or_none,
    get_table_value,
    load_defaults_dict,
    load_toml_dict,
    to_toml,
)
from topmark.config.logging import TopmarkLogger, get_logger
from topmark.rendering.formats import HeaderOutputFormat

# ArgsLike: generic mapping accepted by config loaders (works for CLI namespaces and API dicts).
ArgsLike = Mapping[str, Any]
# We use ArgsLike (Mapping[str, Any]) instead of a CLI-specific namespace to
# keep the config layer decoupled from the CLI. The implementation uses .get()
# and key lookups, so Mapping is the right structural type. This allows the
# CLI to pass its namespace and the API/tests to pass plain dicts.

logger: TopmarkLogger = get_logger(__name__)


# ------------------ Immutable runtime config ------------------


# Internal helpers for normalization
def _abs_path_from(base: Path, raw: str | PathLike[str]) -> Path:
    """Return an absolute Path for *raw* using *base* if *raw* is relative."""
    s = str(raw)
    p = Path(s)
    return (base / p).resolve() if not p.is_absolute() else p.resolve()


def _ps_from_config(raw: str, config_dir: Path) -> PatternSource:
    """Create PatternSource from a config-file-declared path using that file's directory."""
    p: Path = _abs_path_from(config_dir, raw)
    return PatternSource(path=p, base=p.parent)


def _ps_from_cli(raw: str, cwd: Path) -> PatternSource:
    """Create PatternSource from a CLI-declared path using CWD (invocation site)."""
    p: Path = _abs_path_from(cwd, raw)
    return PatternSource(path=p, base=p.parent)


def _extend_ps(
    dst: list[PatternSource],
    items: Iterable[str],
    mk: Callable[[str, Path], PatternSource],
    kind: str,
    base: Path,
) -> None:
    for raw in items or []:
        ps: PatternSource = mk(raw, base)
        dst.append(ps)
        logger.debug(
            "Normalized %s '%s' against %s -> %s (base=%s)", kind, raw, base, ps.path, ps.base
        )


@dataclass(frozen=True, slots=True)
class Config:
    """Immutable runtime configuration for TopMark.

    This snapshot is produced by `MutableConfig.freeze` after merging defaults,
    project files, extra config files, and CLI overrides. Collections are immutable
    (``tuple``/``frozenset``) to prevent accidental mutation during processing.
    Use `Config.thaw` to obtain a mutable builder for edits, and `MutableConfig.freeze`
    to return to an immutable runtime snapshot.

    Layered merging with clear precedence is provided by `MutableConfig.load_merged()`.

    Attributes:
        timestamp (str): ISO-formatted timestamp when the Config instance was created.
        verbosity_level (int | None): None = inherit, 0 = terse, 1 = verbose diagnostics.
        apply_changes (bool | None): Runtime intent: whether to actually write changes (apply)
            or preview only. None = inherit/unspecified, False = dry-run/preview, True = apply.
        config_files (tuple[Path | str, ...]): List of paths or identifiers for config sources used.
        header_fields (tuple[str, ...]): List of header fields from the [header] section.
        field_values (Mapping[str, str]): Mapping of field names to their string values
            from [fields].
        align_fields (bool | None): Whether to align fields, from [formatting].
        header_format (HeaderOutputFormat | None): Header output format
            (file type aware, plain, or json).
        relative_to_raw (str | None): Original string from config or CLI
        relative_to (Path | None): Base path for relative file references, from [files].
        stdin (bool | None): Whether to read from stdin; requires explicit True to activate.
        files (tuple[str, ...]): List of files to process.
        include_from (tuple[PatternSource, ...]): Files containing include patterns.
        exclude_from (tuple[PatternSource, ...]): Files containing exclude patterns.
        files_from (tuple[PatternSource, ...]): Paths to files that list newline-delimited candidate
            file paths to add before filtering.
        include_patterns (tuple[str, ...]): Glob patterns to include.
        exclude_patterns (tuple[str, ...]): Glob patterns to exclude.
        file_types (frozenset[str]): File extensions or types to process.
    """

    # Initialization timestamp for the config instance
    timestamp: str

    # Verbosity & runtime intent
    verbosity_level: int | None
    apply_changes: bool | None

    # Provenance
    config_files: tuple[Path | str, ...]

    # Header configuration
    header_fields: tuple[str, ...]
    field_values: Mapping[str, str]

    # Formatting options
    align_fields: bool | None
    header_format: HeaderOutputFormat | None

    # Base path resolution
    relative_to_raw: str | None
    relative_to: Path | None

    # File processing options
    stdin: bool | None
    files: tuple[str, ...]

    include_from: tuple[PatternSource, ...]
    exclude_from: tuple[PatternSource, ...]
    files_from: tuple[PatternSource, ...]

    include_patterns: tuple[str, ...]
    exclude_patterns: tuple[str, ...]

    # File types (linked to file extensions) to process (filter)
    file_types: frozenset[str]

    def to_toml_dict(self, *, include_files: bool = False) -> dict[str, Any]:
        """Convert this immutable Config into a TOML-serializable dict.

        Args:
            include_files (bool): Whether to include the `files` list in the output.
                Defaults to False to avoid spamming the output with potentially
                large file lists. Set to True for full export.

        Returns:
            dict[str, Any]: the TOML-serializable dict representing the Config

        Note:
            Export-only convenience for documentation/snapshots. Parsing and
            loading live on the **mutable** side (see `MutableConfig` and
           `topmark.config.io`).
        """
        toml_dict: dict[str, Any] = {
            "fields": dict(self.field_values),
            "header": {"fields": list(self.header_fields)},
            "formatting": {
                "align_fields": self.align_fields,
                "header_format": (
                    self.header_format.value if self.header_format is not None else None
                ),
            },
            "files": {
                "file_types": list(self.file_types),
                "files_from": [str(ps.path) for ps in self.files_from],
                "include_from": [str(ps.path) for ps in self.include_from],
                "exclude_from": [str(ps.path) for ps in self.exclude_from],
                "include_patterns": list(self.include_patterns),
                "exclude_patterns": list(self.exclude_patterns),
                "relative_to": self.relative_to_raw,
                "config_files": list(self.config_files),
            },
        }
        if include_files and self.files:
            toml_dict["files"]["files"] = list(self.files)
        return toml_dict

    def thaw(self) -> MutableConfig:
        """Return a mutable copy of this frozen config.

        Symmetry:
            Mirrors `MutableConfig.freeze`. Prefer thaw→edit→freeze rather
            than mutating a runtime `Config`.

        Returns:
            MutableConfig: A mutable builder initialized from this snapshot.
        """
        return MutableConfig(
            timestamp=self.timestamp,
            verbosity_level=self.verbosity_level,
            apply_changes=self.apply_changes,
            config_files=list(self.config_files),
            header_fields=list(self.header_fields),
            field_values=dict(self.field_values),
            align_fields=self.align_fields,
            header_format=self.header_format,
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            stdin=self.stdin,
            files=list(self.files),
            include_patterns=list(self.include_patterns),
            include_from=list(self.include_from),
            exclude_patterns=list(self.exclude_patterns),
            exclude_from=list(self.exclude_from),
            files_from=list(self.files_from),
            file_types=set(self.file_types),
        )


# ------------------ Pattern source reference ------------------
@dataclass(frozen=True)
class PatternSource:
    """Reference to a pattern or file list declared in a config source.

    This value object captures both the absolute path to the referenced file
    and the *base directory* used to interpret the file's contents when it
    contains relative patterns (e.g., a gitignore-style file).

    Attributes:
        path (Path): Absolute path to the referenced file (e.g., ".gitignore").
        base (Path): Absolute directory used as the matching base for the file's
            patterns. Typically equals ``path.parent``.
    """

    path: Path
    base: Path


# -------------------------- Mutable builder --------------------------
@dataclass
class MutableConfig:
    """Mutable configuration used during discovery and merging.

    This builder collects config from defaults, project files, extra files, and CLI
    overrides. It remains convenient to mutate (``list``/``set``), then produces
    an immutable `Config` via `freeze`. TOML I/O is delegated to
    `topmark.config.io` to keep this class focused on merge policy.

    Attributes:
        timestamp (str): ISO-formatted timestamp when the Config instance was created.
        verbosity_level (int | None): None = inherit, 0 = terse, 1 = verbose diagnostics.
        apply_changes (bool | None): Runtime intent: whether to actually write changes (apply)
            or preview only. None = inherit/unspecified, False = dry-run/preview, True = apply.
        config_files (list[Path | str]): List of paths or identifiers for config sources used.
        header_fields (list[str]): List of header fields from the [header] section.
        field_values (dict[str, str]): Mapping of field names to their string values from [fields].
        align_fields (bool | None): Whether to align fields, from [formatting].
        header_format (HeaderOutputFormat | None): Header output format
            (file type aware, plain, or json).
        relative_to_raw (str | None): Original string from config or CLI
        relative_to (Path | None): Base path for relative file references, from [files].
        stdin (bool | None): Whether to read from stdin; requires explicit True to activate.
        files (list[str]): List of files to process.
        include_from (list[PatternSource]): Files containing include patterns.
        exclude_from (list[PatternSource]): Files containing exclude patterns.
        files_from (list[PatternSource]): Paths to files that list newline-delimited
            candidate file paths to add before filtering.
        include_patterns (list[str]): Glob patterns to include.
        exclude_patterns (list[str]): Glob patterns to exclude.
        file_types (set[str]): File extensions or types to process.
    """

    # Initialization timestamp for the draft instance
    timestamp: str = datetime.now().isoformat()

    # Verbosity level ()
    verbosity_level: int | None = None

    # Runtime intent: whether to actually write changes (apply) or preview only
    apply_changes: bool | None = None

    # Provenance
    config_files: list[Path | str] = field(default_factory=lambda: [])

    # Header configuration
    header_fields: list[str] = field(default_factory=lambda: [])
    field_values: dict[str, str] = field(default_factory=lambda: {})

    # Formatting options
    align_fields: bool | None = None
    header_format: HeaderOutputFormat | None = None

    # Base path resolution
    relative_to_raw: str | None = None  # original string from config or CLI
    relative_to: Path | None = None  # resolved version (used at runtime)

    # File processing options
    stdin: bool | None = None  # Explicit True required to enable reading from stdin
    files: list[str] = field(default_factory=lambda: [])

    include_from: list[PatternSource] = field(default_factory=lambda: [])
    exclude_from: list[PatternSource] = field(default_factory=lambda: [])
    files_from: list[PatternSource] = field(default_factory=lambda: [])

    include_patterns: list[str] = field(default_factory=lambda: [])
    exclude_patterns: list[str] = field(default_factory=lambda: [])

    # File types filter
    file_types: set[str] = field(default_factory=lambda: set[str]())

    # ---------------------------- Build/freeze ----------------------------
    def freeze(self) -> Config:
        """Freeze the draft into an immutable `Config` snapshot."""
        return Config(
            timestamp=self.timestamp,
            verbosity_level=self.verbosity_level,
            apply_changes=self.apply_changes,
            config_files=tuple(self.config_files),
            header_fields=tuple(self.header_fields),
            field_values=dict(self.field_values),
            align_fields=self.align_fields,
            header_format=self.header_format,
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            stdin=self.stdin,
            files=tuple(self.files),
            include_patterns=tuple(self.include_patterns),
            include_from=tuple(self.include_from),
            exclude_patterns=tuple(self.exclude_patterns),
            exclude_from=tuple(self.exclude_from),
            files_from=tuple(self.files_from),
            file_types=frozenset(self.file_types),
        )

    # --------------------------- Loaders/parsers --------------------------
    @classmethod
    @functools.cache
    def get_default_config_toml(cls) -> str:
        """Retrieve the default configuration as a raw TOML string.

        Returns:
            str: The contents of the default TOML configuration file.
        """
        toml_data: dict[str, Any] = load_defaults_dict()
        return to_toml(toml_data)

    @classmethod
    def to_cleaned_toml(cls, toml_doc: str) -> str:
        """Return a cleaned TOML string with comments and extraneous whitespace removed.

        Args:
            toml_doc (str): The raw TOML document string.

        Returns:
            str: The cleaned TOML string.
        """
        return clean_toml(toml_doc)

    @classmethod
    def from_defaults(cls) -> MutableConfig:
        """Load the default configuration from the bundled topmark-default.toml file.

        Returns:
            MutableConfig: A `MutableConfig` instance populated with default values.
        """
        default_toml_data: dict[str, Any] = load_defaults_dict()

        # Note: `config_file` is set to None because this is a package resource,
        # not a user-specified filesystem path.
        return cls.from_toml_dict(
            default_toml_data,
            config_file=None,
            use_defaults=True,  # We ONLY include defaults when loading from defaults!
        )

    @classmethod
    def from_toml_file(cls, path: Path) -> MutableConfig | None:
        """Load configuration from a single TOML file.

        This method reads the TOML file, extracts the relevant configuration section,
        and returns a Config instance. Supports both topmark.toml and pyproject.toml files,
        extracting the [tool.topmark] section from pyproject.toml.

        Args:
            path (Path): Path to the TOML file.

        Returns:
            MutableConfig | None: The Config instance if successful;
                None if required sections are missing.
        """
        logger.debug("Creating MutableConfig from TOML config: %s", path)

        toml_data: dict[str, Any] = load_toml_dict(path)

        if path.name == "pyproject.toml":
            # Extract [tool.topmark] subsection from pyproject.toml
            tool_section: dict[str, Any] = toml_data.get("tool", {}).get("topmark", {})
            if not tool_section:
                logger.error(f"[tool.topmark] section missing or malformed in {path}")
                return None
            else:
                toml_data = tool_section

        # Parse the extracted TOML data into a MutableConfig;
        # pass the config file path so the dict parser knows the base directory
        draft: MutableConfig = cls.from_toml_dict(toml_data, config_file=path)
        draft.config_files = [path]
        logger.debug("Generated MutableConfig: %s", draft)
        return draft

    @classmethod
    def discover_local_config_files(cls, start: Path) -> list[Path]:
        """Return config files discovered by walking upward from ``start``.

        Layered discovery semantics:
          * We traverse from the anchor directory up to the filesystem root and
            collect config files in **root-most → nearest** order.
          * In a given directory, we consider **both** `pyproject.toml` (with
            `[tool.topmark]`) and `topmark.toml`. When **both** are present, we
            append **`pyproject.toml` first and `topmark.toml` second** so that a
            later merge (nearest-last-wins) gives same-directory precedence to
            `topmark.toml`.
          * If a discovered config sets ``root = true`` (top-level key in
            `topmark.toml`, or within `[tool.topmark]` for `pyproject.toml`), we
            stop traversing further up after collecting the current directory's
            files.

        Args:
            start (Path): The Path instance where discovery starts.

        Returns:
            list[Path]: Discovered config file paths ordered for stable merging
            (root-most first, nearest last; within a directory: pyproject → topmark).
        """
        candidates: list[Path] = []
        cur: Path = start.resolve()  # Resolve symlinks and get absolute path
        seen: set[Path] = set()

        # Ensure we start from a directory anchor
        if cur.is_file():
            cur = cur.parent

        # Walk up to filesystem root
        while True:
            root_stop_here = False

            # Same-directory precedence: add pyproject first, then topmark
            for name in ("pyproject.toml", "topmark.toml"):
                p: Path = cur / name
                if p.exists() and p.is_file() and p not in seen:
                    candidates.append(p)
                    seen.add(p)
                    logger.debug("Discovered config file: %s", p)
                    # Check for `root = true` to stop traversal after this dir
                    try:
                        data: dict[str, Any] = load_toml_dict(p)
                        if name == "pyproject.toml":
                            tool: dict[str, Any] = data.get("tool", {})
                            topmark_tbl: dict[str, Any] = tool.get("topmark", {})
                            if bool(topmark_tbl.get("root", False)):
                                root_stop_here = True
                        else:  # topmark.toml
                            if bool(data.get("root", False)):
                                root_stop_here = True
                    except Exception as e:
                        # Best-effort discovery; ignore parse errors here.
                        logger.debug("Ignoring parse error in %s: %s", p, e)
                        pass

            parent: Path = cur.parent
            if parent == cur:
                break
            if root_stop_here:
                # Stop after collecting current directory entries if `root=true`
                logger.debug("Stopping upward config discovery at %s due to root=true", cur)
                break
            cur = parent

        # Root-most first, nearest last → merge in this order
        return candidates

    @classmethod
    def discover_user_config_file(cls) -> Path | None:
        """Return a user-scoped config path if it exists.

        Looks under XDG config (``$XDG_CONFIG_HOME/topmark/topmark.toml``) and a legacy
        fallback (``~/.topmark.toml``). The first existing path is returned.
        """
        xdg: str | None = os.environ.get("XDG_CONFIG_HOME")
        base: Path = Path(xdg) if xdg else Path.home() / ".config"
        xdg_path: Path = base / "topmark" / "topmark.toml"
        legacy: Path = Path.home() / ".topmark.toml"
        for p in (xdg_path, legacy):
            if p.exists() and p.is_file():
                return p
        return None

    @classmethod
    def from_toml_dict(
        cls,
        data: dict[str, Any],
        config_file: Path | None = None,
        use_defaults: bool = False,
    ) -> MutableConfig:
        """Create a draft config from a parsed TOML dict.

        - Path-to-file entries declared in the config are normalized to absolute paths
          using the *config file's* directory (config-local base).
        - Glob strings are kept as-is (evaluated later against `relative_to`).

        Args:
            data (dict[str, Any]): The parsed TOML data as a dictionary.
            config_file (Path | None): Optional path to the source TOML file.
            use_defaults (bool): Whether to treat this data as default config (affects behavior).

        Returns:
            MutableConfig: The resulting MutableConfig instance.
        """
        tool_tbl: dict[str, Any] = data  # top-level tool configuration dictionary

        # Extract sub-tables for specific config sections; fallback to empty dicts
        field_tbl: dict[str, Any] = get_table_value(tool_tbl, "fields")
        logger.trace("TOML [fields]: %s", field_tbl)

        header_tbl: dict[str, Any] = get_table_value(tool_tbl, "header")
        logger.trace("TOML [header]: %s", header_tbl)

        formatting_tbl: dict[str, Any] = get_table_value(tool_tbl, "formatting")
        logger.trace("TOML [formatting]: %s", formatting_tbl)

        files_tbl: dict[str, Any] = get_table_value(tool_tbl, "files")
        logger.trace("TOML [files]: %s", files_tbl)

        # Start from a fresh draft with current timestamp
        draft: MutableConfig = cls(timestamp=datetime.now().isoformat())

        # Config file's directory for relative path resolution
        cfg_dir: Path | None = config_file.parent.resolve() if config_file else None

        # ----- config_files: normalize to absolute paths if possible -----
        config_files: tuple[list[Path]] = ([config_file] if config_file else [],)
        draft.config_files = [str(p) for p in config_files[0]] if config_files[0] else []

        # ----- files: normalize to absolute strings against the config file dir -----
        raw_files: list[str] = list(files_tbl.get("files", [])) if "files" in files_tbl else []
        if raw_files:
            if cfg_dir is not None:
                for f in raw_files:
                    absf: Path = _abs_path_from(cfg_dir, f)
                    draft.files.append(str(absf))
                    logger.debug("Normalized config files entry against %s: %s", cfg_dir, absf)
            else:
                draft.files.extend(raw_files)

        # ----- include_from / exclude_from / files_from: convert to PatternSource now -----
        def _normalize_sources(key: str) -> None:
            vals: list[str] = list(files_tbl.get(key, [])) if key in files_tbl else []
            if not vals:
                return
            if cfg_dir is not None:
                _extend_ps(getattr(draft, key), vals, _ps_from_config, f"config {key}", cfg_dir)
            else:
                # Rare fallback: without a config file path, use CWD to avoid losing info
                _extend_ps(
                    getattr(draft, key),
                    vals,
                    _ps_from_cli,
                    f"config {key}",
                    Path.cwd().resolve(),
                )

        for _k in ("include_from", "exclude_from", "files_from"):
            _normalize_sources(_k)

        # ----- glob arrays remain raw strings (evaluated later vs relative_to) -----
        draft.include_patterns.extend(list(files_tbl.get("include_patterns", [])))
        draft.exclude_patterns.extend(list(files_tbl.get("exclude_patterns", [])))

        # Coerce field values to strings, ignoring unsupported types with a warning
        field_values: dict[str, str] = {}
        for k, v in field_tbl.items():
            if isinstance(v, (str, int, float, bool)):
                field_values[k] = str(v)
            else:
                logger.warning("Ignoring unsupported field value for '%s': %r", k, v)
        draft.field_values = field_values

        # Header fields: list of strings
        header_fields: list[str] = get_list_value(header_tbl, "fields")
        draft.header_fields = header_fields or []

        # # Fallback: if no explicit header field order is provided, use the keys of
        # # the field_values table in their declared order. This preserves intuitive
        # # behavior (headers render when values are present).
        # if not header_fields and field_values:
        #     header_fields = list(field_values.keys())

        # Parse relative_to path if present, resolve to absolute path
        draft.relative_to_raw = get_string_value(files_tbl, "relative_to")
        if draft.relative_to_raw:
            p = Path(draft.relative_to_raw)
            if p.is_absolute():
                draft.relative_to = p.resolve()
            else:
                if cfg_dir is not None:
                    # Resolve relative-to against the CONFIG FILE’s directory
                    draft.relative_to = (cfg_dir / p).resolve()
                else:
                    # Defaults or synthetic dicts: don’t bind to CWD; let the resolver
                    # pick the project root later.
                    draft.relative_to = None
        else:
            draft.relative_to = None

        # align_fields = get_bool_value(formatting_cfg, "align_fields", True)
        draft.align_fields = get_bool_value_or_none(
            formatting_tbl, "align_fields"
        )  # NOTE: do not set a default value if not set

        raw_header_format: str | None = get_string_value_or_none(
            formatting_tbl, "header_format"
        )  # NOTE: do not set a default value if not set
        if raw_header_format:
            try:
                draft.header_format = HeaderOutputFormat(raw_header_format)
            except ValueError:
                valid_values: str = ", ".join(e.value for e in HeaderOutputFormat)
                logger.error(
                    "Invalid header format specifier found: %s (allowed values: %s)",
                    raw_header_format,
                    valid_values,
                )
                draft.header_format = None
        else:
            # choose your default; this keeps behavior predictable
            draft.header_format = None

        file_types: list[str] = get_list_value(files_tbl, "file_types")
        draft.file_types = set(file_types) if file_types else set()
        if file_types and len(file_types) != len(draft.file_types):
            logger.warning("Duplicate file types found in config: %s", ", ".join(file_types))

        draft.stdin = False  # Default to False unless explicitly set later -- TODO: False or None?

        return draft

    @classmethod
    def load_merged(
        cls,
        *,
        input_paths: Iterable[str | Path] | None = None,
        extra_config_files: Iterable[str | Path] | None = None,
        no_config: bool = False,
        file_types: Iterable[str] | None = None,
    ) -> MutableConfig:
        """Load a layered configuration with clear precedence.

        Precedence (lowest → highest):
            1. Built-in defaults (``topmark-default.toml``)
            2. User config (``$XDG_CONFIG_HOME/topmark/topmark.toml`` or ``~/.topmark.toml``)
            3. Project chain discovered upward from the anchor (root → current)
            4. Extra config files explicitly provided (in order)
            5. CLI/application overrides via ``apply_cli_args`` (outside this function)

        Args:
            input_paths (Iterable[str | Path] | None): Paths the caller intends to process.
                Used only to pick a discovery anchor (first path's directory) when present;
                otherwise CWD.
            extra_config_files (Iterable[str | Path] | None): Explicit config files to merge
                after discovery.
            no_config (bool): If True, skip user and project discovery.
            file_types (Iterable[str] | None): Optional filter to seed the draft for parity
                with CLI.

        Returns:
            MutableConfig: A merged draft that callers can further override then freeze.
        """
        # 1) start from defaults
        draft: MutableConfig = cls.from_defaults()

        # Optionally seed file_types for parity with CLI flags
        if file_types:
            draft.file_types = set(str(x) for x in file_types)

        if not no_config:
            # 2) user config
            user_cfg: Path | None = cls.discover_user_config_file()
            if user_cfg is not None:
                maybe: MutableConfig | None = cls.from_toml_file(user_cfg)
                if maybe is not None:
                    draft = draft.merge_with(maybe)

            # 3) project chain (root → anchor)
            if input_paths:
                try:
                    first: str | Path = next(iter(input_paths))
                    anchor: Path = Path(first).resolve()
                except StopIteration:
                    anchor = Path.cwd()
            else:
                anchor = Path.cwd()

            for cfg_path in cls.discover_local_config_files(anchor):
                maybe = cls.from_toml_file(cfg_path)
                if maybe is not None:
                    draft = draft.merge_with(maybe)

        # 4) extra config files
        if extra_config_files:
            for entry in extra_config_files:
                p: Path = entry if isinstance(entry, Path) else Path(entry)
                if p.exists() and p.is_file():
                    maybe = cls.from_toml_file(p)
                    if maybe is not None:
                        draft = draft.merge_with(maybe)

        return draft

    # ------------------------------- Merging -------------------------------
    def merge_with(self, other: MutableConfig) -> MutableConfig:
        """Return a new draft where values from ``other`` override this draft."""
        merged = MutableConfig(
            timestamp=self.timestamp,
            config_files=self.config_files + other.config_files,
            field_values=other.field_values or self.field_values,
            header_fields=other.header_fields or self.header_fields,
            align_fields=other.align_fields
            if other.align_fields is not None
            else self.align_fields,
            header_format=other.header_format
            if other.header_format is not None
            else self.header_format,
            stdin=other.stdin if other.stdin is not None else self.stdin,
            files=other.files or self.files,
            include_patterns=other.include_patterns or self.include_patterns,
            include_from=other.include_from or self.include_from,
            exclude_patterns=other.exclude_patterns or self.exclude_patterns,
            exclude_from=other.exclude_from or self.exclude_from,
            files_from=other.files_from or self.files_from,
            relative_to_raw=other.relative_to_raw
            if other.relative_to_raw is not None
            else self.relative_to_raw,
            relative_to=other.relative_to if other.relative_to is not None else self.relative_to,
            file_types=other.file_types or self.file_types,
            verbosity_level=other.verbosity_level
            if other.verbosity_level is not None
            else self.verbosity_level,
            apply_changes=other.apply_changes
            if other.apply_changes is not None
            else self.apply_changes,
        )
        return merged

    def apply_cli_args(self, args: ArgsLike) -> MutableConfig:
        """Update Config fields based on an arguments mapping (CLI or API).

        This method applies overrides from a parsed arguments mapping to the current
        MutableConfig instance. It does not handle flags that influence config file
        discovery (e.g., --no-config, --config).

        Args:
            args (ArgsLike): Parsed arguments mapping (from CLI or API).

        Returns:
            MutableConfig: The updated MutableConfig instance with CLI overrides applied.

        Note:
            CLI path-to-file options (``--include-from``, ``--exclude-from``,
            ``--files-from``) are normalized against the **current working
            directory** (invocation site). Glob arrays remain as strings and
            are later evaluated relative to ``relative_to``.
        """
        logger.debug("Applying CLI arguments to MutableConfig: %s", args)

        # Use a special marker to indicate CLI overrides in config_files list
        CLI_OVERRIDE_STR = "<CLI overrides>"

        # Append or initialize config_files list with CLI override marker
        if self.config_files:
            self.config_files.append(CLI_OVERRIDE_STR)
        else:
            self.config_files = [CLI_OVERRIDE_STR]

        # Merge CLI config_files (config paths) if provided
        if args.get("config_files"):
            self.config_files.extend(args["config_files"])

        # Override files to process if specified
        if "files" in args:
            self.files = list(args["files"]) if args["files"] else []
            # If explicit files are given, force stdin to False (files take precedence)
            if self.files:
                self.stdin = False

        # Glob arrays from CLI: keep as strings (evaluated later vs relative_to)
        if args.get("include_patterns"):
            # self.include_patterns = list(args["include_patterns"])
            self.include_patterns.extend(list(args.get("include_patterns") or []))
        if args.get("exclude_patterns"):
            # self.exclude_patterns = list(args["exclude_patterns"])
            self.exclude_patterns.extend(list(args.get("exclude_patterns") or []))

        # Override include/exclude patterns and files if specified
        cwd: Path = Path.cwd().resolve()

        # Normalize CLI path-to-file options from the invocation CWD
        if args.get("include_from"):
            # self.include_from = list(args["include_from"])
            _extend_ps(
                self.include_from,
                args.get("include_from") or [],
                _ps_from_cli,
                "CLI --include-from",
                cwd,
            )
        if args.get("exclude_from"):
            # self.exclude_from = list(args["exclude_from"])
            _extend_ps(
                self.exclude_from,
                args.get("exclude_from") or [],
                _ps_from_cli,
                "CLI --exclude-from",
                cwd,
            )
        if args.get("files_from"):
            # self.files_from = list(args["files_from"])
            _extend_ps(
                self.files_from,
                args.get("files_from") or [],
                _ps_from_cli,
                "CLI --files-from",
                cwd,
            )

        # Override relative_to path if specified, resolving to absolute path
        if args.get("relative_to"):
            self.relative_to_raw = args["relative_to"]
            self.relative_to = Path(args["relative_to"]).resolve()

        # Override file_types filter if specified
        if args.get("file_types"):
            self.file_types = set(args["file_types"])

        # Apply CLI flags that require explicit True to activate or to explicitly disable
        if "stdin" in args:
            self.stdin = bool(args["stdin"])  # honor False explicitly

        if "header_format" in args and args["header_format"] is not None:
            self.header_format = args["header_format"]
        # else:
        #     logger.warning(
        #         "No header format specified, using default (%s)", HeaderOutputFormat.DEFAULT.value
        #     )
        #     self.header_format = HeaderOutputFormat.DEFAULT

        if "align_fields" in args and args["align_fields"] is not None:
            # Only override if align_fields was passed via CLI
            self.align_fields = args["align_fields"]

        if "verbosity_level" in args and args["verbosity_level"] is not None:
            try:
                self.verbosity_level = int(args["verbosity_level"])
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid verbosity_level=%r (expected int); keeping %r",
                    args["verbosity_level"],
                    self.verbosity_level,
                )

        if "apply_changes" in args and args["apply_changes"] is not None:
            self.apply_changes = bool(args["apply_changes"])

        logger.debug("Patched MutableConfig: %s", self)
        logger.info("Applied CLI overrides to MutableConfig")
        logger.debug("apply_cli_args(): finalized stdin=%s files=%s", self.stdin, self.files)

        return self

# topmark:header:start
#
#   project      : TopMark
#   file         : model.py
#   file_relpath : src/topmark/config/model.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Configuration model and merge policy.

This module defines:
    - `Config`: an immutable, runtime snapshot used by processing steps.
    - `MutableConfig`: a mutable builder used during discovery/merge; it
      can be frozen into `Config` and thawed back for edits.

Scope:
    - *In scope*: data shapes, defaulting rules at the field level, merge policy
      (`MutableConfig.merge_with`), and freeze/thaw mechanics.
    - *Out of scope*: filesystem discovery and TOML I/O. Those belong in
      dedicated modules (e.g., ``discovery.py`` and ``loader.py``) to keep this
      model import-light and avoid cycles. The project may re-export such helpers
      from [`topmark.config`][topmark.config] for a stable public API.

Immutability:
    - `Config` stores tuples/frozensets and is ``frozen=True`` to prevent
      accidental mutation at runtime. Use `Config.thaw` → edit →
      `MutableConfig.freeze` for safe updates.

Path semantics:
    - Path-to-file options declared in config are normalized against that config
      file's directory.
    - CLI path-to-file options are normalized against the invocation CWD.
    - ``relative_to`` influences header metadata (e.g., ``file_relpath``) only,
      not glob expansion.

Testing guidance:
    - Unit-test merge behavior with synthetic builders (no I/O).
    - Exercise TOML/discovery paths in ``loader``/``discovery`` tests.
"""

from __future__ import annotations

import functools
import os

# For runtime type checks, prefer collections.abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

from topmark.cli.keys import CliOpt
from topmark.config.args_io import (
    get_arg_bool_or_none_checked,
    get_arg_enum_checked,
    get_arg_int_or_none_checked,
    get_arg_string_list_checked,
    get_arg_string_or_none_checked,
)
from topmark.config.io import (
    as_toml_table_map,
    clean_toml,
    get_bool_value_or_none_checked,
    get_string_list_value_checked,
    get_string_value_checked,
    get_string_value_or_none_checked,
    get_table_value,
    load_defaults_dict,
    load_toml_dict,
)
from topmark.config.io.loaders import render_runtime_defaults_toml_text
from topmark.config.keys import Toml
from topmark.config.logging import get_logger
from topmark.config.paths import (
    abs_path_from,
    extend_pattern_sources,
    ps_from_cli,
    ps_from_config,
)
from topmark.config.policy import (
    MutablePolicy,
    Policy,
)
from topmark.config.types import (
    ArgsLike,
    FileWriteStrategy,
    OutputTarget,
)
from topmark.constants import CLI_OVERRIDE_STR
from topmark.core.keys import ArgKey
from topmark.diagnostic.model import (
    DiagnosticLog,
    DiagnosticStats,
    FrozenDiagnosticLog,
    compute_diagnostic_stats,
)
from topmark.rendering.formats import HeaderOutputFormat

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from topmark.config.io import TomlTable, TomlTableMap
    from topmark.config.logging import TopmarkLogger
    from topmark.config.types import PatternSource
    from topmark.filetypes.base import FileType


logger: TopmarkLogger = get_logger(__name__)


# ------------------ Immutable runtime config ------------------


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
        timestamp: ISO-formatted timestamp when the Config instance was created.
        verbosity_level: None = inherit, 0 = terse, 1 = verbose diagnostics.
        apply_changes: Runtime intent: whether to actually write changes (apply)
            or preview only. None = inherit/unspecified, False = dry-run/preview, True = apply.
        output_target: Where to send output: `"file"` or `"stdout"`.
        file_write_strategy: How to write when `output_target == "file"`:
            `"atomic"` (safe default) or `"inplace"` (fast, less safe).
        policy: Global, resolved, immutable runtime policy (plain booleans),
            applied after discovery.
        policy_by_type: Per-file-type resolved policy overrides
            (plain booleans), applied after discovery.
        config_files: List of paths or identifiers for config sources used.
        strict_config_checking: If True, enforce strict config checking
            (fail on warnings and errors).
        header_fields: List of header fields from the [header] section.
        field_values: Mapping of field names to their string values
            from [fields].
        align_fields: Whether to align fields, from [formatting].
        header_format: Header output format
            (file type aware, plain, or json).
        relative_to_raw: Original string from config or CLI
        relative_to: Base path used only for header metadata (e.g., file_relpath).
            Note: Glob expansion and filtering are resolved relative to their declaring source
            (config file dir or CWD for CLI), not relative_to.
        stdin_mode: Whether to read from stdin; requires explicit True to activate.
        files: List of files to process.
        include_from: Files containing include patterns.
        exclude_from: Files containing exclude patterns.
        files_from: Paths to files that list newline-delimited candidate
            file paths to add before filtering.
        include_patterns: Glob patterns to include.
        exclude_patterns: Glob patterns to exclude.
        include_file_types: Whitelist of file type identifiers to restrict
            file discovery.
        exclude_file_types: Blacklist of file type identifiers to exclude from
            file discovery.
        diagnostics: Warnings or errors encountered while loading,
            merging or sanitizing config.

    Policy resolution:
        - Public/API overlays are applied to a mutable draft **after** discovery and before
            freezing to this immutable `Config`. Per-type policies override the global policy
            for matching file types.
        - All entries in ``policy_by_type`` are resolved against the global ``policy`` during
            ``MutableConfig.freeze``; at runtime the pipeline simply selects the appropriate
            `Policy` via
            [`topmark.config.policy.effective_policy`][topmark.config.policy.effective_policy]
            without further merging.
    """

    # Initialization timestamp for the config instance
    timestamp: str

    # Verbosity & runtime intent
    verbosity_level: int | None

    apply_changes: bool | None

    # Output target for writing (file, stdout)
    output_target: OutputTarget | None
    # File writer (atomic, in-place)
    file_write_strategy: FileWriteStrategy | None

    # Policy containers
    policy: Policy
    policy_by_type: Mapping[str, Policy]  # e.g., {"python": Policy(...)}

    # Provenance
    config_files: tuple[Path | str, ...]

    # TOML config checking
    strict_config_checking: bool

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
    stdin_mode: bool | None
    files: tuple[str, ...]

    include_from: tuple[PatternSource, ...]
    exclude_from: tuple[PatternSource, ...]
    files_from: tuple[PatternSource, ...]

    include_patterns: tuple[str, ...]
    exclude_patterns: tuple[str, ...]

    # File types (linked to file extensions) to process (filter)
    include_file_types: frozenset[str]
    exclude_file_types: frozenset[str]

    # Collected diagnostics while loading / merging / sanitizing config.
    diagnostics: FrozenDiagnosticLog

    @property
    def should_proceed(self) -> bool:
        """Return True if processing should proceed based on config diagnostics.

        Analyzes `self.diagnostics` and `compute_diagnostic_stats` to decide whether
        to proceed.

        A similar helper exists in `MutableConfig`.

        Returns:
            False if errors occurred, or if warnings detected in strict config processing mode,
            True otherwise.
        """
        stats: DiagnosticStats = compute_diagnostic_stats(self.diagnostics)
        if stats.n_error > 0:
            # Can't proceed with errors
            return False
        # Can't proceed with warnings in strict mode
        return not (self.strict_config_checking is True and stats.n_warning > 0)

    def to_toml_dict(self, *, include_files: bool = False) -> TomlTable:
        """Convert this immutable Config into a TOML-serializable dict.

        Args:
            include_files: Whether to include the `files` list in the output.
                Defaults to False to avoid spamming the output with potentially
                large file lists. Set to True for full export.

        Returns:
            The TOML-serializable dict representing the Config

        Note:
            Export-only convenience for documentation/snapshots. Parsing and
            loading live on the **mutable** side (see `MutableConfig` and
            [`topmark.config.io`][topmark.config.io]).
        """
        # Normalize writer strategy for TOML (map enum to a stable, config-friendly token)
        if self.file_write_strategy is None:
            writer_strategy: str | None = None
        else:
            # FileWriteStrategy names are things like "ATOMIC" / "INPLACE";
            # map them back to lowercase tokens used in config.
            writer_strategy = self.file_write_strategy.name.lower()

        toml_dict: TomlTable = {
            Toml.SECTION_FIELDS: dict(self.field_values),
            Toml.SECTION_HEADER: {Toml.KEY_FIELDS: list(self.header_fields)},
            Toml.SECTION_FORMATTING: {
                Toml.KEY_ALIGN_FIELDS: self.align_fields,
                Toml.KEY_HEADER_FORMAT: (
                    self.header_format.value if self.header_format is not None else None
                ),
            },
            Toml.SECTION_WRITER: {
                # self.output_target is an Enum type
                Toml.KEY_TARGET: self.output_target.value if self.output_target else None,
                Toml.KEY_STRATEGY: writer_strategy,
            },
            Toml.SECTION_FILES: {
                Toml.KEY_INCLUDE_FILE_TYPES: list(self.include_file_types),
                Toml.KEY_EXCLUDE_FILE_TYPES: list(self.exclude_file_types),
                Toml.KEY_FILES_FROM: [str(ps.path) for ps in self.files_from],
                Toml.KEY_INCLUDE_FROM: [str(ps.path) for ps in self.include_from],
                Toml.KEY_EXCLUDE_FROM: [str(ps.path) for ps in self.exclude_from],
                Toml.KEY_INCLUDE_PATTERNS: list(self.include_patterns),
                Toml.KEY_EXCLUDE_PATTERNS: list(self.exclude_patterns),
                Toml.KEY_RELATIVE_TO: self.relative_to_raw,
                Toml.KEY_CONFIG_FILES: [
                    str(p) if isinstance(p, Path) else str(p) for p in self.config_files
                ],
            },
        }

        # Policy serialization (global and per-type)
        toml_dict[Toml.SECTION_POLICY] = {
            Toml.KEY_POLICY_CHECK_ADD_ONLY: self.policy.add_only,
            Toml.KEY_POLICY_CHECK_UPDATE_ONLY: self.policy.update_only,
            Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: self.policy.allow_header_in_empty_files,
        }
        if self.policy_by_type:
            toml_dict[Toml.SECTION_POLICY_BY_TYPE] = {
                ft: {
                    Toml.KEY_POLICY_CHECK_ADD_ONLY: p.add_only,
                    Toml.KEY_POLICY_CHECK_UPDATE_ONLY: p.update_only,
                    Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: p.allow_header_in_empty_files,
                }
                for ft, p in self.policy_by_type.items()
            }

        # Include files in TOML export
        if include_files and self.files:
            toml_dict[Toml.SECTION_FILES][Toml.KEY_FILES] = list(self.files)

        return toml_dict

    def thaw(self) -> MutableConfig:
        """Return a mutable copy of this frozen config.

        Symmetry:
            Mirrors `MutableConfig.freeze`. Prefer thaw→edit→freeze rather
            than mutating a runtime `Config`.

        Returns:
            A mutable builder initialized from this snapshot.
        """
        return MutableConfig(
            timestamp=self.timestamp,
            verbosity_level=self.verbosity_level,
            apply_changes=self.apply_changes,
            output_target=self.output_target,
            file_write_strategy=self.file_write_strategy,
            policy=self.policy.thaw(),
            policy_by_type={k: v.thaw() for k, v in self.policy_by_type.items()},
            config_files=list(self.config_files),
            strict_config_checking=self.strict_config_checking,
            header_fields=list(self.header_fields),
            field_values=dict(self.field_values),
            align_fields=self.align_fields,
            header_format=self.header_format,
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            stdin_mode=self.stdin_mode,
            files=list(self.files),
            include_patterns=list(self.include_patterns),
            include_from=list(self.include_from),
            exclude_patterns=list(self.exclude_patterns),
            exclude_from=list(self.exclude_from),
            files_from=list(self.files_from),
            include_file_types=set(self.include_file_types),
            exclude_file_types=set(self.exclude_file_types),
            diagnostics=DiagnosticLog.from_iterable(self.diagnostics),
        )


def sanitize_config(config: Config) -> Config:
    """Sanitize a Config object.

    Thaws the Config into a MutableConfig, sanitizes and freezes again.

    Args:
        config: The Config to sanitize.

    Returns:
        The sanitized Config instance.
    """
    m: MutableConfig = config.thaw()
    m.sanitize()
    return m.freeze()


# -------------------------- Mutable builder --------------------------
@dataclass
class MutableConfig:
    """Mutable configuration used during discovery and merging.

    This builder collects config from defaults, project files, extra files, and CLI
    overrides. It remains convenient to mutate (``list``/``set``), then produces
    an immutable `Config` via `freeze`. TOML I/O is delegated to
    [`topmark.config.io`][topmark.config.io] to keep this class focused on merge policy.

    Attributes:
        timestamp: ISO-formatted timestamp when the Config instance was created.
        verbosity_level: None = inherit, 0 = terse, 1 = verbose diagnostics.
        apply_changes: Runtime intent: whether to actually write changes (apply)
            or preview only. None = inherit/unspecified, False = dry-run/preview, True = apply.
        output_target: Where to send output: `"file"` or `"stdout"`.
        file_write_strategy: How to write when `output_target == "file"`:
            `"atomic"` (safe default) or `"inplace"` (fast, less safe).
        policy: Optional global policy overrides (public shape).
        policy_by_type: Optional per-type policy.
        config_files: List of paths or identifiers for config sources used.
        strict_config_checking: If True, enforce strict config checking
            (fail on warnings and errors).
        header_fields: List of header fields from the [header] section.
        field_values: Mapping of field names to their string values from [fields].
        align_fields: Whether to align fields, from [formatting].
        header_format: Header output format
            (file type aware, plain, or json).
        relative_to_raw: Original string from config or CLI
        relative_to: Base path for relative file references, from [files].
        stdin_mode: Whether to read from stdin; requires explicit True to activate.
        files: List of files to process.
        include_from: Files containing include patterns.
        exclude_from: Files containing exclude patterns.
        files_from: Paths to files that list newline-delimited
            candidate file paths to add before filtering.
        include_patterns: Glob patterns to include.
        exclude_patterns: Glob patterns to exclude.
        include_file_types: file type identifiers to process.
        exclude_file_types: file type identifiers to exclude.
        diagnostics: Warnings or errors encountered while loading,
            merging or sanitizing config.
    """

    # Initialization timestamp for the draft instance
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Verbosity level ()
    verbosity_level: int | None = None

    # Runtime intent: whether to actually write changes (apply) or preview only
    apply_changes: bool | None = None

    # Output target for writing (file, stdout)
    output_target: OutputTarget | None = None
    # File writer (atomic, in-place)
    file_write_strategy: FileWriteStrategy | None = None

    # Policy containers:
    policy: MutablePolicy = field(default_factory=MutablePolicy)
    policy_by_type: dict[str, MutablePolicy] = field(default_factory=lambda: {})

    # Provenance
    config_files: list[Path | str] = field(default_factory=lambda: [])

    # TOML config checking
    strict_config_checking: bool | None = None

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
    stdin_mode: bool | None = None  # Explicit True required to enable reading from stdin
    files: list[str] = field(default_factory=lambda: [])

    include_from: list[PatternSource] = field(default_factory=lambda: [])
    exclude_from: list[PatternSource] = field(default_factory=lambda: [])
    files_from: list[PatternSource] = field(default_factory=lambda: [])

    include_patterns: list[str] = field(default_factory=lambda: [])
    exclude_patterns: list[str] = field(default_factory=lambda: [])

    # File types filter
    include_file_types: set[str] = field(default_factory=lambda: set[str]())
    exclude_file_types: set[str] = field(default_factory=lambda: set[str]())

    # Collected diagnostics while loading / merging / sanitizing config.
    diagnostics: DiagnosticLog = field(default_factory=DiagnosticLog)

    @property
    def should_proceed(self) -> bool:
        """Return True if processing should proceed based on config diagnostics.

        Analyzes `self.diagnostics` and `compute_diagnostic_stats` to decide whether
        to proceed.

        A similar helper exists in `Config`.

        Returns:
            False if errors occurred, or if warnings detected in strict config processing
                mode, True otherwise.
        """
        stats: DiagnosticStats = compute_diagnostic_stats(self.diagnostics)
        if stats.n_error > 0:
            # Can't proceed with errors
            return False
        # Can't proceed with warnings in strict mode
        return not (self.strict_config_checking is True and stats.n_warning > 0)

    # ---------------------------- Build/freeze ----------------------------
    def freeze(self) -> Config:
        """Freeze this mutable builder into an immutable Config.

        This method applies final sanitation and normalizes internal container
        types before constructing the immutable `Config` snapshot.
        """
        self.sanitize()

        # Resolve global policy against an all-false base
        global_policy_frozen: Policy = self.policy.resolve(Policy())

        # Validate mutual exclusivity on resolved global policy
        if global_policy_frozen.add_only and global_policy_frozen.update_only:
            raise ValueError(
                "Policy invalid: "
                f"`{ArgKey.POLICY_CHECK_ADD_ONLY}` and `{ArgKey.POLICY_CHECK_UPDATE_ONLY}` "
                "cannot both be True."
            )

        # Resolve per-type policies against the resolved global policy
        frozen_by_type: dict[str, Policy] = {}
        for ft, mp in self.policy_by_type.items():
            resolved: Policy = mp.resolve(global_policy_frozen)
            if resolved.add_only and resolved.update_only:
                raise ValueError(
                    f"Policy invalid for type '{ft}': "
                    f"`{ArgKey.POLICY_CHECK_ADD_ONLY}` and `{ArgKey.POLICY_CHECK_UPDATE_ONLY}` "
                    "cannot both be True."
                )
            frozen_by_type[ft] = resolved

        # Set strict_config_checking to True only if self.strict_config_checking === True
        strict_config_checking = bool(self.strict_config_checking)

        return Config(
            timestamp=self.timestamp,
            verbosity_level=self.verbosity_level,
            apply_changes=self.apply_changes,
            output_target=self.output_target,
            file_write_strategy=self.file_write_strategy,
            policy=global_policy_frozen,
            policy_by_type=frozen_by_type,
            config_files=tuple(self.config_files),
            strict_config_checking=strict_config_checking,
            header_fields=tuple(self.header_fields),
            field_values=dict(self.field_values),
            align_fields=self.align_fields,
            header_format=self.header_format,
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            stdin_mode=self.stdin_mode,
            files=tuple(self.files),
            include_from=tuple(self.include_from),
            exclude_from=tuple(self.exclude_from),
            files_from=tuple(self.files_from),
            include_patterns=tuple(self.include_patterns),
            exclude_patterns=tuple(self.exclude_patterns),
            include_file_types=frozenset(self.include_file_types),
            exclude_file_types=frozenset(self.exclude_file_types),
            diagnostics=self.diagnostics.freeze(),
        )

    # --------------------------- Loaders/parsers --------------------------
    @classmethod
    @functools.cache
    def get_default_config_toml(
        cls,
        *,
        for_pyproject: bool,
    ) -> str:
        """Return TopMark runtime defaults as TOML (I/O-free)."""
        return render_runtime_defaults_toml_text(for_pyproject=for_pyproject)

    @classmethod
    def to_cleaned_toml(cls, toml_doc: str) -> str:
        """Return a cleaned TOML string with comments and extraneous whitespace removed.

        Args:
            toml_doc: The raw TOML document string.

        Returns:
            The cleaned TOML string.
        """
        return clean_toml(toml_doc)

    @classmethod
    def from_defaults(cls) -> MutableConfig:
        """Load the default configuration from TopMark's runtime defaults.

        Returns:
            A `MutableConfig` instance populated with default values.
        """
        default_toml_data: TomlTable = load_defaults_dict()

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
            path: Path to the TOML file.

        Returns:
            The Config instance if successful; None if required sections are missing.
        """
        logger.debug("Creating MutableConfig from TOML config: %s", path)

        toml_data: TomlTable = load_toml_dict(path)

        if path.name == "pyproject.toml":
            # Extract [tool.topmark] subsection from pyproject.toml
            tool_section: TomlTable = toml_data.get("tool", {}).get("topmark", {})
            if not tool_section:
                logger.error("[tool.topmark] section missing or malformed in %s", path)
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
            start: The Path instance where discovery starts.

        Returns:
            Discovered config file paths ordered for stable merging
            (root-most first, nearest last; within a directory: pyproject → topmark).
        """
        # Collect per-directory entries preserving same-dir precedence (pyproject → topmark)
        per_dir: list[list[Path]] = []
        cur: Path = start.resolve()  # Resolve symlinks and get absolute path
        seen: set[Path] = set()

        # Ensure we start from a directory anchor
        if cur.is_file():
            cur = cur.parent

        # Walk up to filesystem root, recording entries per directory
        while True:
            root_stop_here = False
            dir_entries: list[Path] = []

            # Same-directory precedence: add pyproject first, then topmark (local order)
            for name in ("pyproject.toml", "topmark.toml"):
                p: Path = cur / name
                if p.exists() and p.is_file() and p not in seen:
                    dir_entries.append(p)
                    seen.add(p)
                    logger.debug("Discovered config file: %s", p)
                    # Check for `root = true` to stop traversal after this dir
                    data: TomlTable = load_toml_dict(p)
                    # load_toml_dict() does a best-effort discovery; it returns {} on errors.
                    if data:
                        if name == "pyproject.toml":
                            tool: TomlTable = data.get("tool", {})
                            topmark_tbl: TomlTable = tool.get("topmark", {})
                            if bool(topmark_tbl.get(Toml.KEY_ROOT, False)):
                                root_stop_here = True
                        else:  # topmark.toml
                            if bool(data.get(Toml.KEY_ROOT, False)):
                                root_stop_here = True
                    else:
                        # Best-effort discovery; ignore parse errors here.
                        logger.debug("Ignoring empty TOML dict from reading %s", p)

            if dir_entries:
                # Keep entries grouped per directory: [pyproject, topmark]
                per_dir.append(dir_entries)

            parent: Path = cur.parent
            if parent == cur:
                break
            if root_stop_here:
                logger.debug(
                    "Stopping upward config discovery at %s due to %s=true",
                    cur,
                    Toml.KEY_ROOT,
                )
                break
            cur = parent

        # Flatten per-directory lists in root→current order, preserving local precedence
        ordered: list[Path] = []
        for dir_list in reversed(per_dir):  # root-most first
            # Within a directory: pyproject then topmark (tool file overrides)
            ordered.extend(dir_list)  # pyproject then topmark within the directory

        return ordered

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
        data: TomlTable,
        config_file: Path | None = None,
        use_defaults: bool = False,
    ) -> MutableConfig:
        """Create a draft config from a parsed TOML dict.

        - Path-to-file entries declared in the config are normalized to absolute paths
          using the *config file's* directory (config-local base).
        - Glob strings are kept as-is (evaluated later against `relative_to`).
        - `[fields]` is a free-form mapping of field_name -> field_value; only names listed
          in `[header].fields` are rendered later by `BuilderStep`.

        Args:
            data: The parsed TOML data as a dictionary.
            config_file: Optional path to the source TOML file.
            use_defaults: Whether to treat this data as default config (affects behavior).

        Returns:
            The resulting MutableConfig instance.
        """
        tool_tbl: TomlTable = data  # top-level tool configuration dictionary

        # Start from a fresh draft with current timestamp early so we can attach diagnostics
        # while parsing.
        draft: MutableConfig = cls(timestamp=datetime.now(timezone.utc).isoformat())

        # Config file's directory for relative path resolution
        cfg_dir: Path | None = config_file.parent.resolve() if config_file else None

        # ------------------------- Unknown key validation -------------------------
        def _warn_unknown(where: str, keys: set[str]) -> None:
            if not keys:
                return
            msg: str = f"Unknown TOML key(s) in {where} (ignored): " + ", ".join(sorted(keys))
            logger.warning(msg)
            draft.diagnostics.add_warning(msg)

        # Validate top-level keys
        _warn_unknown(
            "top-level",
            set(tool_tbl.keys()) - set(Toml.ALLOWED_TOP_LEVEL_KEYS),
        )

        # Validate known sections (tables)
        for section_name, allowed_keys in Toml.ALLOWED_SECTION_KEYS.items():
            if section_name not in tool_tbl:
                continue
            section_val: Any = tool_tbl.get(section_name)
            if not isinstance(section_val, dict):
                msg: str = (
                    f"TOML section [{section_name}] must be a table; "
                    f"got {type(section_val).__name__} (ignored)."
                )
                logger.warning(msg)
                draft.diagnostics.add_warning(msg)
                continue

            section_tbl: TomlTable = cast("TomlTable", section_val)
            _warn_unknown(f"[{section_name}]", set(section_tbl.keys()) - set(allowed_keys))

        # Validate [policy_by_type.<filetype>] subtables (their keys are fixed)
        pbt_val: Any = tool_tbl.get(Toml.SECTION_POLICY_BY_TYPE)
        if isinstance(pbt_val, dict):
            pbt_tbl: TomlTable = cast("TomlTable", pbt_val)
            for ft_name, ft_tbl_any in pbt_tbl.items():
                ft: str = str(ft_name)
                if not isinstance(ft_tbl_any, dict):
                    msg = (
                        f"TOML section [{Toml.SECTION_POLICY_BY_TYPE}.{ft}] "
                        f"must be a table; got {type(ft_tbl_any).__name__} (ignored)."
                    )
                    logger.warning(msg)
                    draft.diagnostics.add_warning(msg)
                    continue

                ft_tbl: TomlTable = cast("TomlTable", ft_tbl_any)
                _warn_unknown(
                    f"[{Toml.SECTION_POLICY_BY_TYPE}.{ft}]",
                    set(ft_tbl.keys()) - set(Toml.ALLOWED_POLICY_KEYS),
                )

        # Extract sub-tables for specific config sections; fallback to empty dicts.
        #
        # NOTE: `[fields]` is an *arbitrary* user-defined mapping of name -> value.
        #       It may contain keys that are not rendered. The rendered/ordered subset
        #       is controlled by `[header].fields` and applied later by
        #       `topmark.pipeline.steps.builder.BuilderStep`.
        field_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_FIELDS)
        logger.trace("TOML [%s]: %s", Toml.SECTION_FIELDS, field_tbl)

        header_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_HEADER)
        logger.trace("TOML [%s]: %s", Toml.SECTION_HEADER, header_tbl)

        formatting_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_FORMATTING)
        logger.trace("TOML [%s]: %s", Toml.SECTION_FORMATTING, formatting_tbl)

        files_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_FILES)
        logger.trace("TOML [%s]: %s", Toml.SECTION_FILES, files_tbl)

        policy_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_POLICY)
        logger.trace("TOML [%s]: %s", Toml.SECTION_POLICY, policy_tbl)

        policy_by_type_raw: TomlTable = get_table_value(tool_tbl, Toml.SECTION_POLICY_BY_TYPE)
        policy_by_type_tbl: TomlTableMap = as_toml_table_map(policy_by_type_raw)
        logger.trace("TOML [%s]: %s", Toml.SECTION_POLICY_BY_TYPE, policy_by_type_tbl)

        writer_tbl: TomlTable = get_table_value(tool_tbl, Toml.SECTION_WRITER)
        logger.trace("TOML [%s]: %s", Toml.SECTION_WRITER, writer_tbl)

        # ----- config_files: normalize to absolute paths if possible -----
        config_files: tuple[list[Path]] = ([config_file] if config_file else [],)
        draft.config_files = [str(p) for p in config_files[0]] if config_files[0] else []

        # ----- Writer settings -----
        where_writer: Final[str] = f"[{Toml.SECTION_WRITER}]"

        # target
        raw_target: str | None = get_string_value_or_none_checked(
            writer_tbl,
            Toml.KEY_TARGET,
            where=where_writer,
            diagnostics=draft.diagnostics,
            logger=logger,
        )
        if raw_target is not None:
            parsed_target: OutputTarget | None = OutputTarget.parse(raw_target)
            if parsed_target is None:
                allowed_targets = ", ".join(t.value for t in OutputTarget)
                msg = (
                    f"Invalid value for {where_writer}.{Toml.KEY_TARGET}: "
                    f"{raw_target!r} (allowed: {allowed_targets})"
                )
                logger.warning(msg)
                draft.diagnostics.add_warning(msg)
            else:
                draft.output_target = parsed_target

        # strategy
        raw_strategy: str | None = get_string_value_or_none_checked(
            writer_tbl,
            Toml.KEY_STRATEGY,
            where=where_writer,
            diagnostics=draft.diagnostics,
            logger=logger,
        )
        if raw_strategy is not None:
            parsed_strategy: FileWriteStrategy | None = FileWriteStrategy.parse(raw_strategy)
            if parsed_strategy is None:
                allowed_strategies = ", ".join(s.value for s in FileWriteStrategy)
                msg = (
                    f"Invalid value for {where_writer}.{Toml.KEY_STRATEGY}: "
                    f"{raw_strategy!r} (allowed: {allowed_strategies})"
                )
                logger.warning(msg)
                draft.diagnostics.add_warning(msg)
            else:
                draft.file_write_strategy = parsed_strategy

        # ----- Global policy -----
        where_policy: Final[str] = f"[{Toml.SECTION_POLICY}]"
        for key in Toml.ALLOWED_POLICY_KEYS:
            # Pre-validate the shapes before calling MutablePolicy.from_toml_table()
            # to add diagnostics for wrong policy types
            _ = get_bool_value_or_none_checked(
                policy_tbl,
                key,
                where=where_policy,
                diagnostics=draft.diagnostics,
                logger=logger,
            )
        draft.policy = MutablePolicy.from_toml_table(policy_tbl)

        # ----- Policy by FileType -----

        for ft, tbl in policy_by_type_tbl.items():
            where: str = f"[{Toml.SECTION_POLICY_BY_TYPE}.{ft}]"
            for key in Toml.ALLOWED_POLICY_KEYS:
                # Pre-validate the shapes before calling MutablePolicy.from_toml_table()
                # to add diagnostics for wrong policy types
                _ = get_bool_value_or_none_checked(
                    tbl,
                    key,
                    where=where,
                    diagnostics=draft.diagnostics,
                    logger=logger,
                )
        draft.policy_by_type = {
            str(ft): MutablePolicy.from_toml_table(tbl) for ft, tbl in policy_by_type_tbl.items()
        }

        # ----- files: normalize to absolute paths against the config file dir (when known) -----
        where_files: Final[str] = f"[{Toml.SECTION_FILES}]"
        raw_files: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_FILES,
            where=where_files,
            diagnostics=draft.diagnostics,
            logger=logger,
        )
        if raw_files:
            if cfg_dir is not None:
                for f in raw_files:
                    absf: Path = abs_path_from(cfg_dir, f)
                    draft.files.append(str(absf))
                    logger.debug("Normalized config files entry against %s: %s", cfg_dir, absf)
            else:
                draft.files.extend(raw_files)

        # ----- include_from / exclude_from / files_from: convert to PatternSource now -----
        def _normalize_sources(key: str) -> None:
            # List-valued keys under [files] (include_from/exclude_from/files_from) should be
            # a list of strings. Wrong types are treated as empty; mixed types drop non-strings.
            # Enforce "list of strings" for field selection in TOML:
            vals: list[str] = get_string_list_value_checked(
                files_tbl,
                key,
                where=where_files,
                diagnostics=draft.diagnostics,
                logger=logger,
            )

            if not vals:
                return

            if cfg_dir is not None:
                extend_pattern_sources(
                    getattr(draft, key),
                    vals,
                    ps_from_config,
                    f"config {where_files}.{key}",
                    cfg_dir,
                )
            else:
                # Rare fallback: without a config file path, use CWD to avoid losing info
                extend_pattern_sources(
                    getattr(draft, key),
                    vals,
                    ps_from_cli,
                    f"config {where_files}.{key}",
                    Path.cwd().resolve(),
                )

        for _k in (Toml.KEY_INCLUDE_FROM, Toml.KEY_EXCLUDE_FROM, Toml.KEY_FILES_FROM):
            _normalize_sources(_k)

        # ----- glob arrays remain raw strings (evaluated later vs relative_to) -----
        # List-valued glob keys under [files] should contain strings. Wrong types are treated
        # as empty; mixed types drop non-strings with a warning + diagnostic.
        def _extend_glob_list(attr: str, key: str) -> None:
            # Enforce "list of strings" for field selection in TOML:
            vals: list[str] = get_string_list_value_checked(
                files_tbl, key, where=where_files, diagnostics=draft.diagnostics, logger=logger
            )

            if vals:
                getattr(draft, attr).extend(vals)

        _extend_glob_list("include_patterns", Toml.KEY_INCLUDE_PATTERNS)
        _extend_glob_list("exclude_patterns", Toml.KEY_EXCLUDE_PATTERNS)

        # Coerce `[fields]` values to strings (the table is user-defined and may include
        # unused keys). Unsupported types are ignored with a warning.
        field_values: dict[str, str] = {}
        for k, v in field_tbl.items():
            if isinstance(v, (str, int, float, bool)):
                field_values[k] = str(v)
            else:
                # [fields] is a free-form table; include the TOML location for consistency.
                loc: str = f"[{Toml.SECTION_FIELDS}].{k}"
                logger.warning(
                    "Ignoring unsupported field value for %s: %r",
                    loc,
                    v,
                )
                draft.diagnostics.add_warning(f"Ignoring unsupported field value for {loc}: {v}")
        draft.field_values = field_values

        # `[header].fields`: ordered list of field names to render (built-ins and/or
        # keys from `[fields]`).
        #
        # Enforce "list of strings" for header field selection in TOML:
        draft.header_fields = get_string_list_value_checked(
            header_tbl,
            Toml.KEY_FIELDS,
            where=f"[{Toml.SECTION_HEADER}]",
            diagnostics=draft.diagnostics,
            logger=logger,
        )

        # # Fallback: if no explicit header field order is provided, use the keys of
        # # the field_values table in their declared order. This preserves intuitive
        # # behavior (headers render when values are present).
        # if not header_fields and field_values:
        #     header_fields = list(field_values.keys())

        # Parse relative_to path if present, resolve to absolute path
        draft.relative_to_raw = get_string_value_checked(
            files_tbl,
            Toml.KEY_RELATIVE_TO,
            where=where_files,
            diagnostics=draft.diagnostics,
            logger=logger,
            default="",
        )
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

        where_fmt: Final[str] = f"[{Toml.SECTION_FORMATTING}]"
        # align_fields --  NOTE: do not set a default value if not set
        draft.align_fields = get_bool_value_or_none_checked(
            formatting_tbl,
            Toml.KEY_ALIGN_FIELDS,
            where=where_fmt,
            diagnostics=draft.diagnostics,
            logger=logger,
        )

        # raw_header_format --  NOTE: do not set a default value if not set
        raw_header_format: str | None = get_string_value_or_none_checked(
            formatting_tbl,
            Toml.KEY_HEADER_FORMAT,
            where=where_fmt,
            diagnostics=draft.diagnostics,
            logger=logger,
        )

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
                draft.diagnostics.add_error(
                    f"Invalid header format specifier found: {raw_header_format} "
                    f"(allowed values: {valid_values})"
                )
                draft.header_format = None
        else:
            # choose your default; this keeps behavior predictable
            draft.header_format = None

        # File-related settings

        # include_file_types
        include_file_types: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_INCLUDE_FILE_TYPES,
            where=where_files,
            diagnostics=draft.diagnostics,
            logger=logger,
        )
        draft.include_file_types = set(include_file_types)

        if include_file_types and len(include_file_types) != len(draft.include_file_types):
            logger.warning(
                "Duplicate included file types found in config (key: %s): %s",
                Toml.KEY_INCLUDE_FILE_TYPES,
                ", ".join(include_file_types),
            )
            draft.diagnostics.add_warning(
                "Duplicate included file types found in config "
                f"(key: {Toml.KEY_INCLUDE_FILE_TYPES}): "
                ", ".join(include_file_types),
            )

        # exclude_file_types
        exclude_file_types: list[str] = get_string_list_value_checked(
            files_tbl,
            Toml.KEY_EXCLUDE_FILE_TYPES,
            where=where_files,
            diagnostics=draft.diagnostics,
            logger=logger,
        )
        draft.exclude_file_types = set(exclude_file_types)

        if exclude_file_types and len(exclude_file_types) != len(draft.exclude_file_types):
            logger.warning(
                "Duplicate excluded file types found in config (key: %s): %s",
                Toml.KEY_EXCLUDE_FILE_TYPES,
                ", ".join(exclude_file_types),
            )
            draft.diagnostics.add_warning(
                "Duplicate excluded file types found in config "
                f"(key: {Toml.KEY_EXCLUDE_FILE_TYPES}): "
                ", ".join(exclude_file_types),
            )

        # stdin_mode
        draft.stdin_mode = (
            False  # Default to False unless explicitly set later -- TODO: False or None?
        )

        return draft

    @classmethod
    def load_merged(
        cls,
        *,
        input_paths: Iterable[Path] | None = None,
        extra_config_files: Iterable[Path] | None = None,
        strict_config_checking: bool | None = None,
        no_config: bool = False,
        include_file_types: Iterable[str] | None = None,
        exclude_file_types: Iterable[str] | None = None,
    ) -> MutableConfig:
        """Discover and merge configuration layers into a draft `MutableConfig`.

        Merge order (lowest → highest precedence):
            1) Built-in defaults
            2) User config (XDG / legacy)
            3) Project configs discovered upward **root → current**; within a directory
               `pyproject.toml` is merged first, then `topmark.toml` (tool file overrides)
            4) Extra config files passed explicitly via ``--config`` (in the order provided)

        Args:
            input_paths: Discovery anchor(s). The first path (or CWD if none) is used as
                the starting directory for upward discovery. If it is a file, its parent directory
                is used.
            extra_config_files: Explicit additional config files to merge **after** discovery
                (their given order).
            strict_config_checking: If True, enforce strict TOML config checking (fail on errors).
            no_config: If True, skip user and project discovery.
            include_file_types: Optional filter to seed the draft for parity with CLI.
            exclude_file_types: Optional filter to seed the draft for parity with CLI.

        Returns:
            A mutable configuration draft ready to be frozen or further edited.
        """
        # 1) Start from defaults
        draft: MutableConfig = cls.from_defaults()

        # Determine discovery anchor
        anchor: Path = list(input_paths)[0] if input_paths else Path.cwd()
        if anchor.is_file():
            anchor = anchor.parent

        # Optionally seed include_file_types for parity with CLI flags
        if include_file_types:
            draft.include_file_types = set(include_file_types)
        # Optionally seed exlude_file_types for parity with CLI flags
        if exclude_file_types:
            draft.exclude_file_types = set(exclude_file_types)

        # Only set strict config checking if not None
        if strict_config_checking is not None:
            draft.strict_config_checking = strict_config_checking

        if not no_config:
            # 2) Merge user config (if present)
            user_cfg_path: Path | None = cls.discover_user_config_file()
            if user_cfg_path is not None:
                user_cfg: MutableConfig | None = cls.from_toml_file(user_cfg_path)
                if user_cfg is not None:
                    draft = draft.merge_with(user_cfg)

            # 3) Discover project configs upward from anchor and merge **root → current**
            discovered: list[Path] = cls.discover_local_config_files(anchor)
            # `discover_local_config_files` already returns root-most → nearest; within a directory
            # it yields `pyproject.toml` then `topmark.toml`.
            for cfg_path in discovered:
                mc: MutableConfig | None = cls.from_toml_file(cfg_path)
                if mc is not None:
                    draft = draft.merge_with(mc)

        # 4) Merge extra config files (e.g., --config), in the given order
        for extra in extra_config_files or ():  # explicit files override discovered ones
            mc = cls.from_toml_file(Path(extra))
            if mc is not None:
                draft = draft.merge_with(mc)

        return draft

    # ------------------------------- Merging -------------------------------
    def merge_with(self, other: MutableConfig) -> MutableConfig:
        """Return a new draft where values from ``other`` override this draft.

        This method performs a last-wins merge across all fields. For the policy
        layer, it delegates to ``MutablePolicy.merge_with`` so that tri-state
        fields (``bool | None``) are combined without losing information.

        Args:
            other: The config whose values override those of this draft.

        Returns:
            A new mutable configuration representing the merged result.
        """
        # --- merge global policy (tri-state) ---
        # Prefer `other`'s explicitly-set policy fields over `self`'s.
        merged_global: MutablePolicy = self.policy.merge_with(other.policy)

        # --- merge per-type policy (key-wise union; tri-state per field) ---
        merged_by_type: dict[str, MutablePolicy] = {}
        all_keys: set[str] = set(self.policy_by_type.keys()) | set(other.policy_by_type.keys())
        for key in all_keys:
            base: MutablePolicy | None = self.policy_by_type.get(key)
            override: MutablePolicy | None = other.policy_by_type.get(key)
            if base is None:
                if override is not None:
                    merged_by_type[key] = override  # take as-is
            elif override is None:
                merged_by_type[key] = base  # keep base
            else:
                merged_by_type[key] = base.merge_with(override)

        # --- Merge diagnostics ---
        merged_diags: DiagnosticLog = DiagnosticLog(
            items=[*self.diagnostics.items, *other.diagnostics.items]
        )

        logger.info(
            "Adding %r to self.config_files = %r",
            other.config_files,
            self.config_files,
        )

        merged = MutableConfig(
            timestamp=self.timestamp,
            # Append config files
            config_files=self.config_files + other.config_files,
            # strict_config_checking: preserve tri-state strict flag
            strict_config_checking=(
                other.strict_config_checking
                if other.strict_config_checking is not None
                else self.strict_config_checking
            ),
            # diagnostics must be carried forward:
            diagnostics=merged_diags,
            # Default " last wins" merge strategy:
            field_values=other.field_values or self.field_values,
            header_fields=other.header_fields or self.header_fields,
            align_fields=other.align_fields
            if other.align_fields is not None
            else self.align_fields,
            header_format=other.header_format
            if other.header_format is not None
            else self.header_format,
            stdin_mode=other.stdin_mode if other.stdin_mode is not None else self.stdin_mode,
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
            include_file_types=other.include_file_types or self.include_file_types,
            exclude_file_types=other.exclude_file_types or self.exclude_file_types,
            verbosity_level=other.verbosity_level
            if other.verbosity_level is not None
            else self.verbosity_level,
            apply_changes=other.apply_changes
            if other.apply_changes is not None
            else self.apply_changes,
            output_target=other.output_target
            if other.output_target is not None
            else self.output_target,
            file_write_strategy=other.file_write_strategy
            if other.file_write_strategy is not None
            else self.file_write_strategy,
        )

        # Attach merged policies
        merged.policy = merged_global
        merged.policy_by_type = merged_by_type

        return merged

    def apply_args(
        self,
        args: ArgsLike,
        *,
        config_only: bool = False,
    ) -> MutableConfig:
        """Update Config fields based on an arguments mapping (CLI or API).

        Accepts CLI or API-provided argument mappings and applies validated overrides.

        This method applies overrides from a parsed arguments mapping to the current
        MutableConfig instance. It does not handle flags that influence config file
        discovery (e.g., --no-config, --config).

        Args:
            args: Parsed arguments mapping (from CLI or API).
            config_only: If True, only process config-related CLI inputs (disregard all other
                CLI inputs)

        Returns:
            The updated MutableConfig instance with CLI overrides applied.

        Note:
            CLI path-to-file options (``--include-from``, ``--exclude-from``,
            ``--files-from``) are normalized against the **current working
            directory** (invocation site). Glob arrays remain as strings and
            are later evaluated relative to ``relative_to``.
        """
        # NOTE: ArgsLike is not typed as strictly as ArgsNamespace so we should check type
        # when reading from args

        logger.debug("Applying ArgsLike arguments to MutableConfig: %s", args)

        # strict_config_checking
        strict: bool | None = get_arg_bool_or_none_checked(
            args,
            ArgKey.STRICT_CONFIG_CHECKING,
            diagnostics=self.diagnostics,
            logger=logger,
        )
        if strict is not None:
            self.strict_config_checking = strict

        # Append or initialize config_files list with CLI override marker;
        # use a special marker to indicate CLI overrides in config_files list
        if self.config_files:
            self.config_files.append(CLI_OVERRIDE_STR)
        else:
            self.config_files = [CLI_OVERRIDE_STR]

        # Note: CLI config paths are already merged elsewhere
        # so we don't extend self.config_files here.

        # Policy flags (add_only, update_only)
        add_only: bool | None = get_arg_bool_or_none_checked(
            args,
            ArgKey.POLICY_CHECK_ADD_ONLY,
            diagnostics=self.diagnostics,
            logger=logger,
        )
        if add_only is not None:
            self.policy.add_only = add_only

        update_only: bool | None = get_arg_bool_or_none_checked(
            args,
            ArgKey.POLICY_CHECK_UPDATE_ONLY,
            diagnostics=self.diagnostics,
            logger=logger,
        )
        if update_only is not None:
            self.policy.update_only = update_only
        # ... but do not zero-out policy_by_type when ArgsLike says nothing

        # Files to process (enforce list[str])
        if ArgKey.FILES in args:
            self.files = get_arg_string_list_checked(
                args,
                ArgKey.FILES,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            if any(not s for s in self.files):
                empties: list[str] = [s for s in self.files if not s]
                logger.warning("Ignoring empty string entries in %s: %r", ArgKey.FILES, empties)
                self.diagnostics.add_warning(
                    f"Ignoring empty string entries in {ArgKey.FILES}: {empties!r}"
                )
                self.files = [s for s in self.files if s]
            if self.files:
                self.stdin_mode = False

        # Glob patterns: include_patterns / exclude_patterns (extend)
        if ArgKey.INCLUDE_PATTERNS in args:
            vals = get_arg_string_list_checked(
                args,
                ArgKey.INCLUDE_PATTERNS,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            vals = [s for s in vals if s]
            if vals:
                self.include_patterns.extend(vals)
        if ArgKey.EXCLUDE_PATTERNS in args:
            vals = get_arg_string_list_checked(
                args,
                ArgKey.EXCLUDE_PATTERNS,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            vals = [s for s in vals if s]
            if vals:
                self.exclude_patterns.extend(vals)

        # Override include/exclude patterns and files if specified
        cwd: Path = Path.cwd().resolve()

        # Path-to-file options: include_from, exclude_from, files_from (validate list[str])
        if ArgKey.INCLUDE_FROM in args:
            vals: list[str] = get_arg_string_list_checked(
                args,
                ArgKey.INCLUDE_FROM,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            vals = [s for s in vals if s]
            extend_pattern_sources(
                self.include_from,
                vals,
                ps_from_cli,
                f"CLI {CliOpt.INCLUDE_FROM}",
                cwd,
            )
        if ArgKey.EXCLUDE_FROM in args:
            vals = get_arg_string_list_checked(
                args,
                ArgKey.EXCLUDE_FROM,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            vals = [s for s in vals if s]
            extend_pattern_sources(
                self.exclude_from,
                vals,
                ps_from_cli,
                f"CLI {CliOpt.EXCLUDE_FROM}",
                cwd,
            )
        if ArgKey.FILES_FROM in args:
            vals = get_arg_string_list_checked(
                args,
                ArgKey.FILES_FROM,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            vals = [s for s in vals if s]
            extend_pattern_sources(
                self.files_from,
                vals,
                ps_from_cli,
                f"CLI {CliOpt.FILES_FROM}",
                cwd,
            )

        # relative_to: string or None, only override if non-empty string (not just whitespace)
        if ArgKey.RELATIVE_TO in args:
            rel: str | None = get_arg_string_or_none_checked(
                args,
                ArgKey.RELATIVE_TO,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            if rel is not None and rel.strip() != "":
                rel_str: str = rel.strip()
                self.relative_to_raw = rel_str
                self.relative_to = Path(rel_str).resolve()

        # If key not present or value is None, **keep** whatever came from discovery/TOML.

        # include_file_types / exclude_file_types: set of strings, only override if present
        raw: Any | None = args.get(ArgKey.INCLUDE_FILE_TYPES)
        if raw not in (None, ()):
            # Only override when the user actually passes a value
            # TODO decide whether `()` clears the property or whether we always extend the set
            vals = get_arg_string_list_checked(
                args,
                ArgKey.INCLUDE_FILE_TYPES,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            filtered: list[str] = [s for s in vals if s]  # drop empty strings
            deduped: set[str] = set(filtered)
            self.include_file_types = deduped
            dup_count: int = len(filtered) - len(deduped)
            if dup_count:
                self.diagnostics.add_info(
                    f"Ignored {dup_count} duplicate values for {ArgKey.INCLUDE_FILE_TYPES}"
                )

        raw: Any | None = args.get(ArgKey.EXCLUDE_FILE_TYPES)
        if raw not in (None, ()):
            # Only override when the user actually passes a value
            # TODO decide whether `()` clears the property or whether we always extend the set
            vals = get_arg_string_list_checked(
                args,
                ArgKey.EXCLUDE_FILE_TYPES,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            filtered: list[str] = [s for s in vals if s]  # drop empty strings
            deduped: set[str] = set(filtered)
            self.exclude_file_types = deduped
            dup_count: int = len(filtered) - len(deduped)
            if dup_count:
                self.diagnostics.add_info(
                    f"Ignored {dup_count} duplicate values for {ArgKey.EXCLUDE_FILE_TYPES}"
                )

        # Apply CLI flags that require explicit True to activate or to explicitly disable

        # stdin_mode: checked bool

        # Apply CLI flags that require explicit True to activate or to explicitly disable
        stdin_mode: bool | None = get_arg_bool_or_none_checked(
            args,
            ArgKey.STDIN_MODE,
            diagnostics=self.diagnostics,
            logger=logger,
        )
        if stdin_mode is not None:
            # honor False explicitly
            self.stdin_mode = stdin_mode

        # header_format: parse enum
        if ArgKey.HEADER_FORMAT in args:
            fmt: HeaderOutputFormat | None = get_arg_enum_checked(
                args,
                ArgKey.HEADER_FORMAT,
                HeaderOutputFormat,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            if fmt is not None:
                self.header_format = fmt

        # align_fields: checked bool
        if ArgKey.ALIGN_FIELDS in args:
            af: bool | None = get_arg_bool_or_none_checked(
                args,
                ArgKey.ALIGN_FIELDS,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            if af is not None:
                self.align_fields = af

        # verbosity_level: checked int
        if ArgKey.VERBOSITY_LEVEL in args:
            v: int | None = get_arg_int_or_none_checked(
                args,
                ArgKey.VERBOSITY_LEVEL,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            if v is not None:
                self.verbosity_level = v
            else:
                logger.warning(
                    "Invalid verbosity_level=%r (expected int); keeping %r",
                    args[ArgKey.VERBOSITY_LEVEL],
                    self.verbosity_level,
                )
                self.diagnostics.add_warning(
                    f"Invalid verbosity_level={args[ArgKey.VERBOSITY_LEVEL]} (expected int); "
                    f"keeping {self.verbosity_level}",
                )

        if ArgKey.APPLY_CHANGES in args and args[ArgKey.APPLY_CHANGES] is not None:
            self.apply_changes = bool(args[ArgKey.APPLY_CHANGES])

        # write_mode: checked string, then parse
        if ArgKey.WRITE_MODE in args:
            # CLI uses ArgKey.WRITE_MODE as a convenience selector:
            #   - "stdout" -> output to STDOUT (no file strategy)
            #   - "atomic"/"inplace" -> output to FILE + set strategy
            logger.debug("CLI ARGS: write_mode=%r", args[ArgKey.WRITE_MODE])
            write_mode: str = str(args[ArgKey.WRITE_MODE]).lower()

            raw_write_mode: str | None = get_arg_string_or_none_checked(
                args,
                ArgKey.WRITE_MODE,
                diagnostics=self.diagnostics,
                logger=logger,
            )
            if raw_write_mode is None:
                # present but wrong type already diagnosed; do not override
                raw_write_mode = ""
            write_mode: str = raw_write_mode.lower()
            if write_mode:
                if write_mode == "stdout":
                    self.output_target = OutputTarget.STDOUT
                    self.file_write_strategy = None
                else:
                    self.output_target = OutputTarget.FILE
                    file_write_strategy: FileWriteStrategy | None = FileWriteStrategy.parse(
                        write_mode
                    )
                    if file_write_strategy is None:
                        logger.warning(
                            "Invalid '%s' value specified in the arguments: %r - "
                            "using defaults: output to file, atomic file write strategy.",
                            ArgKey.WRITE_MODE,
                            raw_write_mode,
                        )
                        self.diagnostics.add_warning(
                            f"Invalid '{ArgKey.WRITE_MODE}' value specified in the arguments: "
                            f"{raw_write_mode} - "
                            "using defaults: output to file, atomic file write strategy."
                        )
                        file_write_strategy = FileWriteStrategy.ATOMIC
                    self.file_write_strategy = file_write_strategy

        logger.debug("Patched MutableConfig: %s", self)
        logger.info("Applied argument mapping overrides to MutableConfig")
        logger.debug("apply_args(): finalized _mode=%s files=%s", self.stdin_mode, self.files)
        return self

    def _validate_policy_flags(self) -> None:
        """Schema-level validation for mutually exclusive policy flags.

        Records an error diagnostic when `add_only` and `update_only` are both True.
        """

        def _check(where: str, add_only: bool | None, update_only: bool | None) -> None:
            if add_only is True and update_only is True:
                msg = (
                    f"Invalid policy in {where}: "
                    f"{Toml.KEY_POLICY_CHECK_ADD_ONLY}=true and "
                    f"{Toml.KEY_POLICY_CHECK_UPDATE_ONLY}=true cannot both be set."
                )
                logger.error(msg)
                self.diagnostics.add_error(msg)

        # Global policy
        _check(f"[{Toml.SECTION_POLICY}]", self.policy.add_only, self.policy.update_only)

        # Per-type policy
        for ft, p in self.policy_by_type.items():
            _check(f"[{Toml.SECTION_POLICY_BY_TYPE}.{ft}]", p.add_only, p.update_only)

    def sanitize(self) -> None:
        """Normalize and validate draft config in-place.

        This step enforces invariants expected by downstream components
        (file_resolver, pipeline, CLI). It is intended to be called just before
        freezing into an immutable `Config`.

        Current rules:
            - include_from / exclude_from / files_from entries must refer to
              concrete files, not glob-style paths. Any `PatternSource.path`
              containing glob metacharacters (*, ?, [, ]) is ignored with a warning.

        Future extensions may:
            - validate relative_to vs. config_files,
            - check existence of pattern files,
            - normalize duplicate patterns or sources.
        """

        def _has_glob_chars(p: Path) -> bool:
            s: str = str(p)
            return any(ch in s for ch in "*?[]")

        def _sanitize_sources(name: str, sources: list[PatternSource]) -> None:
            if not sources:
                return
            kept: list[PatternSource] = []
            for ps in sources:
                if _has_glob_chars(ps.path):
                    msg: str = (
                        f"Ignoring {name} entry with glob characters in path: {ps.path} "
                        "(these options expect concrete files; use "
                        "include_patterns / exclude_patterns for globs)."
                    )
                    logger.warning(msg)
                    self.diagnostics.add_warning(msg)
                    continue
                kept.append(ps)

            if len(kept) != len(sources):
                msg = (
                    f"Sanitized {name}: kept {len(kept)} source(s), "
                    f"dropped {len(sources) - len(kept)} invalid source(s)"
                )
                logger.warning(msg)
                self.diagnostics.add_warning(msg)

            sources[:] = kept

        _sanitize_sources(Toml.KEY_INCLUDE_FROM, self.include_from)
        _sanitize_sources(Toml.KEY_EXCLUDE_FROM, self.exclude_from)
        _sanitize_sources(Toml.KEY_FILES_FROM, self.files_from)

        def _sanitize_file_type_ids(
            name: str,
            ids: set[str],
            *,
            is_exclusion: bool,
        ) -> None:
            """Validate file type identifiers against the registry.

            Unknown identifiers are ignored (dropped) and recorded as config diagnostics.

            Args:
                name: Human-readable name for diagnostics (e.g. "include_file_types").
                ids: The mutable set of identifiers to validate in-place.
                is_exclusion: Whether this selector is an exclusion filter.
            """
            if not ids:
                return

            # Local import to keep config import-safe and avoid incidental cycles.
            from topmark.registry import FileTypeRegistry

            # Validate against the effective file type registry:
            ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping()

            unknown: list[str] = sorted(t for t in ids if t not in ft_registry)
            if not unknown:
                return

            unknown_str: str = ", ".join(unknown)
            if is_exclusion:
                msg: str = f"Unknown excluded file types specified (ignored): {unknown_str}"
            else:
                msg = f"Unknown included file types specified (ignored): {unknown_str}"

            logger.warning(msg)
            self.diagnostics.add_warning(msg)
            ids.difference_update(unknown)

        _sanitize_file_type_ids(
            Toml.KEY_INCLUDE_FILE_TYPES,
            self.include_file_types,
            is_exclusion=False,
        )
        _sanitize_file_type_ids(
            Toml.KEY_EXCLUDE_FILE_TYPES,
            self.exclude_file_types,
            is_exclusion=True,
        )

        # If a type appears in both include and exclude, prefer exclusion.
        overlap: set[str] = self.include_file_types & self.exclude_file_types
        if overlap:
            overlap_str: str = ", ".join(sorted(overlap))
            msg: str = (
                "File types specified in both include and exclude filters; "
                f"exclusion wins (removed from include): {overlap_str}"
            )
            logger.warning(msg)
            self.diagnostics.add_warning(msg)
            # Remove overlaps (blacklisted wins from whitelisted):
            self.include_file_types.difference_update(overlap)

        # STDIN content mode: force stdout destination.
        # We treat content-on-STDIN as "emit updated content"; file strategies are irrelevant.
        if self.stdin_mode is True:
            if self.output_target is None:
                msg = (
                    f"STDIN mode: Setting {Toml.KEY_TARGET} to {OutputTarget.STDOUT.label} "
                    "(was not set)"
                )
                logger.info(msg)
                self.diagnostics.add_info(msg)
            elif self.output_target != OutputTarget.STDOUT:
                msg = (
                    f"STDIN mode: Setting {Toml.KEY_TARGET} "
                    f"from {self.output_target.key} ({self.output_target.label}) "
                    f"to {OutputTarget.STDOUT.key} ({OutputTarget.STDOUT.label})"
                )
                logger.debug(msg)
                self.diagnostics.add_warning(msg)

            self.output_target = OutputTarget.STDOUT

            if self.file_write_strategy is not None:
                msg = (
                    f"STDIN mode: Clearing file_write_strategy "
                    f"(was: {self.file_write_strategy.key} ({self.file_write_strategy.label}))"
                )
                logger.debug(msg)
                self.diagnostics.add_warning(msg)

            self.file_write_strategy = None

        # Validate the policy flags
        self._validate_policy_flags()

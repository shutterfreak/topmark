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

# For runtime type checks, prefer collections.abc
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeGuard

from topmark.config.io import clean_toml, load_defaults_dict, load_toml_dict, to_toml
from topmark.config.logging import get_logger
from topmark.rendering.formats import HeaderOutputFormat

# ArgsLike: generic mapping accepted by config loaders (works for CLI namespaces and API dicts).
ArgsLike = Mapping[str, Any]
# We use ArgsLike (Mapping[str, Any]) instead of a CLI-specific namespace to
# keep the config layer decoupled from the CLI. The implementation uses .get()
# and key lookups, so Mapping is the right structural type. This allows the
# CLI to pass its namespace and the API/tests to pass plain dicts.

logger = get_logger(__name__)


# ------------------ Immutable runtime config ------------------
@dataclass(frozen=True, slots=True)
class Config:
    """Immutable runtime configuration for TopMark.

    This snapshot is produced by `MutableConfig.freeze` after merging defaults,
    project files, extra config files, and CLI overrides. Collections are immutable
    (``tuple``/``frozenset``) to prevent accidental mutation during processing.
    Use `Config.thaw` to obtain a mutable builder for edits, and `MutableConfig.freeze`
    to return to an immutable runtime snapshot.

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
        include_patterns (tuple[str, ...]): Glob patterns to include.
        include_from (tuple[str, ...]): Files containing include patterns.
        exclude_patterns (tuple[str, ...]): Glob patterns to exclude.
        exclude_from (tuple[str, ...]): Files containing exclude patterns.
        files_from (tuple[str, ...]): Paths to files that list newline-delimited candidate
            file paths to add before filtering.
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
    include_patterns: tuple[str, ...]
    include_from: tuple[str, ...]
    exclude_patterns: tuple[str, ...]
    exclude_from: tuple[str, ...]
    files_from: tuple[str, ...]

    # File types (linked to file extensions) to process (filter)
    file_types: frozenset[str]

    def to_toml_dict(self) -> dict[str, Any]:
        """Convert this immutable Config into a TOML-serializable dict.

        Note:
            Export-only convenience for documentation/snapshots. Parsing and
            loading live on the **mutable** side (see `MutableConfig` and
           `topmark.config.io`).
        """
        return {
            "fields": dict(self.field_values),
            "header": {"fields": list(self.header_fields)},
            "formatting": {
                "align_fields": self.align_fields,
                "header_format": self.header_format,
            },
            "files": {
                "file_types": list(self.file_types),
                "include_patterns": list(self.include_patterns),
                "include_from": list(self.include_from),
                "exclude_patterns": list(self.exclude_patterns),
                "exclude_from": list(self.exclude_from),
                "files_from": list(self.files_from),
                "relative_to": self.relative_to_raw,
            },
        }

    def thaw(self) -> MutableConfig:
        """Return a mutable copy of this frozen config.

        Symmetry:
            Mirrors `MutableConfig.freeze`. Prefer thaw→edit→freeze rather
            than mutating a runtime `Config`.
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


# -------------------------- Mutable builder --------------------------
@dataclass
class MutableConfig:
    """Mutable configuration used during discovery and merging.

    This builder collects config from defaults, project files, extra files, and CLI
    overrides. It remains convenient to mutate (``list``/``set``), then produces
    an immutable `Config` via `freeze`. TOML I/O is delegated to
    +   `topmark.config.io` to keep this class focused on merge policy.

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
        include_patterns (list[str]): Glob patterns to include.
        include_from (list[str]): Files containing include patterns.
        exclude_patterns (list[str]): Glob patterns to exclude.
        exclude_from (list[str]): Files containing exclude patterns.
        files_from (list[str]): Paths to files that list newline-delimited candidate file paths
            to add before filtering.
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
    include_patterns: list[str] = field(default_factory=lambda: [])
    include_from: list[str] = field(default_factory=lambda: [])
    exclude_patterns: list[str] = field(default_factory=lambda: [])
    exclude_from: list[str] = field(default_factory=lambda: [])
    files_from: list[str] = field(default_factory=lambda: [])

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
        toml_data = load_defaults_dict()
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
            MutableConfig: A Config instance populated with default values.
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

        draft: MutableConfig = cls.from_toml_dict(toml_data)
        draft.config_files = [path]
        logger.debug("Generated MutableConfig: %s", draft)
        return draft

    @classmethod
    def from_toml_dict(
        cls,
        data: dict[str, Any],
        config_file: Path | None = None,
        use_defaults: bool = False,
    ) -> MutableConfig:
        """Parse a dictionary representation of TOML data into a Config instance.

        Args:
            data (dict[str, Any]): The parsed TOML data as a dictionary.
            config_file (Path | None): Optional path to the source TOML file.
            use_defaults (bool): Whether to treat this data as default config (affects behavior).

        Returns:
            MutableConfig: The resulting MutableConfig instance.
        """

        # Type guards
        def is_str_any_dict(val: Any) -> TypeGuard[dict[str, Any]]:
            return isinstance(val, dict)

        def is_any_list(val: Any) -> TypeGuard[list[Any]]:
            return isinstance(val, list)

        # Helpers
        def get_table_value(table: dict[str, Any], key: str) -> dict[str, Any]:
            # Safely extract a sub-table (dict) from the TOML data
            value = table.get(key)
            return value if is_str_any_dict(value) else {}

        def get_string_value(table: dict[str, Any], key: str, default: str = "") -> str:
            # Coerce various types to string if possible; fallback to default
            value = table.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, (int, float, bool)):
                return str(value)
            return default

        def get_bool_value(table: dict[str, Any], key: str, default: bool = False) -> bool:
            # Extract boolean value, coercing int to bool if needed
            value = table.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, int):
                return bool(value)
            return default

        def get_list_value(
            table: dict[str, Any], key: str, default: list[Any] | None = None
        ) -> list[Any]:
            # Extract list value, ensure list type or fallback to default
            value = table.get(key)
            if is_any_list(value):
                return value
            return default or []

        tool_cfg = data  # top-level tool configuration dictionary

        # Extract sub-tables for specific config sections; fallback to empty dicts
        field_cfg = get_table_value(tool_cfg, "fields")
        logger.trace("TOML [fields]: %s", field_cfg)

        header_cfg = get_table_value(tool_cfg, "header")
        logger.trace("TOML [header]: %s", header_cfg)

        formatting_cfg = get_table_value(tool_cfg, "formatting")
        logger.trace("TOML [formatting]: %s", formatting_cfg)

        file_cfg = get_table_value(tool_cfg, "files")
        logger.trace("TOML [files]: %s", file_cfg)

        include_patterns = get_list_value(file_cfg, "include_patterns")
        include_from = get_list_value(file_cfg, "include_from")
        exclude_patterns = get_list_value(file_cfg, "exclude_patterns")
        exclude_from = get_list_value(file_cfg, "exclude_from")
        files_from = get_list_value(file_cfg, "files_from")

        # Coerce field values to strings, ignoring unsupported types with a warning
        field_values: dict[str, str] = {}
        for k, v in field_cfg.items():
            if isinstance(v, (str, int, float, bool)):
                field_values[k] = str(v)
            else:
                logger.warning("Ignoring unsupported field value for '%s': %r", k, v)

        header_fields = get_list_value(header_cfg, "fields")

        # # Fallback: if no explicit header field order is provided, use the keys of
        # # the field_values table in their declared order. This preserves intuitive
        # # behavior (headers render when values are present).
        # if not header_fields and field_values:
        #     header_fields = list(field_values.keys())

        # Parse relative_to path if present, resolve to absolute path
        relative_to_raw = get_string_value(tool_cfg, "relative_to")
        relative_to = Path(relative_to_raw).resolve() if relative_to_raw else None

        # align_fields = get_bool_value(formatting_cfg, "align_fields", True)
        align_fields = get_bool_value(
            formatting_cfg, "align_fields"
        )  # NOTE: do not set a default value if not set

        raw_header_format = get_string_value(
            formatting_cfg, "header_format"
        )  # NOTE: do not set a default value if not set
        if raw_header_format:
            try:
                header_format = HeaderOutputFormat(raw_header_format)
            except ValueError:
                valid_values = ", ".join(e.value for e in HeaderOutputFormat)
                logger.error(
                    "Invalid header format specifier found: %s (allowed values: %s)",
                    raw_header_format,
                    valid_values,
                )
                header_format = None
        else:
            # choose your default; this keeps behavior predictable
            header_format = None

        file_types = get_list_value(file_cfg, "file_types")
        file_type_set: set[str] = set(file_types) if file_types else set()
        if file_types and len(file_types) != len(file_type_set):
            logger.warning("Duplicate file types found in config: %s", ", ".join(file_types))

        return cls(
            config_files=[config_file] if config_file else [],
            field_values=field_values,
            header_fields=header_fields or [],
            align_fields=align_fields,
            header_format=header_format,
            relative_to_raw=relative_to_raw,
            relative_to=relative_to,
            stdin=False,  # Default to False unless explicitly set later -- TODO: False or None?
            include_patterns=include_patterns or [],
            include_from=include_from or [],
            exclude_patterns=exclude_patterns or [],
            exclude_from=exclude_from or [],
            files_from=files_from or [],
            file_types=file_type_set,
        )

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

        # Override include/exclude patterns and files if specified
        if args.get("include_patterns"):
            self.include_patterns = list(args["include_patterns"])
        if args.get("include_from"):
            self.include_from = list(args["include_from"])
        if args.get("exclude_patterns"):
            self.exclude_patterns = list(args["exclude_patterns"])
        if args.get("exclude_from"):
            self.exclude_from = list(args["exclude_from"])
        if args.get("files_from"):
            self.files_from = list(args["files_from"])

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

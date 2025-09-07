# topmark:header:start
#
#   file         : __init__.py
#   file_relpath : src/topmark/config/__init__.py
#   project      : TopMark
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

import functools
from dataclasses import dataclass, field
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping, TypeGuard

import toml

from topmark.config.logging import get_logger
from topmark.constants import DEFAULT_TOML_CONFIG_RESOURCE, VALUE_NOT_SET
from topmark.rendering.formats import HeaderOutputFormat

# ArgsLike: generic mapping accepted by config loaders (works for CLI namespaces and API dicts).
ArgsLike = Mapping[str, Any]
# We use ArgsLike (Mapping[str, Any]) instead of a CLI-specific namespace to
# keep the config layer decoupled from the CLI. The implementation uses .get()
# and key lookups, so Mapping is the right structural type. This allows the
# CLI to pass its namespace and the API/tests to pass plain dicts.

logger = get_logger(__name__)


@dataclass
class Config:
    """Represents the full configuration for the TopMark tool.

    This dataclass encapsulates all configuration options that can be loaded from TOML files,
    overridden by CLI arguments, or set programmatically. It supports merging multiple configuration
    layers, including defaults, project-specific config files, explicit config file overrides,
    and CLI argument overrides.
    Configuration entry points accept an ArgsLike mapping rather than a CLI-specific namespace.

    Attributes:
        timestamp (str): ISO-formatted timestamp when the Config instance was created.
        config_files (list[Path | str]): List of paths or identifiers for config sources used.
        header_fields (list[str]): List of header fields from the [header] section.
        field_values (dict[str, str]): Mapping of field names to their string values from [fields].
        align_fields (bool | None): Whether to align fields, from [formatting].
        raw_header (bool | None): Whether to use raw header formatting, from [formatting].
        relative_to (Path | None): Base path for relative file references, from [files].
        stdin (bool | None): Whether to read from stdin; requires explicit True to activate.
        files (list[str]): List of files to process.
        include_patterns (list[str]): Glob patterns to include.
        include_from (list[str]): Files containing include patterns.
        exclude_patterns (list[str]): Glob patterns to exclude.
        exclude_from (list[str]): Files containing exclude patterns.
        files_from (list[str]): Paths to files that list newline-delimited candidate file paths
            to add before filtering.
        file_types (list[str]): File extensions or types to process.
    """

    # Initialization timestamp for the config instance
    timestamp: str = datetime.now().isoformat()

    # Paths or identifiers of configuration files or sources used to build this Config
    config_files: list[Path | str] = field(default_factory=lambda: [])

    # Header configuration fields and their values
    header_fields: list[str] = field(default_factory=lambda: [])  # From [header].fields
    field_values: dict[str, str] = field(default_factory=lambda: {})  # From [fields]

    # Formatting options
    align_fields: bool | None = None  # From [formatting]
    # raw_header: bool | None = None  # From [formatting]
    header_format: HeaderOutputFormat | None = None

    # Base path for resolving relative file paths; from [files] section
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

    # File types (linked to file extensions) to process (filter)
    file_types: set[str] = field(default_factory=lambda: set[str]())

    @classmethod
    @functools.cache  # Cache result to avoid repeated file reads per run
    def get_default_config_toml(cls) -> str:
        """Retrieve the default configuration as a raw TOML string.

        Returns:
            str: The contents of the default TOML configuration file.
        """
        logger.debug("Loading defaults from package resource: %s", DEFAULT_TOML_CONFIG_RESOURCE)
        resource = files("topmark.config") / DEFAULT_TOML_CONFIG_RESOURCE
        return resource.read_text(encoding="utf-8")

    @classmethod
    def to_cleaned_toml(cls, toml_doc: str) -> str:
        """Return a cleaned TOML string with comments and extraneous whitespace removed.

        Args:
            toml_doc (str): The raw TOML document string.

        Returns:
            str: The cleaned TOML string.
        """
        # Parse the default config TOML and re-dump it to normalize formatting
        parsed = toml.loads(cls.get_default_config_toml())
        return toml.dumps(parsed)

    @classmethod
    def from_defaults(cls) -> "Config":
        """Load the default configuration from the bundled topmark-default.toml file.

        Returns:
            Config: A Config instance populated with default values.
        """
        resource = files("topmark.config") / DEFAULT_TOML_CONFIG_RESOURCE
        default_toml_text = resource.read_text(encoding="utf-8")
        default_toml_data = toml.loads(default_toml_text)
        logger.debug("Default Config: %s", default_toml_data)

        # Note: `config_file` is set to None because this is a package resource,
        # not a user-specified filesystem path.
        return cls.from_toml_dict(
            default_toml_data,
            config_file=None,
            use_defaults=True,  # We ONLY include defaults when loading from defaults!
        )

    @classmethod
    def from_toml_dict(
        cls,
        data: dict[str, Any],
        config_file: Path | None = None,
        use_defaults: bool = False,
    ) -> "Config":
        """Parse a dictionary representation of TOML data into a Config instance.

        Args:
            data (dict): The parsed TOML data as a dictionary.
            config_file (Path | None): Optional path to the source TOML file.
            use_defaults (bool): Whether to treat this data as default config (affects behavior).

        Returns:
            Config: The resulting Config instance.
        """

        # Type guard helpers to narrow down expected types
        def is_str_any_dict(val: Any) -> TypeGuard[dict[str, Any]]:
            return isinstance(val, dict)

        def is_any_list(val: Any) -> TypeGuard[list[Any]]:
            return isinstance(val, list)

        def get_table_value(table: dict[str, Any], key: str) -> dict[str, Any]:
            # Safely extract a sub-table (dict) from the TOML data
            value = table.get(key)
            if is_str_any_dict(value):
                return value
            return {}

        def get_string_value(table: dict[str, Any], key: str, default: str = "") -> str:
            # Coerce various types to string if possible; fallback to default
            value = table.get(key)
            if isinstance(value, str):
                return value
            elif isinstance(value, (int, float, bool)):
                return str(value)
            return default

        def get_bool_value(table: dict[str, Any], key: str, default: bool = False) -> bool:
            # Extract boolean value, coercing int to bool if needed
            value = table.get(key)
            if isinstance(value, bool):
                return value
            elif isinstance(value, int):
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

        # Parse relative_to path if present, resolve to absolute path
        relative_to_raw = get_string_value(tool_cfg, "relative_to")
        relative_to = Path(relative_to_raw).resolve() if relative_to_raw else None

        # align_fields = get_bool_value(formatting_cfg, "align_fields", True)
        align_fields = get_bool_value(
            formatting_cfg, "align_fields"
        )  # NOTE: do not set a default value if not set
        # raw_header = get_bool_value(formatting_cfg, "raw_header", False)

        raw_header_format = get_string_value(
            formatting_cfg, "header_format"
        )  # NOTE: do not set a default value if not set
        if raw_header_format:
            try:
                header_format = HeaderOutputFormat(raw_header_format)  # <-- parse by value
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

    def apply_cli_args(self, args: ArgsLike) -> "Config":
        """Update Config fields based on an arguments mapping (CLI or API).

        This method applies overrides from a parsed arguments mapping to the current
        Config instance. It does not handle flags that influence config file discovery
        (e.g., --no-config, --config).

        Args:
            args (ArgsLike): Parsed arguments mapping (from CLI or API).

        Returns:
            Config: The updated Config instance with CLI overrides applied.
        """
        logger.debug("Applying CLI arguments to Config: %s", args)

        # Use a special marker to indicate CLI overrides in config_files list
        CLI_OVERRIDE_STR = "<CLI overrides>"

        # Append or initialize config_files list with CLI override marker
        if self.config_files:
            self.config_files.append(CLI_OVERRIDE_STR)
        else:
            self.config_files = [CLI_OVERRIDE_STR]

        # Merge CLI config_files (config paths) if provided
        if "config_files" in args and args["config_files"]:
            self.config_files.extend(args["config_files"])

        # Override files to process if specified
        if "files" in args:
            self.files = args["files"]
            # If explicit files are given, force stdin to False (files take precedence)
            if self.files:
                self.stdin = False

        # Override include/exclude patterns and files if specified
        if "include_patterns" in args and args["include_patterns"]:
            self.include_patterns = args["include_patterns"]
        if "include_from" in args and args["include_from"]:
            self.include_from = args["include_from"]
        if "exclude_patterns" in args and args["exclude_patterns"]:
            self.exclude_patterns = args["exclude_patterns"]
        if "exclude_from" in args and args["exclude_from"]:
            self.exclude_from = args["exclude_from"]
        if "files_from" in args and args["files_from"]:
            self.files_from = args["files_from"]

        # Override relative_to path if specified, resolving to absolute path
        if "relative_to" in args and args["relative_to"]:
            self.relative_to_raw = args["relative_to"]
            self.relative_to = Path(args["relative_to"]).resolve()

        # Override file_types filter if specified
        if "file_types" in args and args["file_types"]:
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

        if (
            "align_fields" in args and args["align_fields"] is not None
        ):  # Only override if align_fields was passed via CLI
            self.align_fields = args["align_fields"]

        logger.debug("Patched Config: %s", self)
        logger.info("Applied CLI overrides to Config")
        logger.debug("apply_cli_args(): finalized stdin=%s files=%s", self.stdin, self.files)

        return self

    @classmethod
    def from_toml_file(cls, path: Path) -> "Config | None":
        """Load configuration from a single TOML file.

        This method reads the TOML file, extracts the relevant configuration section,
        and returns a Config instance. Supports both topmark.toml and pyproject.toml files,
        extracting the [tool.topmark] section from pyproject.toml.

        Args:
            path (Path): Path to the TOML file.

        Returns:
            Config | None: The Config instance if successful; None if required sections are missing.
        """
        logger.debug("Creating Config from TOML config: %s", path)

        # Load the TOML file content once (removed redundant second call)
        data = toml.load(path)

        if path.name == "pyproject.toml":
            # Extract [tool.topmark] subsection from pyproject.toml
            tool_section: dict[str, Any] = data.get("tool", {}).get("topmark", {})
            if not tool_section:
                logger.error(f"[tool.topmark] section missing or malformed in {path}")
                return None
            else:
                data = tool_section

        config = cls.from_toml_dict(data)
        config.config_files = [path]
        logger.debug("Generated Config: %s", config)
        return config

    @classmethod
    def load_merged(cls, args: ArgsLike) -> "Config":
        """Load and merge configuration layers into a single Config instance.

        The merging order is:
        1. Defaults (bundled topmark-default.toml)
        2. Project config (topmark.toml or pyproject.toml), unless suppressed by --no-config
        3. Additional config files specified via --config (in order)
        4. CLI overrides applied last

        Args:
            args (ArgsLike): Parsed arguments mapping (from CLI or API).

        Returns:
            Config: The final merged Config instance.
        """
        config = cls.from_defaults()
        logger.info("Initialized config from defaults")

        # Load local project config unless disabled by --no-config flag
        if not args.get("no_config"):
            for local_toml_file in ["topmark.toml", "pyproject.toml"]:
                local_toml = Path(local_toml_file)
                if local_toml.exists():
                    logger.info("Loading local config from: %s", local_toml)
                    local_config = cls.from_toml_file(local_toml)
                    if local_config:
                        config = config.merge_with(local_config)
                    # Stop after first found local config file
                    break

        # Process additional config files passed via CLI/API
        # Accept both strings and Path objects from CLI or API callers.
        entries: list[str | Path] = args.get("config_files", [])
        for entry in entries:
            p: Path | None = None
            if isinstance(entry, Path):
                p = entry
            else:  # isinstance(entry, str):
                p = Path(entry)

            logger.debug(
                "Adding config file '%s' (type=%s)",
                entry,
                type(entry).__name__,
            )

            if p.exists():
                logger.info("Loading config override from: %s", p)
                extra_config = cls.from_toml_file(p)
                if extra_config:
                    config = config.merge_with(extra_config)
            else:
                logger.debug("Config file does not exist: %s", p)

        # Apply CLI argument overrides last to ensure precedence
        config = config.apply_cli_args(args)

        logger.debug("Final merged config: %s", config)
        return config

    def merge_with(self, other: "Config") -> "Config":
        """Merge another Config instance into this one, returning a new merged Config.

        Values from `other` override those from `self` if explicitly set.
        For lists, non-empty lists from `other` replace those in `self`.

        Args:
            other (Config): The Config instance to merge from.

        Returns:
            Config: A new Config instance resulting from merging `other` into `self`.
        """
        logger.trace(
            "Overriding header_format: %r -> %r",
            self.header_format.value if self.header_format else VALUE_NOT_SET,
            other.header_format.value if other.header_format else VALUE_NOT_SET,
        )
        logger.trace("Overriding align_fields: %r -> %r", self.align_fields, other.align_fields)

        # Combine config file lists to keep track of all sources
        merged_config_files = self.config_files + other.config_files

        return Config(
            timestamp=self.timestamp,
            # Update the list of config files
            config_files=merged_config_files,
            # Use other's field_values if non-empty, else fall back to self's
            field_values=other.field_values or self.field_values,
            # Override header fields if other's list is non-empty
            header_fields=other.header_fields or self.header_fields,
            # For boolean flags, use other's value if not None, else self's
            align_fields=(
                other.align_fields if other.align_fields is not None else self.align_fields
            ),
            header_format=(
                other.header_format if other.header_format is not None else self.header_format
            ),
            stdin=other.stdin if other.stdin is not None else self.stdin,
            # For lists, override only if other's list is non-empty
            files=other.files or self.files,
            include_patterns=other.include_patterns or self.include_patterns,
            include_from=other.include_from or self.include_from,
            exclude_patterns=other.exclude_patterns or self.exclude_patterns,
            exclude_from=other.exclude_from or self.exclude_from,
            files_from=other.files_from or self.files_from,
            # Use other's relative_to if set, else self's
            relative_to_raw=(
                other.relative_to_raw if other.relative_to_raw is not None else self.relative_to_raw
            ),
            relative_to=(other.relative_to if other.relative_to is not None else self.relative_to),
            # Use other's file_types if set, else self's
            file_types=other.file_types or self.file_types,
        )

    def to_toml_dict(self) -> dict[str, Any]:
        """Convert the Config instance into a dictionary suitable for TOML serialization.

        Returns:
            dict: Dictionary representing the config, structured for TOML output.
        """
        # Compose the config as a nested dictionary structure matching TOML layout
        return {
            "fields": dict(self.field_values),
            "header": {
                "fields": list(self.header_fields),
            },
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
            # The following fields are intentionally omitted from TOML output:
            # "stdin": self.stdin,
            # "files": list(self.files),
            # "config_files": list(self.config_files) if self.config_files else [],
            # "timestamp": self.timestamp,
        }

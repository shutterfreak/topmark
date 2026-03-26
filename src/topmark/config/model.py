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
      dedicated modules (e.g.,
      [`topmark.config.io.resolution`][topmark.config.io.resolution] and
      [`topmark.config.io.loaders`][topmark.config.io.loaders])
      to keep this model import-light and avoid import cycles.

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

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from topmark.config.keys import Toml
from topmark.config.policy import MutablePolicy
from topmark.config.policy import Policy
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.core.logging import get_logger
from topmark.diagnostic.model import DiagnosticLog
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import FrozenDiagnosticLog
from topmark.diagnostic.model import compute_diagnostic_stats
from topmark.utils.timestamp import get_utc_now

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from pathlib import Path

    from topmark.config.types import PatternSource
    from topmark.core.logging import TopmarkLogger
    from topmark.filetypes.model import FileType


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

    Layered merging with clear precedence is provided by `load_resolved_config()`.

    Attributes:
        timestamp: Timestamp when the Config instance was created.
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
        relative_to_raw: Original string from config or CLI
        relative_to: Base path used only for header metadata (e.g., file_relpath).
            Note: Glob expansion and filtering are resolved relative to their declaring source
            (config file dir or CWD for CLI), not relative_to.
        stdin_mode: Whether to read from stdin; requires explicit True to activate.
        stdin_filename: File name to use when reading file contents from stdin (used when building
            headers).
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
    timestamp: datetime

    # Runtime intent: whether to actually write changes (apply) or preview only
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

    # Header formatting
    align_fields: bool | None

    # Header formatting: base path resolution
    relative_to_raw: str | None
    relative_to: Path | None

    # File processing options
    stdin_mode: bool | None
    stdin_filename: str | None
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
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            stdin_mode=self.stdin_mode,
            stdin_filename=self.stdin_filename,
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


def sanitized_config(config: Config) -> Config:
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
        timestamp: Timestamp when the MutableConfig instance was created.
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
        relative_to_raw: Original string from config or CLI
        relative_to: Base path used only for resolving header metadata (e.g., `file_relpath`).
        stdin_mode: Whether to read from stdin; requires explicit True to activate.
        stdin_filename: File name to use when reading file contents from stdin (used when building
            headers).
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
    timestamp: datetime = field(default_factory=get_utc_now)

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

    # Header formatting
    align_fields: bool | None = None

    # Header formatting: base path resolution
    relative_to_raw: str | None = None  # original string from config or CLI
    relative_to: Path | None = None  # resolved version (used at runtime)

    # File processing options
    stdin_mode: bool | None = None  # Explicit True required to enable reading from stdin
    stdin_filename: str | None = None

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
            raise ValueError("Policy invalid: `add_only` and `update_only` cannot both be True.")

        # Resolve per-type policies against the resolved global policy
        frozen_by_type: dict[str, Policy] = {}
        for ft, mp in self.policy_by_type.items():
            resolved: Policy = mp.resolve(global_policy_frozen)
            if resolved.add_only and resolved.update_only:
                raise ValueError(
                    f"Policy invalid for type '{ft}': "
                    "`add_only` and `update_only` cannot both be True."
                )
            frozen_by_type[ft] = resolved

        # Set strict_config_checking to True only if self.strict_config_checking === True
        strict_config_checking = bool(self.strict_config_checking)

        return Config(
            timestamp=self.timestamp,
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
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            stdin_mode=self.stdin_mode,
            stdin_filename=self.stdin_filename,
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
            header_fields=other.header_fields or self.header_fields,
            relative_to_raw=other.relative_to_raw
            if other.relative_to_raw is not None
            else self.relative_to_raw,
            relative_to=other.relative_to if other.relative_to is not None else self.relative_to,
            field_values=other.field_values or self.field_values,
            align_fields=other.align_fields
            if other.align_fields is not None
            else self.align_fields,
            stdin_mode=other.stdin_mode if other.stdin_mode is not None else self.stdin_mode,
            files=other.files or self.files,
            include_patterns=other.include_patterns or self.include_patterns,
            include_from=other.include_from or self.include_from,
            exclude_patterns=other.exclude_patterns or self.exclude_patterns,
            exclude_from=other.exclude_from or self.exclude_from,
            files_from=other.files_from or self.files_from,
            include_file_types=other.include_file_types or self.include_file_types,
            exclude_file_types=other.exclude_file_types or self.exclude_file_types,
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
                    self.diagnostics.add_warning(msg)
                    continue
                kept.append(ps)

            if len(kept) != len(sources):
                msg = (
                    f"Sanitized {name}: kept {len(kept)} source(s), "
                    f"dropped {len(sources) - len(kept)} invalid source(s)"
                )
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
            from topmark.registry.filetypes import FileTypeRegistry

            # Validate against the effective file type registry:
            ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()

            unknown: list[str] = sorted(t for t in ids if t not in ft_registry)
            if not unknown:
                return

            unknown_str: str = ", ".join(unknown)
            if is_exclusion:
                msg: str = f"Unknown excluded file types specified (ignored): {unknown_str}"
            else:
                msg = f"Unknown included file types specified (ignored): {unknown_str}"

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
                self.diagnostics.add_info(msg)
            elif self.output_target != OutputTarget.STDOUT:
                msg = (
                    f"STDIN mode: Setting {Toml.KEY_TARGET} "
                    f"from {self.output_target.key} ({self.output_target.label}) "
                    f"to {OutputTarget.STDOUT.key} ({OutputTarget.STDOUT.label})"
                )
                self.diagnostics.add_warning(msg)

            self.output_target = OutputTarget.STDOUT

            if self.file_write_strategy is not None:
                msg = (
                    f"STDIN mode: Clearing file_write_strategy "
                    f"(was: {self.file_write_strategy.key} ({self.file_write_strategy.label}))"
                )
                self.diagnostics.add_warning(msg)

            self.file_write_strategy = None

        # Validate the policy flags
        self._validate_policy_flags()

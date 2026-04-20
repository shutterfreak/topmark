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
    - `Config`: an immutable layered configuration snapshot used by processing
      steps.
    - `MutableConfig`: a mutable builder used during discovery/merge; it can
      be frozen into `Config` and thawed back for edits.

Scope:
    - *In scope*: data shapes, defaulting rules at the field level, merge policy
      (`MutableConfig.merge_with`), and freeze/thaw mechanics.
    - *Out of scope*: filesystem discovery, TOML I/O, and whole-source TOML
      schema validation. Those belong in dedicated modules to keep this model
      import-light and avoid import cycles, e.g.:
      - TOML document handling
        - [`topmark.toml.resolution`][topmark.toml.resolution]
        - [`topmark.config.resolution`][topmark.config.resolution]
      - Layered config handling:
        - [`topmark.toml.loaders`][topmark.toml.loaders]

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

from topmark.config.policy import MutablePolicy
from topmark.config.policy import Policy
from topmark.config.validation import ValidationLogs
from topmark.core.errors import ConfigValidationError
from topmark.core.logging import get_logger
from topmark.diagnostic.model import DiagnosticLog
from topmark.diagnostic.model import DiagnosticStats
from topmark.diagnostic.model import FrozenDiagnosticLog
from topmark.diagnostic.model import compute_diagnostic_stats
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.config.types import PatternGroup
    from topmark.config.types import PatternSource
    from topmark.config.validation import FrozenValidationLogs
    from topmark.core.logging import TopmarkLogger
    from topmark.filetypes.model import FileType


logger: TopmarkLogger = get_logger(__name__)


# ------------------ Immutable layered config ------------------


@dataclass(frozen=True, slots=True)
class Config:
    """Immutable layered configuration for TopMark.

    This snapshot is produced by `MutableConfig.freeze` after merging defaults, project files, extra
    config files, and config-like API overrides. Collections are immutable (``tuple``/``frozenset``)
    to prevent accidental mutation during processing. Use `Config.thaw` to obtain a mutable builder
    for edits, and `MutableConfig.freeze` to return to an immutable layered snapshot.

    Layered merging with clear precedence is provided by the config-resolution helpers in
    [topmark.config.resolution][topmark.config.resolution].

    Attributes:
        policy: Global, resolved, immutable runtime policy (plain booleans),
            applied after discovery.
        policy_by_type: Per-file-type resolved policy overrides
            (plain booleans), applied after discovery.
        config_files: List of paths or identifiers for config sources used.
        header_fields: List of header fields from the [header] section.
        field_values: Mapping of field names to their string values
            from [fields].
        align_fields: Whether to align fields, from [formatting].
        relative_to_raw: Original string from config, API or CLI.
        relative_to: Base path used only for header metadata (e.g., file_relpath).
            Note: Glob expansion and filtering are resolved relative to their declaring source
            (config file dir or CWD for CLI), not relative_to.
        files: List of files to process.
        include_from: Files containing include patterns.
        exclude_from: Files containing exclude patterns.
        files_from: Paths to files that list newline-delimited candidate
            file paths to add before filtering.
        include_pattern_groups: Glob patterns to include.
        exclude_pattern_groups: Glob patterns to exclude.
        include_file_types: Whitelist of file type identifiers to restrict
            file discovery.
        exclude_file_types: Blacklist of file type identifiers to exclude from
            file discovery.
        validation_logs: Stage-aware diagnostics collected during config
            loading and preflight validation.
        diagnostics: Flattened compatibility view of `validation_logs` used by
            existing validation and reporting code during the staged-refactor
            transition.

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

    # Policy containers
    policy: Policy
    policy_by_type: Mapping[str, Policy]  # e.g., {"python": Policy(...)}

    # Provenance
    config_files: tuple[Path | str, ...]

    # Header configuration
    header_fields: tuple[str, ...]
    field_values: Mapping[str, str]

    # Header formatting
    align_fields: bool | None

    # Header formatting: base path resolution
    relative_to_raw: str | None
    relative_to: Path | None

    # File processing options
    files: tuple[str, ...]

    include_from: tuple[PatternSource, ...]
    exclude_from: tuple[PatternSource, ...]
    files_from: tuple[PatternSource, ...]

    include_pattern_groups: tuple[PatternGroup, ...]
    exclude_pattern_groups: tuple[PatternGroup, ...]

    # File types (linked to file extensions) to process (filter)
    include_file_types: frozenset[str]
    exclude_file_types: frozenset[str]

    # Collected diagnostics while loading / merging / sanitizing config.
    validation_logs: FrozenValidationLogs
    diagnostics: FrozenDiagnosticLog

    def is_valid(
        self,
        *,
        strict: bool | None = None,
    ) -> bool:
        """Return whether this config is valid.

        A config is valid when it has no error diagnostics. In strict mode, a
        config is valid only when it has neither error diagnostics nor warning
        diagnostics.

        Here, `strict` is the effective resolved strictness used for
        config/preflight validation. Callers typically derive it from
        `strict_config_checking` after applying TOML resolution and any CLI/API
        override precedence.

        A similar helper exists on `MutableConfig`.

        Args:
            strict: Effective strictness for config/preflight validation.

        Returns:
            `True` if the config is valid, else `False`.
        """
        return _is_config_valid(self, strict=strict)

    def ensure_valid(
        self,
        *,
        strict: bool | None = None,
    ) -> None:
        """Raise `ConfigValidationError` if this config is not valid.

        A config is valid when it has no error diagnostics. In strict mode, a
        config is valid only when it has neither error diagnostics nor warning
        diagnostics.

        Here, `strict` is the effective resolved strictness used for
        config/preflight validation. Callers typically derive it from
        `strict_config_checking` after applying TOML resolution and any CLI/API
        override precedence.

        A similar helper exists on `MutableConfig`.

        Args:
            strict: Effective strictness for config/preflight validation.

        Raises:
            ConfigValidationError: If the config is invalid.
        """
        if not self.is_valid(strict=strict):
            raise ConfigValidationError(
                diagnostics=self.diagnostics,
                strict_config_checking=strict,
            )

    def thaw(self) -> MutableConfig:
        """Return a mutable copy of this frozen config.

        Symmetry:
            Mirrors `MutableConfig.freeze`. Prefer thaw→edit→freeze rather
            than mutating a runtime `Config`.

        Returns:
            A mutable builder initialized from this snapshot.
        """
        validation_logs: ValidationLogs = self.validation_logs.thaw()
        return MutableConfig(
            policy=self.policy.thaw(),
            policy_by_type={k: v.thaw() for k, v in self.policy_by_type.items()},
            config_files=list(self.config_files),
            header_fields=list(self.header_fields),
            field_values=dict(self.field_values),
            align_fields=self.align_fields,
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            files=list(self.files),
            include_from=list(self.include_from),
            exclude_from=list(self.exclude_from),
            include_pattern_groups=list(self.include_pattern_groups),
            exclude_pattern_groups=list(self.exclude_pattern_groups),
            files_from=list(self.files_from),
            include_file_types=set(self.include_file_types),
            exclude_file_types=set(self.exclude_file_types),
            validation_logs=validation_logs,
            diagnostics=validation_logs.flattened(),
        )


def sanitized_config(config: Config) -> Config:
    """Sanitize a Config object.

    Thaws the Config into a MutableConfig, sanitizes and freezes again.

    Sanitization may add diagnostics, and those diagnostics participate in later
    config/preflight validity checks.

    Args:
        config: The Config to sanitize.

    Returns:
        The sanitized Config instance.
    """
    m: MutableConfig = config.thaw()
    m.sanitize()
    return m.freeze()


# -------------------------- Mutable layered builder --------------------------


@dataclass
class MutableConfig:
    """Mutable configuration used during discovery and merging.

    This builder collects layered config from defaults, project files, extra files,
    and config-like API overrides. It remains convenient to mutate (``list``/``set``),
    then produces an immutable `Config` via `freeze`. TOML I/O is delegated to
    [`topmark.config.io`][topmark.config.io] to keep this class focused on merge policy.

    Attributes:
        policy: Optional global policy overrides (public shape).
        policy_by_type: Optional per-type policy.
        config_files: List of paths or identifiers for config sources used.
        header_fields: List of header fields from the [header] section.
        field_values: Mapping of field names to their string values from [fields].
        align_fields: Whether to align fields, from [formatting].
        relative_to_raw: Original string from config or CLI
        relative_to: Base path used only for resolving header metadata (e.g., `file_relpath`).
        files: List of files to process.
        include_from: Files containing include patterns.
        exclude_from: Files containing exclude patterns.
        files_from: Paths to files that list newline-delimited
            candidate file paths to add before filtering.
        include_pattern_groups: Glob patterns to include.
        exclude_pattern_groups: Glob patterns to exclude.
        include_file_types: file type identifiers to process.
        exclude_file_types: file type identifiers to exclude.
        validation_logs: Stage-aware diagnostics collected during config
            loading and preflight validation.
        diagnostics: Flattened compatibility view of `validation_logs` used by
            existing validation and reporting code during the staged-refactor
            transition.
    """

    # Policy containers:
    policy: MutablePolicy = field(default_factory=MutablePolicy)
    policy_by_type: dict[str, MutablePolicy] = field(default_factory=lambda: {})

    # Provenance
    config_files: list[Path | str] = field(default_factory=lambda: [])

    # Header configuration
    header_fields: list[str] = field(default_factory=lambda: [])
    field_values: dict[str, str] = field(default_factory=lambda: {})

    # Header formatting
    align_fields: bool | None = None

    # Header formatting: base path resolution
    relative_to_raw: str | None = None  # original string from config or CLI
    relative_to: Path | None = None  # resolved version (used at runtime)

    # File processing options
    files: list[str] = field(default_factory=lambda: [])

    include_from: list[PatternSource] = field(default_factory=lambda: [])
    exclude_from: list[PatternSource] = field(default_factory=lambda: [])
    files_from: list[PatternSource] = field(default_factory=lambda: [])

    include_pattern_groups: list[PatternGroup] = field(default_factory=lambda: [])
    exclude_pattern_groups: list[PatternGroup] = field(default_factory=lambda: [])

    # File types filter
    include_file_types: set[str] = field(default_factory=lambda: set[str]())
    exclude_file_types: set[str] = field(default_factory=lambda: set[str]())

    # Collected diagnostics while loading / merging / sanitizing config.
    validation_logs: ValidationLogs = field(default_factory=ValidationLogs)
    diagnostics: DiagnosticLog = field(default_factory=DiagnosticLog)

    def refresh_diagnostics(self) -> None:
        """Refresh the flattened compatibility diagnostics from staged logs.

        During the staged-validation refactor, `validation_logs` is the
        structured source of truth and `diagnostics` remains a derived,
        flattened compatibility view for existing callers.
        """
        self.diagnostics = self.validation_logs.flattened()

    def is_valid(
        self,
        *,
        strict: bool | None = None,
    ) -> bool:
        """Return whether this mutable config is valid.

        A mutable config is valid when it has no error diagnostics. In strict
        mode, a mutable config is valid only when it has neither error
        diagnostics nor warning diagnostics.

        Here, `strict` is the effective resolved strictness used for
        config/preflight validation. Callers typically derive it from
        `strict_config_checking` after applying TOML resolution and any CLI/API
        override precedence.

        A similar helper exists on `Config`.

        Args:
            strict: Effective strictness for config/preflight validation.

        Returns:
            `True` if the mutable config is valid, else `False`.
        """
        return _is_config_valid(self, strict=strict)

    def ensure_valid(
        self,
        *,
        strict: bool | None = None,
    ) -> None:
        """Raise `ConfigValidationError` if this mutable config is not valid.

        A mutable config is valid when it has no error diagnostics. In strict
        mode, a mutable config is valid only when it has neither error
        diagnostics nor warning diagnostics.

        Here, `strict` is the effective resolved strictness used for
        config/preflight validation. Callers typically derive it from
        `strict_config_checking` after applying TOML resolution and any CLI/API
        override precedence.

        A similar helper exists on `Config`.

        Args:
            strict: Effective strictness for config/preflight validation.

        Raises:
            ConfigValidationError: If the mutable config is invalid.
        """
        if not self.is_valid(strict=strict):
            raise ConfigValidationError(
                diagnostics=self.diagnostics,
                strict_config_checking=strict,
            )

    # ---------------------------- Build/freeze ----------------------------

    def freeze(self) -> Config:
        """Freeze this mutable builder into an immutable Config.

        This method applies final sanitation and normalizes internal container
        types before constructing the immutable `Config` snapshot.
        """
        self.sanitize()

        # Resolve global policy against an all-false base
        global_policy_frozen: Policy = self.policy.resolve(Policy())

        # Resolve per-type policies against the resolved global policy
        frozen_by_type: dict[str, Policy] = {}
        for ft, mp in self.policy_by_type.items():
            resolved: Policy = mp.resolve(global_policy_frozen)
            frozen_by_type[ft] = resolved

        # Derive the flattened compatibility diagnostics from the merged staged logs.
        self.refresh_diagnostics()

        return Config(
            policy=global_policy_frozen,
            policy_by_type=frozen_by_type,
            config_files=tuple(self.config_files),
            header_fields=tuple(self.header_fields),
            field_values=dict(self.field_values),
            align_fields=self.align_fields,
            relative_to_raw=self.relative_to_raw,
            relative_to=self.relative_to,
            files=tuple(self.files),
            include_from=tuple(self.include_from),
            exclude_from=tuple(self.exclude_from),
            files_from=tuple(self.files_from),
            include_pattern_groups=tuple(self.include_pattern_groups),
            exclude_pattern_groups=tuple(self.exclude_pattern_groups),
            include_file_types=frozenset(self.include_file_types),
            exclude_file_types=frozenset(self.exclude_file_types),
            validation_logs=self.validation_logs.freeze(),
            diagnostics=self.diagnostics.freeze(),
        )

    # ------------------------------- Merging -------------------------------

    def merge_with(self, other: MutableConfig) -> MutableConfig:
        """Return a new draft that merges ``self`` with a higher-precedence ``other`` draft.

        Merge behavior is field-specific rather than uniformly "last wins". The
        current policy follows TopMark's layered-config mental model:

        - provenance and diagnostics **accumulate**
        - behavioral/configuration fields usually use **nearest-wins** semantics
        - mapping fields usually **overlay keys**
        - discovery pattern groups **accumulate** across layers
        - runtime/execution intent is out of scope for layered config merging

        Current merge groups:
            Provenance and diagnostics:
                - `config_files`: append
                - `validation_logs`: append within each validation stage
                - `diagnostics`: derived flattened compatibility view of merged `validation_logs`

            Behavioral config:
                - `header_fields`: replace when `other` provides a non-empty list
                - `align_fields`: replace only when explicitly set in `other`
                - `relative_to_raw`, `relative_to`: replace only when explicitly set in `other`

            Policy:
                - `policy`: tri-state field merge via `MutablePolicy.merge_with()`
                - `policy_by_type`: key-wise merge, then tri-state merge per key

            Field values:
                - `field_values`: key-wise overlay; `other` wins on overlapping keys

            Discovery inputs:
                - `include_pattern_groups`, `exclude_pattern_groups`: append
                - `include_from`, `exclude_from`, `files_from`: append
                - `files`: replace when `other` provides a non-empty list

            Discovery filters:
                - `include_file_types`, `exclude_file_types`: replace when `other`
                  provides a non-empty set

        Args:
            other: Higher-precedence config whose values should be merged on top
                of this draft.

        Returns:
            A new mutable configuration representing the merged result.
        """
        # --------------------------- Provenance and policies ---------------------------
        # Merge global policy using tri-state semantics so explicit child values override
        # matching parent values without collapsing `None` too early.
        merged_global: MutablePolicy = self.policy.merge_with(other.policy)

        # Merge per-type policies key-wise, then tri-state merge per shared key.
        merged_by_type: dict[str, MutablePolicy] = {}
        all_policy_keys: set[str] = set(self.policy_by_type.keys()) | set(
            other.policy_by_type.keys()
        )
        for key in all_policy_keys:
            base: MutablePolicy | None = self.policy_by_type.get(key)
            override: MutablePolicy | None = other.policy_by_type.get(key)
            if base is None:
                if override is not None:
                    merged_by_type[key] = override
            elif override is None:
                merged_by_type[key] = base
            else:
                merged_by_type[key] = base.merge_with(override)

        # Provenance accumulates across layers. Validation diagnostics also
        # accumulate, but remain separated by stage so the flattened
        # compatibility log can be derived afterward.
        merged_config_files: list[Path | str] = [*self.config_files, *other.config_files]

        merged_validation_logs: ValidationLogs = self.validation_logs.merge_with(
            other.validation_logs
        )

        # Derive the flattened compatibility diagnostics from the merged staged logs.
        merged_diags: DiagnosticLog = merged_validation_logs.flattened()

        # ------------------------ Behavioral config ------------------------
        merged_header_fields: list[str] = other.header_fields or self.header_fields
        merged_align_fields: bool | None = (
            other.align_fields if other.align_fields is not None else self.align_fields
        )
        merged_relative_to_raw: str | None = (
            other.relative_to_raw if other.relative_to_raw is not None else self.relative_to_raw
        )
        merged_relative_to: Path | None = (
            other.relative_to if other.relative_to is not None else self.relative_to
        )

        # ----------------------------- Mapping-style overlays ----------------------------
        # Field values use key-wise overlay semantics: unrelated parent keys remain
        # inherited while matching child keys override.
        merged_field_values: dict[str, str] = {
            **self.field_values,
            **other.field_values,
        }

        # -------------------------------- Discovery inputs -------------------------------
        # Discovery pattern groups always accumulate across applicable layers.
        merged_include_pattern_groups: list[PatternGroup] = [
            *self.include_pattern_groups,
            *other.include_pattern_groups,
        ]
        merged_exclude_pattern_groups: list[PatternGroup] = [
            *self.exclude_pattern_groups,
            *other.exclude_pattern_groups,
        ]

        # Path-to-file discovery sources now accumulate across layers as well.
        merged_include_from: list[PatternSource] = [*self.include_from, *other.include_from]
        merged_exclude_from: list[PatternSource] = [*self.exclude_from, *other.exclude_from]
        merged_files_from: list[PatternSource] = [*self.files_from, *other.files_from]

        # Explicit file lists remain authoritative: nearest applicable non-empty list wins.
        merged_files: list[str] = other.files or self.files

        # File-type filters express a nearest-scope decision rather than a union.
        merged_include_file_types: set[str] = other.include_file_types or self.include_file_types
        merged_exclude_file_types: set[str] = other.exclude_file_types or self.exclude_file_types

        logger.info(
            "Merging config layers: adding %r to existing config_files %r",
            other.config_files,
            self.config_files,
        )

        merged = MutableConfig(
            config_files=merged_config_files,
            validation_logs=merged_validation_logs,
            diagnostics=merged_diags,
            header_fields=merged_header_fields,
            field_values=merged_field_values,
            align_fields=merged_align_fields,
            relative_to_raw=merged_relative_to_raw,
            relative_to=merged_relative_to,
            files=merged_files,
            include_from=merged_include_from,
            exclude_from=merged_exclude_from,
            files_from=merged_files_from,
            include_pattern_groups=merged_include_pattern_groups,
            exclude_pattern_groups=merged_exclude_pattern_groups,
            include_file_types=merged_include_file_types,
            exclude_file_types=merged_exclude_file_types,
        )

        merged.policy = merged_global
        merged.policy_by_type = merged_by_type
        return merged

    def sanitize(self) -> None:
        """Normalize and sanitize draft config in-place.

        This step enforces downstream invariants expected by config resolution,
        runtime processing, and related components such as the file resolver,
        pipeline, and CLI. It is intended to be called just before freezing into
        an immutable `Config`.

        Sanitization may drop or rewrite invalid entries and records diagnostics
        describing those recoveries. During the staged-validation refactor,
        these diagnostics are part of the runtime-applicability validation
        stage and continue to participate in config/preflight validity checks,
        including strict config checking. The flattened compatibility
        diagnostics are refreshed after sanitization completes.

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
                    self.validation_logs.runtime_applicability.add_warning(msg)
                    continue
                kept.append(ps)

            if len(kept) != len(sources):
                msg = (
                    f"Sanitized {name}: kept {len(kept)} source(s), "
                    f"dropped {len(sources) - len(kept)} invalid source(s)"
                )
                self.validation_logs.runtime_applicability.add_warning(msg)

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

            self.validation_logs.runtime_applicability.add_warning(msg)
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
            self.validation_logs.runtime_applicability.add_warning(msg)
            # Remove overlaps (blacklisted wins from whitelisted):
            self.include_file_types.difference_update(overlap)

        # Derive the flattened compatibility diagnostics from the merged staged logs.
        self.refresh_diagnostics()


# ---- Helpers ----


def _is_config_valid(
    cfg: Config | MutableConfig,
    *,
    strict: bool | None = None,
) -> bool:
    """Return whether a config-like object is valid.

    A config is valid when it has no error diagnostics. In strict mode, a
    config is valid only when it has neither error diagnostics nor warning
    diagnostics.

    The flattened compatibility log may include replayed TOML validation
    issues, merged-config diagnostics, and runtime-applicability
    sanitization warnings.

    Here, `strict` represents the effective resolved strictness for
    config/preflight validation, typically derived from
    `strict_config_checking` after TOML resolution and any CLI/API override.

    Args:
        cfg: Frozen or mutable config carrying diagnostics.
        strict: Effective strictness for config/preflight validation.

    Returns:
        `True` if the config is valid, else `False`.
    """
    strict_config_checking = bool(strict)
    stats: DiagnosticStats = compute_diagnostic_stats(cfg.diagnostics)
    if strict_config_checking:
        return stats.n_error == 0 and stats.n_warning == 0
    else:
        return stats.n_error == 0

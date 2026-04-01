# topmark:header:start
#
#   project      : TopMark
#   file         : policy.py
#   file_relpath : src/topmark/config/policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Policy model for TopMark (global and per-file-type).

This module defines the *policy layer* used to control run intent and safety
rules, both globally and with per-file-type overrides.

Design:
    * `MutablePolicy` uses tri-state options (`bool | None` / `Enum | None`) to
      represent explicit values versus *unset*. This enables non-destructive
      merges and inheritance when composing multiple sources
      (defaults -> user -> project -> CLI).
    * `Policy` is the fully resolved, immutable runtime view with plain values,
      so pipeline steps do not branch on `None`.
    * `MutablePolicy.resolve(base)` fills unset fields from `base` and returns a
      frozen `Policy`; use it at `Config.freeze()` time.

TOML mapping:

    ```toml
    [policy]
    header_mutation_mode = "all"
    allow_header_in_empty_files = false
    empty_insert_mode = "logical_empty"
    allow_content_probe = true

    [policy_by_type.python]
    allow_header_in_empty_files = true
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from typing import Protocol

from topmark.core.merge import opt_bool
from topmark.core.merge import opt_enum
from topmark.core.merge import overlay
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from collections.abc import Mapping


class HeaderMutationMode(str, Enum):
    """Defines how headers may be mutated.

    Attributes:
        ALL: Process all files (default).
        ADD_ONLY: Only add headers when no header present.
        UPDATE_ONLY: Only update existing headers.
    """

    ALL = "all"
    ADD_ONLY = "add_only"
    UPDATE_ONLY = "update_only"


class EmptyInsertMode(str, Enum):
    """How TopMark classifies “empty” inputs for header insertion.

    The selected mode determines which files count as “empty” when evaluating
    `Policy.allow_header_in_empty_files`.

    Attributes:
        BYTES_EMPTY: Only true 0-byte files (`FsStatus.EMPTY`).
        LOGICAL_EMPTY: 0-byte files plus logically-empty placeholders
            (optional BOM, optional horizontal whitespace, and at most one
            trailing newline).
        WHITESPACE_EMPTY: 0-byte files plus any effectively-empty decoded image
            (no non-whitespace characters; whitespace/newlines allowed).
    """

    BYTES_EMPTY = "bytes_empty"
    LOGICAL_EMPTY = "logical_empty"
    WHITESPACE_EMPTY = "whitespace_empty"


@dataclass(frozen=True, slots=True)
class Policy:
    """Immutable, runtime policy used by processing steps.

    Attributes:
        header_mutation_mode: Defines how headers may be mutated: process all files if (`ALL`,
            default); only add headers when no header present (ADD_ONLY); only update existing
            headers (`UPDATE_ONLY`).
        allow_header_in_empty_files: Allow inserting headers into files that are
            classified as empty under `empty_insert_mode`.
        empty_insert_mode: Defines which files are considered “empty” for
            insertion policy (`bytes_empty`, `logical_empty`, or `whitespace_empty`).
        render_empty_header_when_no_fields: Allow inserting an otherwise empty
            header when no fields are configured.
        allow_reflow: Allow reflowing file content when inserting a header.
            Enabling this can break check/strip idempotence.
        allow_content_probe: Whether the resolver may consult file contents
            during file-type detection. `True` allows content-based probes;
            `False` forces name/extension-only resolution.
    """

    header_mutation_mode: HeaderMutationMode = HeaderMutationMode.ALL
    allow_header_in_empty_files: bool = False
    empty_insert_mode: EmptyInsertMode = EmptyInsertMode.LOGICAL_EMPTY
    render_empty_header_when_no_fields: bool = False
    allow_reflow: bool = False
    # Whether resolver may perform content-based probes during file-type detection
    allow_content_probe: bool = True

    def thaw(self) -> MutablePolicy:
        """Return a mutable builder initialized from this frozen policy.

        Returns:
            A tri-state mutable policy.
        """
        return MutablePolicy(
            header_mutation_mode=self.header_mutation_mode,
            allow_header_in_empty_files=self.allow_header_in_empty_files,
            empty_insert_mode=self.empty_insert_mode,
            render_empty_header_when_no_fields=self.render_empty_header_when_no_fields,
            allow_reflow=self.allow_reflow,
            allow_content_probe=self.allow_content_probe,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize this resolved policy to a TOML-friendly dictionary.

        Returns:
            Dictionary containing primitive TOML-serializable values.

        Notes:
            This is an export helper for documentation, machine payloads, and config rendering.
            Resolved `Policy` instances always emit all fields.
        """
        return policy_to_dict(self)


@dataclass
class MutablePolicy:
    """Mutable builder for `Policy`, suitable for config loading/merging.

    This class is merged in a **last-wins** manner when reading multiple config files.

    Attributes:
        header_mutation_mode: See `Policy`. `None` means "inherit".
        allow_header_in_empty_files: See `Policy`. `None` means "inherit".
        empty_insert_mode: See `Policy`. `None` means "inherit".
        render_empty_header_when_no_fields: See `Policy`. `None` means "inherit".
        allow_reflow: See `Policy`. `None` means "inherit".
        allow_content_probe: See `Policy`. `None` means "inherit".
    """

    header_mutation_mode: HeaderMutationMode | None = None
    allow_header_in_empty_files: bool | None = None
    empty_insert_mode: EmptyInsertMode | None = None
    render_empty_header_when_no_fields: bool | None = None
    allow_reflow: bool | None = None
    allow_content_probe: bool | None = None

    def merge_with(self, other: MutablePolicy) -> MutablePolicy:
        """Return a new MutablePolicy by applying ``other`` over ``self`` (last-wins).

        ``None`` fields in ``other`` do not override explicit values in ``self``.

        Args:
            other: The policy whose values override current ones.

        Returns:
            Merged policy.
        """
        return MutablePolicy(
            header_mutation_mode=overlay(
                override=other.header_mutation_mode,
                current=self.header_mutation_mode,
            ),
            allow_header_in_empty_files=overlay(
                override=other.allow_header_in_empty_files,
                current=self.allow_header_in_empty_files,
            ),
            empty_insert_mode=overlay(
                override=other.empty_insert_mode,
                current=self.empty_insert_mode,
            ),
            render_empty_header_when_no_fields=overlay(
                override=other.render_empty_header_when_no_fields,
                current=self.render_empty_header_when_no_fields,
            ),
            allow_reflow=overlay(
                override=other.allow_reflow,
                current=self.allow_reflow,
            ),
            allow_content_probe=overlay(
                override=other.allow_content_probe,
                current=self.allow_content_probe,
            ),
        )

    def resolve(self, base: Policy) -> Policy:
        """Resolve tri-state fields against a base frozen policy.

        Args:
            base: Base policy that provides defaults for unset fields.

        Returns:
            A fully-resolved immutable policy with plain booleans.
        """
        return Policy(
            header_mutation_mode=(
                base.header_mutation_mode
                if self.header_mutation_mode is None
                else self.header_mutation_mode
            ),
            allow_header_in_empty_files=(
                base.allow_header_in_empty_files
                if self.allow_header_in_empty_files is None
                else self.allow_header_in_empty_files
            ),
            empty_insert_mode=(
                base.empty_insert_mode if self.empty_insert_mode is None else self.empty_insert_mode
            ),
            render_empty_header_when_no_fields=(
                base.render_empty_header_when_no_fields
                if self.render_empty_header_when_no_fields is None
                else self.render_empty_header_when_no_fields
            ),
            allow_reflow=base.allow_reflow if self.allow_reflow is None else self.allow_reflow,
            allow_content_probe=(
                base.allow_content_probe
                if self.allow_content_probe is None
                else self.allow_content_probe
            ),
        )

    def freeze(self) -> Policy:
        """Freeze to a concrete `Policy` using the built-in policy defaults.

        Returns:
            Fully resolved immutable policy.

        Notes:
            This is equivalent to resolving against `Policy()`.
        """
        return self.resolve(Policy())

    @classmethod
    def from_toml_table(cls, tbl: Mapping[str, object] | None) -> MutablePolicy:
        """Create a MutablePolicy from a TOML table.

        Unspecified keys remain `None` so they can inherit from the base policy during `resolve()`.

        Args:
            tbl: TOML table mapping for `[policy]` or `[policy_by_type.<name>]`.

        Returns:
            Parsed mutable policy.
        """
        if not tbl:
            return cls()

        return cls(
            header_mutation_mode=opt_enum(
                tbl,
                key=Toml.KEY_POLICY_HEADER_MUTATION_MODE,
                enum_cls=HeaderMutationMode,
            ),
            allow_header_in_empty_files=opt_bool(
                tbl,
                key=Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES,
            ),
            empty_insert_mode=opt_enum(
                tbl,
                key=Toml.KEY_POLICY_EMPTIES_INSERT_MODE,
                enum_cls=EmptyInsertMode,
            ),
            render_empty_header_when_no_fields=opt_bool(
                tbl,
                key=Toml.KEY_POLICY_ALLOW_EMPTY_HEADER,
            ),
            allow_reflow=opt_bool(
                tbl,
                key=Toml.KEY_POLICY_ALLOW_REFLOW,
            ),
            allow_content_probe=opt_bool(
                tbl,
                key=Toml.KEY_POLICY_ALLOW_CONTENT_PROBE,
            ),
        )


def policy_to_dict(policy: Policy) -> dict[str, object]:
    """Serialize a resolved or tri-state policy to a TOML-friendly dictionary.

    Args:
        policy: Frozen Policy object.

    Returns:
        Dictionary containing all policy fields as TOML-friendly primitives. Enum values are
        serialized via `.value`.
    """
    out: dict[str, object] = {}
    out[Toml.KEY_POLICY_HEADER_MUTATION_MODE] = policy.header_mutation_mode.value  # StrEnum
    out[Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES] = policy.allow_header_in_empty_files
    out[Toml.KEY_POLICY_EMPTIES_INSERT_MODE] = policy.empty_insert_mode.value  # StrEnum
    out[Toml.KEY_POLICY_ALLOW_EMPTY_HEADER] = policy.render_empty_header_when_no_fields
    out[Toml.KEY_POLICY_ALLOW_REFLOW] = policy.allow_reflow
    out[Toml.KEY_POLICY_ALLOW_CONTENT_PROBE] = policy.allow_content_probe
    return out


class HasPolicyConfig(Protocol):
    """Read-only view of resolved policy configuration.

    This protocol captures the *minimum* surface required by helpers like `make_policy_registry`
    and `effective_policy`.

    It intentionally avoids importing the concrete
    [`Config`][topmark.config.model.Config] / [`MutableConfig`][topmark.config.model.MutableConfig]
    classes to prevent type-check-time import cycles.

    Implementations are expected to expose *resolved* runtime policies:
      - `policy` is a fully resolved `Policy`
      - `policy_by_type` maps file-type identifiers to resolved per-type `Policy`

    Attributes are defined as read-only properties so both frozen `Config` and mutable builders
    can satisfy the protocol.
    """

    @property
    def policy(self) -> Policy:
        """Resolved global policy."""
        ...

    @property
    def policy_by_type(self) -> Mapping[str, Policy]:
        """Mapping of file-type identifiers to resolved per-type policies."""
        ...


@dataclass(frozen=True, slots=True)
class PolicyRegistry:
    """Immutable registry of effective policies per file type.

    Instances of this class are derived from a resolved Config and provide constant-time lookup of
    the effective Policy to apply for a given file type.
    """

    global_policy: Policy
    by_type: Mapping[str, Policy]

    def for_type(self, name: str | None) -> Policy:
        """Return the effective policy for the given file-type name.

        Args:
            name: File type name, or None for the global/default case.

        Returns:
            The resolved per-type policy if present; otherwise the global policy.
        """
        if name is None:
            return self.global_policy
        return self.by_type.get(name, self.global_policy)


def make_policy_registry(config: HasPolicyConfig) -> PolicyRegistry:
    """Build an immutable PolicyRegistry from a resolved Config-like object."""
    return PolicyRegistry(
        global_policy=config.policy,
        by_type=config.policy_by_type,
    )


def effective_policy(cfg: HasPolicyConfig, file_type_id: str | None) -> Policy:
    r"""Return the effective policy for a given file type.

    Per-type overrides take precedence over the global policy. If `file_type_id` is `None` or
    no per-type policy exists for that identifier, the global policy is returned.

    This helper assumes that both `cfg.policy` and entries in `cfg.policy_by_type` are already
    fully resolved `Policy` instances (that is, no tri-state inheritance remains at runtime).

    Args:
        cfg: Resolved runtime configuration.
        file_type_id: File type identifier (for example, `"python"`).

    Returns:
        Effective policy to use for processing.
    """
    if file_type_id is None:
        return cfg.policy

    override: Policy | None = cfg.policy_by_type.get(file_type_id)
    if override is not None:
        return override
    return cfg.policy

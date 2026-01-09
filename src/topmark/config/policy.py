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

This module defines the **policy layer** used to control run intent and safety
rules, both globally and with per-file-type overrides.

Design:
    * ``MutablePolicy`` uses tri-state options (``bool | None``) to represent
      explicit True/False vs. *unset*. This enables non-destructive merges and
      inheritance when composing multiple sources (defaults → user → project → CLI).
    * ``Policy`` is the fully-resolved, immutable runtime view with plain
      booleans, so pipeline steps do not need to branch on ``None``.
    * ``MutablePolicy.resolve(base)`` fills unset fields from ``base`` and returns
      a frozen ``Policy``; use it at ``Config.freeze()`` time.

TOML mapping:

TOML mapping:

    ```toml
    [policy]
    add_only = false
    update_only = false
    allow_header_in_empty_files = false
    allow_content_probe = true  # allow resolver to inspect file contents when detecting types

    [policy_by_type.python]
    allow_header_in_empty_files = true
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.config.model import Config


@dataclass(frozen=True, slots=True)
class Policy:
    """Immutable, runtime policy used by processing steps.

    Attributes:
        add_only (bool): Only add missing headers; do not update existing ones.
        update_only (bool): Only update existing headers; do not add new ones.
        allow_header_in_empty_files (bool): Allow inserting headers in empty files
            (e.g., `__init__.py`).
        render_empty_header_when_no_fields (bool): Allow inserting empty headers when
            no fields are defined.
        allow_reflow (bool): If True, allow revlowing file content when inserting a header.
            This potentially breaks check/strip idempotence.
        allow_content_probe (bool): Whether the resolver may consult file contents
            during file-type detection. True allows content-based probes, False
            forces name/extension-only resolution.

    Notes:
    - `Policy` holds plain booleans and is fully resolved at runtime (no tri-state).
      Steps never branch on `None` here.
    - allow_content_probe controls only the resolver's type-detection behaviour. It does
      not affect SnifferStep/ReaderStep, which may still read bytes or text to
      enforce encoding, BOM/shebang, and newline policies.
    """

    add_only: bool = False
    update_only: bool = False
    allow_header_in_empty_files: bool = False
    render_empty_header_when_no_fields: bool = False
    allow_reflow: bool = False
    # Whether resolver may perform content-based probes during file-type detection
    allow_content_probe: bool = True

    def thaw(self) -> MutablePolicy:
        """Return a mutable builder initialized from this frozen policy.

        Returns:
            MutablePolicy: A tri-state mutable policy.
        """
        return MutablePolicy(
            add_only=self.add_only,
            update_only=self.update_only,
            allow_header_in_empty_files=self.allow_header_in_empty_files,
            render_empty_header_when_no_fields=self.render_empty_header_when_no_fields,
            allow_reflow=self.allow_reflow,
            allow_content_probe=self.allow_content_probe,
        )


@dataclass
class MutablePolicy:
    """Mutable builder for `Policy`, suitable for config loading/merging.

    This class is merged in a **last-wins** manner when reading multiple config files.

    Attributes:
        add_only (bool | None): See `Policy`. `None` means "inherit".
        update_only (bool | None): See `Policy`. `None` means "inherit".
        allow_header_in_empty_files (bool | None): See `Policy`. `None` means "inherit".
        render_empty_header_when_no_fields (bool | None): See `Policy`. `None` means "inherit".
        allow_reflow (bool | None): See `Policy`. `None` means "inherit".
        allow_content_probe (bool | None): See `Policy`. `None` means "inherit".
    """

    add_only: bool | None = None
    update_only: bool | None = None
    allow_header_in_empty_files: bool | None = None
    render_empty_header_when_no_fields: bool | None = None
    allow_reflow: bool | None = None
    allow_content_probe: bool | None = None

    def merge_with(self, other: MutablePolicy) -> MutablePolicy:
        """Return a new MutablePolicy by applying ``other`` over ``self`` (last-wins).

        ``None`` fields in ``other`` do not override explicit values in ``self``.

        Args:
            other (MutablePolicy): The policy whose values override current ones.

        Returns:
            MutablePolicy: Merged policy.
        """

        def pick(*, current: bool | None, override: bool | None) -> bool | None:
            return override if override is not None else current

        return MutablePolicy(
            add_only=pick(override=other.add_only, current=self.add_only),
            update_only=pick(override=other.update_only, current=self.update_only),
            allow_header_in_empty_files=pick(
                override=other.allow_header_in_empty_files, current=self.allow_header_in_empty_files
            ),
            render_empty_header_when_no_fields=pick(
                override=other.render_empty_header_when_no_fields,
                current=self.render_empty_header_when_no_fields,
            ),
            allow_reflow=pick(override=other.allow_reflow, current=self.allow_reflow),
            allow_content_probe=pick(
                override=other.allow_content_probe, current=self.allow_content_probe
            ),
        )

    def resolve(self, base: Policy) -> Policy:
        """Resolve tri-state fields against a base frozen policy.

        Args:
            base (Policy): Base policy that provides defaults for unset fields.

        Returns:
            Policy: A fully-resolved immutable policy with plain booleans.
        """
        return Policy(
            add_only=(base.add_only if self.add_only is None else self.add_only),
            update_only=(base.update_only if self.update_only is None else self.update_only),
            allow_header_in_empty_files=(
                base.allow_header_in_empty_files
                if self.allow_header_in_empty_files is None
                else self.allow_header_in_empty_files
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
        """Freeze to a concrete `Policy` using default ``False`` for unset fields.

        This is equivalent to resolving against an all-false base policy.
        """
        return self.resolve(Policy())

    @classmethod
    def from_toml_table(cls, tbl: Mapping[str, Any] | None) -> MutablePolicy:
        """Create a MutablePolicy from a TOML table mapping.

        Unspecified keys become ``None`` (inherit from base at freeze time).

        Args:
            tbl (Mapping[str, Any] | None): Table with keys matching the attributes.

        Returns:
            MutablePolicy: Parsed policy.
        """
        if not tbl:
            return cls()

        def pick(key: str) -> bool | None:
            return None if key not in tbl else bool(tbl[key])

        return cls(
            add_only=pick("add_only"),
            update_only=pick("update_only"),
            allow_header_in_empty_files=pick("allow_header_in_empty_files"),
            render_empty_header_when_no_fields=pick("render_empty_header_when_no_fields"),
            allow_reflow=pick("allow_reflow"),
            allow_content_probe=pick("allow_content_probe"),
        )

    def to_toml_table(self) -> dict[str, Any]:
        """Serialize only explicitly set keys to a TOML-friendly dict.

        Returns:
            dict[str, Any]: Table with primitive types only.
        """
        out: dict[str, Any] = {}
        if self.add_only is not None:
            out["add_only"] = self.add_only
        if self.update_only is not None:
            out["update_only"] = self.update_only
        if self.allow_header_in_empty_files is not None:
            out["allow_header_in_empty_files"] = self.allow_header_in_empty_files
        if self.render_empty_header_when_no_fields is not None:
            out["render_empty_header_when_no_fields"] = self.render_empty_header_when_no_fields
        if self.allow_reflow is not None:
            out["allow_reflow"] = self.allow_reflow
        if self.allow_content_probe is not None:
            out["allow_content_probe"] = self.allow_content_probe
        return out


@dataclass(frozen=True, slots=True)
class PolicyRegistry:
    """Immutable registry of effective policies per file type.

    Instances of this class are derived from a resolved Config and
    provide constant-time lookup of the effective Policy to apply for
    a given file type.
    """

    global_policy: Policy
    by_type: Mapping[str, Policy]

    def for_type(self, name: str | None) -> Policy:
        """Return the effective policy for the given file-type name.

        Args:
            name (str | None): File type name, or None for the global/default case.

        Returns:
            Policy: The resolved per-type policy if present; otherwise
            the global policy.
        """
        if name is None:
            return self.global_policy
        return self.by_type.get(name, self.global_policy)


def make_policy_registry(config: Config) -> PolicyRegistry:
    """Build a PolicyRegistry from a resolved Config."""
    return PolicyRegistry(
        global_policy=config.policy,
        by_type=config.policy_by_type,
    )


def effective_policy(cfg: Config, file_type_id: str | None) -> Policy:
    r"""Return the effective policy for a given file type.

    Per-type overrides take precedence over the global policy. If ``file_type_id``
    is ``None`` or no per-type policy is present for the given identifier, the
    global policy is returned.

    This helper assumes that both ``cfg.policy`` (global) and any entries in
    ``cfg.policy_by_type`` are already fully resolved ``Policy`` instances
    (no tri-state fields). In other words, inheritance of per-type overrides
    against the global policy must happen at configuration freeze time via
    ``MutablePolicy.resolve``.

    Args:
        cfg (Config): Frozen runtime configuration.
        file_type_id (str | None): File type identifier (e.g., ``"python"``).

    Returns:
        Policy: The effective policy to use for processing.
    """
    if file_type_id is None:
        return cfg.policy

    override: Policy | None = cfg.policy_by_type.get(file_type_id)
    if override is not None:
        return override
    return cfg.policy

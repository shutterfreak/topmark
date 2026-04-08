# topmark:header:start
#
#   project      : TopMark
#   file         : test_policy_resolution.py
#   file_relpath : tests/config/test_policy_resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for TopMark policy resolution and merging.

These tests exercise the interaction between:

* `MutablePolicy` (tri-state builder)
* `Policy` (fully-resolved runtime view)
* `MutableConfig.merge_with` (policy merge semantics)
* `MutableConfig.freeze` (inheritance from global → per-type)
* `effective_policy` (runtime selection without further merging)
* `apply_config_overrides` (structured policy override application)

The goal is to ensure that:

* Global policy is resolved once at freeze time.
* Per-file-type policies are resolved *on top of* the global policy.
* `effective_policy` is a simple selector (no thaw/resolve at runtime).
* `header_mutation_mode` is resolved and preserved correctly.
"""

from __future__ import annotations

from dataclasses import fields
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_layered_toml_table
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import PolicyOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import HeaderMutationMode
from topmark.config.policy import MutablePolicy
from topmark.config.policy import Policy
from topmark.config.policy import effective_policy

if TYPE_CHECKING:
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.toml.types import TomlTable


def _assert_policy_fields(
    pol: Policy,
    *,
    header_mutation_mode: HeaderMutationMode,
    allow_content_probe: bool,
) -> None:
    """Helper to assert core Policy fields used in these tests.

    Args:
        pol: Resolved policy instance to inspect.
        header_mutation_mode: Expected header-mutation mode.
        allow_content_probe: Expected allow-content-probe flag.
    """
    assert pol.header_mutation_mode == header_mutation_mode
    assert pol.allow_content_probe is allow_content_probe


def test_global_policy_only_resolves_correctly() -> None:
    """Global MutablePolicy resolves into a fully-concrete Policy."""
    mc: MutableConfig = mutable_config_from_defaults()
    # Override only a subset of fields; others inherit defaults.
    mc.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,
        allow_content_probe=False,
    )

    cfg: Config = mc.freeze()
    global_pol: Policy = cfg.policy

    # Global policy should reflect explicit overrides.
    _assert_policy_fields(
        global_pol,
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,
        allow_content_probe=False,
    )
    # No per-type overrides by default.
    assert cfg.policy_by_type == {}


def test_per_type_override_inherits_global_policy() -> None:
    """Per-type policy inherits unspecified fields from the resolved global policy."""
    mc: MutableConfig = mutable_config_from_defaults()
    # Global: header_mutation_mode=ADD_ONLY, allow_content_probe=False
    mc.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,
        allow_content_probe=False,
    )
    # Python: override allow_content_probe only, inherit header_mutation_mode
    mc.policy_by_type = {
        "python": MutablePolicy(
            allow_content_probe=True,
        ),
    }

    cfg: Config = mc.freeze()
    global_pol: Policy = cfg.policy
    py_pol: Policy = cfg.policy_by_type["python"]

    # Global policy: explicit overrides respected.
    _assert_policy_fields(
        global_pol,
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,
        allow_content_probe=False,
    )

    # Per-type policy: inherits header_mutation_mode, overrides allow_content_probe.
    _assert_policy_fields(
        py_pol,
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,  # inherited
        allow_content_probe=True,  # override
    )


def test_effective_policy_prefers_per_type_over_global() -> None:
    """effective_policy should select per-type policy when available."""
    mc: MutableConfig = mutable_config_from_defaults()
    mc.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,
        allow_content_probe=False,
    )
    mc.policy_by_type = {
        "python": MutablePolicy(
            allow_content_probe=True,
        ),
    }

    cfg: Config = mc.freeze()
    global_pol: Policy = cfg.policy
    py_pol: Policy = cfg.policy_by_type["python"]

    # No type → global
    assert effective_policy(cfg, None) is global_pol

    # Known type → per-type override
    assert effective_policy(cfg, "python") is py_pol

    # Unknown type → fall back to global
    assert effective_policy(cfg, "unknown") is global_pol


def test_mutable_config_policy_merge_global_and_per_type() -> None:
    """MutableConfig.merge_with delegates policy merging to MutablePolicy.merge_with.

    This test validates the tri-state merge behavior on the mutable layer only.
    The merged config is intentionally *not* frozen, because policy resolution
    is covered by dedicated tests below.
    """
    base: MutableConfig = mutable_config_from_defaults()
    base.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,
    )
    base.policy_by_type = {
        "python": MutablePolicy(
            header_mutation_mode=HeaderMutationMode.ADD_ONLY,
        ),
    }

    override: MutableConfig = mutable_config_from_defaults()
    override.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.UPDATE_ONLY,
    )
    override.policy_by_type = {
        "python": MutablePolicy(
            header_mutation_mode=HeaderMutationMode.UPDATE_ONLY,
        ),
        "markdown": MutablePolicy(
            allow_content_probe=False,
        ),
    }

    merged: MutableConfig = base.merge_with(override)

    # Global policy (tri-state) should have both flags set at this stage.
    assert merged.policy.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY

    # Per-type "python" should also see last-wins per field.
    py_mut: MutablePolicy = merged.policy_by_type["python"]
    assert py_mut.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY

    # Per-type "markdown" should be taken as-is from override.
    md_mut: MutablePolicy = merged.policy_by_type["markdown"]
    assert md_mut.allow_content_probe is False


def test_mutable_config_policy_by_type_merge_preserves_unrelated_parent_keys() -> None:
    """policy_by_type should merge by key instead of replacing the whole mapping."""
    base: MutableConfig = mutable_config_from_defaults()
    base.policy_by_type = {
        "python": MutablePolicy(header_mutation_mode=HeaderMutationMode.ADD_ONLY),
    }

    override: MutableConfig = mutable_config_from_defaults()
    override.policy_by_type = {
        "markdown": MutablePolicy(allow_content_probe=False),
    }

    merged: MutableConfig = base.merge_with(override)

    assert set(merged.policy_by_type.keys()) == {"python", "markdown"}
    assert merged.policy_by_type["python"].header_mutation_mode == HeaderMutationMode.ADD_ONLY
    assert merged.policy_by_type["markdown"].allow_content_probe is False


def test_freeze_resolves_global_header_mutation_mode() -> None:
    """freeze() must preserve an explicit global header-mutation mode."""
    mc: MutableConfig = mutable_config_from_defaults()
    mc.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.UPDATE_ONLY,
    )

    cfg: Config = mc.freeze()
    assert cfg.policy.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY


def test_freeze_resolves_per_type_header_mutation_mode() -> None:
    """freeze() must preserve an explicit per-type header-mutation mode."""
    mc: MutableConfig = mutable_config_from_defaults()
    mc.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.ALL,
    )
    mc.policy_by_type = {
        "python": MutablePolicy(
            header_mutation_mode=HeaderMutationMode.UPDATE_ONLY,
        ),
    }

    cfg: Config = mc.freeze()
    assert cfg.policy_by_type["python"].header_mutation_mode == HeaderMutationMode.UPDATE_ONLY


def test_policy_loaded_from_toml_tables() -> None:
    """TOML-shaped dicts must hydrate MutableConfig and resolve Policy correctly.

    This test ensures that `[policy]` and `[policy_by_type.*]` TOML tables are
    parsed into `MutableConfig`, then frozen into a `Config` where:

    * `cfg.policy` reflects global policy fields from `[policy]`, and
    * `cfg.policy_by_type["python"]` inherits unset fields from the global
      policy while applying per-type overrides.
    """
    toml_root: TomlTable = {
        "policy": {
            "header_mutation_mode": "add_only",
            "allow_content_probe": False,
        },
        "policy_by_type": {
            "python": {
                "allow_header_in_empty_files": True,
            },
        },
    }
    mc: MutableConfig = mutable_config_from_layered_toml_table(toml_root)
    cfg: Config = mc.freeze()

    # Global values from [policy]
    assert cfg.policy.header_mutation_mode == HeaderMutationMode.ADD_ONLY
    assert cfg.policy.allow_content_probe is False

    # Per-type inherits + overrides
    py_pol: Policy = cfg.policy_by_type["python"]
    assert py_pol.header_mutation_mode == HeaderMutationMode.ADD_ONLY  # inherited
    assert py_pol.allow_content_probe is False  # inherited
    assert py_pol.allow_header_in_empty_files is True  # override


def test_policy_precedence_across_merged_configs() -> None:
    """Merged configs must apply last-wins precedence before policy resolution.

    This test simulates a typical precedence chain:

        defaults < project config < local override

    and verifies that:

    * The merged global `MutablePolicy` reflects last-wins semantics before
      `freeze()`.
    * Per-type policies inherit from the resolved global policy while layering
      per-type overrides from multiple sources.
    """
    base: MutableConfig = mutable_config_from_defaults()
    project: MutableConfig = mutable_config_from_defaults()
    project.policy = MutablePolicy(header_mutation_mode=HeaderMutationMode.ADD_ONLY)
    project.policy_by_type = {"python": MutablePolicy(allow_content_probe=False)}

    local: MutableConfig = mutable_config_from_defaults()
    local.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.UPDATE_ONLY,
    )
    local.policy_by_type = {"python": MutablePolicy(allow_header_in_empty_files=True)}

    merged: MutableConfig = base.merge_with(project).merge_with(local)
    cfg: Config = merged.freeze()

    # Global: local overrides project
    assert cfg.policy.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY

    # Python per-type: local overrides project but still inherits from global
    py_pol: Policy = cfg.policy_by_type["python"]
    assert py_pol.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY  # from global
    assert py_pol.allow_content_probe is False  # from project per-type
    assert py_pol.allow_header_in_empty_files is True  # from local per-type


def test_apply_config_overrides_updates_global_policy_fields() -> None:
    """Structured global policy overrides must patch the mutable config policy."""
    mc: MutableConfig = mutable_config_from_defaults()

    apply_config_overrides(
        mc,
        ConfigOverrides(
            policy=PolicyOverrides(
                header_mutation_mode=HeaderMutationMode.UPDATE_ONLY,
                allow_header_in_empty_files=True,
                render_empty_header_when_no_fields=True,
                allow_reflow=True,
                allow_content_probe=False,
            ),
        ),
    )

    assert mc.policy.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY
    assert mc.policy.allow_header_in_empty_files is True
    assert mc.policy.render_empty_header_when_no_fields is True
    assert mc.policy.allow_reflow is True
    assert mc.policy.allow_content_probe is False


def test_apply_config_overrides_updates_per_type_policy_fields() -> None:
    """Structured per-type policy overrides must patch `policy_by_type` entries."""
    mc: MutableConfig = mutable_config_from_defaults()
    mc.policy = MutablePolicy(
        header_mutation_mode=HeaderMutationMode.ADD_ONLY,
        allow_content_probe=True,
    )

    apply_config_overrides(
        mc,
        ConfigOverrides(
            policy_by_type={
                "python": PolicyOverrides(
                    header_mutation_mode=HeaderMutationMode.UPDATE_ONLY,
                    allow_header_in_empty_files=True,
                    allow_content_probe=False,
                ),
            },
        ),
    )

    py_mut: MutablePolicy = mc.policy_by_type["python"]
    assert py_mut.header_mutation_mode == HeaderMutationMode.UPDATE_ONLY
    assert py_mut.allow_header_in_empty_files is True
    assert py_mut.allow_content_probe is False


def test_apply_config_overrides_noop_policy_still_leaves_runtime_policy_unchanged() -> None:
    """An empty `PolicyOverrides` object must not change resolved policy values."""
    mc: MutableConfig = mutable_config_from_defaults()
    before: Config = mc.freeze()

    apply_config_overrides(
        mc,
        ConfigOverrides(),
    )

    after: Config = mc.freeze()
    assert after.policy == before.policy
    assert after.policy_by_type == before.policy_by_type


def test_policy_and_mutable_policy_field_sets_are_in_sync() -> None:
    """Policy and MutablePolicy must expose the same set of field names.

    This guards against drift between the frozen and mutable policy
    representations: adding a new field to one without updating the other
    will cause this test to fail.
    """
    policy_fields: set[str] = {f.name for f in fields(Policy)}
    mutable_fields: set[str] = {f.name for f in fields(MutablePolicy)}
    assert policy_fields == mutable_fields


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("header_mutation_mode", HeaderMutationMode.ADD_ONLY),
        ("allow_header_in_empty_files", True),
        ("empty_insert_mode", EmptyInsertMode.WHITESPACE_EMPTY),
        ("render_empty_header_when_no_fields", True),
        ("allow_reflow", True),
        ("allow_content_probe", False),  # default is True, so flip it
    ],
)
def test_policy_thaw_resolve_roundtrip_preserves_field(
    field_name: str,
    value: HeaderMutationMode | EmptyInsertMode | bool,
) -> None:
    """Each Policy field must survive a thaw() + resolve() round-trip.

    For every parametrized field, this test constructs a Policy override,
    calls `thaw()` to obtain a MutablePolicy, resolves it against a fresh
    default Policy, and verifies that the explicit override value is
    preserved in the resolved result.
    """
    base_default = Policy()
    pol: Policy = replace(base_default, **{field_name: value})

    mp: MutablePolicy = pol.thaw()
    resolved: Policy = mp.resolve(Policy())  # resolve against a fresh default Policy

    resolved_value = getattr(resolved, field_name)
    if isinstance(value, bool):
        assert resolved_value is value
    else:
        assert resolved_value == value


@pytest.mark.parametrize(
    ("field_name", "base_val", "override_val", "expected"),
    [
        (
            "header_mutation_mode",
            HeaderMutationMode.ADD_ONLY,
            None,
            HeaderMutationMode.ADD_ONLY,
        ),
        (
            "header_mutation_mode",
            HeaderMutationMode.ADD_ONLY,
            HeaderMutationMode.UPDATE_ONLY,
            HeaderMutationMode.UPDATE_ONLY,
        ),
        (
            "empty_insert_mode",
            EmptyInsertMode.LOGICAL_EMPTY,
            None,
            EmptyInsertMode.LOGICAL_EMPTY,
        ),
        (
            "empty_insert_mode",
            EmptyInsertMode.LOGICAL_EMPTY,
            EmptyInsertMode.WHITESPACE_EMPTY,
            EmptyInsertMode.WHITESPACE_EMPTY,
        ),
        ("allow_content_probe", True, None, True),
        ("allow_content_probe", True, False, False),
    ],
)
def test_mutable_policy_merge_with_per_field(
    field_name: str,
    base_val: HeaderMutationMode | EmptyInsertMode | bool | None,
    override_val: HeaderMutationMode | EmptyInsertMode | bool | None,
    expected: HeaderMutationMode | EmptyInsertMode | bool | None,
) -> None:
    """MutablePolicy.merge_with must honor last-wins semantics per field.

    The parametrization exercises representative combinations of base and
    override values for selected fields and asserts that the merged policy
    reflects the expected tri-state (bool | None) outcome.
    """
    base = MutablePolicy()
    override = MutablePolicy()
    setattr(base, field_name, base_val)
    setattr(override, field_name, override_val)

    merged: MutablePolicy = base.merge_with(override)
    merged_value = getattr(merged, field_name)
    if isinstance(expected, bool) or expected is None:
        assert merged_value is expected
    else:
        assert merged_value == expected

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

* `MutablePolicy` (tri-state builder: `bool | None`)
* `Policy` (fully-resolved runtime view)
* `MutableConfig.merge_with` (policy merge semantics)
* `MutableConfig.freeze` (inheritance from global → per-type)
* `effective_policy` (runtime selection without further merging)

The goal is to ensure that:

* Global policy is resolved once at freeze time.
* Per-file-type policies are resolved *on top of* the global policy.
* `effective_policy` is a simple selector (no thaw/resolve at runtime).
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

import pytest

from topmark.config import Config, MutableConfig
from topmark.config.policy import MutablePolicy, Policy, effective_policy


def _assert_policy_fields(
    pol: Policy,
    *,
    add_only: bool,
    update_only: bool,
    allow_content_probe: bool,
) -> None:
    """Helper to assert core Policy fields used in these tests.

    Args:
        pol: Resolved policy instance to inspect.
        add_only: Expected add-only flag.
        update_only: Expected update-only flag.
        allow_content_probe: Expected allow-content-probe flag.
    """
    assert pol.add_only is add_only
    assert pol.update_only is update_only
    assert pol.allow_content_probe is allow_content_probe


def test_global_policy_only_resolves_correctly() -> None:
    """Global MutablePolicy resolves into a fully-concrete Policy."""
    mc: MutableConfig = MutableConfig.from_defaults()
    # Override only a subset of fields; others inherit defaults.
    mc.policy = MutablePolicy(
        add_only=True,
        allow_content_probe=False,
    )

    cfg: Config = mc.freeze()
    global_pol: Policy = cfg.policy

    # Global policy should reflect explicit overrides.
    _assert_policy_fields(
        global_pol,
        add_only=True,
        update_only=False,
        allow_content_probe=False,
    )
    # No per-type overrides by default.
    assert cfg.policy_by_type == {}


def test_per_type_override_inherits_global_policy() -> None:
    """Per-type policy inherits unspecified fields from the resolved global policy."""
    mc: MutableConfig = MutableConfig.from_defaults()
    # Global: add_only=True, allow_content_probe=False
    mc.policy = MutablePolicy(
        add_only=True,
        allow_content_probe=False,
    )
    # Python: override allow_content_probe only, inherit add_only/update_only
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
        add_only=True,
        update_only=False,
        allow_content_probe=False,
    )

    # Per-type policy: inherits add_only/update_only, overrides allow_content_probe.
    _assert_policy_fields(
        py_pol,
        add_only=True,  # inherited
        update_only=False,  # inherited
        allow_content_probe=True,  # override
    )


def test_effective_policy_prefers_per_type_over_global() -> None:
    """effective_policy should select per-type policy when available."""
    mc: MutableConfig = MutableConfig.from_defaults()
    mc.policy = MutablePolicy(
        add_only=True,
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
    The merged config is intentionally *not* frozen, because a conflicting
    combination (add_only=True and update_only=True) must be rejected by
    `MutableConfig.freeze`, which is covered by dedicated tests below.
    """
    base: MutableConfig = MutableConfig.from_defaults()
    base.policy = MutablePolicy(add_only=True)  # base global: add_only=True
    base.policy_by_type = {
        "python": MutablePolicy(
            add_only=True,
        ),
    }

    override: MutableConfig = MutableConfig.from_defaults()
    override.policy = MutablePolicy(update_only=True)  # override global: update_only=True
    override.policy_by_type = {
        "python": MutablePolicy(
            update_only=True,
        ),
        "markdown": MutablePolicy(
            allow_content_probe=False,
        ),
    }

    merged: MutableConfig = base.merge_with(override)

    # Global policy (tri-state) should have both flags set at this stage.
    assert merged.policy.add_only is True
    assert merged.policy.update_only is True

    # Per-type "python" should also see last-wins per field.
    py_mut: MutablePolicy = merged.policy_by_type["python"]
    assert py_mut.add_only is True
    assert py_mut.update_only is True

    # Per-type "markdown" should be taken as-is from override.
    md_mut: MutablePolicy = merged.policy_by_type["markdown"]
    assert md_mut.allow_content_probe is False


def test_freeze_rejects_conflicting_global_policy() -> None:
    """freeze() must reject a global policy that sets both add_only and update_only."""
    mc: MutableConfig = MutableConfig.from_defaults()
    mc.policy = MutablePolicy(
        add_only=True,
        update_only=True,
    )
    with pytest.raises(ValueError):
        _ = mc.freeze()


def test_freeze_rejects_conflicting_per_type_policy() -> None:
    """freeze() must reject a per-type policy that sets both add_only and update_only."""
    mc: MutableConfig = MutableConfig.from_defaults()
    mc.policy = MutablePolicy(
        add_only=True,
        update_only=False,
    )
    mc.policy_by_type = {
        "python": MutablePolicy(
            add_only=True,
            update_only=True,
        ),
    }
    with pytest.raises(ValueError):
        _ = mc.freeze()


def test_policy_loaded_from_toml_tables() -> None:
    """TOML-shaped dicts must hydrate MutableConfig and resolve Policy correctly.

    This test ensures that `[policy]` and `[policy_by_type.*]` TOML tables are
    parsed into `MutableConfig`, then frozen into a `Config` where:

    * `cfg.policy` reflects global policy fields from `[policy]`, and
    * `cfg.policy_by_type["python"]` inherits unset fields from the global
      policy while applying per-type overrides.
    """
    toml_root: dict[str, Any] = {
        "policy": {
            "add_only": True,
            "allow_content_probe": False,
        },
        "policy_by_type": {
            "python": {
                "allow_header_in_empty_files": True,
            },
        },
    }
    mc: MutableConfig = MutableConfig.from_toml_dict(toml_root)
    cfg: Config = mc.freeze()

    # Global values from [policy]
    assert cfg.policy.add_only is True
    assert cfg.policy.allow_content_probe is False

    # Per-type inherits + overrides
    py_pol: Policy = cfg.policy_by_type["python"]
    assert py_pol.add_only is True  # inherited
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
    base: MutableConfig = MutableConfig.from_defaults()
    project: MutableConfig = MutableConfig.from_defaults()
    project.policy = MutablePolicy(add_only=True)
    project.policy_by_type = {"python": MutablePolicy(allow_content_probe=False)}

    local: MutableConfig = MutableConfig.from_defaults()
    local.policy = MutablePolicy(add_only=False, update_only=True)
    local.policy_by_type = {"python": MutablePolicy(allow_header_in_empty_files=True)}

    merged: MutableConfig = base.merge_with(project).merge_with(local)
    cfg: Config = merged.freeze()

    # Global: local overrides project
    assert cfg.policy.add_only is False
    assert cfg.policy.update_only is True

    # Python per-type: local overrides project but still inherits from global
    py_pol: Policy = cfg.policy_by_type["python"]
    assert py_pol.add_only is False  # from global (after merge)
    assert py_pol.update_only is True  # from global (after merge)
    assert py_pol.allow_content_probe is False  # from project per-type
    assert py_pol.allow_header_in_empty_files is True  # from local per-type


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
        ("add_only", True),
        ("update_only", True),
        ("allow_header_in_empty_files", True),
        ("render_empty_header_when_no_fields", True),
        ("allow_reflow", True),
        ("allow_content_probe", False),  # default is True, so flip it
    ],
)
def test_policy_thaw_resolve_roundtrip_preserves_field(field_name: str, value: bool) -> None:
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

    assert getattr(resolved, field_name) is value


@pytest.mark.parametrize(
    ("field_name", "base_val", "override_val", "expected"),
    [
        ("add_only", True, None, True),
        ("add_only", True, False, False),
        ("allow_content_probe", True, None, True),
        ("allow_content_probe", True, False, False),
        # Add more if needed
    ],
)
def test_mutable_policy_merge_with_per_field(
    field_name: str,
    base_val: bool | None,
    override_val: bool | None,
    expected: bool | None,
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
    assert getattr(merged, field_name) is expected

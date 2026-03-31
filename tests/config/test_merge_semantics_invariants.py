# topmark:header:start
#
#   project      : TopMark
#   file         : test_merge_semantics_invariants.py
#   file_relpath : tests/config/test_merge_semantics_invariants.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Focused regression tests for config merge semantics invariants.

These tests are intentionally small and explicit. They lock down the core
field-by-field merge rules that TopMark now relies on for layered and per-path
configuration resolution.

The goal is not broad TOML parsing coverage, but stable invariants for
`MutableConfig.merge_with()`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.policy import HeaderMutationMode
from topmark.config.policy import MutablePolicy
from topmark.config.types import PatternGroup
from topmark.config.types import PatternSource

if TYPE_CHECKING:
    from topmark.config.model import MutableConfig


@pytest.mark.pipeline
def test_merge_invariant_provenance_and_diagnostics_accumulate() -> None:
    """config_files and diagnostics should always accumulate."""
    base: MutableConfig = mutable_config_from_defaults()
    base.config_files = ["<defaults>", "root/topmark.toml"]
    base.diagnostics.add_warning("base warning")

    override: MutableConfig = mutable_config_from_defaults()
    override.config_files = ["child/topmark.toml"]
    override.diagnostics.add_warning("override warning")

    merged: MutableConfig = base.merge_with(override)

    assert merged.config_files == ["<defaults>", "root/topmark.toml", "child/topmark.toml"]
    assert [item.message for item in merged.diagnostics.items] == [
        "base warning",
        "override warning",
    ]


@pytest.mark.pipeline
def test_merge_invariant_header_fields_nearest_non_empty_wins() -> None:
    """header_fields uses nearest-wins semantics for non-empty child lists."""
    base: MutableConfig = mutable_config_from_defaults()
    base.header_fields = ["project", "license"]

    override: MutableConfig = mutable_config_from_defaults()
    override.header_fields = ["project", "file"]

    merged: MutableConfig = base.merge_with(override)

    assert merged.header_fields == ["project", "file"]


@pytest.mark.pipeline
def test_merge_invariant_empty_header_fields_do_not_clear_parent() -> None:
    """An empty child header_fields list is treated as not-set in merge_with()."""
    base: MutableConfig = mutable_config_from_defaults()
    base.header_fields = ["project", "license"]

    override: MutableConfig = mutable_config_from_defaults()
    override.header_fields = []

    merged: MutableConfig = base.merge_with(override)

    assert merged.header_fields == ["project", "license"]


@pytest.mark.pipeline
def test_merge_invariant_field_values_overlay_by_key() -> None:
    """field_values should merge by key, with child keys overriding parent keys."""
    base: MutableConfig = mutable_config_from_defaults()
    base.field_values = {
        "project": "TopMark",
        "license": "MIT",
    }

    override: MutableConfig = mutable_config_from_defaults()
    override.field_values = {
        "license": "Apache-2.0",
        "file": "pkg/module.py",
    }

    merged: MutableConfig = base.merge_with(override)

    assert merged.field_values == {
        "project": "TopMark",
        "license": "Apache-2.0",
        "file": "pkg/module.py",
    }


@pytest.mark.pipeline
def test_merge_invariant_pattern_groups_accumulate() -> None:
    """include/exclude pattern groups should append across layers."""
    base: MutableConfig = mutable_config_from_defaults()
    base.include_pattern_groups = [
        PatternGroup(patterns=("src/**/*.py",), base=Path("/repo")),
    ]
    base.exclude_pattern_groups = [
        PatternGroup(patterns=("build/**",), base=Path("/repo")),
    ]

    override: MutableConfig = mutable_config_from_defaults()
    override.include_pattern_groups = [
        PatternGroup(patterns=("pkg/**/*.py",), base=Path("/repo/pkg")),
    ]
    override.exclude_pattern_groups = [
        PatternGroup(patterns=("dist/**",), base=Path("/repo/pkg")),
    ]

    merged: MutableConfig = base.merge_with(override)

    assert merged.include_pattern_groups == [
        PatternGroup(patterns=("src/**/*.py",), base=Path("/repo")),
        PatternGroup(patterns=("pkg/**/*.py",), base=Path("/repo/pkg")),
    ]
    assert merged.exclude_pattern_groups == [
        PatternGroup(patterns=("build/**",), base=Path("/repo")),
        PatternGroup(patterns=("dist/**",), base=Path("/repo/pkg")),
    ]


@pytest.mark.pipeline
def test_merge_invariant_pattern_sources_accumulate() -> None:
    """include_from/exclude_from/files_from should append across layers."""
    base: MutableConfig = mutable_config_from_defaults()
    base.include_from = [
        PatternSource(path=Path("/repo/.gitignore"), base=Path("/repo")),
    ]
    base.exclude_from = [
        PatternSource(path=Path("/repo/.ignore"), base=Path("/repo")),
    ]
    base.files_from = [
        PatternSource(path=Path("/repo/files.txt"), base=Path("/repo")),
    ]

    override: MutableConfig = mutable_config_from_defaults()
    override.include_from = [
        PatternSource(path=Path("/repo/pkg/.include"), base=Path("/repo/pkg")),
    ]
    override.exclude_from = [
        PatternSource(path=Path("/repo/pkg/.exclude"), base=Path("/repo/pkg")),
    ]
    override.files_from = [
        PatternSource(path=Path("/repo/pkg/more-files.txt"), base=Path("/repo/pkg")),
    ]

    merged: MutableConfig = base.merge_with(override)

    assert merged.include_from == [
        PatternSource(path=Path("/repo/.gitignore"), base=Path("/repo")),
        PatternSource(path=Path("/repo/pkg/.include"), base=Path("/repo/pkg")),
    ]
    assert merged.exclude_from == [
        PatternSource(path=Path("/repo/.ignore"), base=Path("/repo")),
        PatternSource(path=Path("/repo/pkg/.exclude"), base=Path("/repo/pkg")),
    ]
    assert merged.files_from == [
        PatternSource(path=Path("/repo/files.txt"), base=Path("/repo")),
        PatternSource(path=Path("/repo/pkg/more-files.txt"), base=Path("/repo/pkg")),
    ]


@pytest.mark.pipeline
def test_merge_invariant_explicit_files_nearest_non_empty_wins() -> None:
    """Files uses nearest-wins semantics for non-empty child lists."""
    base: MutableConfig = mutable_config_from_defaults()
    base.files = ["/repo/README.md"]

    override: MutableConfig = mutable_config_from_defaults()
    override.files = ["/repo/pkg/module.py"]

    merged: MutableConfig = base.merge_with(override)

    assert merged.files == ["/repo/pkg/module.py"]


@pytest.mark.pipeline
def test_merge_invariant_empty_files_do_not_clear_parent() -> None:
    """An empty child files list is treated as not-set in merge_with()."""
    base: MutableConfig = mutable_config_from_defaults()
    base.files = ["/repo/README.md"]

    override: MutableConfig = mutable_config_from_defaults()
    override.files = []

    merged: MutableConfig = base.merge_with(override)

    assert merged.files == ["/repo/README.md"]


@pytest.mark.pipeline
def test_merge_invariant_file_type_filters_nearest_non_empty_wins() -> None:
    """include/exclude file type filters should replace, not union."""
    base: MutableConfig = mutable_config_from_defaults()
    base.include_file_types = {"python"}
    base.exclude_file_types = {"markdown"}

    override: MutableConfig = mutable_config_from_defaults()
    override.include_file_types = {"html"}
    override.exclude_file_types = {"xml"}

    merged: MutableConfig = base.merge_with(override)

    assert merged.include_file_types == {"html"}
    assert merged.exclude_file_types == {"xml"}


@pytest.mark.pipeline
def test_merge_invariant_policy_by_type_merges_by_key() -> None:
    """policy_by_type should preserve unrelated parent keys and merge shared keys."""
    base: MutableConfig = mutable_config_from_defaults()
    base.policy_by_type = {
        "python": MutablePolicy(header_mutation_mode=HeaderMutationMode.ADD_ONLY),
        "markdown": MutablePolicy(allow_content_probe=False),
    }

    override: MutableConfig = mutable_config_from_defaults()
    override.policy_by_type = {
        "python": MutablePolicy(allow_content_probe=True),
        "html": MutablePolicy(header_mutation_mode=HeaderMutationMode.UPDATE_ONLY),
    }

    merged: MutableConfig = base.merge_with(override)

    assert set(merged.policy_by_type) == {"python", "markdown", "html"}
    assert merged.policy_by_type["python"].header_mutation_mode == HeaderMutationMode.ADD_ONLY
    assert merged.policy_by_type["python"].allow_content_probe is True
    assert merged.policy_by_type["markdown"].allow_content_probe is False
    assert merged.policy_by_type["html"].header_mutation_mode == HeaderMutationMode.UPDATE_ONLY


@pytest.mark.pipeline
def test_merge_invariant_runtime_compat_fields_use_explicit_child_values() -> None:
    """Runtime-oriented compatibility fields replace only when explicitly set."""
    base: MutableConfig = mutable_config_from_defaults()
    base.stdin_mode = False
    base.stdin_filename = "stdin.py"
    base.apply_changes = False

    override: MutableConfig = mutable_config_from_defaults()
    override.stdin_mode = True
    override.stdin_filename = "override.py"
    override.apply_changes = True

    merged: MutableConfig = base.merge_with(override)

    assert merged.stdin_mode is True
    assert merged.stdin_filename == "override.py"
    assert merged.apply_changes is True


@pytest.mark.pipeline
def test_merge_invariant_timestamp_preserves_base_draft() -> None:
    """Timestamp should remain the base draft timestamp across merge_with()."""
    base: MutableConfig = mutable_config_from_defaults()
    override: MutableConfig = mutable_config_from_defaults()

    merged: MutableConfig = base.merge_with(override)

    assert merged.timestamp == base.timestamp


# --- Additional three-layer invariants ---


@pytest.mark.pipeline
def test_merge_invariant_three_layer_field_values_and_policy_overlay() -> None:
    """Three-layer merges should preserve ordering for mappings and per-type policies."""
    root: MutableConfig = mutable_config_from_defaults()
    root.field_values = {
        "project": "TopMark",
        "license": "MIT",
    }
    root.policy_by_type = {
        "python": MutablePolicy(header_mutation_mode=HeaderMutationMode.ADD_ONLY),
    }

    child: MutableConfig = mutable_config_from_defaults()
    child.field_values = {
        "license": "Apache-2.0",
        "copyright": "(c) Example Org",
    }
    child.policy_by_type = {
        "python": MutablePolicy(allow_content_probe=False),
        "markdown": MutablePolicy(header_mutation_mode=HeaderMutationMode.UPDATE_ONLY),
    }

    override: MutableConfig = mutable_config_from_defaults()
    override.field_values = {
        "file": "pkg/module.py",
        "license": "BSD-3-Clause",
    }
    override.policy_by_type = {
        "python": MutablePolicy(header_mutation_mode=HeaderMutationMode.UPDATE_ONLY),
        "html": MutablePolicy(allow_content_probe=True),
    }

    merged: MutableConfig = root.merge_with(child).merge_with(override)

    assert merged.field_values == {
        "project": "TopMark",
        "license": "BSD-3-Clause",
        "copyright": "(c) Example Org",
        "file": "pkg/module.py",
    }

    assert set(merged.policy_by_type) == {"python", "markdown", "html"}
    assert merged.policy_by_type["python"].header_mutation_mode == HeaderMutationMode.UPDATE_ONLY
    assert merged.policy_by_type["python"].allow_content_probe is False
    assert merged.policy_by_type["markdown"].header_mutation_mode == HeaderMutationMode.UPDATE_ONLY
    assert merged.policy_by_type["html"].allow_content_probe is True


@pytest.mark.pipeline
def test_merge_invariant_three_layer_include_from_accumulates_in_order() -> None:
    """Three-layer merges should accumulate include_from sources in precedence order."""
    root: MutableConfig = mutable_config_from_defaults()
    root.include_from = [
        PatternSource(path=Path("/repo/.gitignore"), base=Path("/repo")),
    ]

    child: MutableConfig = mutable_config_from_defaults()
    child.include_from = [
        PatternSource(path=Path("/repo/pkg/.include"), base=Path("/repo/pkg")),
    ]

    override: MutableConfig = mutable_config_from_defaults()
    override.include_from = [
        PatternSource(path=Path("/repo/pkg/local.include"), base=Path("/repo/pkg")),
    ]

    merged: MutableConfig = root.merge_with(child).merge_with(override)

    assert merged.include_from == [
        PatternSource(path=Path("/repo/.gitignore"), base=Path("/repo")),
        PatternSource(path=Path("/repo/pkg/.include"), base=Path("/repo/pkg")),
        PatternSource(path=Path("/repo/pkg/local.include"), base=Path("/repo/pkg")),
    ]

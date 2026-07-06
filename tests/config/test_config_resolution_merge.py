# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_resolution_merge.py
#   file_relpath : tests/config/test_config_resolution_merge.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for config-layer applicability and merge behavior.

These tests exercise:
- accumulation versus nearest-wins behavior across layers,
- selection of layers applicable to a given path,
- construction of effective per-path configs,
- merging behavior for empty layer sets,
- and precedence of CLI overrides over resolved TOML layers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from tests.helpers.diagnostics import NON_EMPTY
from tests.helpers.diagnostics import assert_diagnostic_level_stats
from tests.helpers.diagnostics import assert_validation_stage_totals
from tests.helpers.registry import make_file_type
from tests.helpers.registry import patched_effective_registries
from tests.toml.conftest import write_toml_document
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.model import sanitized_config
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.policy import HeaderMutationMode
from topmark.config.policy import MutablePolicy
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_mutable_config
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.merge import build_effective_config_for_path
from topmark.config.resolution.merge import merge_layers_globally
from topmark.config.resolution.merge import select_applicable_layers
from topmark.core.errors import ConfigValidationError
from topmark.toml.resolution import ResolvedTopmarkTomlSources
from topmark.toml.resolution import resolve_topmark_toml_sources

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.config.policy import FrozenPolicy
    from topmark.config.resolution.bridge import ResolvedConfigDraft
    from topmark.config.resolution.layers import ConfigLayer
    from topmark.diagnostic.model import MutableDiagnosticLog
    from topmark.filetypes.model import FileType


def test_include_from_accumulates_across_multiple_applicable_layers(
    tmp_path: Path,
) -> None:
    """include_from sources accumulate across applicable discovered config layers."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)
    write_toml_document(
        path=root / ".gitignore",
        content="*.tmp\n",
    )
    write_toml_document(
        path=child / ".include",
        content="src/**/*.py\n",
    )

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.files]
            include_from = [".gitignore"]
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [files]
            include_from = [".include"]
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child],
    )
    paths: list[Path] = [ps.path for ps in resolved_config.draft.include_from]

    assert paths == [
        (root / ".gitignore").resolve(),
        (child / ".include").resolve(),
    ]


def test_files_nearest_non_empty_list_wins_across_layers(
    tmp_path: Path,
) -> None:
    """Explicit files lists use nearest-wins semantics across applicable layers."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.files]
            files = ["README.md"]
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [files]
            files = ["module.py"]
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child],
    )
    assert resolved_config.draft.files == [str((child / "module.py").resolve())]


def test_include_file_types_nearest_non_empty_set_wins_across_layers(
    tmp_path: Path,
) -> None:
    """include_file_types uses nearest-wins semantics rather than set union."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.files]
            include_file_types = ["python"]
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [files]
            include_file_types = ["markdown"]
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[child],
    )
    assert resolved_config.draft.include_file_types == {"markdown"}


def test_select_applicable_layers_filters_child_scoped_layer(
    tmp_path: Path,
) -> None:
    """select_applicable_layers keeps global layers and filters file-backed layers by scope."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.formatting]
            align_fields = false
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [formatting]
            align_fields = true
        """,
    )

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(input_paths=[child])
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(resolved.sources)

    child_file: Path = child / "module.py"
    sibling_file: Path = sibling / "guide.md"
    child_file.write_text("x\n", encoding="utf-8")
    sibling_file.write_text("x\n", encoding="utf-8")

    child_layers: list[ConfigLayer] = select_applicable_layers(layers, child_file)
    sibling_layers: list[ConfigLayer] = select_applicable_layers(layers, sibling_file)

    assert any(layer.scope_root == child.resolve() for layer in child_layers)
    assert not any(layer.scope_root == child.resolve() for layer in sibling_layers)


def test_build_effective_config_for_path_merges_only_applicable_layers(
    tmp_path: Path,
) -> None:
    """Per-path effective configs should merge only the layers whose scope applies."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir(parents=True)

    write_toml_document(
        path=root / "pyproject.toml",
        content="""
            [tool.topmark.header]
            fields = ["project", "license"]

            [tool.topmark.fields]
            project = "TopMark"
            license = "MIT"
        """,
    )
    write_toml_document(
        path=child / "topmark.toml",
        content="""
            [header]
            fields = ["project", "file"]

            [fields]
            file = "pkg/module.py"
        """,
    )

    child_file: Path = child / "module.py"
    sibling_file: Path = sibling / "guide.md"
    child_file.write_text("x\n", encoding="utf-8")
    sibling_file.write_text("x\n", encoding="utf-8")

    resolved: ResolvedTopmarkTomlSources = resolve_topmark_toml_sources(input_paths=[child])
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(resolved.sources)

    child_cfg: FrozenConfig = build_effective_config_for_path(layers, child_file).freeze()
    sibling_cfg: FrozenConfig = build_effective_config_for_path(layers, sibling_file).freeze()

    assert child_cfg.header_fields == ("project", "file")
    assert child_cfg.field_values["project"] == "TopMark"
    assert child_cfg.field_values["file"] == "pkg/module.py"

    assert sibling_cfg.header_fields == ("project", "license")
    assert sibling_cfg.field_values["project"] == "TopMark"
    assert "file" not in sibling_cfg.field_values


def test_merge_layers_globally_empty_returns_defaults() -> None:
    """Merging an empty layer sequence should fall back to defaults."""
    draft: MutableConfig = merge_layers_globally(())
    default_draft: MutableConfig = mutable_config_from_defaults()

    assert draft.header_fields == default_draft.header_fields
    assert draft.include_from == default_draft.include_from
    assert draft.include_pattern_groups == default_draft.include_pattern_groups


def test_cli_overrides_merge_last(
    tmp_path: Path,
) -> None:
    """CLI overrides have highest precedence."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    write_toml_document(
        path=proj / "pyproject.toml",
        content="""
            [tool.topmark.formatting]
            align_fields = false
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[proj],
    )
    # Simulate CLI override
    overrides = ConfigOverrides(
        align_fields=True,
    )
    apply_config_overrides(
        resolved_config.draft,
        overrides,
    )
    assert resolved_config.draft.align_fields is True


def test_override_diagnostics_land_in_merged_config(tmp_path: Path) -> None:
    """Override application diagnostics should land in the merged-config stage."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    # Minimal base config to avoid unrelated header warnings
    write_toml_document(
        path=proj / "topmark.toml",
        content="""
            [header]
            fields = ["file"]
        """,
    )

    resolved_config: ResolvedConfigDraft = resolve_toml_sources_and_build_mutable_config(
        input_paths=[proj],
    )

    # Trigger an override diagnostic (empty entry in files)
    overrides = ConfigOverrides(
        files=["", "README.md"],
    )
    apply_config_overrides(resolved_config.draft, overrides)

    flattened_diagnostics: MutableDiagnosticLog = resolved_config.draft.validation_logs.flattened()
    # Flat diagnostics reflect the warning
    assert_diagnostic_level_stats(
        stats=flattened_diagnostics.stats(),
        expected_warning=NON_EMPTY,
    )

    # Staged diagnostics: only merged_config should contain entries
    assert_validation_stage_totals(
        resolved_config.draft.validation_logs,
        # Skip TOML-source assertions here: this fixture intentionally defines
        # only `[header]`, so TOML missing-section INFO diagnostics are expected
        # and are not relevant to this override-routing test.
        config=NON_EMPTY,
        runtime=0,
    )

    # Sanity: message content present in both views
    assert any(
        "Ignoring empty string entries in override files" in d.message
        for d in resolved_config.draft.validation_logs.merged_config.items
    )
    assert any(
        "Ignoring empty string entries in override files" in d.message
        for d in flattened_diagnostics.items
    )


def test_sanitized_config_resolves_runtime_applicability_diagnostics() -> None:
    """Sanitizing a frozen config should normalize file-type filters via thaw/freeze."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.include_file_types = {"python", "unknown"}

    sanitized: FrozenConfig = sanitized_config(draft.freeze())

    assert sanitized.include_file_types == frozenset({"topmark:python"})
    assert any(
        "Unknown included file types specified" in diagnostic.message
        for diagnostic in sanitized.validation_logs.runtime_applicability.items
    )


def test_mutable_config_ensure_valid_raises_for_invalid_draft() -> None:
    """Mutable config validity should raise with staged validation context."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_error("bad override")

    try:
        draft.ensure_valid()
    except ConfigValidationError as exc:
        assert exc.context.diagnostics is not None
        assert any(
            diagnostic.message == "bad override" for diagnostic in exc.context.diagnostics.items
        )
    else:  # pragma: no cover - assertion guard
        raise AssertionError("MutableConfig.ensure_valid() did not raise")


def test_merge_policy_by_type_preserves_parent_when_override_key_missing() -> None:
    """Per-type policy merge should preserve parent-only policy entries."""
    base: MutableConfig = mutable_config_from_defaults()
    base.policy_by_type = {
        "python": MutablePolicy(header_mutation_mode=HeaderMutationMode.ADD_ONLY),
    }
    override: MutableConfig = mutable_config_from_defaults()

    merged: MutableConfig = base.merge_with(override)

    assert merged.policy_by_type["python"].header_mutation_mode == HeaderMutationMode.ADD_ONLY


def test_freeze_records_unknown_excluded_file_type_diagnostic() -> None:
    """Unknown exclude-file-type identifiers should be ignored with exclusion wording."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.exclude_file_types = {"missing"}

    frozen: FrozenConfig = draft.freeze()

    assert frozen.exclude_file_types == frozenset()
    assert any(
        "Unknown excluded file types specified (ignored): missing" in diagnostic.message
        for diagnostic in frozen.validation_logs.runtime_applicability.items
    )


def test_freeze_records_malformed_file_type_filter_diagnostics() -> None:
    """Malformed include/exclude file-type filters should be ignored with diagnostics."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.include_file_types = {":python"}
    draft.exclude_file_types = {"topmark:"}

    frozen: FrozenConfig = draft.freeze()

    assert frozen.include_file_types == frozenset()
    assert frozen.exclude_file_types == frozenset()
    messages: list[str] = [
        diagnostic.message for diagnostic in frozen.validation_logs.runtime_applicability.items
    ]
    assert "Malformed include_file_types file type identifier ignored: :python" in messages
    assert "Malformed exclude_file_types file type identifier ignored: topmark:" in messages


def test_freeze_records_ambiguous_file_type_filter_diagnostics() -> None:
    """Ambiguous include/exclude local file-type identifiers should be ignored."""
    first: FileType = make_file_type(
        local_key="shared",
        namespace="first",
        extensions=[".one"],
        description="First shared file type",
    )
    second: FileType = make_file_type(
        local_key="shared",
        namespace="second",
        extensions=[".two"],
        description="Second shared file type",
    )
    draft: MutableConfig = mutable_config_from_defaults()
    draft.include_file_types = {"shared"}
    draft.exclude_file_types = {"shared"}

    with patched_effective_registries(
        filetypes={"first-shared": first, "second-shared": second},
        processors={},
    ):
        frozen: FrozenConfig = draft.freeze()

    assert frozen.include_file_types == frozenset()
    assert frozen.exclude_file_types == frozenset()
    messages: list[str] = [
        diagnostic.message for diagnostic in frozen.validation_logs.runtime_applicability.items
    ]
    assert any(
        message.startswith("Ambiguous include_file_types file type identifier ignored: shared")
        for message in messages
    )
    assert any(
        message.startswith("Ambiguous exclude_file_types file type identifier ignored: shared")
        for message in messages
    )


def test_frozen_config_ensure_valid_raises_for_invalid_snapshot() -> None:
    """Frozen config validity should raise with staged validation context."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.runtime_applicability.add_error("bad runtime filter")
    frozen: FrozenConfig = draft.freeze()

    try:
        frozen.ensure_valid()
    except ConfigValidationError as exc:
        assert exc.context.diagnostics is not None
        assert any(
            diagnostic.message == "bad runtime filter"
            for diagnostic in exc.context.diagnostics.items
        )
    else:  # pragma: no cover - assertion guard
        raise AssertionError("FrozenConfig.ensure_valid() did not raise")


def test_freeze_empty_file_type_identifier_is_ignored_with_diagnostic() -> None:
    """Empty file-type filter entries should be ignored during sanitization."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.include_file_types = {""}

    frozen: FrozenConfig = draft.freeze()

    assert frozen.include_file_types == frozenset()
    assert any(
        "Unknown included file types specified (ignored): " in diagnostic.message
        for diagnostic in frozen.validation_logs.runtime_applicability.items
    )


def test_freeze_warns_when_file_type_is_included_and_excluded() -> None:
    """Overlapping file-type filters should be preserved with an exclusion-wins warning."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.include_file_types = {"python"}
    draft.exclude_file_types = {"python"}

    frozen: FrozenConfig = draft.freeze()

    assert frozen.include_file_types == frozenset({"topmark:python"})
    assert frozen.exclude_file_types == frozenset({"topmark:python"})
    expected_message: str = (
        "File types specified in both include and exclude filters; exclusion wins: topmark:python"
    )
    assert any(
        diagnostic.message == expected_message
        for diagnostic in frozen.validation_logs.runtime_applicability.items
    )


def test_freeze_merges_duplicate_policy_by_type_canonical_keys() -> None:
    """Equivalent local and qualified per-type policy keys should merge."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.policy_by_type = {
        "python": MutablePolicy(header_mutation_mode=HeaderMutationMode.ADD_ONLY),
        "topmark:python": MutablePolicy(allow_content_probe=False),
    }

    frozen: FrozenConfig = draft.freeze()

    python_policy: FrozenPolicy = frozen.policy_by_type["topmark:python"]
    assert python_policy.header_mutation_mode == HeaderMutationMode.ADD_ONLY
    assert python_policy.allow_content_probe is False


def test_config_ensure_valid_noops_for_valid_snapshots() -> None:
    """Validation helpers should return normally for valid mutable and frozen config."""
    draft: MutableConfig = mutable_config_from_defaults()
    frozen: FrozenConfig = draft.freeze()

    draft.ensure_valid()
    frozen.ensure_valid()


def test_merge_policy_by_type_ignores_type_violating_missing_override() -> None:
    """Policy merge should tolerate an impossible missing override value defensively."""
    base: MutableConfig = mutable_config_from_defaults()
    override: MutableConfig = mutable_config_from_defaults()
    # Intentional: exercise the defensive branch for runtime type-violating callers.
    override.policy_by_type = cast("dict[str, MutablePolicy]", {"python": None})

    merged: MutableConfig = base.merge_with(override)

    assert "python" not in merged.policy_by_type
    assert merged.policy.header_mutation_mode == HeaderMutationMode.ALL

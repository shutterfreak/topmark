# topmark:header:start
#
#   project      : TopMark
#   file         : test_synthetic_sources.py
#   file_relpath : tests/config/test_synthetic_sources.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Synthetic source contracts across loading, merging, and serialization."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import tomlkit

from topmark.config.assignments import FileTypeRule
from topmark.config.assignments import file_type_rule_to_table
from topmark.config.assignments import parse_file_type_rules
from topmark.config.io.deserializers import mutable_config_from_layered_toml_table
from topmark.config.io.serializers import config_to_topmark_toml_table
from topmark.config.model import FrozenConfig
from topmark.config.model import MutableConfig
from topmark.config.resolution.bridge import ResolvedConfigDraft
from topmark.config.resolution.bridge import resolve_config_mapping_and_build_mutable_config
from topmark.config.resolution.layers import ConfigLayer
from topmark.config.resolution.layers import build_config_layers_from_resolved_toml_sources
from topmark.config.resolution.synthetic import ANONYMOUS_CONFIG_SOURCE
from topmark.config.resolution.synthetic import API_CONFIG_SOURCE
from topmark.config.resolution.synthetic import API_OVERRIDE_SOURCE
from topmark.config.resolution.synthetic import API_POLICY_OVERRIDE_SOURCE
from topmark.config.resolution.synthetic import BUILTIN_DEFAULTS_TOML_SOURCE
from topmark.config.resolution.synthetic import BUNDLED_TEMPLATE_TOML_SOURCE
from topmark.config.resolution.synthetic import CLI_ASSIGNMENT_SOURCE
from topmark.config.resolution.synthetic import CLI_OVERRIDE_SOURCE
from topmark.config.resolution.synthetic import DEFAULT_CONFIG_SOURCE
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.toml.typing_guards import toml_table_from_mapping
from topmark.utils.path import format_config_source_path

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.toml.types import TomlTable


@pytest.mark.parametrize(
    ("source", "label"),
    [
        (DEFAULT_CONFIG_SOURCE, "<defaults>"),
        (BUILTIN_DEFAULTS_TOML_SOURCE, "<built-in topmark defaults>"),
        (BUNDLED_TEMPLATE_TOML_SOURCE, "<bundled topmark-template.toml>"),
        (API_CONFIG_SOURCE, "<API config>"),
        (API_OVERRIDE_SOURCE, "<API overrides>"),
        (API_POLICY_OVERRIDE_SOURCE, "<API policy overrides>"),
        (CLI_OVERRIDE_SOURCE, "<CLI overrides>"),
        (CLI_ASSIGNMENT_SOURCE, "<CLI assignments>"),
        (ANONYMOUS_CONFIG_SOURCE, "<anonymous config>"),
    ],
)
def test_canonical_source_labels(
    source: SyntheticConfigSource,
    label: str,
) -> None:
    """Pin external spellings independently of the production catalog."""
    assert str(source) == label
    assert format_config_source_path(source) == label
    assert format_config_source_path(label) == label


def _rules_table() -> TomlTable:
    """Return an assignment followed by an inference control."""
    return {
        "files": {
            "file_type_assignments": [
                {
                    "file_type": "jsonc",
                    "patterns": ["*.json"],
                },
                {
                    "action": "infer",
                    "patterns": ["*.json"],
                },
            ],
        },
    }


def test_anonymous_and_explicit_api_sources_are_distinct() -> None:
    """Only an API mapping entry point attributes API provenance."""
    anonymous: MutableConfig = mutable_config_from_layered_toml_table(_rules_table())
    api: ResolvedConfigDraft = resolve_config_mapping_and_build_mutable_config(_rules_table())
    assert anonymous.config_files == []
    assert all(rule.source is ANONYMOUS_CONFIG_SOURCE for rule in anonymous.file_type_assignments)
    assert api.resolved.sources[0].path is API_CONFIG_SOURCE
    assert api.draft.config_files == [API_CONFIG_SOURCE]
    assert all(rule.source is API_CONFIG_SOURCE for rule in api.draft.file_type_assignments)
    assert "<anonymous config>" in next(iter(anonymous.validation_logs.merged_config)).message
    assert "<API config>" in next(iter(api.draft.validation_logs.merged_config)).message


@pytest.mark.parametrize(
    "source",
    [
        API_CONFIG_SOURCE,
        API_OVERRIDE_SOURCE,
        API_POLICY_OVERRIDE_SOURCE,
        CLI_ASSIGNMENT_SOURCE,
    ],
)
def test_typed_sources_survive_merge_freeze_and_dump(
    source: SyntheticConfigSource,
    tmp_path: Path,
) -> None:
    """Typed provenance survives in memory; relocated TOML retains opaque labels."""
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        _rules_table(),
        config_file=source,
    )
    frozen: FrozenConfig = MutableConfig().merge_with(draft).freeze().thaw().freeze()
    assert frozen.config_files[0] is source
    assert all(rule.source is source for rule in frozen.file_type_assignments)
    table: TomlTable = config_to_topmark_toml_table(frozen)
    text: str = tomlkit.dumps(table)
    reloaded: MutableConfig = mutable_config_from_layered_toml_table(
        toml_table_from_mapping(tomlkit.parse(text).unwrap()),
        config_file=tmp_path / "relocated" / "topmark.toml",
    )
    assert [file_type_rule_to_table(rule) for rule in reloaded.file_type_assignments] == [
        file_type_rule_to_table(rule) for rule in frozen.file_type_assignments
    ]
    assert all(rule.source == source.label for rule in reloaded.file_type_assignments)
    assert (
        sum("Contradictory duplicate" in d.message for d in reloaded.validation_logs.merged_config)
        == 1
    )


@pytest.mark.parametrize("same_identity", [True, False])
def test_duplicate_identity_preserves_legacy_source_labels(
    tmp_path: Path,
    *,
    same_identity: bool,
) -> None:
    """Typed and legacy origins compare by label without conflating anonymous input."""
    log = MutableDiagnosticLog()
    rules: list[FileTypeRule] = parse_file_type_rules(
        [
            {
                "file_type": "jsonc",
                "patterns": ["*.json"],
            },
            {
                "action": "infer",
                "patterns": ["*.json"],
                "source": "<API config>" if same_identity else "<anonymous config>",
            },
        ],
        base=tmp_path,
        source=API_CONFIG_SOURCE,
        scope=None,
        diagnostics=log,
    )
    assert len(rules) == 2
    assert rules[0].source is API_CONFIG_SOURCE
    assert isinstance(rules[1].source, str)
    assert log.stats().n_warning == int(same_identity)


def test_file_rule_provenance_remains_a_path(
    tmp_path: Path,
) -> None:
    """File-backed assignment provenance remains typed until export."""
    path: Path = tmp_path / "topmark.toml"
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        _rules_table(),
        config_file=path,
    )
    assert all(rule.source is path for rule in draft.freeze().file_type_assignments)
    assert file_type_rule_to_table(draft.file_type_assignments[0])["source"] == path.as_posix()


def test_synthetic_sources_do_not_undergo_filesystem_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic markers, even path-looking labels, never reach Path.resolve."""
    original: Callable[..., Path] = Path.resolve

    def checked_resolve(
        path: Path,
        *,
        strict: bool = False,
    ) -> Path:
        assert "synthetic/../marker" not in path.as_posix()
        assert "<" not in path.as_posix()
        return original(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", checked_resolve)
    marker = SyntheticConfigSource(label="synthetic/../marker")
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        _rules_table(),
        config_file=marker,
    )
    assert draft.freeze().config_files == (marker,)
    assert format_config_source_path(draft.file_type_assignments[0].source) == marker.label
    resolved: ResolvedConfigDraft = resolve_config_mapping_and_build_mutable_config(_rules_table())
    layers: list[ConfigLayer] = build_config_layers_from_resolved_toml_sources(
        resolved.resolved.sources
    )
    assert layers[0].origin is DEFAULT_CONFIG_SOURCE
    assert layers[1].origin is API_CONFIG_SOURCE
    assert layers[1].config.config_files[0] is API_CONFIG_SOURCE

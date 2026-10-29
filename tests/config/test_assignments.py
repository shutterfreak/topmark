# topmark:header:start
#
#   project      : TopMark
#   file         : test_assignments.py
#   file_relpath : tests/config/test_assignments.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Configuration variants, matching semantics, and assignment safety contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from topmark.config.assignments import AssignmentRule
from topmark.config.assignments import FileTypeRule
from topmark.config.assignments import InferenceRule
from topmark.config.assignments import file_type_rule_to_table
from topmark.config.assignments import matching_file_type_rules
from topmark.config.assignments import parse_file_type_rules
from topmark.config.io.deserializers import mutable_config_from_layered_toml_table
from topmark.diagnostic.model import MutableDiagnosticLog
from topmark.resolution.filetypes import probe_resolution_for_path

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import EffectiveRegistries
    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.filetypes.model import FileType
    from topmark.resolution.probe import ResolutionProbeResult


@pytest.mark.parametrize(
    "entry",
    [
        {},
        {"patterns": ["*"]},
        {"file_type": "jsonc"},
        {"file_type": "jsonc", "patterns": []},
        {"file_type": "jsonc", "patterns": "*"},
        {"file_type": "jsonc", "patterns": [1]},
        {"file_type": "jsonc", "patterns": [""]},
        {"file_type": "jsonc", "patterns": ["!ignored"]},
        {"file_type": "jsonc", "patterns": ["#comment"]},
        {"file_type": "jsonc", "patterns": ["a\nb"]},
        {"file_type": "jsonc", "patterns": ["[z-a]"]},
        {"file_type": "missing", "patterns": ["*"]},
        {"file_type": "topmark:jsonc:other", "patterns": ["*"]},
        {"file_type": " jsonc", "patterns": ["*"]},
        {"action": "unknown", "patterns": ["*"]},
        {"action": None, "patterns": ["*"]},
        {"action": "infer", "file_type": "", "patterns": ["*"]},
        {"action": "infer", "file_type": None, "patterns": ["*"]},
        {"action": "infer", "file_type": "jsonc", "patterns": ["*"]},
        {"action": "infer", "patterns": ["*"], "base": []},
    ],
)
def test_invalid_variants(
    entry: object,
    tmp_path: Path,
) -> None:
    """Every entry point rejects malformed variants rather than guessing intent."""
    log = MutableDiagnosticLog()
    assert not parse_file_type_rules(
        [entry],
        base=tmp_path,
        source="test",
        scope=None,
        diagnostics=log,
    )
    assert log.stats().n_error == 1


@pytest.mark.parametrize("value", [None, {}, "*", 2, ["*"]])
def test_invalid_list_shapes(
    value: object,
    tmp_path: Path,
) -> None:
    """The rule container and entries must have their declared shapes."""
    log = MutableDiagnosticLog()
    assert not parse_file_type_rules(
        value,
        base=tmp_path,
        source="test",
        scope=None,
        diagnostics=log,
    )
    assert log.stats().n_error


@pytest.mark.parametrize("action", [None, "assign", "infer"])
def test_valid_variants_and_round_trip(
    action: str | None,
    tmp_path: Path,
) -> None:
    """Variants normalize identities and preserve provenance when relocated."""
    entry: dict[str, object] = {
        "patterns": ["*.json"],
    }
    if action is not None:
        entry["action"] = action
    if action != "infer":
        entry["file_type"] = "jsonc"
    log = MutableDiagnosticLog()
    rules: list[FileTypeRule] = parse_file_type_rules(
        [entry],
        base=tmp_path,
        source="origin",
        scope=None,
        diagnostics=log,
    )
    assert not log.stats().n_error
    rule = rules[0]
    assert isinstance(rule, InferenceRule if action == "infer" else AssignmentRule)
    if isinstance(rule, AssignmentRule):
        assert rule.file_type == "topmark:jsonc"
    reloaded: list[FileTypeRule] = parse_file_type_rules(
        [file_type_rule_to_table(rule)],
        base=tmp_path / "elsewhere",
        source="relocated",
        scope=tmp_path / "elsewhere",
        diagnostics=log,
    )
    assert reloaded == rules
    assert not log.stats().n_error


@pytest.mark.parametrize(
    ("pattern", "relative", "expected"),
    [
        (".aiderignore", "nested/.aiderignore", True),
        ("*.json", ".hidden.json", True),
        ("*.json", "nested/a.json", True),
        ("*.json", "a.JSON", False),
        ("/a.json", "nested/a.json", False),
        ("config/*.json", "config/deep/a.json", False),
        ("config/**", "config/deep/a.json", True),
        ("a=b:c:d,é.json", "a=b:c:d,é.json", True),
        ("a[12].json", "a2.json", True),
        (r"a\[1\].json", "a[1].json", True),
        (" a.json", " a.json", True),
        ("a.json ", "a.json", True),
        (r"a.json\ ", "a.json ", True),
    ],
)
def test_matching_synthetic_paths(
    pattern: str,
    relative: str,
    *,
    expected: bool,
    tmp_path: Path,
) -> None:
    """Gitignore path behavior is tested separately from CLI token preservation."""
    rule = InferenceRule(
        patterns=(pattern,),
        base=tmp_path,
        scope=tmp_path,
        source="test",
        order=0,
    )
    assert bool(matching_file_type_rules(tmp_path / relative, (rule,))) is expected
    assert not matching_file_type_rules(tmp_path.parent / relative, (rule,))


def test_inheritance_freeze_and_duplicate_diagnostics(
    tmp_path: Path,
) -> None:
    """Empty lists retain rules; suspicious duplicates warn once per declaration."""
    draft: MutableConfig = mutable_config_from_layered_toml_table(
        {
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
                ]
            }
        },
        tmp_path / "topmark.toml",
    )
    empty: MutableConfig = mutable_config_from_layered_toml_table(
        {
            "files": {
                "file_type_assignments": [],
            },
        }
    )
    merged: FrozenConfig = draft.merge_with(empty).freeze()
    assert len(merged.file_type_assignments) == 2
    assert merged.thaw().freeze().file_type_assignments == merged.file_type_assignments
    assert (
        sum("Contradictory duplicate" in d.message for d in merged.validation_logs.merged_config)
        == 1
    )
    assert merged.is_valid()
    assert not merged.is_valid(strict=True)


@pytest.mark.parametrize(
    ("target", "status"),
    [
        ("json", "activation_blocked"),
        ("jsonc", "resolved"),
        ("json-as-jsonc", "activation_blocked"),
        ("python-typed-marker", "activation_blocked"),
    ],
)
def test_assigned_activation_without_content_gates(
    target: str,
    status: str,
    tmp_path: Path,
) -> None:
    """Explicit recognition preserves activation and never invents candidates."""
    path: Path = tmp_path / "document.unknown"
    path.write_text("{}\n", encoding="utf-8")
    log = MutableDiagnosticLog()
    rules: list[FileTypeRule] = parse_file_type_rules(
        [{"file_type": target, "patterns": ["*"]}],
        base=tmp_path,
        source="test",
        scope=None,
        diagnostics=log,
    )
    assert rules, tuple(log)
    probe: ResolutionProbeResult = probe_resolution_for_path(
        path,
        file_type_assignments=tuple(rules),
    )
    assert probe.status.value == status
    assert probe.candidates == ()
    assert probe.selected_file_type is not None
    assert probe.selected_file_type.score is None


def test_assigned_unbound_and_ambiguous_types(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """No binding has no fallback; ambiguous local identities fail validation."""
    first: FileType = make_file_type(
        namespace="first",
        local_key="custom",
    )
    second: FileType = make_file_type(
        namespace="second",
        local_key="custom",
    )
    with effective_registries(
        {
            first.qualified_key: first,
            second.qualified_key: second,
        },
        {},
    ):
        log = MutableDiagnosticLog()
        assert not parse_file_type_rules(
            [
                {
                    "file_type": "custom",
                    "patterns": ["*"],
                }
            ],
            base=tmp_path,
            source="test",
            scope=None,
            diagnostics=log,
        )
        assert log.stats().n_error == 1
        rule = AssignmentRule(
            file_type=first.qualified_key,
            patterns=("*",),
            base=tmp_path,
            scope=None,
            source="test",
            order=0,
        )
        probe: ResolutionProbeResult = probe_resolution_for_path(
            tmp_path / "a.py",
            file_type_assignments=(rule,),
        )
        assert probe.status.value == "no_processor"
        assert probe.selected_file_type is not None
        assert probe.selected_file_type.qualified_key == first.qualified_key


def test_unknown_keys_and_harmless_redundancy(
    tmp_path: Path,
) -> None:
    """Unknown keys warn, while equivalent repeated outcomes remain harmless."""
    log = MutableDiagnosticLog()
    rules: list[FileTypeRule] = parse_file_type_rules(
        [
            {
                "file_type": "jsonc",
                "patterns": ["*.json"],
                "unexpected": True,
            },
            {
                "file_type": "topmark:jsonc",
                "patterns": ["*.json"],
            },
        ],
        base=tmp_path,
        source="test",
        scope=None,
        diagnostics=log,
    )
    assert len(rules) == 2
    assert log.stats().n_warning == 1
    assert "Unknown" in next(iter(log)).message
    assert not log.stats().n_error


@pytest.mark.parametrize(
    "pattern",
    [
        "\\",
        "folder/\\",
        "   ",
        "\x00",
        "[z-a]",
    ],
)
def test_invalid_globs_fail_as_diagnostics(
    pattern: str,
    tmp_path: Path,
) -> None:
    """Compiler errors and no-op patterns become validation errors for both variants."""
    for entry in [
        {
            "file_type": "jsonc",
            "patterns": [pattern],
        },
        {
            "action": "infer",
            "patterns": [pattern],
        },
    ]:
        log = MutableDiagnosticLog()
        assert not parse_file_type_rules(
            [entry],
            base=tmp_path,
            source="test",
            scope=None,
            diagnostics=log,
        )
        assert log.stats().n_error == 1


def test_symlink_matching_uses_target_scope(
    tmp_path: Path,
) -> None:
    """Symlink aliases follow the selected resolved target path and its rule scope."""
    from tests.helpers.paths import symlink_or_skip

    directory: Path = tmp_path / "target"
    directory.mkdir()
    target: Path = directory / "a.json"
    target.write_text("{}\n", encoding="utf-8")
    alias: Path = tmp_path / "alias.json"
    symlink_or_skip(alias, target)
    rule = InferenceRule(
        patterns=("a.json",),
        base=directory,
        scope=directory,
        source="test",
        order=0,
    )
    assert matching_file_type_rules(alias, (rule,)) == ((rule, "a.json"),)


def test_contradictory_shared_patterns_warn_once_per_rule_pair(
    tmp_path: Path,
) -> None:
    """Partially repeated pattern lists diagnose one contradiction per source/scope pair."""
    log = MutableDiagnosticLog()
    rules: list[FileTypeRule] = parse_file_type_rules(
        [
            {
                "file_type": "jsonc",
                "patterns": ["a.json", "b.json", "c.json"],
            },
            {
                "action": "infer",
                "patterns": ["b.json", "a.json"],
            },
        ],
        base=tmp_path,
        source="test",
        scope=tmp_path,
        diagnostics=log,
    )
    assert len(rules) == 2
    assert log.stats().n_warning == 1
    assert not log.stats().n_error


def test_definition_base_is_independent_of_scope(
    tmp_path: Path,
) -> None:
    """A global-scope rule still cannot match relative patterns outside its definition base."""
    rule = InferenceRule(
        patterns=("*.json",),
        base=tmp_path / "definition",
        scope=None,
        source="test",
        order=0,
    )
    assert not matching_file_type_rules(tmp_path / "other/a.json", (rule,))


@pytest.mark.parametrize(
    "metadata",
    [
        {"order": True},
        {"order": "first"},
        {"precedence": False},
        {"precedence": []},
    ],
)
def test_exported_metadata_shapes_are_validated(
    metadata: dict[str, object],
    tmp_path: Path,
) -> None:
    """Reading exported provenance enforces the documented field shapes."""
    log = MutableDiagnosticLog()
    assert not parse_file_type_rules(
        [
            {
                "action": "infer",
                "patterns": ["*"],
                **metadata,
            }
        ],
        base=tmp_path,
        source="test",
        scope=None,
        diagnostics=log,
    )
    assert log.stats().n_error == 1


def test_validated_assignment_rejects_type_removed_before_resolution(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Registry drift after validation raises instead of silently falling back to inference."""
    temporary: FileType = make_file_type(namespace="temporary", local_key="retired")
    log = MutableDiagnosticLog()
    with effective_registries({temporary.qualified_key: temporary}, {}):
        rules: list[FileTypeRule] = parse_file_type_rules(
            [
                {
                    "file_type": temporary.qualified_key,
                    "patterns": ["*.py"],
                }
            ],
            base=tmp_path,
            source="test",
            scope=None,
            diagnostics=log,
        )
    assert len(rules) == 1
    assert log.stats().n_error == 0

    path: Path = tmp_path / "example.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    automatic: ResolutionProbeResult = probe_resolution_for_path(path)
    assert automatic.selected_file_type is not None
    assert automatic.selected_file_type.qualified_key == "topmark:python"

    with pytest.raises(ValueError) as exc_info:
        probe_resolution_for_path(path, file_type_assignments=tuple(rules))
    assert str(exc_info.value) == (
        f"Assigned file type is no longer registered: {temporary.qualified_key}"
    )

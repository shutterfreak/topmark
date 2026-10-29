# topmark:header:start
#
#   project      : TopMark
#   file         : test_file_type_assignments.py
#   file_relpath : tests/api/test_file_type_assignments.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public API assignment, scoped layering, consent, and policy contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark import api
from topmark.core.constants import TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path


def test_api_structured_assignment_processing_and_inference(
    tmp_path: Path,
) -> None:
    """Public configuration selects the same type for probe, insertion, and stripping."""
    path: Path = tmp_path / "service.json"
    path.write_text("{}\n", encoding="utf-8")
    config: dict[str, object] = {
        "files": {
            "file_type_assignments": [
                {
                    "file_type": "jsonc",
                    "patterns": [path.name],
                    "base": tmp_path.as_posix(),
                }
            ]
        }
    }
    result: api.ProbeRunResult = api.probe([path], config=config)
    assert result.files[0].selection_method == "assignment"
    assert result.files[0].selected_file_type == "jsonc"
    assert api.probe([path], config={}).files[0].selected_file_type == "json"
    api.check([path], config=config, apply=True)
    inserted: str = path.read_text(encoding="utf-8")
    assert TOPMARK_START_MARKER in inserted
    api.check([path], config=config, apply=True)
    assert path.read_text(encoding="utf-8") == inserted
    api.strip([path], config=config, apply=True)
    assert path.read_text(encoding="utf-8") == "{}\n"


def test_descendant_scope_restore_inference_and_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root-invoked descendant rules override ancestors without leaking into siblings."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        """[config]
root = true
[[files.file_type_assignments]]
file_type = "jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    for name in ("local", "sibling"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "a.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "local/topmark.toml").write_text(
        """[[files.file_type_assignments]]
action = "infer"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    result: api.ProbeRunResult = api.probe([tmp_path])
    files: dict[str, api.ProbeFileResult] = {str(f.path.resolve()): f for f in result.files}
    local: api.ProbeFileResult = files[str(tmp_path / "local/a.json")]
    sibling: api.ProbeFileResult = files[str(tmp_path / "sibling/a.json")]
    assert local.selection_method == "inference"
    assert sibling.selection_method == "assignment"
    assert len(local.rule_matches) == 2
    assert len(sibling.rule_matches) == 1
    assert local.rule_matches[-1]["scope"] == (tmp_path / "local").as_posix()
    assert local.rule_matches[-1]["source"] == (tmp_path / "local/topmark.toml").as_posix()
    multi: api.ProbeRunResult = api.probe([tmp_path / "local", tmp_path / "sibling"])
    assert {(f.path, f.selected_file_type) for f in multi.files} == {
        (f.path, f.selected_file_type) for f in result.files if f.path.suffix == ".json"
    } | {(f.path, f.selected_file_type) for f in multi.files if f.path.suffix != ".json"}


def test_nested_root_boundary_discards_ancestor_assignment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root boundaries remove ancestor assignments through existing scoped layers."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        """[config]
root = true
[[files.file_type_assignments]]
file_type = "jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    child: Path = tmp_path / "child"
    child.mkdir()
    (child / "topmark.toml").write_text("[config]\nroot = true\n", encoding="utf-8")
    path: Path = child / "a.json"
    path.write_text("{}\n", encoding="utf-8")
    result: api.ProbeRunResult = api.probe([tmp_path])
    file: api.ProbeFileResult = next(f for f in result.files if f.path.name == "a.json")
    assert file.selection_method == "inference"
    assert file.rule_matches == ()


def test_api_assignment_policy_scope_does_not_leak_to_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assigned types retain the policy from their own effective configuration scope."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        """[config]
root = true
[[files.file_type_assignments]]
file_type = "jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    for directory in ("local", "sibling"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "a.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "local/topmark.toml").write_text(
        """[policy_by_type."topmark:jsonc"]
header_mutation_mode = "update_only"
""",
        encoding="utf-8",
    )
    api.check([tmp_path], apply=True, include_file_types=["jsonc"])
    assert (tmp_path / "local/a.json").read_text(encoding="utf-8") == "{}\n"
    assert TOPMARK_START_MARKER in (tmp_path / "sibling/a.json").read_text(encoding="utf-8")


def test_api_assignment_activation_consent_stays_in_its_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local opt-in consent authorizes local assignments without authorizing siblings."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        """[config]
root = true
[[files.file_type_assignments]]
file_type = "json-as-jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    for directory in ("local", "sibling"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "a.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "local/topmark.toml").write_text(
        """[files]
opt_in_file_types = ["json-as-jsonc"]
""",
        encoding="utf-8",
    )
    result: api.ProbeRunResult = api.probe([tmp_path], include_file_types=["json-as-jsonc"])
    statuses: dict[str, object] = {f.path.parent.name: f.status for f in result.files}
    assert statuses == {
        "local": "resolved",
        "sibling": "activation_blocked",
    }


@pytest.mark.parametrize(
    ("filter_key", "filter_type", "expected_status"),
    [
        ("exclude_file_types", "json", "resolved"),
        ("exclude_file_types", "jsonc", "filtered"),
        ("include_file_types", "json", "filtered"),
        ("include_file_types", "jsonc", "resolved"),
    ],
)
def test_assignment_filters_apply_to_effective_type(
    tmp_path: Path,
    filter_key: str,
    filter_type: str,
    expected_status: str,
) -> None:
    """Public filters veto only the effective assigned type, without fallback."""
    path: Path = tmp_path / "service.json"
    path.write_text("{}\n", encoding="utf-8")
    config: dict[str, object] = {
        "files": {
            "file_type_assignments": [
                {
                    "file_type": "jsonc",
                    "patterns": [path.name],
                    "base": tmp_path.as_posix(),
                }
            ],
            filter_key: [filter_type],
        }
    }
    result: api.ProbeRunResult = api.probe([path], config=config)
    assert result.files[0].status == expected_status
    assert result.files[0].selected_file_type == "jsonc"
    assert result.files[0].selection_method == "assignment"
    assert result.files[0].candidates == ()

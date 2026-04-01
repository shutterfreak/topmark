# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_resolution.py
#   file_relpath : tests/config/test_config_resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""Tests for configuration discovery, precedence, and TOML parsing.

These tests exercise:
- discovery and merge ordering (`load_resolved_config`),
- file-based loading for both `topmark.toml` and `[tool.topmark]` in `pyproject.toml`,
- TOML parsing/normalization in `MutableConfig.from_toml_dict`,
- and that user-facing warnings are mirrored into `MutableConfig.diagnostics`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.conftest import group_patterns
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.io.deserializers import mutable_config_from_toml_dict
from topmark.config.io.deserializers import mutable_config_from_toml_file
from topmark.config.io.resolution import build_effective_config_for_path
from topmark.config.io.resolution import discover_config_layers
from topmark.config.io.resolution import load_resolved_config
from topmark.config.io.resolution import merge_layers_globally
from topmark.config.io.resolution import select_applicable_layers
from topmark.config.keys import Toml
from topmark.config.overrides import ConfigOverrides
from topmark.config.overrides import apply_config_overrides
from topmark.config.policy import HeaderMutationMode
from topmark.resolution.files import resolve_file_list

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.io.types import ConfigLayer
    from topmark.config.io.types import TomlTable
    from topmark.config.io.types import TomlValue
    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.config.types import PatternSource


def _write(path: Path, content: str) -> None:
    """Write a small TOML snippet to `path`, creating parent directories."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        textwrap.dedent(content).lstrip("\n"),
        encoding="utf-8",
    )


@pytest.mark.pipeline
def test_relative_to_resolves_against_config_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`relative_to = "."` in a config file resolves to that file's directory."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src" / "pkg"
    src.mkdir(parents=True)

    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.header]
        relative_to = "."
        """,
    )

    # Anchor discovery under nested path
    draft: MutableConfig = load_resolved_config(input_paths=[src])
    assert draft.relative_to is not None
    assert draft.relative_to == proj.resolve()


@pytest.mark.pipeline
def test_same_dir_precedence_topmark_over_pyproject(tmp_path: Path) -> None:
    """In the same directory, `topmark.toml` overrides `pyproject.toml`."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.formatting]
        align_fields = false
        """,
    )
    _write(
        proj / "topmark.toml",
        """
        [formatting]
        align_fields = true
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[proj])
    # topmark.toml should win within the same directory
    assert draft.align_fields is True


@pytest.mark.pipeline
def test_root_true_stops_traversal(tmp_path: Path) -> None:
    """`root = true` stops discovery above that directory."""
    root: Path = tmp_path / "root"
    child: Path = root / "apps" / "a"
    child.mkdir(parents=True)

    # Parent *above* root that should be ignored if traversal stops
    above: Path = tmp_path / "above"
    _write(
        above / "pyproject.toml",
        """
        [tool.topmark.formatting]
        align_fields = false
        """,
    )

    # Root with `root = true`
    _write(
        root / "pyproject.toml",
        """
        [tool.topmark]
        root = true

        [tool.topmark.formatting]
        align_fields = true
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    # Should see settings from `root`, not from `above`
    assert draft.align_fields is True


@pytest.mark.pipeline
def test_include_from_normalized_to_patternsources(tmp_path: Path) -> None:
    """`include_from` entries are normalized into absolute `PatternSource`s."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    _write(proj / ".gitignore", "*.tmp\n")
    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.files]
        include_from = [".gitignore"]
        """,
    )

    draft: MutableConfig | None = mutable_config_from_toml_file(proj / "pyproject.toml")
    assert draft is not None
    assert draft.include_from, "include_from should not be empty"
    ps: PatternSource = draft.include_from[0]
    assert ps.path.is_absolute()
    assert ps.base == proj.resolve()


@pytest.mark.pipeline
def test_cli_path_options_resolve_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI path-to-file options resolve against the invocation CWD."""
    cwd: Path = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    # Create a file the CLI would reference relatively
    gi: Path = cwd / ".gitignore"
    gi.write_text("*.log\n", encoding="utf-8")

    draft: MutableConfig = mutable_config_from_defaults()
    overrides = ConfigOverrides(
        include_from=[".gitignore"],
    )
    apply_config_overrides(
        draft,
        overrides,
    )

    assert draft.include_from, "CLI include_from should be normalized"
    ps: PatternSource = draft.include_from[0]
    assert ps.path == gi.resolve()
    assert ps.base == cwd.resolve()


@pytest.mark.pipeline
def test_globs_evaluated_relative_to_relative_to(tmp_path: Path) -> None:
    """Globs are evaluated relative to `relative_to` (workspace base)."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src" / "pkg"
    src.mkdir(parents=True)
    py: Path = src / "mod.py"
    py.write_text("print('ok')\n", encoding="utf-8")

    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.header]
        relative_to = "."
        [tool.topmark.files]
        include_patterns = ["src/**/*.py"]
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[proj])
    # `resolve_file_list` should include our file based on the glob evaluated from proj
    paths: list[Path] = resolve_file_list(draft.freeze())
    assert py.resolve() in paths


@pytest.mark.pipeline
def test_relative_to_inheritance_across_multiple_discovered_configs(
    tmp_path: Path,
) -> None:
    """Child config inherits parent's `relative_to` when not set."""
    root: Path = tmp_path / "root"
    child: Path = root / "apps" / "a"
    child.mkdir(parents=True)

    # Parent declares relative_to="."
    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.header]
        relative_to = "."
        """,
    )
    # Child has a config but doesn't set relative_to (should inherit)
    _write(
        child / "pyproject.toml",
        """
        [tool.topmark]
        # no header.relative_to here
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    assert draft.relative_to is not None
    assert draft.relative_to == root.resolve()


@pytest.mark.pipeline
def test_child_overrides_relative_to_with_its_own_dir(tmp_path: Path) -> None:
    """Child config can override `relative_to`, resolved against its own config directory."""
    root: Path = tmp_path / "root"
    child: Path = root / "apps" / "a"
    sub: Path = child / "subroot"
    sub.mkdir(parents=True)

    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.header]
        relative_to = "."
        """,
    )
    _write(
        child / "pyproject.toml",
        """
        [tool.topmark.header]
        relative_to = "subroot"
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    assert draft.relative_to is not None
    assert draft.relative_to == sub.resolve()


@pytest.mark.pipeline
def test_parent_include_from_and_child_exclude_from_normalized_with_proper_bases(
    tmp_path: Path,
) -> None:
    """include_from/exclude_from from different configs normalize with the correct bases."""
    root: Path = tmp_path / "root"
    child: Path = root / "mod"
    child.mkdir(parents=True)
    _write(root / ".gitignore", "*.tmp\n")
    _write(child / ".ignore", "*.log\n")

    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.files]
        include_from = [".gitignore"]
        """,
    )
    _write(
        child / "topmark.toml",
        """
        [files]
        exclude_from = [".ignore"]
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    # include_from normalized to root base
    assert draft.include_from
    assert draft.include_from[0].base == root.resolve()
    # exclude_from normalized to child base
    assert draft.exclude_from
    assert draft.exclude_from[0].base == child.resolve()


# --- Inserted tests ---


@pytest.mark.pipeline
def test_include_from_accumulates_across_multiple_applicable_layers(tmp_path: Path) -> None:
    """include_from sources accumulate across applicable discovered config layers."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)
    _write(root / ".gitignore", "*.tmp\n")
    _write(child / ".include", "src/**/*.py\n")

    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.files]
        include_from = [".gitignore"]
        """,
    )
    _write(
        child / "topmark.toml",
        """
        [files]
        include_from = [".include"]
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    paths: list[Path] = [ps.path for ps in draft.include_from]

    assert paths == [
        (root / ".gitignore").resolve(),
        (child / ".include").resolve(),
    ]


@pytest.mark.pipeline
def test_files_nearest_non_empty_list_wins_across_layers(tmp_path: Path) -> None:
    """Explicit files lists use nearest-wins semantics across applicable layers."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)

    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.files]
        files = ["README.md"]
        """,
    )
    _write(
        child / "topmark.toml",
        """
        [files]
        files = ["module.py"]
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    assert draft.files == [str((child / "module.py").resolve())]


@pytest.mark.pipeline
def test_include_file_types_nearest_non_empty_set_wins_across_layers(tmp_path: Path) -> None:
    """include_file_types uses nearest-wins semantics rather than set union."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    child.mkdir(parents=True)

    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.files]
        include_file_types = ["python"]
        """,
    )
    _write(
        child / "topmark.toml",
        """
        [files]
        include_file_types = ["markdown"]
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    assert draft.include_file_types == {"markdown"}


@pytest.mark.pipeline
def test_select_applicable_layers_filters_child_scoped_layer(tmp_path: Path) -> None:
    """select_applicable_layers keeps global layers and filters file-backed layers by scope."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir(parents=True)

    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.formatting]
        align_fields = false
        """,
    )
    _write(
        child / "topmark.toml",
        """
        [formatting]
        align_fields = true
        """,
    )

    layers: list[ConfigLayer] = discover_config_layers(input_paths=[child])

    child_file: Path = child / "module.py"
    sibling_file: Path = sibling / "guide.md"
    child_file.write_text("x\n", encoding="utf-8")
    sibling_file.write_text("x\n", encoding="utf-8")

    child_layers: list[ConfigLayer] = select_applicable_layers(layers, child_file)
    sibling_layers: list[ConfigLayer] = select_applicable_layers(layers, sibling_file)

    assert any(layer.scope_root == child.resolve() for layer in child_layers)
    assert not any(layer.scope_root == child.resolve() for layer in sibling_layers)


@pytest.mark.pipeline
def test_build_effective_config_for_path_merges_only_applicable_layers(tmp_path: Path) -> None:
    """Per-path effective configs should merge only the layers whose scope applies."""
    root: Path = tmp_path / "root"
    child: Path = root / "pkg"
    sibling: Path = root / "docs"
    child.mkdir(parents=True)
    sibling.mkdir(parents=True)

    _write(
        root / "pyproject.toml",
        """
        [tool.topmark.header]
        fields = ["project", "license"]

        [tool.topmark.fields]
        project = "TopMark"
        license = "MIT"
        """,
    )
    _write(
        child / "topmark.toml",
        """
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

    layers: list[ConfigLayer] = discover_config_layers(input_paths=[child])
    child_cfg: Config = build_effective_config_for_path(layers, child_file).freeze()
    sibling_cfg: Config = build_effective_config_for_path(layers, sibling_file).freeze()

    assert child_cfg.header_fields == ("project", "file")
    assert child_cfg.field_values["project"] == "TopMark"
    assert child_cfg.field_values["file"] == "pkg/module.py"

    assert sibling_cfg.header_fields == ("project", "license")
    assert sibling_cfg.field_values["project"] == "TopMark"
    assert "file" not in sibling_cfg.field_values


@pytest.mark.pipeline
def test_merge_layers_globally_empty_returns_defaults() -> None:
    """Merging an empty layer sequence should fall back to defaults."""
    draft: MutableConfig = merge_layers_globally(())
    default_draft: MutableConfig = mutable_config_from_defaults()

    assert draft.header_fields == default_draft.header_fields
    assert draft.include_from == default_draft.include_from
    assert draft.include_pattern_groups == default_draft.include_pattern_groups


@pytest.mark.pipeline
def test_cli_overrides_merge_last(tmp_path: Path) -> None:
    """CLI overrides have highest precedence."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()

    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.formatting]
        align_fields = false
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[proj])
    # Simulate CLI override
    overrides = ConfigOverrides(
        align_fields=True,
    )
    apply_config_overrides(
        draft,
        overrides,
    )
    assert draft.align_fields is True


@pytest.mark.pipeline
def test_config_seeding_globs_when_no_inputs_and_cwd_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Config-declared globs still seed candidates when CWD differs and no inputs are given."""
    proj: Path = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "mod.py").write_text("x", encoding="utf-8")
    elsewhere: Path = tmp_path / "elsewhere"
    elsewhere.mkdir()

    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.files]
        include_patterns = ["src/**/*.py"]
        """,
    )

    # Build merged config anchored under "elsewhere"
    monkeypatch.chdir(elsewhere)
    draft: MutableConfig = load_resolved_config(
        input_paths=[elsewhere],
        extra_config_files=[proj / "pyproject.toml"],
    )
    files: list[Path] = resolve_file_list(draft.freeze())
    # normalize
    rel: list[str] = sorted(
        (p if not p.is_absolute() else p.relative_to(tmp_path)).as_posix() for p in files
    )
    assert rel == ["proj/src/mod.py"]


@pytest.mark.pipeline
def test_files_from_declared_in_config_normalizes_to_patternsource(tmp_path: Path) -> None:
    """files_from entries become absolute PatternSource with base set to the config dir."""
    proj: Path = tmp_path / "proj"
    proj.mkdir()
    lst: Path = proj / "files.txt"
    lst.write_text("src/a.py\n", encoding="utf-8")

    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.files]
        files_from = ["files.txt"]
        """,
    )

    draft: MutableConfig | None = mutable_config_from_toml_file(proj / "pyproject.toml")
    assert draft is not None
    assert draft.files_from
    ps: PatternSource = draft.files_from[0]
    assert ps.path == lst.resolve()
    assert ps.base == proj.resolve()


@pytest.mark.pipeline
def test_malformed_toml_in_discovered_config_is_ignored(tmp_path: Path) -> None:
    """Discovery ignores TOML parse errors in an unrelated parent."""
    parent: Path = tmp_path / "parent"
    child: Path = parent / "child"
    child.mkdir(parents=True)

    # Malformed pyproject.toml in parent
    (parent / "pyproject.toml").write_text("[tool.topmark\nbad", encoding="utf-8")
    # Valid config in child
    _write(
        child / "topmark.toml",
        """
        [formatting]
        align_fields = true
        """,
    )

    draft: MutableConfig = load_resolved_config(input_paths=[child])
    assert draft.align_fields is True


def _diag_messages(draft: MutableConfig) -> list[str]:
    """Return all diagnostic messages recorded on `draft`."""
    return [d.message for d in draft.diagnostics]


def _caplog_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return all captured log messages."""
    return [r.message for r in caplog.records]


def assert_warned_and_diagnosed(
    *,
    caplog: pytest.LogCaptureFixture,
    draft: MutableConfig,
    needle: str,
    min_count: int = 1,
) -> None:
    """Assert a warning substring appears in logs and `draft.diagnostics`.

    Args:
        caplog: Pytest log capture fixture.
        draft: Parsed draft config with diagnostics attached.
        needle: Substring expected to appear in warning messages.
        min_count: Minimum number of matching messages expected in *each*
            sink (logs and diagnostics). Defaults to 1.
    """
    caplog_msgs: list[str] = _caplog_messages(caplog)
    diag_msgs: list[str] = _diag_messages(draft)

    log_hits: int = sum(1 for m in caplog_msgs if needle in m)
    diag_hits: int = sum(1 for m in diag_msgs if needle in m)

    assert log_hits >= min_count, (
        f"Expected at least {min_count} log message(s) containing: {needle!r}.\n"
        f"Found: {log_hits}.\nCaptured logs:\n- " + "\n- ".join(caplog_msgs)
    )
    assert diag_hits >= min_count, (
        f"Expected at least {min_count} diagnostic(s) containing: {needle!r}.\n"
        f"Found: {diag_hits}.\nDiagnostics:\n- " + "\n- ".join(diag_msgs)
    )


def assert_not_warned(
    *,
    caplog: pytest.LogCaptureFixture,
    needle: str,
) -> None:
    """Assert no captured log message contains `needle`."""
    caplog_msgs: list[str] = _caplog_messages(caplog)
    assert not any(needle in m for m in caplog_msgs), (
        f"Did not expect log message containing: {needle!r}.\n"
        f"Captured logs:\n- " + "\n- ".join(caplog_msgs)
    )


@pytest.mark.pipeline
def test_header_fields_wrong_type_is_treated_as_empty() -> None:
    """Wrong-type [header].fields is treated as empty (must not crash)."""
    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_HEADER: {Toml.KEY_FIELDS: True}},
    )
    assert draft.header_fields == []


@pytest.mark.pipeline
def test_header_fields_mixed_types_ignores_non_strings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-string entries in [header].fields are ignored with a warning."""
    caplog.set_level("WARNING")

    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_HEADER: {Toml.KEY_FIELDS: ["file", 123, "file_relpath"]}},
    )

    assert draft.header_fields == ["file", "file_relpath"]

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_HEADER}].{Toml.KEY_FIELDS}",
        min_count=1,
    )


@pytest.mark.pipeline
def test_unknown_top_level_keys_warn_and_are_recorded(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown top-level TOML keys are warned about and recorded in diagnostics."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict({"unknown_root_key": 123})

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Unknown TOML key(s) in top-level",
    )


@pytest.mark.pipeline
def test_unknown_top_level_table_warns_and_is_recorded(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown top-level tables (unknown sections) are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict({"bogus": {"x": 1}})

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Unknown TOML key(s) in top-level",
    )


@pytest.mark.pipeline
def test_unknown_keys_are_reported_in_sorted_order(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown-key diagnostics list keys in sorted order for stable output."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_FILES: {Toml.KEY_INCLUDE_PATTERNS: ["src/**"], "z": True, "a": True}}
    )

    needle: str = f"Unknown TOML key(s) in [{Toml.SECTION_FILES}] (ignored): a, z"
    assert_warned_and_diagnosed(caplog=caplog, draft=draft, needle=needle)


@pytest.mark.pipeline
def test_policy_by_type_section_wrong_type_is_ignored() -> None:
    """Non-table [policy_by_type] values are ignored (must not crash)."""
    draft: MutableConfig = mutable_config_from_toml_dict({Toml.SECTION_POLICY_BY_TYPE: 123})
    assert draft.policy_by_type == {}


# Silence pyright for empty lists and sets of strings
_empty_str_list: list[str] = []
_empty_str_set: set[str] = set()


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "key,_kind,expect_empty",
    [
        (Toml.KEY_INCLUDE_PATTERNS, "pattern_groups", _empty_str_list),
        (Toml.KEY_EXCLUDE_PATTERNS, "pattern_groups", _empty_str_list),
        (Toml.KEY_INCLUDE_FROM, "attr", _empty_str_list),
        (Toml.KEY_EXCLUDE_FROM, "attr", _empty_str_list),
        (Toml.KEY_FILES_FROM, "attr", _empty_str_list),
        (Toml.KEY_INCLUDE_FILE_TYPES, "attr", _empty_str_set),
        (Toml.KEY_EXCLUDE_FILE_TYPES, "attr", _empty_str_set),
    ],
)
def test_files_list_valued_keys_wrong_type_is_treated_as_empty(
    key: str,
    _kind: str,
    expect_empty: object,
) -> None:
    """Wrong-type list values in [files] are treated as empty (must not crash)."""
    toml_dict: TomlTable = {Toml.SECTION_FILES: {key: True}}
    draft: MutableConfig = mutable_config_from_toml_dict(toml_dict)

    if key == Toml.KEY_INCLUDE_PATTERNS:
        assert group_patterns(draft.include_pattern_groups) == expect_empty
    elif key == Toml.KEY_EXCLUDE_PATTERNS:
        assert group_patterns(draft.exclude_pattern_groups) == expect_empty
    elif key == Toml.KEY_INCLUDE_FROM:
        assert draft.include_from == expect_empty
    elif key == Toml.KEY_EXCLUDE_FROM:
        assert draft.exclude_from == expect_empty
    elif key == Toml.KEY_FILES_FROM:
        assert draft.files_from == expect_empty
    elif key == Toml.KEY_INCLUDE_FILE_TYPES:
        assert draft.include_file_types == expect_empty
    else:
        assert draft.exclude_file_types == expect_empty


@pytest.mark.pipeline
def test_include_from_mixed_types_ignores_non_strings(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-string entries in [files].include_from are ignored with a warning."""
    caplog.set_level("WARNING")

    proj: Path = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_text("*.tmp\n", encoding="utf-8")

    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_FILES: {Toml.KEY_INCLUDE_FROM: ["a.txt", 123]}},
        config_file=proj / "topmark.toml",
    )

    assert len(draft.include_from) == 1
    assert draft.include_from[0].path.name == "a.txt"

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_FILES}].{Toml.KEY_INCLUDE_FROM}",
    )


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "key,is_include",
    [
        (Toml.KEY_INCLUDE_PATTERNS, True),
        (Toml.KEY_EXCLUDE_PATTERNS, False),
    ],
)
def test_glob_patterns_mixed_types_ignores_non_strings(
    caplog: pytest.LogCaptureFixture,
    key: str,
    is_include: bool,
) -> None:
    """Non-string entries in [files].(include|exclude)_patterns are ignored with a warning."""
    caplog.set_level("WARNING")

    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_FILES: {key: ["src/**/*.py", 123]}},
    )

    patterns: list[str] = group_patterns(
        draft.include_pattern_groups if is_include else draft.exclude_pattern_groups
    )
    assert patterns == ["src/**/*.py"]

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_FILES}].{key}",
        min_count=1,
    )


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "key,is_include",
    [
        (Toml.KEY_INCLUDE_PATTERNS, True),
        (Toml.KEY_EXCLUDE_PATTERNS, False),
    ],
)
def test_glob_patterns_all_non_strings_results_in_empty_list(
    caplog: pytest.LogCaptureFixture,
    key: str,
    is_include: str,
) -> None:
    """If all entries are non-strings, the patterns list becomes empty (and warnings emitted)."""
    caplog.set_level("WARNING")

    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_FILES: {key: [True, 123]}},
    )

    patterns: list[str] = group_patterns(
        draft.include_pattern_groups if is_include else draft.exclude_pattern_groups
    )
    assert patterns == []

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_FILES}].{key}",
        min_count=2,
    )


@pytest.mark.pipeline
def test_unknown_section_keys_warn_and_are_recorded(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown keys inside known sections are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {
            Toml.SECTION_FILES: {
                Toml.KEY_INCLUDE_PATTERNS: ["src/**/*.py"],
                "bogus": True,
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{Toml.SECTION_FILES}]",
    )


@pytest.mark.pipeline
def test_section_wrong_type_warns_and_is_ignored(caplog: pytest.LogCaptureFixture) -> None:
    """If a known section is not a table, TopMark warns and ignores it."""
    caplog.set_level("WARNING")
    # [files] must be a table; provide a scalar to trigger the warning.
    draft: MutableConfig = mutable_config_from_toml_dict({Toml.SECTION_FILES: "not-a-table"})

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"TOML section [{Toml.SECTION_FILES}] must be a table",
    )


@pytest.mark.pipeline
def test_policy_by_type_unknown_keys_warn(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown keys inside [policy_by_type.<ft>] are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": {
                    Toml.KEY_POLICY_HEADER_MUTATION_MODE: HeaderMutationMode.ADD_ONLY.value,
                    "unknown_policy_key": False,
                }
            }
        }
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{Toml.SECTION_POLICY_BY_TYPE}.python]",
    )


@pytest.mark.pipeline
def test_policy_by_type_entry_wrong_type_warns(caplog: pytest.LogCaptureFixture) -> None:
    """Non-table entries in [policy_by_type] are warned about and ignored."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_POLICY_BY_TYPE: {"python": 123}}
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"TOML section [{Toml.SECTION_POLICY_BY_TYPE}.python] must be a table",
    )


@pytest.mark.pipeline
@pytest.mark.parametrize("filename", ["topmark.toml", "pyproject.toml"])
def test_unknown_keys_reported_via_from_toml_file(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    filename: str,
) -> None:
    """Unknown keys are also reported when loading from a TOML file."""
    caplog.set_level("WARNING")
    p: Path = tmp_path / filename

    if filename == "topmark.toml":
        # Root table for topmark.toml
        p.write_text(
            """
            [files]
            include_patterns = ["src/**/*.py"]
            unknown_key = true
            """.lstrip(),
            encoding="utf-8",
        )
    else:
        # Nested under [tool.topmark] for pyproject.toml
        p.write_text(
            """
            [tool.topmark.files]
            include_patterns = ["src/**/*.py"]
            unknown_key = true
            """.lstrip(),
            encoding="utf-8",
        )

    draft: MutableConfig | None = mutable_config_from_toml_file(p)
    assert draft is not None

    # We should see a warning for the unknown key inside [files]
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{Toml.SECTION_FILES}]",
    )


@pytest.mark.pipeline
def test_fields_scalar_values_are_stringified_and_unsupported_are_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """[fields] values are stringified for scalar types; ignore unsupported values.

    Unsupported values are ignored with location.
    """
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {
            Toml.SECTION_FIELDS: {
                "project": "TopMark",
                "year": 2025,
                "pi": 3.14,
                "flag": True,
                "bad": {"nested": "nope"},
                "bad_list": [1, 2],
                "bad_none": None,
            }
        }
    )

    assert draft.field_values["project"] == "TopMark"
    assert draft.field_values["year"] == "2025"
    assert draft.field_values["pi"] == "3.14"
    assert draft.field_values["flag"] == "True"
    assert "bad" not in draft.field_values
    assert "bad_list" not in draft.field_values
    assert "bad_none" not in draft.field_values

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Ignoring unsupported field value for [fields].bad",
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Ignoring unsupported field value for [fields].bad_list",
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Ignoring unsupported field value for [fields].bad_none",
    )


@pytest.mark.pipeline
def test_fields_table_is_free_form_and_not_subject_to_unknown_key_validation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """[fields] is intentionally free-form and must not be subject to unknown-key validation."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {
            Toml.SECTION_FIELDS: {"totally_custom": "x"},
            Toml.SECTION_FILES: {Toml.KEY_INCLUDE_PATTERNS: ["src/**"], "bogus": True},
        }
    )

    # Should warn about bogus in [files]
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{Toml.SECTION_FILES}]",
    )
    # Should NOT warn about fields keys being unknown
    assert_not_warned(caplog=caplog, needle="Unknown TOML key(s) in [fields]")

    assert draft.field_values["totally_custom"] == "x"


@pytest.mark.pipeline
def test_header_fields_can_reference_missing_custom_fields_without_error() -> None:
    """header.fields may reference names not present in [fields] and should not crash."""
    draft: MutableConfig = mutable_config_from_toml_dict(
        {
            Toml.SECTION_HEADER: {Toml.KEY_FIELDS: ["file", "project", "missing_custom"]},
            Toml.SECTION_FIELDS: {"project": "TopMark"},
        }
    )
    assert draft.header_fields == ["file", "project", "missing_custom"]
    assert draft.field_values["project"] == "TopMark"


@pytest.mark.pipeline
def test_policy_by_type_valid_keys_parse_and_unknown_keys_are_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Valid [policy_by_type] entries parse; unknown keys are warned and ignored."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": {
                    Toml.KEY_POLICY_HEADER_MUTATION_MODE: HeaderMutationMode.ADD_ONLY.value,
                    "bogus": False,
                }
            }
        }
    )

    assert "python" in draft.policy_by_type
    assert draft.policy_by_type["python"].header_mutation_mode == HeaderMutationMode.ADD_ONLY

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{Toml.SECTION_POLICY_BY_TYPE}.python]",
    )


@pytest.mark.pipeline
@pytest.mark.parametrize("bad_val", ["x", 123, {"a": 1}, None])
def test_header_fields_wrong_type_falls_back_to_empty_list(bad_val: TomlValue) -> None:
    """Wrong-type list values should be treated as empty lists (parsing must not crash)."""
    # NOTE: If you want warnings for that, add them later in one place
    #       and update this test accordingly

    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_HEADER: {Toml.KEY_FIELDS: bad_val}}
    )
    assert draft.header_fields == []


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "section, valid_key, valid_value",
    [
        (Toml.SECTION_HEADER, Toml.KEY_FIELDS, ["file"]),
        (Toml.SECTION_FILES, Toml.KEY_INCLUDE_PATTERNS, ["src/**"]),
        (Toml.SECTION_WRITER, Toml.KEY_TARGET, "file"),
        (Toml.SECTION_FORMATTING, Toml.KEY_ALIGN_FIELDS, True),
        (
            Toml.SECTION_POLICY,
            Toml.KEY_POLICY_HEADER_MUTATION_MODE,
            HeaderMutationMode.ADD_ONLY.value,
        ),
    ],
)
def test_unknown_key_in_known_section_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
    section: str,
    valid_key: str,
    valid_value: TomlValue,
) -> None:
    """Unknown keys inside closed sections are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {section: {valid_key: valid_value, "bogus": True}}
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{section}]",
    )


def test_extend_pattern_sources_resolves_relative_paths_against_base(tmp_path: Path) -> None:
    """extend_pattern_sources() resolves relative paths against the provided base."""
    from topmark.config.paths import extend_pattern_sources
    from topmark.config.paths import pattern_source_from_config

    cfg_dir: Path = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "a.txt").write_text("x", encoding="utf-8")

    dst: list[PatternSource] = []
    extend_pattern_sources(
        ["a.txt"],
        dst=dst,
        mk=pattern_source_from_config,
        kind="include_from",
        base=cfg_dir,
    )

    assert len(dst) == 1
    assert dst[0].path == (cfg_dir / "a.txt").resolve()
    assert dst[0].base == (cfg_dir / "a.txt").resolve().parent


@pytest.mark.pipeline
def test_duplicate_include_file_types_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicate include_file_types entries produce a warning and a diagnostic."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_FILES: {Toml.KEY_INCLUDE_FILE_TYPES: ["python", "python"]}}
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Duplicate included file types found in config "
        f"(key: {Toml.KEY_INCLUDE_FILE_TYPES})",
    )


@pytest.mark.pipeline
def test_duplicate_exclude_file_types_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicate exclude_file_types entries produce a warning and a diagnostic."""
    caplog.set_level("WARNING")
    draft: MutableConfig = mutable_config_from_toml_dict(
        {Toml.SECTION_FILES: {Toml.KEY_EXCLUDE_FILE_TYPES: ["python", "python"]}}
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Duplicate excluded file types found in config "
        f"(key: {Toml.KEY_EXCLUDE_FILE_TYPES})",
    )


@pytest.mark.pipeline
def test_should_proceed_false_on_errors_even_when_not_strict() -> None:
    """Errors always prevent proceeding, regardless of strict mode."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.strict_config_checking = False
    draft.diagnostics.add_error("boom")
    assert draft.should_proceed is False

    c: Config = draft.freeze()
    assert c.should_proceed is False


@pytest.mark.pipeline
def test_should_proceed_true_on_warnings_when_not_strict() -> None:
    """Warnings do not block proceeding when strict mode is disabled."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.strict_config_checking = False
    draft.diagnostics.add_warning("warn")
    assert draft.should_proceed is True

    c: Config = draft.freeze()
    assert c.should_proceed is True


@pytest.mark.pipeline
def test_should_proceed_false_on_warnings_when_strict() -> None:
    """Warnings block proceeding when strict mode is enabled."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.strict_config_checking = True
    draft.diagnostics.add_warning("warn")
    assert draft.should_proceed is False

    c: Config = draft.freeze()
    assert c.strict_config_checking is True
    assert c.should_proceed is False


@pytest.mark.pipeline
def test_freeze_preserves_diagnostics() -> None:
    """freeze() must preserve diagnostics when producing an immutable Config."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.diagnostics.add_warning("hello")
    c: Config = draft.freeze()
    assert len(c.diagnostics.items) == 1
    assert c.diagnostics.items[0].message == "hello"


@pytest.mark.pipeline
@pytest.mark.parametrize("val,expected", [(None, False), (False, False), (True, True)])
def test_strict_config_checking_freeze_bool_semantics(val: object, expected: bool) -> None:
    """freeze() normalizes strict_config_checking to a concrete bool.

    strict_config_checking defaults to False when not explicitly True.
    """
    draft: MutableConfig = mutable_config_from_defaults()
    draft.strict_config_checking = val  # type: ignore[assignment]
    c: Config = draft.freeze()
    assert c.strict_config_checking is expected

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
- discovery and merge ordering (`MutableConfig.load_merged`),
- file-based loading for both `topmark.toml` and `[tool.topmark]` in `pyproject.toml`,
- TOML parsing/normalization in `MutableConfig.from_toml_dict`,
- and that user-facing warnings are mirrored into `MutableConfig.diagnostics`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from topmark.config import MutableConfig, PatternSource
from topmark.config.keys import Toml
from topmark.file_resolver import resolve_file_list

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, content: str) -> None:
    """Write a small TOML snippet to `path`, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


@pytest.mark.pipeline
def test_relative_to_resolves_against_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`relative_to = "."` in a config file resolves to that file's directory."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src" / "pkg"
    src.mkdir(parents=True)

    _write(
        proj / "pyproject.toml",
        """
        [tool.topmark.files]
        relative_to = "."
        """,
    )

    # Anchor discovery under nested path
    draft: MutableConfig = MutableConfig.load_merged(input_paths=[src])
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

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[proj])
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

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[child])
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

    draft: MutableConfig | None = MutableConfig.from_toml_file(proj / "pyproject.toml")
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

    draft: MutableConfig = MutableConfig.from_defaults()
    draft.apply_args({"include_from": [".gitignore"]})

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
        [tool.topmark.files]
        relative_to = "."
        include_patterns = ["src/**/*.py"]
        """,
    )

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[proj])
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
        [tool.topmark.files]
        relative_to = "."
        """,
    )
    # Child has a config but doesn't set relative_to (should inherit)
    _write(
        child / "pyproject.toml",
        """
        [tool.topmark]
        # no files.relative_to here
        """,
    )

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[child])
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
        [tool.topmark.files]
        relative_to = "."
        """,
    )
    _write(
        child / "pyproject.toml",
        """
        [tool.topmark.files]
        relative_to = "subroot"
        """,
    )

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[child])
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

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[child])
    # include_from normalized to root base
    assert draft.include_from
    assert draft.include_from[0].base == root.resolve()
    # exclude_from normalized to child base
    assert draft.exclude_from
    assert draft.exclude_from[0].base == child.resolve()


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

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[proj])
    # Simulate CLI override
    draft.apply_args({"align_fields": True})
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
    draft: MutableConfig = MutableConfig.load_merged(
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

    draft: MutableConfig | None = MutableConfig.from_toml_file(proj / "pyproject.toml")
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

    draft: MutableConfig = MutableConfig.load_merged(input_paths=[child])
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
        caplog (pytest.LogCaptureFixture): Pytest log capture fixture.
        draft (MutableConfig): Parsed draft config with diagnostics attached.
        needle (str): Substring expected to appear in warning messages.
        min_count (int): Minimum number of matching messages expected in *each*
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
    draft: MutableConfig = MutableConfig.from_toml_dict(
        {Toml.SECTION_HEADER: {Toml.KEY_FIELDS: True}},
    )
    assert draft.header_fields == []


@pytest.mark.pipeline
def test_header_fields_mixed_types_ignores_non_strings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-string entries in [header].fields are ignored with a warning."""
    caplog.set_level("WARNING")

    draft: MutableConfig = MutableConfig.from_toml_dict(
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
    draft: MutableConfig = MutableConfig.from_toml_dict({"unknown_root_key": 123})

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Unknown TOML key(s) in top-level",
    )


@pytest.mark.pipeline
def test_unknown_top_level_table_warns_and_is_recorded(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown top-level tables (unknown sections) are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = MutableConfig.from_toml_dict({"bogus": {"x": 1}})

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle="Unknown TOML key(s) in top-level",
    )


@pytest.mark.pipeline
def test_unknown_keys_are_reported_in_sorted_order(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown-key diagnostics list keys in sorted order for stable output."""
    caplog.set_level("WARNING")
    draft: MutableConfig = MutableConfig.from_toml_dict(
        {Toml.SECTION_FILES: {Toml.KEY_INCLUDE_PATTERNS: ["src/**"], "z": True, "a": True}}
    )

    needle: str = f"Unknown TOML key(s) in [{Toml.SECTION_FILES}] (ignored): a, z"
    assert_warned_and_diagnosed(caplog=caplog, draft=draft, needle=needle)


@pytest.mark.pipeline
def test_policy_by_type_section_wrong_type_is_ignored() -> None:
    """Non-table [policy_by_type] values are ignored (must not crash)."""
    draft: MutableConfig = MutableConfig.from_toml_dict({Toml.SECTION_POLICY_BY_TYPE: 123})
    assert draft.policy_by_type == {}


# Silence pyright for empty lists and sets of strings
_empty_str_list: list[str] = []
_empty_str_set: set[str] = set()


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "key,bad_value,attr,expect_empty",
    [
        (Toml.KEY_INCLUDE_PATTERNS, True, "include_patterns", _empty_str_list),
        (Toml.KEY_EXCLUDE_PATTERNS, True, "exclude_patterns", _empty_str_list),
        (Toml.KEY_INCLUDE_FROM, True, "include_from", _empty_str_list),
        (Toml.KEY_EXCLUDE_FROM, True, "exclude_from", _empty_str_list),
        (Toml.KEY_FILES_FROM, True, "files_from", _empty_str_list),
        (Toml.KEY_INCLUDE_FILE_TYPES, True, "include_file_types", _empty_str_set),
        (Toml.KEY_EXCLUDE_FILE_TYPES, True, "exclude_file_types", _empty_str_set),
    ],
)
def test_files_list_valued_keys_wrong_type_is_treated_as_empty(
    key: str,
    bad_value: object,
    attr: str,
    expect_empty: object,
) -> None:
    """Wrong-type list values in [files] are treated as empty (must not crash)."""
    draft: MutableConfig = MutableConfig.from_toml_dict({Toml.SECTION_FILES: {key: bad_value}})

    assert getattr(draft, attr) == expect_empty


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

    draft: MutableConfig = MutableConfig.from_toml_dict(
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
    "key,attr",
    [
        (Toml.KEY_INCLUDE_PATTERNS, "include_patterns"),
        (Toml.KEY_EXCLUDE_PATTERNS, "exclude_patterns"),
    ],
)
def test_glob_patterns_mixed_types_ignores_non_strings(
    caplog: pytest.LogCaptureFixture,
    key: str,
    attr: str,
) -> None:
    """Non-string entries in [files].(include|exclude)_patterns are ignored with a warning."""
    caplog.set_level("WARNING")

    draft: MutableConfig = MutableConfig.from_toml_dict(
        {Toml.SECTION_FILES: {key: ["src/**/*.py", 123]}},
    )

    assert getattr(draft, attr) == ["src/**/*.py"]

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Ignoring non-string entry in [{Toml.SECTION_FILES}].{key}",
        min_count=1,
    )


@pytest.mark.pipeline
@pytest.mark.parametrize(
    "key,attr",
    [
        (Toml.KEY_INCLUDE_PATTERNS, "include_patterns"),
        (Toml.KEY_EXCLUDE_PATTERNS, "exclude_patterns"),
    ],
)
def test_glob_patterns_all_non_strings_results_in_empty_list(
    caplog: pytest.LogCaptureFixture,
    key: str,
    attr: str,
) -> None:
    """If all entries are non-strings, the patterns list becomes empty (and warnings emitted)."""
    caplog.set_level("WARNING")

    draft: MutableConfig = MutableConfig.from_toml_dict(
        {Toml.SECTION_FILES: {key: [True, 123]}},
    )

    assert getattr(draft, attr) == []

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
    draft: MutableConfig = MutableConfig.from_toml_dict(
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
    draft: MutableConfig = MutableConfig.from_toml_dict({Toml.SECTION_FILES: "not-a-table"})

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"TOML section [{Toml.SECTION_FILES}] must be a table",
    )


@pytest.mark.pipeline
def test_policy_by_type_unknown_keys_warn(caplog: pytest.LogCaptureFixture) -> None:
    """Unknown keys inside [policy_by_type.<ft>] are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = MutableConfig.from_toml_dict(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": {
                    Toml.KEY_POLICY_CHECK_ADD_ONLY: True,
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
    draft: MutableConfig = MutableConfig.from_toml_dict(
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

    draft: MutableConfig | None = MutableConfig.from_toml_file(p)
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
    draft: MutableConfig = MutableConfig.from_toml_dict(
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
    draft: MutableConfig = MutableConfig.from_toml_dict(
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
    draft: MutableConfig = MutableConfig.from_toml_dict(
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
    draft: MutableConfig = MutableConfig.from_toml_dict(
        {
            Toml.SECTION_POLICY_BY_TYPE: {
                "python": {
                    Toml.KEY_POLICY_CHECK_ADD_ONLY: True,
                    "bogus": False,
                }
            }
        }
    )

    assert "python" in draft.policy_by_type
    assert draft.policy_by_type["python"].add_only is True

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{Toml.SECTION_POLICY_BY_TYPE}.python]",
    )


@pytest.mark.pipeline
@pytest.mark.parametrize("bad_val", ["x", 123, {"a": 1}, None])
def test_header_fields_wrong_type_falls_back_to_empty_list(bad_val: object) -> None:
    """Wrong-type list values should be treated as empty lists (parsing must not crash)."""
    # NOTE: If you want warnings for that, add them later in one place
    #       and update this test accordingly

    draft: MutableConfig = MutableConfig.from_toml_dict(
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
        (Toml.SECTION_POLICY, Toml.KEY_POLICY_CHECK_ADD_ONLY, True),
    ],
)
def test_unknown_key_in_known_section_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
    section: str,
    valid_key: str,
    valid_value: object,
) -> None:
    """Unknown keys inside closed sections are warned about and recorded."""
    caplog.set_level("WARNING")
    draft: MutableConfig = MutableConfig.from_toml_dict(
        {section: {valid_key: valid_value, "bogus": True}}
    )

    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Unknown TOML key(s) in [{section}]",
    )


def test_extend_pattern_sources_resolves_relative_paths_against_base(tmp_path: Path) -> None:
    """extend_pattern_sources() resolves relative paths against the provided base."""
    from topmark.config.paths import extend_pattern_sources, ps_from_config

    cfg_dir: Path = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "a.txt").write_text("x", encoding="utf-8")

    dst: list[PatternSource] = []
    extend_pattern_sources(dst, ["a.txt"], ps_from_config, "include_from", cfg_dir)

    assert len(dst) == 1
    assert dst[0].path == (cfg_dir / "a.txt").resolve()
    assert dst[0].base == (cfg_dir / "a.txt").resolve().parent


@pytest.mark.pipeline
def test_duplicate_include_file_types_warns_and_is_recorded(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicate include_file_types entries produce a warning and a diagnostic."""
    caplog.set_level("WARNING")
    draft: MutableConfig = MutableConfig.from_toml_dict(
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
    draft: MutableConfig = MutableConfig.from_toml_dict(
        {Toml.SECTION_FILES: {Toml.KEY_EXCLUDE_FILE_TYPES: ["python", "python"]}}
    )
    assert_warned_and_diagnosed(
        caplog=caplog,
        draft=draft,
        needle=f"Duplicate excluded file types found in config "
        f"(key: {Toml.KEY_EXCLUDE_FILE_TYPES})",
    )

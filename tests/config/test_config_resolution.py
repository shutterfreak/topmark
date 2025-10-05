# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_resolution.py
#   file_relpath : tests/config/test_config_resolution.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end


"""End-to-end tests for TopMark configuration discovery, precedence, and path normalization."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from topmark.config import MutableConfig, PatternSource
from topmark.file_resolver import resolve_file_list

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, content: str) -> None:
    """Helper: write dedented content to a file, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


@pytest.mark.pipeline
def test_relative_to_resolves_against_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`relative_to = "."` in a config file must resolve to that file's directory."""
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
    """In the same directory, `pyproject.toml` is merged first, then `topmark.toml` overrides it."""
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
    """Paths in `include_from` are normalized to absolute PatternSource with proper base."""
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
    """CLI path-to-file options resolve against the *invocation CWD* and become absolute."""
    cwd: Path = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    # Create a file the CLI would reference relatively
    gi: Path = cwd / ".gitignore"
    gi.write_text("*.log\n", encoding="utf-8")

    draft: MutableConfig = MutableConfig.from_defaults()
    draft.apply_cli_args({"include_from": [".gitignore"]})

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
    """Child config inherits parent's `relative_to` when not set; resolves against parent dir."""
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
    """Child config can override `relative_to`, resolved against the child config directory."""
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
    """include_from/exclude_from from different configs normalize with correct bases.

    include_from/exclude_from from different configs normalize to PatternSource with correct bases.
    """
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
    """CLI overrides have highest precedence and can flip values set in config."""
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
    draft.apply_cli_args({"align_fields": True})
    assert draft.align_fields is True


@pytest.mark.pipeline
def test_config_seeding_globs_when_no_inputs_and_cwd_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no inputs, config-declared globs seed candidates from config dir even if CWD differs.

    When no inputs are given, config-declared globs seed candidates from the config dir
    even if CWD differs.
    """
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
    """Discovery ignores parse errors in an unrelated parent and continues with others."""
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

# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_discovery_parity.py
#   file_relpath : tests/api/test_api_discovery_parity.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API–CLI discovery parity tests.

These tests assert that `topmark.api.check()` with `config=None` follows the
same discovery/precedence model as the CLI:
  * root → current directory order (nearest wins)
  * same-directory precedence: pyproject.toml first, then topmark.toml
  * honors `root = true` to stop traversal
  * discovery anchor is the first input path (its parent if a file), else CWD
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.api.conftest import run_cli_like
from topmark import api
from topmark.config.keys import Toml
from topmark.config.model import MutableConfig
from topmark.pipeline.context.model import ProcessingContext

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig
    from topmark.pipeline.context.model import ProcessingContext


def _write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def _mk_py_headerless() -> str:
    # headerless file that will receive a header in dry-run
    return "print('ok')\n"


def _contains_aligned_fields(diff: str) -> bool:
    # When align_fields=True, header uses padded keys e.g. "file         :"
    return "file         :" in diff


def _contains_unaligned_fields(diff: str) -> bool:
    """Detect unaligned header fields (align_fields=False).

    Unaligned format is now 'file: value' (no space before ':'), while aligned
    format contains padding, e.g. 'file         : value'.
    """
    return ("file:" in diff) and ("file         :" not in diff)


@pytest.mark.api
@pytest.mark.cli
@pytest.mark.integration
def test_same_dir_precedence_topmark_over_pyproject(tmp_path: Path) -> None:
    """Nearest directory: topmark.toml should override pyproject.toml in the same dir."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src"
    _write(src / "a.py", _mk_py_headerless())

    # Same directory: pyproject sets align_fields = false, topmark.toml sets true
    _write(
        proj / "pyproject.toml",
        textwrap.dedent(
            f"""
            [tool.topmark]
            [tool.topmark.{Toml.SECTION_FORMATTING}]
            {Toml.KEY_ALIGN_FIELDS} = false
            """
        ).strip()
        + "\n",
    )
    _write(
        proj / "topmark.toml",
        textwrap.dedent(
            f"""
            [{Toml.SECTION_FORMATTING}]
            {Toml.KEY_ALIGN_FIELDS} = true
            """
        ).strip()
        + "\n",
    )

    apply: bool = False
    diff: bool = True

    # API run (anchor = project dir)
    rr: api.RunResult = api.check(
        [str(proj)],
        apply=apply,
        diff=diff,
        prune_views=False,
        include_file_types=("python",),
    )
    assert rr.files, "API produced no files to check"
    api_diff: str = rr.files[0].diff or ""

    # CLI-like run from same anchor
    _draft: MutableConfig
    files: list[Path]
    results: list[ProcessingContext]
    _draft, files, results = run_cli_like(
        proj,
        kind="check",
        apply=apply,
        diff=diff,
        prune_views=False,
        include_file_types=("python",),
    )
    assert files, "CLI-like resolver produced no files"

    # The aligned form must be present (topmark.toml overrides pyproject.toml)
    assert _contains_aligned_fields(api_diff), "API did not reflect topmark.toml override"
    # Parity: ensure CLI-like result also aligns
    cli_diff: str = results[0].views.diff.text or "" if results[0].views.diff else ""
    assert _contains_aligned_fields(cli_diff), "CLI-like did not reflect topmark.toml override"


@pytest.mark.api
@pytest.mark.cli
@pytest.mark.integration
def test_discovery_anchor_subdir_nearest_wins(tmp_path: Path) -> None:
    """Anchor in subdir: parent pyproject.toml, child topmark.toml — child wins."""
    proj: Path = tmp_path / "proj"
    child: Path = proj / "pkg"
    _write(child / "b.py", _mk_py_headerless())

    _write(
        proj / "pyproject.toml",
        textwrap.dedent(
            f"""
            [tool.topmark]
            [tool.topmark.{Toml.SECTION_FORMATTING}]
            {Toml.KEY_ALIGN_FIELDS} = false
            """
        ).strip()
        + "\n",
    )
    _write(
        child / "topmark.toml",
        textwrap.dedent(
            f"""
            [{Toml.SECTION_FORMATTING}]
            {Toml.KEY_ALIGN_FIELDS} = true
            """
        ).strip()
        + "\n",
    )

    apply: bool = False
    diff: bool = True

    # API run with anchor at child dir
    rr: api.RunResult = api.check(
        [str(child)],
        apply=apply,
        diff=diff,
        prune_views=False,
        include_file_types=("python",),
    )
    assert rr.files
    api_diff: str = rr.files[0].diff or ""
    assert _contains_aligned_fields(api_diff), "API did not honor nearest (child) config"

    # CLI-like parity
    _draft: MutableConfig
    files: list[Path]
    results: list[ProcessingContext]
    _draft, files, results = run_cli_like(
        child,
        kind="check",
        apply=apply,
        diff=diff,
        prune_views=False,
        include_file_types=("python",),
    )
    assert files
    cli_diff: str = results[0].views.diff.text or "" if results[0].views.diff else ""
    assert _contains_aligned_fields(cli_diff), "CLI-like did not honor nearest (child) config"


@pytest.mark.api
@pytest.mark.cli
@pytest.mark.integration
def test_root_true_stops_traversal(tmp_path: Path) -> None:
    """root=true in parent prevents overrides from ancestors."""
    root: Path = tmp_path / "root"
    sub: Path = root / "sub"
    _write(sub / "c.py", _mk_py_headerless())

    # Parent declares align_fields=false and root=true (stop traversal above this dir)
    _write(
        root / "pyproject.toml",
        textwrap.dedent(
            f"""
            [tool.topmark]
            {Toml.KEY_ROOT} = true
            [tool.topmark.{Toml.SECTION_FORMATTING}]
            {Toml.KEY_ALIGN_FIELDS} = false
            """
        ).strip()
        + "\n",
    )

    # Grandparent tries to flip to true (should be ignored due to root=true below)
    grand: Path = tmp_path
    _write(
        grand / "topmark.toml",
        textwrap.dedent(
            f"""
            [{Toml.SECTION_FORMATTING}]
            {Toml.KEY_ALIGN_FIELDS} = true
            """
        ).strip()
        + "\n",
    )

    apply: bool = False
    diff: bool = True

    # API run anchored at sub (should stop at root because of root=true)
    rr: api.RunResult = api.check(
        [str(sub)],
        apply=apply,
        diff=diff,
        prune_views=False,
        include_file_types=("python",),
    )
    assert rr.files
    api_diff: str = rr.files[0].diff or ""
    assert _contains_unaligned_fields(api_diff), "API did not stop at root=true boundary"

    # CLI-like parity
    _draft: MutableConfig
    files: list[Path]
    results: list[ProcessingContext]
    _draft, files, results = run_cli_like(
        sub,
        kind="check",
        apply=apply,
        diff=diff,
        prune_views=False,
        include_file_types=("python",),
    )
    assert files
    cli_diff: str = results[0].views.diff.text or "" if results[0].views.diff else ""
    assert _contains_unaligned_fields(cli_diff), "CLI-like did not stop at root=true boundary"


@pytest.mark.api
@pytest.mark.cli
@pytest.mark.integration
def test_cli_like_positional_paths_preserve_discovered_exclude_from_gitignore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI-like overrides must not wipe discovered ``exclude_from`` patterns.

    Regression coverage for a bug where positional CLI paths were applied via
    `ConfigOverrides(files=...)`, but other list-valued CLI fields were also
    forwarded as empty lists. That caused discovered values such as
    ``exclude_from = [".gitignore"]`` to be replaced with empty collections,
    so ignored subtrees like ``__pycache__/`` leaked into file discovery.
    """
    repo: Path = tmp_path / "repo"
    pkg: Path = repo / "src" / "pkg"
    cache_dir: Path = pkg / "__pycache__"
    pkg.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    (repo / ".gitignore").write_text("__pycache__/\n*.py[cod]\n", encoding="utf-8")
    (pkg / "good.py").write_text("print('ok')\n", encoding="utf-8")
    (cache_dir / "bad.cpython-312.pyc").write_bytes(b"\x00\x00pyc")

    (repo / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [tool.topmark]
            root = true

            [tool.topmark.files]
            exclude_from = [".gitignore"]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)

    _draft, files, _results = run_cli_like(
        pkg,
        kind="check",
        diff=True,
        include_file_types=("python",),
    )

    file_names: set[str] = {path.name for path in files}
    file_texts: set[str] = {path.as_posix() for path in files}

    assert file_names == {"good.py"}
    assert all("__pycache__" not in text for text in file_texts)
    assert all(not text.endswith(".pyc") for text in file_texts)

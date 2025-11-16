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
from typing import TYPE_CHECKING, Sequence

from topmark import api
from topmark.config import MutableConfig
from topmark.file_resolver import resolve_file_list
from topmark.pipeline.engine import run_steps_for_files
from topmark.pipeline.pipelines import Pipeline

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from topmark.cli_shared.exit_codes import ExitCode
    from topmark.pipeline.context import ProcessingContext
    from topmark.pipeline.contracts import Step


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


def _run_cli_like(
    anchor: Path, file_types: tuple[str, ...] = ()
) -> tuple[MutableConfig, list[Path], list[ProcessingContext]]:
    """Build config via authoritative loader to model CLI behavior."""
    draft: MutableConfig = MutableConfig.load_merged(input_paths=(anchor,))
    draft.files = [str(anchor)]  # seed positional inputs
    if file_types:
        draft.file_types = set(file_types)
    cfg: api.Config = draft.freeze()
    files: list[Path] = resolve_file_list(cfg)
    results: list[ProcessingContext]
    _exit_code: ExitCode | None
    pipeline: Sequence[Step] = Pipeline.CHECK_APPLY_PATCH.steps
    results, _exit_code = run_steps_for_files(
        file_list=files,
        pipeline=pipeline,
        config=cfg,
        prune=False,
    )
    return draft, files, results


def test_same_dir_precedence_topmark_over_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nearest directory: topmark.toml should override pyproject.toml in the same dir."""
    proj: Path = tmp_path / "proj"
    src: Path = proj / "src"
    _write(src / "a.py", _mk_py_headerless())

    # Same directory: pyproject sets align_fields = false, topmark.toml sets true
    _write(
        proj / "pyproject.toml",
        textwrap.dedent(
            """
            [tool.topmark]
            [tool.topmark.formatting]
            align_fields = false
            """
        ).strip()
        + "\n",
    )
    _write(
        proj / "topmark.toml",
        textwrap.dedent(
            """
            [formatting]
            align_fields = true
            """
        ).strip()
        + "\n",
    )

    # API run (anchor = project dir)
    rr: api.RunResult = api.check(
        [str(proj)], apply=False, diff=True, prune=False, file_types=("python",)
    )
    assert rr.files, "API produced no files to check"
    api_diff: str = rr.files[0].diff or ""

    # CLI-like run from same anchor
    _draft: MutableConfig
    files: list[Path]
    results: list[ProcessingContext]
    _draft, files, results = _run_cli_like(proj, file_types=("python",))
    assert files, "CLI-like resolver produced no files"

    # The aligned form must be present (topmark.toml overrides pyproject.toml)
    assert _contains_aligned_fields(api_diff), "API did not reflect topmark.toml override"
    # Parity: ensure CLI-like result also aligns
    cli_diff: str = results[0].views.diff.text or "" if results[0].views.diff else ""
    assert _contains_aligned_fields(cli_diff), "CLI-like did not reflect topmark.toml override"


def test_discovery_anchor_subdir_nearest_wins(tmp_path: Path) -> None:
    """Anchor in subdir: parent pyproject.toml, child topmark.toml — child wins."""
    proj: Path = tmp_path / "proj"
    child: Path = proj / "pkg"
    _write(child / "b.py", _mk_py_headerless())

    _write(
        proj / "pyproject.toml",
        textwrap.dedent(
            """
            [tool.topmark]
            [tool.topmark.formatting]
            align_fields = false
            """
        ).strip()
        + "\n",
    )
    _write(
        child / "topmark.toml",
        textwrap.dedent(
            """
            [formatting]
            align_fields = true
            """
        ).strip()
        + "\n",
    )

    # API run with anchor at child dir
    rr: api.RunResult = api.check(
        [str(child)], apply=False, diff=True, prune=False, file_types=("python",)
    )
    assert rr.files
    api_diff: str = rr.files[0].diff or ""
    assert _contains_aligned_fields(api_diff), "API did not honor nearest (child) config"

    # CLI-like parity
    _draft: MutableConfig
    files: list[Path]
    results: list[ProcessingContext]
    _draft, files, results = _run_cli_like(child, file_types=("python",))
    assert files
    cli_diff: str = results[0].views.diff.text or "" if results[0].views.diff else ""
    assert _contains_aligned_fields(cli_diff), "CLI-like did not honor nearest (child) config"


def test_root_true_stops_traversal(tmp_path: Path) -> None:
    """root=true in parent prevents overrides from ancestors."""
    root: api.Path = tmp_path / "root"
    sub: api.Path = root / "sub"
    _write(sub / "c.py", _mk_py_headerless())

    # Parent declares align_fields=false and root=true (stop traversal above this dir)
    _write(
        root / "pyproject.toml",
        textwrap.dedent(
            """
            [tool.topmark]
            root = true
            [tool.topmark.formatting]
            align_fields = false
            """
        ).strip()
        + "\n",
    )

    # Grandparent tries to flip to true (should be ignored due to root=true below)
    grand: api.Path = tmp_path
    _write(
        grand / "topmark.toml",
        textwrap.dedent(
            """
            [formatting]
            align_fields = true
            """
        ).strip()
        + "\n",
    )

    # API run anchored at sub (should stop at root because of root=true)
    rr: api.RunResult = api.check([str(sub)], apply=False, diff=True, file_types=("python",))
    assert rr.files
    api_diff: str = rr.files[0].diff or ""
    assert _contains_unaligned_fields(api_diff), "API did not stop at root=true boundary"

    # CLI-like parity
    _draft: MutableConfig
    files: list[Path]
    results: list[ProcessingContext]
    _draft, files, results = _run_cli_like(sub, file_types=("python",))
    assert files
    cli_diff: str = results[0].views.diff.text or "" if results[0].views.diff else ""
    assert _contains_unaligned_fields(cli_diff), "CLI-like did not stop at root=true boundary"

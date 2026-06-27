# topmark:header:start
#
#   project      : TopMark
#   file         : test_nested_config_e2e.py
#   file_relpath : tests/pipeline/integration/test_nested_config_e2e.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""End-to-end nested-config pipeline tests."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from topmark.api.runtime import ApiPipelineResultRun
from topmark.api.runtime import run_pipeline_results
from topmark.pipeline.pipelines import select_pipeline
from topmark.runtime.model import RunOptions

pytestmark: pytest.MarkDecorator = pytest.mark.integration

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.pipelines import PipelineSelection
    from topmark.pipeline.result import ProcessingResult


def _write(path: Path, content: str) -> None:
    """Write a text file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def test_nested_config_applies_only_within_its_subtree(tmp_path: Path) -> None:
    """A nested config should affect durable output for its own subtree only.

    This end-to-end test intentionally observes nested configuration through
    reduced [`ProcessingResult`][topmark.pipeline.result.ProcessingResult]
    snapshots instead of retained mutable processing contexts. The API runtime
    path reduces each file to durable result state and releases context-owned
    volatile views, so output-facing behavior must be asserted via copied
    details such as `diff_text` rather than `ProcessingContext.config`.
    """
    root: Path = tmp_path / "repo"
    pkg: Path = root / "pkg"
    docs: Path = root / "docs"
    pkg.mkdir(parents=True)
    docs.mkdir(parents=True)

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
        pkg / "topmark.toml",
        """
        [header]
        fields = ["project", "file"]

        [fields]
        file = "pkg/mod.py"
        """,
    )

    pkg_file: Path = pkg / "mod.py"
    docs_file: Path = docs / "guide.py"
    pkg_file.write_text("print('pkg')\n", encoding="utf-8")
    docs_file.write_text("print('docs')\n", encoding="utf-8")

    pipeline: PipelineSelection = select_pipeline(
        "check",
        apply=False,
        diff=True,
    )
    run_options: RunOptions = RunOptions.from_pipeline_selection(
        selection=pipeline,
    )
    api_run: ApiPipelineResultRun = run_pipeline_results(
        pipeline=pipeline,
        paths=[pkg_file, docs_file],
        run_options=run_options,
        base_config=None,
        include_file_types=["python"],
    )

    assert api_run.exit_code is None
    assert run_options.apply_changes is False
    # Limit discovery to Python files so the config files themselves are not part
    # of the processed candidate set for this end-to-end behavior check.
    assert set(api_run.file_list) == {pkg_file.resolve(), docs_file.resolve()}
    assert len(api_run.results) == 2

    by_path: dict[Path, ProcessingResult] = {
        result.path.resolve(): result for result in api_run.results
    }

    pkg_result: ProcessingResult = by_path[pkg_file.resolve()]
    docs_result: ProcessingResult = by_path[docs_file.resolve()]

    # `ProcessingResult` deliberately does not expose the per-file FrozenConfig.
    # The nested-config contract is therefore verified through the durable diff
    # snapshot copied across the reduction boundary.
    pkg_diff: str | None = pkg_result.detail.diff_text
    docs_diff: str | None = docs_result.detail.diff_text

    assert pkg_diff is not None
    assert docs_diff is not None

    assert "+#   project : TopMark" in pkg_diff
    assert "+#   file    : pkg/mod.py" in pkg_diff
    assert "+#   license : MIT" not in pkg_diff

    assert "+#   project : TopMark" in docs_diff
    assert "+#   license : MIT" in docs_diff
    assert "+#   file" not in docs_diff

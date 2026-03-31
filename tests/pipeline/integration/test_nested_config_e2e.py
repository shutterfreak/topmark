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

from topmark.api.runtime import run_pipeline
from topmark.pipeline.pipelines import Pipeline

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.core.exit_codes import ExitCode
    from topmark.pipeline.context.model import ProcessingContext


def _write(path: Path, content: str) -> None:
    """Write a text file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


@pytest.mark.pipeline
def test_nested_config_applies_only_within_its_subtree(tmp_path: Path) -> None:
    """A nested config should affect only files within its own subtree."""
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

    cfg: Config
    file_list: list[Path]
    results: list[ProcessingContext]
    exit_code: ExitCode | None

    cfg, file_list, results, exit_code = run_pipeline(
        pipeline=Pipeline.CHECK.steps,
        paths=[pkg_file, docs_file],
        base_config=None,
        include_file_types=["python"],
        apply_changes=False,
        prune=False,
    )

    assert exit_code is None
    assert cfg.apply_changes is False
    # Limit discovery to Python files so the config files themselves are not part
    # of the processed candidate set for this end-to-end behavior check.
    assert set(file_list) == {pkg_file.resolve(), docs_file.resolve()}
    assert len(results) == 2

    by_path: dict[Path, ProcessingContext] = {ctx.path.resolve(): ctx for ctx in results}

    pkg_ctx: ProcessingContext = by_path[pkg_file.resolve()]
    docs_ctx: ProcessingContext = by_path[docs_file.resolve()]

    assert pkg_ctx.config.header_fields == ("project", "file")
    assert pkg_ctx.config.field_values["project"] == "TopMark"
    assert pkg_ctx.config.field_values["license"] == "MIT"
    assert pkg_ctx.config.field_values["file"] == "pkg/mod.py"

    assert docs_ctx.config.header_fields == ("project", "license")
    assert docs_ctx.config.field_values["project"] == "TopMark"
    assert docs_ctx.config.field_values["license"] == "MIT"
    assert "file" not in docs_ctx.config.field_values

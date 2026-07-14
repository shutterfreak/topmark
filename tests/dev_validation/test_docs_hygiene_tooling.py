# topmark:header:start
#
#   project      : TopMark
#   file         : test_docs_hygiene_tooling.py
#   file_relpath : tests/dev_validation/test_docs_hygiene_tooling.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation tests for documentation-hygiene tooling."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tools.docs.check_docs_hygiene import iter_markdown_files

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.dev_validation
def test_markdown_discovery_excludes_draft_documentation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Markdown discovery omits root-level and nested docs draft directories."""
    docs_dir: Path = tmp_path / "docs"
    root_drafts_dir: Path = docs_dir / "_drafts"
    nested_drafts_dir: Path = docs_dir / "guide" / "_drafts"
    root_drafts_dir.mkdir(parents=True)
    nested_drafts_dir.mkdir(parents=True)

    included_paths: tuple[Path, ...] = (
        tmp_path / "README.md",
        docs_dir / "index.md",
        docs_dir / "guide" / "published.md",
    )
    excluded_paths: tuple[Path, ...] = (
        root_drafts_dir / "idea.md",
        nested_drafts_dir / "future.md",
    )
    for path in (*included_paths, *excluded_paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Test\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert iter_markdown_files(None) == [
        path.relative_to(tmp_path) for path in sorted(included_paths)
    ]

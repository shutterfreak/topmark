# topmark:header:start
#
#   project      : TopMark
#   file         : test_project_docs_links.py
#   file_relpath : tests/dev_validation/test_project_docs_links.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for local validation of TopMark-hosted documentation links."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tools.docs.check_project_links import check_project_docs_links
from tools.docs.check_project_links import iter_project_doc_urls

if TYPE_CHECKING:
    from pathlib import Path

    from tools.docs.check_project_links import ProjectLinkDiagnostic


@pytest.mark.dev_validation
def test_project_docs_link_accepts_local_route_and_fragment(
    tmp_path: Path,
) -> None:
    """A hosted route and fragment pass when both exist in the local site."""
    source: Path = tmp_path / "README.md"
    source.write_text(
        "[Policy](https://topmark.readthedocs.io/en/latest/ci/codecov/#project-coverage-status)\n",
        encoding="utf-8",
    )
    rendered: Path = tmp_path / "site" / "ci" / "codecov" / "index.html"
    rendered.parent.mkdir(parents=True)
    rendered.write_text(
        '<h2 id="project-coverage-status">Project coverage status</h2>\n',
        encoding="utf-8",
    )

    assert check_project_docs_links([source], site_dir=tmp_path / "site") == []


@pytest.mark.dev_validation
def test_project_docs_link_reports_missing_local_route(
    tmp_path: Path,
) -> None:
    """A hosted route fails when the proposed site does not contain it."""
    source: Path = tmp_path / "README.md"
    source.write_text(
        "\n[Missing](https://topmark.readthedocs.io/en/latest/missing/page/)\n",
        encoding="utf-8",
    )

    diagnostics: list[ProjectLinkDiagnostic] = check_project_docs_links(
        [source],
        site_dir=tmp_path / "site",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 2
    assert "route is absent" in diagnostics[0].message


@pytest.mark.dev_validation
def test_project_docs_link_reports_missing_local_fragment(
    tmp_path: Path,
) -> None:
    """A hosted fragment fails when the rendered page lacks its anchor."""
    source: Path = tmp_path / "README.md"
    source.write_text(
        "[Policy](https://topmark.readthedocs.io/en/latest/ci/codecov/#missing)\n",
        encoding="utf-8",
    )
    rendered: Path = tmp_path / "site" / "ci" / "codecov" / "index.html"
    rendered.parent.mkdir(parents=True)
    rendered.write_text('<h1 id="present">Policy</h1>\n', encoding="utf-8")

    diagnostics: list[ProjectLinkDiagnostic] = check_project_docs_links(
        [source],
        site_dir=tmp_path / "site",
    )

    assert len(diagnostics) == 1
    assert "fragment is absent" in diagnostics[0].message


@pytest.mark.dev_validation
def test_project_docs_link_ignores_fenced_and_inline_code() -> None:
    """Example URLs inside Markdown code do not become validation inputs."""
    text = """\
`https://topmark.readthedocs.io/en/latest/inline/`

```text
https://topmark.readthedocs.io/en/latest/fenced/
```

[Real](https://topmark.readthedocs.io/en/latest/real/)
"""

    assert list(iter_project_doc_urls(text)) == [
        ("https://topmark.readthedocs.io/en/latest/real/", 7)
    ]


@pytest.mark.dev_validation
def test_project_docs_link_accepts_latest_root_with_query(tmp_path: Path) -> None:
    """The hosted documentation root maps to the local site index."""
    source: Path = tmp_path / "README.md"
    source.write_text(
        "<https://topmark.readthedocs.io/en/latest/?badge=latest>\n",
        encoding="utf-8",
    )
    rendered: Path = tmp_path / "site" / "index.html"
    rendered.parent.mkdir()
    rendered.write_text("<h1>TopMark</h1>\n", encoding="utf-8")

    assert check_project_docs_links([source], site_dir=tmp_path / "site") == []

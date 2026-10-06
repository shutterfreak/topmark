# topmark:header:start
#
#   project      : TopMark
#   file         : test_zensical_output_parity.py
#   file_relpath : tests/dev_validation/test_zensical_output_parity.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the production Zensical output-parity contract."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tools.docs.check_zensical_parity import REQUIRED_ROUTES
from tools.docs.check_zensical_parity import check_site

if TYPE_CHECKING:
    from pathlib import Path


def _write_contract_site(site_dir: Path) -> None:
    """Create the smallest site that satisfies TopMark's checked output contract."""
    for route, content in REQUIRED_ROUTES.items():
        page: Path = site_dir / route
        page.parent.mkdir(parents=True, exist_ok=True)
        extra: str = " usage/cli/ configuration/discovery/ api/" if route == "index.html" else ""
        page.write_text(content + extra, encoding="utf-8")
    (site_dir / "search.json").write_text(
        json.dumps({"items": [{"title": "TopMark"}]}), encoding="utf-8"
    )


def test_check_site_accepts_routes_navigation_search_and_content_contract(tmp_path: Path) -> None:
    """Production parity accepts the expected Zensical output surfaces."""
    _write_contract_site(tmp_path)

    assert check_site(tmp_path) == []


def test_check_site_reports_missing_route_and_search_index(tmp_path: Path) -> None:
    """Production parity reports actionable missing-output failures."""
    (tmp_path / "index.html").write_text("TopMark documentation", encoding="utf-8")

    failures: list[str] = check_site(tmp_path)

    assert "missing required route: usage/cli/index.html" in failures
    assert "missing search index: search.json" in failures

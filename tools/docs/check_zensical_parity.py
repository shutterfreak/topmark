# topmark:header:start
#
#   project      : TopMark
#   file         : check_zensical_parity.py
#   file_relpath : tools/docs/check_zensical_parity.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Validate production Zensical output against TopMark's route and content contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final
from typing import cast

REQUIRED_ROUTES: Final[dict[str, str]] = {
    "index.html": "TopMark documentation",
    "usage/cli/index.html": "Command overview",
    "usage/generated/filetypes/index.html": "Supported file types",
    "configuration/discovery/index.html": "Configuration discovery",
    "api/index.html": "API reference",
    "api/internals/topmark/api/index.html": "topmark.api",
}
REQUIRED_NAVIGATION_TARGETS: Final[tuple[str, ...]] = (
    "usage/cli/",
    "configuration/discovery/",
    "api/",
)


def check_site(site_dir: Path) -> list[str]:
    """Return route, navigation, search, and representative-content parity failures.

    Args:
        site_dir: Root of a completed Zensical site build.

    Returns:
        Human-readable contract failures; an empty list means the checked production surfaces match.
    """
    failures: list[str] = []
    for route, expected_content in REQUIRED_ROUTES.items():
        page: Path = site_dir / route
        if not page.is_file():
            failures.append(f"missing required route: {route}")
            continue
        if expected_content not in page.read_text(encoding="utf-8"):
            failures.append(f"route does not contain representative content: {route}")

    index_page: Path = site_dir / "index.html"
    if index_page.is_file():
        index_html: str = index_page.read_text(encoding="utf-8")
        for target in REQUIRED_NAVIGATION_TARGETS:
            if target not in index_html:
                failures.append(f"navigation is missing required target: {target}")

    search_index: Path = site_dir / "search.json"
    if not search_index.is_file():
        failures.append("missing search index: search.json")
    else:
        try:
            search_payload: object = json.loads(search_index.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            failures.append(f"invalid search index: {error.msg}")
        else:
            if isinstance(search_payload, dict):
                search_payload = cast("dict[str, object]", search_payload)
                search_items: object = search_payload.get("items")
            else:
                search_items = search_payload
            if not isinstance(search_items, list) or not search_items:
                failures.append("search index contains no searchable pages")
    return failures


def main() -> None:
    """Parse command-line arguments and fail on output-parity drift."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=Path(".zensical/site"))
    arguments = parser.parse_args()
    failures: list[str] = check_site(arguments.site_dir)
    if failures:
        raise SystemExit("Zensical output parity failed:\n- " + "\n- ".join(failures))
    print(f"Zensical output parity passed: {arguments.site_dir}")


if __name__ == "__main__":
    main()

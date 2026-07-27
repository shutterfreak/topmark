#!/usr/bin/env python3

# topmark:header:start
#
#   project      : TopMark
#   file         : check_project_links.py
#   file_relpath : tools/docs/check_project_links.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Validate TopMark-hosted documentation links against a local MkDocs build.

Links to TopMark's own ``/en/latest/`` Read the Docs routes describe the documentation produced by
the current source tree. Checking those URLs over the network during a pull request is brittle
because the deployed ``latest`` site still represents the base branch. This tool maps those URLs to
the locally built site and validates both routes and fragments without network access.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence
    from typing import Any
    from typing import Final
    from urllib.parse import SplitResult


PROJECT_DOCS_ORIGIN: Final[str] = "https://topmark.readthedocs.io"
PROJECT_DOCS_PREFIX: Final[str] = "/en/latest/"
DEFAULT_MARKDOWN_PATHS: Final[tuple[Path, ...]] = (
    Path("docs"),
    Path("README.md"),
    Path("INSTALL.md"),
    Path("CONTRIBUTING.md"),
)
EXCLUDED_DIR_NAMES: Final[frozenset[str]] = frozenset({"_drafts"})
PROJECT_DOCS_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"https://topmark\.readthedocs\.io/en/latest(?:/[^\s<>\"')\]`]*)?",
)
FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")
INLINE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"(?P<fence>`+)[^\n]*?(?P=fence)")
TRAILING_URL_PUNCTUATION: Final[str] = ".,;:"


@dataclass(frozen=True, kw_only=True, slots=True)
class ProjectLinkDiagnostic:
    """One invalid project-owned documentation link."""

    path: Path
    line: int
    url: str
    message: str

    def render(self) -> str:
        """Render the diagnostic in compiler-style form."""
        return f"{self.path}:{self.line}: {self.message}: {self.url}"


class _AnchorParser(HTMLParser):
    """Collect HTML ``id`` and legacy anchor ``name`` attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: set[str] = set()

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Collect anchor-bearing attributes from a start tag."""
        del tag
        for name, value in attrs:
            if value is not None and name in {"id", "name"}:
                self.anchors.add(value)


def _is_excluded(
    path: Path,
) -> bool:
    """Return whether a Markdown path belongs to an unpublished tree."""
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def iter_markdown_files(
    paths: Sequence[Path] | None = None,
) -> list[Path]:
    """Discover Markdown files from explicit paths or the repository defaults."""
    discovered: set[Path] = set()
    for path in paths or DEFAULT_MARKDOWN_PATHS:
        if path.is_file() and path.suffix.lower() == ".md" and not _is_excluded(path):
            discovered.add(path)
            continue
        if path.is_dir():
            discovered.update(
                candidate
                for candidate in path.rglob("*.md")
                if candidate.is_file() and not _is_excluded(candidate)
            )
    return sorted(discovered)


def _mask_span(
    text: str,
) -> str:
    """Mask non-newline characters while preserving offsets and line numbers."""
    return "".join("\n" if char == "\n" else " " for char in text)


def mask_markdown_code(
    text: str,
) -> str:
    """Mask fenced and inline code so example URLs are not validated as links."""
    masked_lines: list[str] = []
    open_fence_char: str | None = None
    open_fence_length: int = 0

    for line in text.splitlines(keepends=True):
        fence_match: re.Match[str] | None = FENCE_RE.match(line)
        if open_fence_char is not None:
            masked_lines.append(_mask_span(line))
            if fence_match is not None:
                fence: str | Any = fence_match.group("fence")
                if fence[0] == open_fence_char and len(fence) >= open_fence_length:
                    open_fence_char = None
                    open_fence_length = 0
            continue

        if fence_match is not None:
            fence = fence_match.group("fence")
            open_fence_char = fence[0]
            open_fence_length = len(fence)
            masked_lines.append(_mask_span(line))
            continue

        masked_lines.append(INLINE_CODE_RE.sub(lambda match: _mask_span(match.group(0)), line))

    return "".join(masked_lines)


def iter_project_doc_urls(
    text: str,
) -> Iterable[tuple[str, int]]:
    """Yield project-hosted documentation URLs with one-based source lines."""
    masked: str = mask_markdown_code(text)
    for match in PROJECT_DOCS_URL_RE.finditer(masked):
        url: str = match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
        line: int = text.count("\n", 0, match.start()) + 1
        yield url, line


def _route_candidates(
    url: str,
    site_dir: Path,
) -> list[Path]:
    """Map one hosted documentation URL to possible local build outputs."""
    parsed: SplitResult = urlsplit(url)
    if f"{parsed.scheme}://{parsed.netloc}" != PROJECT_DOCS_ORIGIN:
        return []
    if not parsed.path.startswith(PROJECT_DOCS_PREFIX):
        return []

    route: str = unquote(parsed.path.removeprefix(PROJECT_DOCS_PREFIX))
    route_path = Path(route)
    if route_path.is_absolute() or ".." in route_path.parts:
        return []
    if not route:
        return [site_dir / "index.html"]
    if parsed.path.endswith("/"):
        return [site_dir / route_path / "index.html"]
    if route_path.suffix == ".html":
        return [site_dir / route_path]
    return [
        site_dir / route_path,
        site_dir / f"{route}.html",
        site_dir / route_path / "index.html",
    ]


def _load_anchors(
    html_path: Path,
    cache: dict[Path, frozenset[str]],
) -> frozenset[str]:
    """Load and cache anchor identifiers from one rendered HTML page."""
    if html_path not in cache:
        parser = _AnchorParser()
        parser.feed(html_path.read_text(encoding="utf-8"))
        cache[html_path] = frozenset(parser.anchors)
    return cache[html_path]


def check_project_docs_links(
    markdown_paths: Sequence[Path] | None,
    *,
    site_dir: Path,
) -> list[ProjectLinkDiagnostic]:
    """Validate project-hosted routes and fragments against a rendered site."""
    diagnostics: list[ProjectLinkDiagnostic] = []
    anchor_cache: dict[Path, frozenset[str]] = {}

    for markdown_path in iter_markdown_files(markdown_paths):
        text: str = markdown_path.read_text(encoding="utf-8")
        for url, line in iter_project_doc_urls(text):
            candidates: list[Path] = _route_candidates(url, site_dir)
            rendered_path: Path | None = next(
                (candidate for candidate in candidates if candidate.is_file()), None
            )
            if rendered_path is None:
                route: str = urlsplit(url).path.removeprefix(PROJECT_DOCS_PREFIX)
                expected: Path = (
                    site_dir / route / "index.html" if route else site_dir / "index.html"
                )
                diagnostics.append(
                    ProjectLinkDiagnostic(
                        path=markdown_path,
                        line=line,
                        url=url,
                        message=f"hosted route is absent from local build ({expected})",
                    )
                )
                continue

            fragment: str = unquote(urlsplit(url).fragment)
            if fragment and fragment not in _load_anchors(rendered_path, anchor_cache):
                diagnostics.append(
                    ProjectLinkDiagnostic(
                        path=markdown_path,
                        line=line,
                        url=url,
                        message=(
                            "hosted documentation fragment is absent from local build "
                            f"({rendered_path}#{fragment})"
                        ),
                    )
                )

    return diagnostics


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Markdown files or directories (defaults to docs/ and selected root Markdown files)",
    )
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=Path("site"),
        help="Rendered MkDocs directory (default: site)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print validation statistics",
    )
    return parser.parse_args(argv)


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run project-owned documentation link validation."""
    args: argparse.Namespace = parse_args(argv)
    markdown_paths: Any = args.paths or None
    markdown_files: list[Path] = iter_markdown_files(markdown_paths)
    diagnostics: list[ProjectLinkDiagnostic] = check_project_docs_links(
        markdown_paths,
        site_dir=args.site_dir,
    )

    for diagnostic in diagnostics:
        print(diagnostic.render())

    if args.stats:
        print(f"Markdown files checked: {len(markdown_files)}")
        print(f"Errors found: {len(diagnostics)}")

    return 1 if diagnostics else 0


if __name__ == "__main__":
    sys.exit(main())

# topmark:header:start
#
#   project      : TopMark
#   file         : audit_python_lifecycle.py
#   file_relpath : tools/ci/audit_python_lifecycle.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Emit maintainer-review decisions for CPython RC, final, and EOL transitions."""

from __future__ import annotations

import html.parser
import json
import re
import urllib.request
from dataclasses import asdict
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Final

import tomlkit

from topmark.core.typing_guards import is_mapping

STATUS_URL: Final = "https://devguide.python.org/versions/"
RELEASES_URL: Final = "https://www.python.org/ftp/python/"
FINAL: Final = frozenset(
    {
        "bugfix",
        "security",
        "end-of-life",
    }
)


@dataclass(frozen=True, slots=True)
class Status:
    """A released CPython feature series."""

    series: str
    state: str
    released: str
    eol: str


@dataclass(frozen=True, slots=True)
class Decision:
    """An issue to create or update."""

    marker: str
    title: str
    body: str


class TableParser(html.parser.HTMLParser):
    """Extract plain table cells from the CPython status page."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Start collecting a table row or cell from CPython's status table.

        Args:
            tag: HTML element name received from :class:`HTMLParser`.
            attrs: Element attributes, which do not affect lifecycle extraction.
        """
        del attrs
        if tag == "tr":
            self.row = []
        if tag == "td" and self.row is not None:
            self.cell = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        """Append text that belongs to the current status-table cell.

        Args:
            data: Raw character data supplied by :class:`HTMLParser`.
        """
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        """Finalize a status-table cell or preserve its completed row.

        Args:
            tag: HTML element name received from :class:`HTMLParser`.
        """
        if tag == "td" and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def parse_status(
    text: str,
    today: date,
) -> tuple[Status, ...]:
    """Return released final CPython series, excluding development rows."""
    parser = TableParser()
    parser.feed(text)
    result: list[Status] = []
    for row in parser.rows:
        if (
            len(row) >= 5
            and re.fullmatch(r"3\.\d+", row[0])
            and row[2] in FINAL
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[3])
            and date.fromisoformat(row[3]) <= today
        ):
            result.append(Status(row[0], row[2], row[3], row[4]))
    return tuple(result)


def parse_rcs(
    text: str,
) -> dict[str, str]:
    """Return the latest official X.Y.0 release candidate per series."""
    latest: dict[str, tuple[int, str]] = {}
    for version in re.findall(r'href="(3\.\d+\.0rc\d+)/"', text):
        series, number = version.split(".0rc")
        if (int(number), version) > latest.get(series, (-1, "")):
            latest[series] = (int(number), version)
    return {series: version for series, (_, version) in latest.items()}


def supported(
    series: str,
    requirement: str,
) -> bool:
    """Return whether the repository's simple Python range includes a series."""
    match: re.Match[str] | None = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)", requirement)
    if match is None:
        raise ValueError(f"Unsupported requires-python format: {requirement}")
    major, minor, upper_major, upper_minor = map(int, match.groups())
    current: tuple[int, ...] = tuple(map(int, series.split(".")))
    return (major, minor) <= current < (upper_major, upper_minor)


def body(marker: str, phase: str, observed: str, source: str, requirement: str) -> str:
    """Return a consistent issue body for a lifecycle decision."""
    intro: str = (
        "This release candidate starts preparation only; it is not a TopMark support commitment."
        if phase == "prerelease"
        else "A maintainer must review this lifecycle transition before changing "
        "TopMark's support contract."
    )
    return "\n".join(
        (
            f"<!-- {marker} -->",
            "## Python lifecycle maintainer decision required",
            "",
            intro,
            "",
            f"- Lifecycle phase: **{phase}**",
            f"- Observed version/status: {observed}",
            f"- Source: {source}",
            f"- Current `requires-python`: `{requirement}`",
            "",
            "## Review checklist",
            "",
            "- [ ] Confirm final-release compatibility testing "
            "(or the EOL compatibility decision).",
            "- [ ] Update `pyproject.toml`, runtime bounds, Nox/CI, "
            "and published-artifact matrices.",
            "- [ ] Refresh and review `uv.lock` when package metadata changes.",
            "- [ ] Update support-policy, contributor, installation, and CI documentation.",
            "- [ ] Add the user-visible decision to `CHANGELOG.md`.",
        )
    )


def decisions(
    requirement: str, policy: str, statuses: tuple[Status, ...], rcs: dict[str, str]
) -> tuple[Decision, ...]:
    """Return RC, final-release, and EOL decisions needing maintainer review."""
    final_series: set[str] = {item.series for item in statuses if item.state != "end-of-life"}
    result: list[Decision] = []
    for series, rc in sorted(rcs.items()):
        if series not in final_series and not supported(series, requirement):
            marker: str = f"topmark-python-lifecycle:release-{series}"
            result.append(
                Decision(
                    marker,
                    f"build(ci): prepare Python {series} support",
                    body(marker, "prerelease", rc, RELEASES_URL, requirement),
                )
            )
    for item in statuses:
        if item.state != "end-of-life" and not supported(item.series, requirement):
            marker = f"topmark-python-lifecycle:release-{item.series}"
            result.append(
                Decision(
                    marker,
                    f"build(ci): evaluate Python {item.series} final release support",
                    body(marker, "final", item.released, STATUS_URL, requirement),
                )
            )
        elif (
            item.state == "end-of-life"
            and supported(item.series, requirement)
            and not re.search(
                rf"^\|\s*{re.escape(item.series)}\s*\|\s*EOL\s*\|\s*Compatibility-supported",
                policy,
                re.MULTILINE,
            )
        ):
            marker = f"topmark-python-lifecycle:eol-{item.series}"
            result.append(
                Decision(
                    marker,
                    f"build(ci): evaluate Python {item.series} EOL transition",
                    body(marker, "eol", item.eol, STATUS_URL, requirement),
                )
            )
    return tuple(result)


def fetch(url: str) -> str:
    """Fetch a fixed official source URL."""
    request = urllib.request.Request(  # noqa: S310 - fixed official URLs
        url, headers={"User-Agent": "TopMark-python-lifecycle-audit/1"}
    )
    # The only callers pass module-owned HTTPS constants for CPython and Python.org.
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read().decode("utf-8")


def main() -> None:
    """Print the current lifecycle decisions as JSON."""
    root: Path = Path.cwd()
    project: tomlkit.TOMLDocument = tomlkit.loads(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project_metadata = project["project"]
    if not is_mapping(project_metadata):
        raise TypeError("pyproject.toml must define a [project] table")
    requirement: object = project_metadata["requires-python"]
    if not isinstance(requirement, str):
        raise TypeError("pyproject.toml must define project.requires-python as a string")
    policy: str = (root / "docs/usage/python-support.md").read_text(encoding="utf-8")
    output: tuple[Decision, ...] = decisions(
        requirement,
        policy,
        parse_status(fetch(STATUS_URL), datetime.now(timezone.utc).date()),
        parse_rcs(fetch(RELEASES_URL)),
    )
    print(json.dumps([asdict(item) for item in output]))


if __name__ == "__main__":
    main()

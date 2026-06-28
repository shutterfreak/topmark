# topmark:header:start
#
#   project      : TopMark
#   file         : test_version_rendering.py
#   file_relpath : tests/presentation/test_version_rendering.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Version presentation rendering contract tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.cli.errors import TopmarkCliVersionConversionError
from topmark.core.constants import TOPMARK_VERSION
from topmark.presentation.markdown.version import render_version_footer_markdown
from topmark.presentation.markdown.version import render_version_markdown
from topmark.presentation.shared.version import VersionHumanReport
from topmark.presentation.shared.version import make_version_human_report
from topmark.presentation.text.version import render_version_text
from topmark.utils import version as version_utils

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def _version_report(
    *,
    version_text: str = "1.2.3",
    version_format: str = "semver",
    error: TopmarkCliVersionConversionError | None = None,
    verbosity_level: int = 0,
    styled: bool = False,
) -> VersionHumanReport:
    """Create a small version report for renderer tests."""
    return VersionHumanReport(
        version_text=version_text,
        version_format=version_format,
        error=error,
        verbosity_level=verbosity_level,
        styled=styled,
    )


def test_render_version_text_verbose_includes_heading_and_indented_version() -> None:
    """Verbose TEXT output should label the version format."""
    output: str = render_version_text(
        _version_report(
            version_text="2.0.0-rc.1",
            version_format="semver",
            verbosity_level=1,
        )
    )

    assert output.splitlines() == [
        "TopMark version (semver):",
        "    2.0.0-rc.1",
    ]


def test_render_version_text_includes_conversion_warning() -> None:
    """TEXT output should preserve fallback conversion warnings."""
    output: str = render_version_text(
        _version_report(
            version_text="1.2.3.post1",
            version_format="pep440",
            error=TopmarkCliVersionConversionError(
                "Post-releases are not valid SemVer: '1.2.3.post1'"
            ),
        )
    )

    assert output.splitlines() == [
        "1.2.3.post1",
        "Warning: Post-releases are not valid SemVer: '1.2.3.post1'",
    ]


def test_render_version_markdown_includes_conversion_warning() -> None:
    """Markdown version output should expose fallback conversion warnings."""
    output: str = render_version_markdown(
        _version_report(
            version_text="1.2.3.post1",
            version_format="pep440",
            error=TopmarkCliVersionConversionError(
                "Post-releases are not valid SemVer: '1.2.3.post1'"
            ),
            verbosity_level=2,
        )
    )

    assert "# TopMark Version" in output
    assert "**Version format:** `pep440`" in output
    assert "**Version:** `1.2.3.post1`" in output
    assert "> **Warning:** Post-releases are not valid SemVer: '1.2.3.post1'" in output
    assert output.endswith("\n")


def test_render_version_footer_markdown_uses_runtime_version() -> None:
    """Markdown footers should include the runtime TopMark version."""
    assert render_version_footer_markdown() == f"---\n_Generated with TopMark v{TOPMARK_VERSION}_"


def test_render_version_markdown_without_warning_omits_warning_block() -> None:
    """Markdown version output should omit warning blocks when conversion succeeds."""
    output: str = render_version_markdown(
        _version_report(
            version_text="1.2.3",
            version_format="pep440",
            error=None,
        )
    )

    assert "**Version:** `1.2.3`" in output
    assert "> **Warning:**" not in output


def test_make_version_human_report_wraps_semver_conversion_errors(
    monkeypatch: MonkeyPatch,
) -> None:
    """Shared reports should convert SemVer failures to CLI presentation errors."""
    monkeypatch.setattr(version_utils, "TOPMARK_VERSION", "1.2.3.post4")

    report: VersionHumanReport = make_version_human_report(
        semver=True,
        verbosity_level=2,
        styled=True,
    )

    assert report.version_text == "1.2.3.post4"
    assert report.version_format == "pep440"
    assert report.verbosity_level == 2
    assert report.styled is True
    assert isinstance(report.error, TopmarkCliVersionConversionError)
    assert str(report.error) == "Post-releases are not valid SemVer: '1.2.3.post4'"

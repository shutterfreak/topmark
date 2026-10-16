# topmark:header:start
#
#   project      : TopMark
#   file         : test_docs_hygiene.py
#   file_relpath : tests/tools/docs/test_docs_hygiene.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for documentation-hygiene tooling."""

# Allow focused contracts for private diagnostics helpers without inline comment overhead.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tools.docs import check_docs_hygiene as hygiene
from tools.docs.check_docs_hygiene import iter_markdown_files

if TYPE_CHECKING:
    import pytest


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


def test_docs_hygiene_reports_markdown_errors_and_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Markdown checks diagnose navigation, headings, links, and punctuation."""
    docs_dir: Path = tmp_path / "docs"
    docs_dir.mkdir()
    page: Path = docs_dir / "page.md"
    page.write_text(
        "# Heading \N{ROCKET}\n\n## First section\n\n"
        "Text\N{RIGHT SINGLE QUOTATION MARK}s smart.\n\n"
        '## Second section\n{% include-markdown "missing.md" %}\n',
        encoding="utf-8",
    )
    config: Path = tmp_path / "zensical.toml"
    config.write_text("[project]\nnav = []\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(hygiene, "DOCS_DIR", Path("docs"))
    monkeypatch.setattr(hygiene, "SNIPPET_DIR", Path("docs/_snippets"))
    monkeypatch.setattr(hygiene, "ZENSICAL_CONFIG", config)

    assert hygiene.check_docs_hygiene(["docs"], stats=True) == 1

    output: str = capsys.readouterr().out
    assert "missing from zensical.toml nav" in output
    assert "emoji are not allowed" in output
    assert "horizontal rule" in output
    assert "does not exist" in output
    assert "replace smart punctuation" in output
    assert "Errors found:" in output


def test_docs_hygiene_accepts_included_snippet_and_can_fail_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Included snippets are nav-exempt while warning policy remains configurable."""
    docs_dir: Path = tmp_path / "docs"
    snippets_dir: Path = docs_dir / "_snippets"
    snippets_dir.mkdir(parents=True)
    page: Path = docs_dir / "page.md"
    page.write_text('{% include-markdown "\\_snippets/note.md" %}\n', encoding="utf-8")
    snippet: Path = snippets_dir / "note.md"
    snippet.write_text("# Snippet heading\n", encoding="utf-8")
    config: Path = tmp_path / "zensical.toml"
    config.write_text('nav = ["page.md"]\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(hygiene, "DOCS_DIR", Path("docs"))
    monkeypatch.setattr(hygiene, "SNIPPET_DIR", Path("docs/_snippets"))
    monkeypatch.setattr(hygiene, "ZENSICAL_CONFIG", config)

    assert hygiene.check_docs_hygiene(["docs"], fail_on_warnings=False) == 0
    assert hygiene.check_docs_hygiene(["docs"], fail_on_warnings=True) == 1
    assert "headings inside reusable snippets" in capsys.readouterr().out


def test_docstring_checks_find_raw_urls_and_respect_code_masks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Docstring scanning flags prose URLs but ignores fenced code examples."""
    source: Path = tmp_path / "sample.py"
    source.write_text(
        '"""See https://bad.example.\n\n```text\nhttps://ignored.example\n```\n"""\n',
        encoding="utf-8",
    )

    assert hygiene.main([str(source)]) == 1

    output: str = capsys.readouterr().out
    assert output.count("raw URL") == 1


def test_changelog_hygiene_accepts_release_and_section_headings() -> None:
    """Well-formed release headings and allowed section names produce no diagnostics."""
    diagnostics: list[hygiene.Diagnostic] = hygiene._check_changelog_hygiene(
        Path("CHANGELOG.md"),
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "### Added - 1.2.3\n\n"
        "## [1.2.3] - 2026-10-16\n\n"
        "### Fixed - 1.2.3\n",
    )

    assert diagnostics == []


def test_changelog_hygiene_reports_structural_and_decorative_heading_errors() -> None:
    """Invalid release, section, emoji, and deep headings retain useful diagnostics."""
    diagnostics: list[hygiene.Diagnostic] = hygiene._check_changelog_hygiene(
        Path("CHANGELOG.md"),
        "# Changelog\n"
        "## [1.2.3]\n"
        "### Unexpected - 1.2.3\n"
        "### Added - 1.2.3\N{ROCKET}\n"
        "#### Details\n",
    )

    assert [(diagnostic.line, diagnostic.message) for diagnostic in diagnostics] == [
        (
            2,
            "CHANGELOG.md dated release headings must use a proper version identifier and date, "
            "shaped like '## [1.0.0] - YYYY-MM-DD', found '## [1.2.3]'",
        ),
        (
            3,
            "CHANGELOG.md level-3 heading uses an unsupported section name: 'Unexpected'",
        ),
        (
            4,
            "emoji are not allowed in CHANGELOG.md headings",
        ),
        (
            5,
            "CHANGELOG.md must not use level-4 or deeper headings; use bold list labels for "
            "level-4 and list labels for level-5+ sections instead",
        ),
    ]

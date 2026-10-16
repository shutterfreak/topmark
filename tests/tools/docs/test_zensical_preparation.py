# topmark:header:start
#
#   project      : TopMark
#   file         : test_zensical_preparation.py
#   file_relpath : tests/tools/docs/test_zensical_preparation.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the disposable Zensical documentation-preparation helpers."""

# Allow testing private helper functions directly without inline comment overhead.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
import tomlkit

from tools.docs import gen_cli_reference_pages
from tools.docs import prepare_zensical_docs
from tools.docs.gen_cli_reference_pages import DocsWriter
from tools.docs.gen_cli_reference_pages import FilesystemDocsWriter

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from subprocess import CompletedProcess


def test_filesystem_docs_writer_writes_relative_page(
    tmp_path: Path,
) -> None:
    """The staging writer materializes nested generated documentation pages."""
    docs_dir: Path = tmp_path / "docs"
    writer = FilesystemDocsWriter(docs_dir)

    with writer.open("api/internals/topmark/api/index.md", "w") as page:
        page.write("# API\n")

    generated_page: Path = docs_dir / "api/internals/topmark/api/index.md"
    assert generated_page.read_text(encoding="utf-8") == "# API\n"


def test_generate_cli_reference_pages_writes_all_cli_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI export generation maps each command output to its generated page."""
    writer = FilesystemDocsWriter(tmp_path / "docs")
    outputs: Iterator[str] = iter(
        (
            "filetypes\n",
            "processors\n",
            "bindings\n",
            "example\n",
            "defaults\n",
        )
    )

    def run_topmark_markdown(*args: str) -> str:
        """Return deterministic output for each generated CLI page."""
        assert args
        return next(outputs)

    monkeypatch.setattr(
        gen_cli_reference_pages,
        "_run_topmark_markdown",
        run_topmark_markdown,
    )

    gen_cli_reference_pages.generate_cli_reference_pages(writer)

    assert (
        (tmp_path / "docs/usage/generated/filetypes.md")
        .read_text(encoding="utf-8")
        .endswith("filetypes\n")
    )
    assert (
        (tmp_path / "docs/usage/generated/processors.md")
        .read_text(encoding="utf-8")
        .endswith("processors\n")
    )
    assert (
        (tmp_path / "docs/configuration/generated/config-defaults.md")
        .read_text(encoding="utf-8")
        .endswith("defaults\n")
    )


def test_run_topmark_markdown_includes_command_output_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed CLI export includes both output streams in the raised error."""
    completed: CompletedProcess[str] = gen_cli_reference_pages.subprocess.CompletedProcess(
        args=["topmark"],
        returncode=2,
        stdout="out",
        stderr="err",
    )

    def run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> CompletedProcess[str]:
        """Return a deterministic failed subprocess result."""
        assert command
        assert capture_output
        assert text
        assert not check
        return completed

    monkeypatch.setattr(
        gen_cli_reference_pages.subprocess,
        "run",
        run,
    )

    with pytest.raises(RuntimeError, match="STDERR:\\nerr"):
        gen_cli_reference_pages._run_topmark_markdown("registry", "filetypes")


def test_module_path_helpers_identify_packages_and_private_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API-autonav paths follow the physical source package layout."""
    package: Path = tmp_path / "src" / "topmark" / "nested"
    package.mkdir(parents=True)
    (tmp_path / "src" / "topmark" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "module.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert gen_cli_reference_pages._exists_in_src("topmark.nested.module")
    assert gen_cli_reference_pages._is_package("topmark.nested")
    assert gen_cli_reference_pages._api_autonav_doc_path("topmark.nested") == (
        "api/internals/topmark/nested/index.md"
    )
    assert gen_cli_reference_pages._api_autonav_doc_path("topmark.nested.module") == (
        "api/internals/topmark/nested/module.md"
    )
    assert gen_cli_reference_pages._should_skip("topmark._internal.module")
    assert not gen_cli_reference_pages._should_skip("topmark.public.module")


def test_scan_module_docstring_collects_unlinked_symbols(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The docstring scanner records source-relative symbol findings for strict mode."""
    source = tmp_path / "module.py"
    source.write_text('"""Uses `topmark.api.run`."""\n', encoding="utf-8")

    def find_unlinked_symbols(_docstring: str) -> dict[str, set[int]]:
        """Return the deterministic unresolved symbol finding."""
        return {
            "topmark.api.run": {1},
        }

    monkeypatch.setattr(
        gen_cli_reference_pages,
        "find_unlinked_backticked_symbols_with_locations",
        find_unlinked_symbols,
    )
    gen_cli_reference_pages._DOCSTRING_REF_FINDINGS.clear()

    gen_cli_reference_pages._scan_module_docstring(
        "topmark.module",
        str(source),
        "api/internals/topmark/module.md",
    )

    assert [
        (str(source), {"topmark.api.run": {1}})
    ] == gen_cli_reference_pages._DOCSTRING_REF_FINDINGS


def test_main_requires_writer_and_runs_validation_before_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The staging entry point rejects implicit output and preserves operation order."""
    with pytest.raises(ValueError, match="writer"):
        gen_cli_reference_pages.main()

    calls: list[str] = []

    def validate_docstring_links() -> None:
        """Record the reference-validation phase."""
        calls.append("validate")

    def generate_cli_reference_pages(_writer: DocsWriter) -> None:
        """Record the page-generation phase."""
        calls.append("generate")

    monkeypatch.setattr(
        gen_cli_reference_pages,
        "validate_docstring_links",
        validate_docstring_links,
    )
    monkeypatch.setattr(
        gen_cli_reference_pages,
        "generate_cli_reference_pages",
        generate_cli_reference_pages,
    )

    gen_cli_reference_pages.main(FilesystemDocsWriter(tmp_path))

    assert calls == ["validate", "generate"]


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.md",
        "../outside.md",
        r"..\outside.md",
    ],
)
def test_filesystem_docs_writer_rejects_escaping_paths(
    tmp_path: Path,
    path: str,
) -> None:
    """The staging writer cannot create files outside its documentation root."""
    writer = FilesystemDocsWriter(tmp_path / "docs")

    with pytest.raises(ValueError, match="must be relative"):
        writer.open(path, "w")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows drive semantics only")
@pytest.mark.parametrize(
    "path",
    [
        r"\rooted.md",
        r"C:\absolute.md",
        r"C:drive-relative.md",
    ],
)
def test_filesystem_docs_writer_rejects_windows_rooted_or_drive_paths(
    tmp_path: Path,
    path: str,
) -> None:
    """The staging writer rejects Windows-rooted and drive-qualified paths."""
    writer = FilesystemDocsWriter(tmp_path / "docs")

    with pytest.raises(ValueError, match="must be relative"):
        writer.open(path, "w")


def test_write_staging_config_uses_staged_docs_and_source_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The derived config redirects docs and mkdocstrings paths for the staging tree."""
    source_config: Path = tmp_path / "zensical.toml"
    staging_config: Path = tmp_path / ".zensical" / "zensical.toml"
    source_config.write_text(
        "[project]\n\n  [project.plugins.api-autonav]\n"
        '  modules                       = ["src/topmark"]\n'
        "\n    [project.plugins.mkdocstrings.handlers.python]\n"
        '    paths = ["src"]\n',
        encoding="utf-8",
    )
    staging_config.parent.mkdir()
    monkeypatch.setattr(
        prepare_zensical_docs,
        "SOURCE_CONFIG",
        source_config,
    )
    monkeypatch.setattr(
        prepare_zensical_docs,
        "STAGING_CONFIG",
        staging_config,
    )

    prepare_zensical_docs._write_staging_config()

    staging_text: str = staging_config.read_text(encoding="utf-8")
    staging_config_document: tomlkit.TOMLDocument = tomlkit.parse(staging_text)
    assert staging_config_document.unwrap() == {
        "project": {
            "docs_dir": "docs",
            "site_dir": "site",
            "plugins": {
                "api-autonav": {
                    "modules": [
                        "../src/topmark",
                    ],
                },
                "mkdocstrings": {
                    "handlers": {
                        "python": {
                            "paths": [
                                "../src",
                            ],
                        },
                    },
                },
            },
        },
    }

    assert staging_text.endswith(
        "# Generated by tools/docs/prepare_zensical_docs.py; do not edit.\n"
    )


def test_substitute_version_tokens_rewrites_all_staged_markdown(
    tmp_path: Path,
) -> None:
    """Version tokens are expanded in handwritten and generated staged pages."""
    handwritten_page: Path = tmp_path / "index.md"
    generated_page: Path = tmp_path / "api" / "reference.md"
    generated_page.parent.mkdir()
    handwritten_page.write_text("# TopMark %%TOPMARK_VERSION%%\n", encoding="utf-8")
    generated_page.write_text("%%TOPMARK_VERSION%% API\n", encoding="utf-8")

    prepare_zensical_docs._substitute_version_tokens(
        tmp_path,
        "1.2.3",
    )

    assert handwritten_page.read_text(encoding="utf-8") == "# TopMark 1.2.3\n"
    assert generated_page.read_text(encoding="utf-8") == "1.2.3 API\n"


def test_expand_include_markdown_directives_expands_nested_snippets_and_rewrites_links(
    tmp_path: Path,
) -> None:
    """Local snippets are expanded recursively with links valid from their final page."""
    docs_dir: Path = tmp_path / "docs"
    page_path: Path = docs_dir / "ci" / "page.md"
    snippets_dir: Path = docs_dir / "_snippets"
    page_path.parent.mkdir(parents=True)
    snippets_dir.mkdir()
    page_path.write_text(
        'Before\n{% include-markdown "\\_snippets/wrapper.md" %}\nAfter\n',
        encoding="utf-8",
    )
    (snippets_dir / "wrapper.md").write_text(
        '{% include-markdown "_snippets/nested.md" %}\n',
        encoding="utf-8",
    )
    (snippets_dir / "nested.md").write_text("[Guide](../guide.md#intro)\n", encoding="utf-8")

    prepare_zensical_docs._expand_include_markdown_directives(docs_dir)

    assert page_path.read_text(encoding="utf-8") == "Before\n[Guide](../guide.md#intro)\nAfter\n"
    assert not snippets_dir.exists()


@pytest.mark.parametrize(
    ("directive", "message"),
    [
        ('{% include-markdown "_snippets/missing.md" %}', "does not exist"),
        ('{% include-markdown "../outside.md" %}', "escapes"),
        ('{% include-markdown "_snippets/item.md" start="1" %}', "Unsupported"),
    ],
)
def test_expand_include_markdown_directives_rejects_unsupported_or_missing_includes(
    tmp_path: Path,
    directive: str,
    message: str,
) -> None:
    """The adapter fails rather than silently accepting unsupported include syntax."""
    docs_dir: Path = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "page.md").write_text(f"{directive}\n", encoding="utf-8")

    with pytest.raises((FileNotFoundError, ValueError), match=message):
        prepare_zensical_docs._expand_include_markdown_directives(docs_dir)


def test_expand_include_markdown_directives_rejects_cycles(
    tmp_path: Path,
) -> None:
    """Recursive snippet references report their inclusion cycle."""
    docs_dir: Path = tmp_path / "docs"
    snippets_dir: Path = docs_dir / "_snippets"
    docs_dir.mkdir()
    snippets_dir.mkdir()
    (docs_dir / "page.md").write_text(
        '{% include-markdown "_snippets/first.md" %}\n',
        encoding="utf-8",
    )
    (snippets_dir / "first.md").write_text(
        '{% include-markdown "_snippets/second.md" %}\n',
        encoding="utf-8",
    )
    (snippets_dir / "second.md").write_text(
        '{% include-markdown "_snippets/first.md" %}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Include cycle"):
        prepare_zensical_docs._expand_include_markdown_directives(docs_dir)

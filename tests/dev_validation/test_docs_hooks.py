# topmark:header:start
#
#   project      : TopMark
#   file         : test_docs_hooks.py
#   file_relpath : tests/dev_validation/test_docs_hooks.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation tests for TopMark's MkDocs hooks."""

from __future__ import annotations

import pytest

from tools.docs import hooks


def _transform(markdown: str) -> str:
    """Run the page-Markdown hook without enabling diagnostic-only behavior."""
    return hooks.on_page_markdown(markdown, page=object(), config={}, files=None)


@pytest.mark.dev_validation
def test_page_markdown_transforms_version_and_github_callouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page hook substitutes the build version and renders supported callouts."""
    monkeypatch.setattr(hooks, "topmark_version_id", "1.2.3")
    monkeypatch.setattr(hooks, "TOPMARK_DOCS_DEBUG", False)
    monkeypatch.setattr(hooks, "TOPMARK_DOCS_STRICT_REFS", False)

    assert _transform("> [!WARNING] Version %%TOPMARK_VERSION%%") == (
        '<div class="admonition warning" markdown="1">\n'
        '  <p class="admonition-title">Warning</p>\n'
        "Version 1.2.3\n"
        "</div>\n"
    )


@pytest.mark.dev_validation
def test_page_markdown_repairs_prose_links_but_preserves_fenced_examples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page hook normalizes authored links without changing fenced examples."""
    monkeypatch.setattr(hooks, "TOPMARK_DOCS_DEBUG", False)
    monkeypatch.setattr(hooks, "TOPMARK_DOCS_STRICT_REFS", False)
    markdown = "[`topmark.api`][]\n\n```md\n[`topmark.registry`][]\n```\n"

    assert _transform(markdown) == (
        "[`topmark.api`][topmark.api]\n\n```md\n[`topmark.registry`][]\n```\n"
    )

# topmark:header:start
#
#   project      : TopMark
#   file         : test_defaults.py
#   file_relpath : tests/toml/test_defaults.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contracts for the bundled and generated default TOML documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import tomlkit

import topmark.toml.defaults as defaults
from topmark.toml.defaults import load_default_topmark_template_toml_text
from topmark.toml.defaults import render_default_topmark_toml_text

if TYPE_CHECKING:
    import pytest
    from _pytest.capture import CaptureResult

    from topmark.toml.defaults import DefaultTomlTemplateText


@dataclass
class _FakeResource:
    text: str = ""
    error: OSError | None = None

    def read_text(self, *, encoding: str) -> str:
        assert encoding == "utf8"
        if self.error is not None:
            raise self.error
        return self.text


@dataclass
class _FakePackage:
    resource: _FakeResource

    def joinpath(self, name: str) -> _FakeResource:
        assert name == defaults.EXAMPLE_TOPMARK_TOML_NAME
        return self.resource


def _install_resource(monkeypatch: pytest.MonkeyPatch, resource: _FakeResource) -> None:
    def fake_files(_package: object) -> _FakePackage:
        return _FakePackage(resource)

    monkeypatch.setattr(defaults, "files", fake_files)


def test_load_default_template_strips_only_owned_header_and_leading_blanks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful loading should retain annotated content after the owned marker."""
    resource = _FakeResource(
        text=(
            "# topmark:header:start\n# metadata\n# topmark:header:end\n\n\n"
            "  # meaningful comment\n[config]\nstrict = false\n"
        )
    )
    _install_resource(monkeypatch, resource)

    result: DefaultTomlTemplateText = load_default_topmark_template_toml_text()

    assert result.error is None
    assert result.toml_text.startswith("  # meaningful comment\n[config]")
    assert "topmark:header" not in result.toml_text
    tomlkit.parse(result.toml_text)


def test_load_default_template_strips_crlf_blank_lines_consistently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owned-header cleanup should not leave CRLF-only preamble blanks."""
    resource = _FakeResource(
        text=(
            "# topmark:header:start\r\n# topmark:header:end\r\n\r\n"
            "  # meaningful\r\n[config]\r\nstrict = false\r\n"
        )
    )
    _install_resource(monkeypatch, resource)

    result: DefaultTomlTemplateText = load_default_topmark_template_toml_text()

    assert result.toml_text.startswith("  # meaningful\r\n")
    assert "\n" not in result.toml_text.replace("\r\n", "")
    tomlkit.parse(result.toml_text)


def test_load_default_template_without_end_marker_is_conservative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An incomplete owned header should not cause arbitrary content removal."""
    source: str = "\n# topmark:header:start\n# keep me\n[config]\nstrict = false\n"
    _install_resource(monkeypatch, _FakeResource(text=source))

    result: DefaultTomlTemplateText = load_default_topmark_template_toml_text()

    assert result.error is None
    assert result.toml_text == source
    tomlkit.parse(result.toml_text)


def test_load_default_template_falls_back_to_independent_parseable_defaults(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Resource failures should return explicit generated defaults and metadata."""
    error = OSError("resource unavailable")
    _install_resource(monkeypatch, _FakeResource(error=error))
    warnings: list[tuple[str, tuple[object, ...]]] = []

    def record_warning(message: str, *args: object) -> None:
        warnings.append((message, args))

    monkeypatch.setattr(defaults.logger, "warning", record_warning)

    first: DefaultTomlTemplateText = load_default_topmark_template_toml_text()
    second: DefaultTomlTemplateText = load_default_topmark_template_toml_text()

    assert first is not second
    assert first.toml_text == second.toml_text
    assert first.error is error
    assert second.error is error
    assert "packaged default configuration template" in first.toml_text
    assert "generated from TopMark built-in defaults" in first.toml_text
    assert "End of generated defaults" in first.toml_text
    parsed: tomlkit.TOMLDocument = tomlkit.parse(first.toml_text)
    assert parsed["config"]["strict"] is False
    assert parsed["writer"]["strategy"] == "atomic"
    assert len(warnings) == 2
    assert all(error in args for _, args in warnings)
    captured: CaptureResult[str] = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_real_bundled_template_loads_as_utf8_annotated_toml() -> None:
    """The installed resource should remain parseable and retain its annotations."""
    result: DefaultTomlTemplateText = load_default_topmark_template_toml_text()

    assert result.error is None
    assert "# TopMark configuration" in result.toml_text
    assert "# root = true" in result.toml_text
    assert "[writer]" in result.toml_text
    tomlkit.parse(result.toml_text)


def test_render_default_topmark_toml_text_uses_central_defaults_in_both_shapes() -> None:
    """Generated defaults should be parseable and own pyproject nesting exactly once."""
    plain: str = render_default_topmark_toml_text(for_pyproject=False)
    pyproject: str = render_default_topmark_toml_text(for_pyproject=True)

    plain_doc: tomlkit.TOMLDocument = tomlkit.parse(plain)
    pyproject_doc: tomlkit.TOMLDocument = tomlkit.parse(pyproject)
    assert plain_doc["config"]["strict"] is False
    assert plain_doc["writer"]["strategy"] == "atomic"
    assert pyproject_doc["tool"]["topmark"]["config"]["strict"] is False
    assert pyproject_doc["tool"]["topmark"]["writer"]["strategy"] == "atomic"
    assert pyproject.count("[tool.topmark]") == 1

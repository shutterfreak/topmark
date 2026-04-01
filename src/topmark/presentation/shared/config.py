# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/presentation/shared/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared data preparation for config CLI emitters.

This module contains Click-free helpers that *prepare* domain data for human-facing emitters
(TEXT / MARKDOWN).

It intentionally sits between:

- configuration I/O helpers in [`topmark.config.io`][topmark.config.io], and
- renderer in [`topmark.presentation.text.config`][topmark.presentation.text.config] (ANSI) and
  [`topmark.presentation.markdown.config`][topmark.presentation.markdown.config] (Markdown).

Notes:
    These helpers may perform I/O (e.g. loading bundled resources). They do not print to
    stdout/stderr; user-facing warnings should be handled by the caller or the emitters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.config.io.loaders import load_default_config_template_toml_text
from topmark.config.io.loaders import render_runtime_defaults_toml_text
from topmark.config.io.render import clean_toml_text
from topmark.config.io.render import to_toml
from topmark.config.io.serializers import config_to_toml_dict
from topmark.config.io.template_surgery import TemplateEditResult
from topmark.config.io.template_surgery import ensure_pyproject_header
from topmark.config.io.template_surgery import set_root_flag_in_template_text
from topmark.config.io.template_surgery import validate_toml_for_config_init
from topmark.presentation.shared.diagnostic import HumanDiagnosticCounts
from topmark.presentation.shared.diagnostic import HumanDiagnosticLine
from topmark.presentation.shared.diagnostic import prepare_human_diagnostics
from topmark.toml.surgery import set_root_flag

if TYPE_CHECKING:
    from topmark.config.model import Config


# --- Generate initial / default Config ---


@dataclass(frozen=True, slots=True)
class ConfigInitHumanReport:
    """Prepared payload for `topmark config init` (human formats).

    Attributes:
        toml_text: Starter configuration TOML text (annotated template).
        error: Optional exception raised while reading the bundled template. When set, callers may
            render a warning and still proceed with the returned TOML text (which may be a
            synthesized fallback).
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)
    """

    toml_text: str
    error: Exception | None
    verbosity_level: int
    styled: bool


def build_config_init_human_report(
    *,
    for_pyproject: bool,
    root: bool,
    verbosity_level: int,
    styled: bool,
) -> ConfigInitHumanReport:
    """Prepare human-facing data for `topmark config init`.

    Uses the annotated packaged template when available; otherwise falls back to generated defaults
    with an embedded TOML comment notice.

    Args:
        for_pyproject: If True, nest under [tool.topmark].
        root: If True, set `root = true` (top-level or tool.topmark.root).
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)

    Returns:
        Prepared TOML text plus optional template read error.
    """
    toml_text, err = load_default_config_template_toml_text()

    changed = False

    if for_pyproject:
        res: TemplateEditResult = ensure_pyproject_header(toml_text)
        toml_text, changed = res.text, (changed or res.changed)

    if root:
        res = set_root_flag_in_template_text(
            toml_text,
            root=True,
        )
        toml_text, changed = res.text, (changed or res.changed)

    # TOML correctness backstop
    validate_toml_for_config_init(
        toml_text,
        for_pyproject=for_pyproject,
        root_expected=root,
    )

    return ConfigInitHumanReport(
        toml_text=toml_text,
        error=err,
        verbosity_level=verbosity_level,
        styled=styled,
    )


@dataclass(frozen=True, slots=True)
class ConfigDefaultsHumanReport:
    """Prepared TOML payload for `topmark config defaults`.

    This is the *cleaned* default configuration (copy/paste friendly).

    Attributes:
        toml_text: Cleaned TOML text. When prepared with `for_pyproject=True`, the TOML is nested
            under `[tool.topmark]`.
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)

    """

    toml_text: str
    verbosity_level: int
    styled: bool


def build_config_defaults_human_report(
    *,
    for_pyproject: bool,
    root: bool,
    verbosity_level: int,
    styled: bool,
) -> ConfigDefaultsHumanReport:
    """Prepare human-facing data for `topmark config defaults`.

    Loads the packaged default TOML *template* as text, optionally nests it under `[tool.topmark]`
    for `pyproject.toml` usage, then cleans it (removing comments/extraneous whitespace) to make it
    suitable for copy/paste.

    Important:
        This uses the bundled template text (not a synthesized `Config`) so the  output remains the
        canonical reference document.

    Args:
        for_pyproject: If True, nest the TOML under `[tool.topmark]`.
        root: If True, set `root = true` (top-level or tool.topmark.root).
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)

    Returns:
        Prepared cleaned TOML text.
    """
    toml_text: str = render_runtime_defaults_toml_text(for_pyproject=for_pyproject)

    if root:
        toml_text = set_root_flag(toml_text, for_pyproject=for_pyproject, root=True)

    cleaned: str = clean_toml_text(toml_text)
    return ConfigDefaultsHumanReport(
        toml_text=cleaned,
        verbosity_level=verbosity_level,
        styled=styled,
    )


# --- Check a resolved Config


@dataclass(frozen=True, slots=True)
class ConfigCheckHumanReport:
    """Prepared human-facing data for `topmark config check`.

    Attributes:
        config_files: Config files contributing to the effective config (stringified paths).
        ok: Whether the configuration passed validation.
        strict: Whether strict checking was enabled.
        merged_toml: Effective merged configuration as TOML, or None when not requested
            (typically only included at verbosity >= 2).
        counts: Human diagnostic counts.
        diagnostics: Human diagnostic lines (ordered).
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)

    """

    config_files: list[str]
    ok: bool
    strict: bool
    merged_toml: str | None
    counts: HumanDiagnosticCounts
    diagnostics: list[HumanDiagnosticLine]
    verbosity_level: int
    styled: bool


def _stringify_config_files(config: Config) -> list[str]:
    """Return `config.config_files` as a list of string paths.

    This keeps prepared payloads Click-free and renderer-friendly by avoiding `Path` objects in the
    shared prepared shapes.
    """
    return [str(p) for p in config.config_files]


def build_config_check_human_report(
    *,
    config: Config,
    ok: bool,
    strict: bool,
    verbosity_level: int,
    styled: bool,
) -> ConfigCheckHumanReport:
    """Prepare human-facing data for `topmark config check`.

    This helper is Click-free and may perform light computation (counts, string normalization).
    It does not print.

    Args:
        config: Effective frozen configuration.
        ok: Whether the configuration passed validation.
        strict: Whether strict checking was enabled.
        verbosity_level: Effective verbosity (used for gating heavy/verbose sections).
        styled: Whether to style text output (OutputFormat.TEXT)

    Returns:
        Prepared config file list, optional merged TOML (verbosity > 1), plus human diagnostic
        counts and lines.
    """
    merged_toml: str | None = None
    if verbosity_level > 1:
        merged_toml = to_toml(
            config_to_toml_dict(
                config,
                include_files=False,
            )
        )

    counts, lines = prepare_human_diagnostics(config.diagnostics)

    return ConfigCheckHumanReport(
        config_files=_stringify_config_files(config),
        ok=ok,
        strict=strict,
        merged_toml=merged_toml,
        counts=counts,
        diagnostics=lines,
        styled=styled,
        verbosity_level=verbosity_level,
    )


# --- Dump a resolved Config


@dataclass(frozen=True, slots=True)
class ConfigDumpHumanReport:
    """Prepared human-facing data for `topmark config dump`.

    Attributes:
        config_files: Config files contributing to the effective config (stringified paths).
        merged_toml: Effective merged configuration rendered as TOML.
        verbosity_level: Effective verbosity for gating extra details.
        styled: Whether to style text output (OutputFormat.TEXT)
    """

    config_files: list[str]
    merged_toml: str
    verbosity_level: int
    styled: bool


def build_config_dump_human_report(
    *,
    config: Config,
    styled: bool,
    verbosity_level: int,
) -> ConfigDumpHumanReport:
    """Prepare human-facing data for `topmark config dump`.

    This helper is Click-free: it performs serialization to TOML but does not print.

    Args:
        config: Effective frozen configuration.
        styled: Whether to style text output (OutputFormat.TEXT)
        verbosity_level: Effective verbosity for gating extra details.

    Returns:
        Prepared config file list and merged TOML text.
    """
    merged_toml: str = to_toml(
        config_to_toml_dict(
            config,
            include_files=False,
        )
    )
    return ConfigDumpHumanReport(
        config_files=_stringify_config_files(config),
        merged_toml=merged_toml,
        styled=styled,
        verbosity_level=verbosity_level,
    )

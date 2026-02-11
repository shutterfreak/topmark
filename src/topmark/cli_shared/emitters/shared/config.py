# topmark:header:start
#
#   project      : TopMark
#   file         : config.py
#   file_relpath : src/topmark/cli_shared/emitters/shared/config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared data preparation for config CLI emitters.

This module contains Click-free helpers that *prepare* domain data for human-facing emitters
(TEXT / MARKDOWN).

It intentionally sits between:

- configuration I/O helpers in [`topmark.config.io`][topmark.config.io], and
- renderer/emitters in [`topmark.cli.emitters`][topmark.cli.emitters] (ANSI) and
  [`topmark.cli_shared.emitters`][topmark.cli_shared.emitters] (Markdown).

Notes:
    These helpers may perform I/O (e.g. loading bundled resources). They do not print to
    stdout/stderr; user-facing warnings should be handled by the caller or the emitters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.cli_shared.emitters.shared.diagnostic import (
    HumanDiagnosticCounts,
    HumanDiagnosticLine,
    prepare_human_diagnostics,
)
from topmark.config.io import to_toml
from topmark.config.io.loaders import load_default_config_template_toml_text
from topmark.config.io.surgery import set_root_flag
from topmark.config.io.template_surgery import (
    TemplateEditResult,
    ensure_pyproject_header,
    set_root_flag_in_template_text,
    validate_toml_for_config_init,
)
from topmark.config.model import MutableConfig

if TYPE_CHECKING:
    from topmark.config.model import Config


# --- Generate initial / default Config ---


@dataclass(frozen=True, slots=True)
class ConfigInitPrepared:
    """Prepared payload for `topmark config init` (human formats).

    Attributes:
        toml_text: Starter configuration TOML text (annotated template).
        error: Optional exception raised while reading the bundled template. When set, callers may
            render a warning and still proceed with the returned TOML text (which may be a
            synthesized fallback).
    """

    toml_text: str
    error: Exception | None


def prepare_config_init(
    *,
    for_pyproject: bool,
    root: bool,
) -> ConfigInitPrepared:
    """Prepare human-facing data for `topmark config init`.

    Uses the annotated packaged template when available; otherwise falls back to generated defaults
    with an embedded TOML comment notice.

    Args:
        for_pyproject: If True, nest under [tool.topmark].
        root: If True, set `root = true` (top-level or tool.topmark.root).

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

    return ConfigInitPrepared(toml_text=toml_text, error=err)


@dataclass(frozen=True, slots=True)
class ConfigDefaultsPrepared:
    """Prepared TOML payload for `topmark config defaults`.

    This is the *cleaned* default configuration (copy/paste friendly).

    Attributes:
        toml_text: Cleaned TOML text. When prepared with `for_pyproject=True`, the TOML is nested
            under `[tool.topmark]`.
    """

    toml_text: str


def prepare_config_defaults(
    *,
    for_pyproject: bool,
    root: bool,
) -> ConfigDefaultsPrepared:
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

    Returns:
        Prepared cleaned TOML text.
    """
    toml_text: str = MutableConfig.get_default_config_toml(for_pyproject=for_pyproject)

    if root:
        toml_text = set_root_flag(toml_text, for_pyproject=for_pyproject, root=True)

    cleaned: str = MutableConfig.to_cleaned_toml(toml_text)
    return ConfigDefaultsPrepared(toml_text=cleaned)


# --- Check a resolved Config


@dataclass(frozen=True, slots=True)
class ConfigCheckPrepared:
    """Prepared human-facing data for `topmark config check`.

    Attributes:
        config_files: Config files contributing to the effective config (stringified paths).
        merged_toml: Effective merged configuration as TOML, or None when not requested
            (typically only included at verbosity >= 2).
        counts: Human diagnostic counts.
        diagnostics: Human diagnostic lines (ordered).
    """

    config_files: list[str]
    merged_toml: str | None
    counts: HumanDiagnosticCounts
    diagnostics: list[HumanDiagnosticLine]


def _stringify_config_files(config: Config) -> list[str]:
    """Return `config.config_files` as a list of string paths.

    This keeps prepared payloads Click-free and renderer-friendly by avoiding `Path` objects in the
    shared prepared shapes.
    """
    return [str(p) for p in config.config_files]


def prepare_config_check(
    *,
    config: Config,
    verbosity_level: int,
) -> ConfigCheckPrepared:
    """Prepare human-facing data for `topmark config check`.

    This helper is Click-free and may perform light computation (counts, string normalization).
    It does not print.

    Args:
        config: Effective frozen configuration.
        verbosity_level: Effective verbosity (used for gating heavy/verbose sections).

    Returns:
        Prepared config file list, optional merged TOML (verbosity > 1), plus human diagnostic
        counts and lines.
    """
    merged_toml: str | None = None
    if verbosity_level > 1:
        merged_toml = to_toml(config.to_toml_dict())

    counts, lines = prepare_human_diagnostics(config.diagnostics)

    return ConfigCheckPrepared(
        config_files=_stringify_config_files(config),
        merged_toml=merged_toml,
        counts=counts,
        diagnostics=lines,
    )


# --- Dump a resolved Config


@dataclass(frozen=True, slots=True)
class ConfigDumpPrepared:
    """Prepared human-facing data for `topmark config dump`.

    Attributes:
        config_files: Config files contributing to the effective config (stringified paths).
        merged_toml: Effective merged configuration rendered as TOML.
    """

    config_files: list[str]
    merged_toml: str


def prepare_config_dump(
    *,
    config: Config,
) -> ConfigDumpPrepared:
    """Prepare human-facing data for `topmark config dump`.

    This helper is Click-free: it performs serialization to TOML but does not print.

    Args:
        config: Effective frozen configuration.

    Returns:
        Prepared config file list and merged TOML text.
    """
    merged_toml: str = to_toml(config.to_toml_dict())
    return ConfigDumpPrepared(
        config_files=_stringify_config_files(config),
        merged_toml=merged_toml,
    )

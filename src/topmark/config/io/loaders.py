# topmark:header:start
#
#   project      : TopMark
#   file         : loaders.py
#   file_relpath : src/topmark/config/io/loaders.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Load TOML configuration sources.

This module provides I/O helpers for reading TopMark configuration from:
- the packaged default TOML resource, and
- on-disk TOML files (`topmark.toml` / `pyproject.toml`).

Parsing is done with `tomlkit` and returned as plain `dict` structures.
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING, Any, cast

import tomlkit
from tomlkit.exceptions import ParseError as TomlkitParseError

from topmark.config.io.render import to_toml
from topmark.config.io.surgery import nest_toml_under_section
from topmark.config.keys import Toml
from topmark.config.logging import get_logger
from topmark.constants import (
    DEFAULT_TOML_CONFIG_NAME,
    DEFAULT_TOML_CONFIG_PACKAGE,
    TOPMARK_END_MARKER,
)

if TYPE_CHECKING:
    import sys
    from pathlib import Path

    if sys.version_info < (3, 14):
        # Python <=3.13
        from importlib.abc import Traversable
    else:
        # Python 3.14+: Traversable moved here
        from importlib.resources.abc import Traversable

    from topmark.config.logging import TopmarkLogger

    from .types import TomlTable

logger: TopmarkLogger = get_logger(__name__)


# --- TOML file I/O and normalization ---


def load_default_config_template_toml_text() -> tuple[str, Exception | None]:
    """Load the bundled default TOML config *template* as text.

    This reads the annotated template bundled with TopMark
    (``topmark-default.toml``) and returns it as UTF-8 text.

    Unlike `load_defaults_dict`, this helper preserves the template's
    comments and formatting (when the packaged resource is available).

    If the packaged template cannot be read, the function falls back to a
    generated TOML document built from TopMark's **runtime defaults**
    (`load_defaults_dict`). The returned ``error`` is the exception
    raised while reading the packaged template.

    Returns:
        A tuple ``(toml_text, error)`` where:

        - ``toml_text`` is the TOML document text.
        - ``error`` is the exception raised while reading the bundled template,
            if any. Callers may surface this as a user-facing warning.

    Notes:
        - This function performs I/O and logs a warning on fallback, but it does
          not print to stdout/stderr.
        - User-facing warnings should be emitted by CLI emitters.
    """
    # Attempt to read the annotated bundled template; preserve comments and formatting.
    # This is the preferred source for human-facing outputs.
    resource: Traversable = files(DEFAULT_TOML_CONFIG_PACKAGE).joinpath(DEFAULT_TOML_CONFIG_NAME)
    err: Exception | None = None

    try:
        toml_text: str = resource.read_text(encoding="utf8")
        # Strip the TopMark header block (if present) so config-init output starts
        # at the actual template content.
        #
        # We remove everything up to and including the line `# topmark:header:end`.
        # Keep any subsequent blank line trimming conservative.
        lines: list[str] = toml_text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.strip() == f"# {TOPMARK_END_MARKER}":
                toml_text = "".join(lines[i + 1 :])
                # Remove leading blank lines introduced by stripping.
                toml_text = toml_text.lstrip("\n")
                break
    except OSError as exc:
        # Fallback: the packaged annotated template is missing/unreadable.
        # Generate a usable document from the runtime defaults dict.
        err = exc
        logger.warning("Cannot read packaged default config template %s: %s", resource, exc)

        generated: str = to_toml(load_defaults_dict())

        # Make the fallback explicit in the generated output, without breaking TOML.
        notice: str = (
            "# NOTE: The packaged default configuration template 'topmark-default.toml' "
            "could not be read.\n"
            f"# Reason: {exc}\n"
            "# The content below was generated from TopMark runtime defaults and "
            "may not include the usual comments/formatting.\n\n"
        )
        trailer: str = "\n# NOTE: End of generated defaults (template was missing/unreadable).\n"
        toml_text = f"{notice}{generated}{trailer}"

    return toml_text, err


def load_defaults_dict() -> TomlTable:
    """Return TopMark's **runtime defaults** as a Python dict.

    This function intentionally performs **no I/O**.

    The bundled file ``topmark-default.toml`` is an *annotated* template intended
    for human-facing output (e.g. ``topmark config init``). Runtime defaults,
    however, are defined in code so TopMark can operate even if the packaged
    template is missing or unreadable.

    If you need the annotated template (comments/formatting preserved), use
    `load_default_config_template_toml_text`.

    Returns:
        A TOML-table-compatible dict containing the runtime defaults.

    Notes:
        The returned value is a new dict so callers can mutate it safely.
    """
    # Keep this dict small and stable: it is the base layer for config merging.
    # Sections/keys align with `topmark.config.keys.Toml`.
    return {
        Toml.SECTION_HEADER: {
            Toml.KEY_FIELDS: ["file", "file_relpath"],
        },
        Toml.SECTION_FIELDS: {},
        Toml.SECTION_FORMATTING: {
            Toml.KEY_ALIGN_FIELDS: True,
            # NOTE: header_format defaults to None (unset) unless configured.
        },
        Toml.SECTION_WRITER: {
            Toml.KEY_TARGET: "file",
            Toml.KEY_STRATEGY: "atomic",
        },
        Toml.SECTION_POLICY: {
            Toml.KEY_POLICY_CHECK_ADD_ONLY: False,
            Toml.KEY_POLICY_CHECK_UPDATE_ONLY: False,
            Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: False,
        },
        Toml.SECTION_FILES: {
            # Pattern sources / explicit lists are empty by default.
            Toml.KEY_INCLUDE_FROM: [],
            Toml.KEY_EXCLUDE_FROM: [],
            Toml.KEY_FILES_FROM: [],
            Toml.KEY_INCLUDE_PATTERNS: [],
            Toml.KEY_EXCLUDE_PATTERNS: [],
            Toml.KEY_INCLUDE_FILE_TYPES: [],
            Toml.KEY_EXCLUDE_FILE_TYPES: [],
            Toml.KEY_FILES: [],
            # `relative_to` defaults to empty/unset.
            Toml.KEY_RELATIVE_TO: "",
        },
        # No policy_by_type defaults.
    }


def render_runtime_defaults_toml_text(
    *,
    for_pyproject: bool,
) -> str:
    """Render TopMark runtime defaults as TOML text.

    This is I/O-free: it serializes the dict returned by `load_defaults_dict()`.
    It does not preserve the annotated template comments/formatting.

    Args:
        for_pyproject: If True, nest the output under ``[tool.topmark]``.

    Returns:
        TOML document text.
    """
    toml_text: str = to_toml(load_defaults_dict())
    if for_pyproject:
        toml_text = nest_toml_under_section(toml_text, "tool.topmark")
    return toml_text


def load_toml_dict(path: Path) -> TomlTable:
    """Load and parse a TOML file from the filesystem.

    Args:
        path: Path to a TOML document (e.g., ``topmark.toml`` or ``pyproject.toml``).

    Returns:
        The parsed TOML content.

    Notes:
        - Errors are logged and an empty dict is returned on failure.
        - Encoding is assumed to be UTF-8.
    """
    try:
        text: str = path.read_text(encoding="utf-8")
        doc: tomlkit.TOMLDocument = tomlkit.parse(text)
        data_any: Any = doc.unwrap()
        return cast("TomlTable", data_any) if isinstance(data_any, dict) else {}
    except OSError as e:
        logger.error("Error loading TOML from %s: %s", path, e)
        return {}
    except TomlkitParseError as e:
        logger.error("Error decoding TOML from %s: %s", path, e)
        return {}
    except (TypeError, ValueError) as e:
        logger.error("Unknown error while reading TOML from %s: %s", path, e)
        return {}

# topmark:header:start
#
#   project      : TopMark
#   file         : loaders.py
#   file_relpath : src/topmark/config/io/loaders.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Helpers for TopMark's bundled/default TOML documents.

This module is intentionally separate from
[`topmark.toml.loaders`][topmark.toml.loaders]. It does not load TOML from
arbitrary on-disk user config files. Instead, it owns the bundled template and
the code-defined default TopMark TOML document used when the annotated template
is unavailable.

Today, `load_defaults_dict()` assembles one complete TOML-serializable default
TopMark document in a single place. Over time, this should evolve toward
merging smaller domain-scoped default fragments such as:
- layered config defaults
- persisted writer-option defaults
- config-resolution/discovery defaults (for example strict mode)

The current helper remains the single centralized assembly point for those
partial defaults until that split is implemented.
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING

from topmark.config.policy import HeaderMutationMode
from topmark.constants import DEFAULT_TOML_CONFIG_NAME
from topmark.constants import DEFAULT_TOML_CONFIG_PACKAGE
from topmark.constants import TOPMARK_END_MARKER
from topmark.core.logging import get_logger
from topmark.toml.keys import Toml
from topmark.toml.render import to_toml
from topmark.toml.surgery import nest_toml_under_section

if TYPE_CHECKING:
    import sys

    if sys.version_info < (3, 14):
        # Python <=3.13
        from importlib.abc import Traversable
    else:
        # Python 3.14+: Traversable moved here
        from importlib.resources.abc import Traversable

    from topmark.core.logging import TopmarkLogger
    from topmark.toml.types import TomlTable

logger: TopmarkLogger = get_logger(__name__)


# --- TOML file I/O and normalization ---


def load_default_config_template_toml_text() -> tuple[str, Exception | None]:
    """Load the bundled default TOML config *template* as text.

    This reads the annotated template bundled with TopMark
    (``topmark-example.toml``) and returns it as UTF-8 text.

    Unlike `load_defaults_dict`, this helper preserves the template's
    comments and formatting (when the packaged resource is available).

    If the packaged template cannot be read, the function falls back to a
    generated TOML document built from TopMark's default TOML document
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
        # Generate a usable document from the centralized default TOML dict.
        err = exc
        logger.warning("Cannot read packaged default config template %s: %s", resource, exc)

        generated: str = to_toml(load_defaults_dict())

        # Make the fallback explicit in the generated output, without breaking TOML.
        notice: str = (
            "# NOTE: The packaged default configuration template 'topmark-example.toml' "
            "could not be read.\n"
            f"# Reason: {exc}\n"
            "# The content below was generated from TopMark runtime defaults and "
            "may not include the usual comments/formatting.\n\n"
        )
        trailer: str = "\n# NOTE: End of generated defaults (template was missing/unreadable).\n"
        toml_text = f"{notice}{generated}{trailer}"

    return toml_text, err


def load_defaults_dict() -> TomlTable:
    """Return TopMark's default TOML document as a plain-Python table.

    This helper intentionally performs **no I/O**.

    The bundled file `topmark-example.toml` is an annotated template intended
    for human-facing output (for example `topmark config init`). The actual
    default TopMark TOML document is assembled in code so TopMark can still
    operate when the packaged template is missing or unreadable.

    Today, this helper assembles one centralized TOML-serializable default
    document that includes both layered config defaults and persisted writer
    defaults. In the future, the implementation may delegate to smaller
    domain-scoped helpers and then merge those partial TOML tables here.

    If you need the annotated template with comments and formatting preserved,
    use `load_default_config_template_toml_text()`.

    Returns:
        A new TOML-table-compatible dictionary containing the default TopMark
        TOML document.
    """
    # Keep this document small and stable: it is the centralized default
    # TopMark TOML document assembled in code.
    return {
        Toml.SECTION_HEADER: {
            Toml.KEY_FIELDS: ["file", "file_relpath"],
            # `relative_to` defaults to empty/unset.
            Toml.KEY_RELATIVE_TO: "",
        },
        Toml.SECTION_FIELDS: {},
        Toml.SECTION_FORMATTING: {
            Toml.KEY_ALIGN_FIELDS: True,
        },
        Toml.SECTION_WRITER: {
            Toml.KEY_STRATEGY: "atomic",
        },
        Toml.SECTION_POLICY: {
            Toml.KEY_POLICY_HEADER_MUTATION_MODE: HeaderMutationMode.ALL.value,
            Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES: False,
            Toml.KEY_POLICY_EMPTIES_INSERT_MODE: "logical_empty",
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
        },
        # No policy_by_type defaults.
    }


def render_runtime_defaults_toml_text(
    *,
    for_pyproject: bool,
) -> str:
    """Render the centralized default TopMark TOML document as text.

    This helper is I/O-free: it serializes the TOML table returned by
    `load_defaults_dict()`. It does not preserve the annotated template's
    comments or formatting.

    Note:
        The function name is transitional. The rendered content is the default
        TopMark TOML document, not execution-only `RunOptions`.

    Args:
        for_pyproject: If `True`, nest the output under `[tool.topmark]`.

    Returns:
        TOML document text.
    """
    toml_text: str = to_toml(load_defaults_dict())
    if for_pyproject:
        toml_text = nest_toml_under_section(toml_text, "tool.topmark")
    return toml_text

# topmark:header:start
#
#   project      : TopMark
#   file         : schema.py
#   file_relpath : src/topmark/toml/schema.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static TOML schema metadata and validation helpers for TopMark.

This module defines the explicit, typed schema used to validate the structure
of TopMark TOML documents before value-level parsing. It complements
[`topmark.toml.keys`][topmark.toml.keys], which remains the canonical registry
for user-facing string keys.

The schema layer focuses on shape validation:
    - known top-level sections,
    - allowed keys inside closed sections,
    - open sections such as `[fields]`,
    - nested policy subtables such as `[policy_by_type.<filetype>]`,
    - dump/provenance-only keys that should not appear in ordinary input mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from enum import Enum
from typing import TYPE_CHECKING
from typing import Final

from topmark.diagnostic.model import DiagnosticLevel
from topmark.toml.keys import Toml
from topmark.toml.validation import TomlDiagnosticCode
from topmark.toml.validation import TomlValidationIssue

if TYPE_CHECKING:
    from topmark.toml.types import TomlTable
    from topmark.toml.types import TomlValue


class TomlSection(str, Enum):
    """Known top-level TOML sections owned by TopMark."""

    CONFIG = "config"
    HEADER = "header"
    FIELDS = "fields"
    FORMATTING = "formatting"
    WRITER = "writer"
    POLICY = "policy"
    POLICY_BY_TYPE = "policy_by_type"
    FILES = "files"


class TomlValidationMode(str, Enum):
    """Validation modes for TopMark TOML documents.

    `INPUT` validates user-authored configuration. `PROVENANCE` additionally
    allows dump-only keys emitted by commands such as
    `topmark config dump --show-origin`.
    """

    INPUT = "input"
    PROVENANCE = "provenance"


@dataclass(
    frozen=True,
    kw_only=True,
    slots=True,
)
class TomlSchemaSection:
    """Schema metadata for a named top-level TOML section.

    Attributes:
        name: Canonical top-level section name.
        allowed_keys: Keys accepted directly inside this section.
        open_keys: Whether arbitrary user-defined keys are allowed.
        dump_only_keys: Extra keys valid only in provenance/dump mode.
    """

    name: TomlSection
    allowed_keys: frozenset[str]
    open_keys: bool = False
    dump_only_keys: frozenset[str] = frozenset()

    def keys_for_mode(self, mode: TomlValidationMode) -> frozenset[str]:
        """Return the effective allowed keys for the given validation mode.

        Args:
            mode: Validation mode to evaluate.

        Returns:
            Allowed keys, including dump-only keys in provenance mode.
        """
        if mode is TomlValidationMode.PROVENANCE:
            return self.allowed_keys | self.dump_only_keys
        return self.allowed_keys


@dataclass(
    frozen=True,
    kw_only=True,
    slots=True,
)
class TomlNestedSchema:
    """Schema metadata for dynamic nested TOML subtables.

    This is used for structures such as `[policy_by_type.<filetype>]`, where
    the child table names are dynamic but the keys inside each child table are
    fixed.

    Attributes:
        parent: Parent top-level section containing dynamic child subtables.
        allowed_child_keys: Keys accepted in each child subtable.
        child_label: Human-readable label for the dynamic child name.
    """

    parent: TomlSection
    allowed_child_keys: frozenset[str]
    child_label: str


@dataclass(
    frozen=True,
    kw_only=True,
    slots=True,
)
class TomlSchema:
    """Static schema for TopMark TOML document shape validation.

    The schema owns section-level structure and emits
    [`TomlValidationIssue`][topmark.toml.validation.TomlValidationIssue]
    instances for unknown keys, wrong section shapes, and nested-policy shape
    mismatches.

    Attributes:
        sections: Mapping of known top-level sections to their schema metadata.
        policy_by_type_nested: Optional nested schema for
            `[policy_by_type.<filetype>]` subtables.
    """

    sections: dict[TomlSection, TomlSchemaSection]
    policy_by_type_nested: TomlNestedSchema | None = None

    def validate_top_level_keys(
        self,
        table: TomlTable,
        *,
        mode: TomlValidationMode,
    ) -> tuple[TomlValidationIssue, ...]:
        """Validate top-level entries and section table shapes.

        Top-level TopMark TOML entries are expected to be named sections such as
        `[config]` or `[files]`. Unknown top-level tables are therefore reported
        as unknown sections, while unknown non-table entries are reported as
        misplaced top-level keys.

        Args:
            table: Top-level TOML table to validate.
            mode: Validation mode controlling context-specific allowances.

        Returns:
            Structured validation issues for unknown top-level entries and
            invalid top-level section types.
        """
        del mode

        issues: list[TomlValidationIssue] = []
        known_names: frozenset[str] = frozenset(section.value for section in self.sections)

        for key, value in table.items():
            if key not in known_names:
                suggestion: str | None = _suggest_key(key, known_names)
                if isinstance(value, dict):
                    message: str = f"Unknown TOML section [{key}] (ignored)."
                    if suggestion is not None:
                        message = f"{message[:-1]} Did you mean [{suggestion}]?"
                else:
                    message = f"Unknown top-level key '{key}' in TopMark TOML (ignored)."
                    if suggestion is not None:
                        message = (
                            f"{message[:-1]} Did you mean section [{suggestion}] "
                            "or key under that section?"
                        )
                issues.append(
                    TomlValidationIssue(
                        code=TomlDiagnosticCode.UNKNOWN_TOP_LEVEL_SECTION,
                        level=DiagnosticLevel.WARNING,
                        message=message,
                        path=(key,),
                        section=None,
                        key=key,
                        allowed_keys=tuple(sorted(known_names)),
                        suggestion=suggestion,
                    )
                )
                continue

            if not isinstance(value, dict):
                issues.append(
                    TomlValidationIssue(
                        code=TomlDiagnosticCode.INVALID_SECTION_TYPE,
                        level=DiagnosticLevel.WARNING,
                        message=(
                            f"TOML section [{key}] must be a table; "
                            f"got {type(value).__name__} (ignored)."
                        ),
                        path=(key,),
                        section=key,
                        key=None,
                    )
                )

        return tuple(issues)

    def validate_section_keys(
        self,
        section: TomlSection,
        table: TomlTable,
        *,
        mode: TomlValidationMode,
    ) -> tuple[TomlValidationIssue, ...]:
        """Validate keys inside a known top-level TOML section.

        Args:
            section: Known section being validated.
            table: Section table contents.
            mode: Validation mode controlling dump-only-key allowances.

        Returns:
            Structured validation issues for unknown or context-disallowed keys.
        """
        schema_section: TomlSchemaSection = self.sections[section]
        if schema_section.open_keys:
            return ()

        issues: list[TomlValidationIssue] = []
        allowed_for_mode: frozenset[str] = schema_section.keys_for_mode(mode)

        for key in table:
            if key in allowed_for_mode:
                continue

            suggestion_pool: frozenset[str] = allowed_for_mode
            suggestion: str | None = _suggest_key(key, suggestion_pool)

            if mode is TomlValidationMode.INPUT and key in schema_section.dump_only_keys:
                message: str = (
                    f'Key "{key}" is only valid in [{section.value}] when '
                    "reading provenance/dump output (ignored)."
                )
                issues.append(
                    TomlValidationIssue(
                        code=TomlDiagnosticCode.DUMP_ONLY_KEY_IN_INPUT,
                        level=DiagnosticLevel.WARNING,
                        message=message,
                        path=(section.value, key),
                        section=section.value,
                        key=key,
                        allowed_keys=tuple(sorted(allowed_for_mode)),
                        suggestion=None,
                    )
                )
                continue

            message = f'Unknown key "{key}" in [{section.value}] (ignored).'
            if suggestion is not None:
                message = f'{message[:-1]} Did you mean "{suggestion}"?'
            issues.append(
                TomlValidationIssue(
                    code=TomlDiagnosticCode.UNKNOWN_SECTION_KEY,
                    level=DiagnosticLevel.WARNING,
                    message=message,
                    path=(section.value, key),
                    section=section.value,
                    key=key,
                    allowed_keys=tuple(sorted(suggestion_pool)),
                    suggestion=suggestion,
                )
            )

        return tuple(issues)

    def validate(
        self,
        table: TomlTable,
        *,
        mode: TomlValidationMode,
    ) -> tuple[TomlValidationIssue, ...]:
        """Validate a complete TopMark TOML table against the static schema.

        This performs shape validation for the full TopMark TOML fragment,
        including top-level entries, fixed-key sections, open sections, and
        nested policy-by-type child tables.

        Args:
            table: Top-level TOML table to validate.
            mode: Validation mode controlling dump-only-key allowances.

        Returns:
            Structured TOML validation issues.
        """
        issues: list[TomlValidationIssue] = []
        issues.extend(self.validate_top_level_keys(table, mode=mode))

        for section in self.sections:
            raw_section: TomlValue | None = table.get(section.value)
            if raw_section is None or not isinstance(raw_section, dict):
                continue

            issues.extend(self.validate_section_keys(section, raw_section, mode=mode))

            if section is TomlSection.POLICY_BY_TYPE and self.policy_by_type_nested is not None:
                issues.extend(
                    self._validate_nested_section(
                        raw_section,
                        nested=self.policy_by_type_nested,
                        mode=mode,
                    )
                )

        return tuple(issues)

    def _validate_nested_section(
        self,
        table: TomlTable,
        *,
        nested: TomlNestedSchema,
        mode: TomlValidationMode,
    ) -> tuple[TomlValidationIssue, ...]:
        """Validate dynamic child tables inside a nested TOML section.

        Args:
            table: Parent section table containing dynamic child entries.
            nested: Nested schema metadata.
            mode: Validation mode controlling context-specific allowances.

        Returns:
            Validation issues for malformed child tables or unknown child keys.
        """
        del mode

        issues: list[TomlValidationIssue] = []
        allowed_child_keys: frozenset[str] = nested.allowed_child_keys

        for child_name, child_value in table.items():
            path_prefix: tuple[str, ...] = (nested.parent.value, child_name)
            if not isinstance(child_value, dict):
                issues.append(
                    TomlValidationIssue(
                        code=TomlDiagnosticCode.INVALID_NESTED_SECTION_TYPE,
                        level=DiagnosticLevel.WARNING,
                        message=(
                            f"TOML section [{nested.parent.value}.{child_name}] "
                            f"must be a table; got {type(child_value).__name__} "
                            "(ignored)."
                        ),
                        path=path_prefix,
                        section=nested.parent.value,
                        key=child_name,
                    )
                )
                continue

            for key in child_value:
                if key in allowed_child_keys:
                    continue

                suggestion: str | None = _suggest_key(key, allowed_child_keys)
                message = f'Unknown key "{key}" in [{nested.parent.value}.{child_name}] (ignored).'
                if suggestion is not None:
                    message = f'{message[:-1]} Did you mean "{suggestion}"?'
                issues.append(
                    TomlValidationIssue(
                        code=TomlDiagnosticCode.UNKNOWN_SECTION_KEY,
                        level=DiagnosticLevel.WARNING,
                        message=message,
                        path=path_prefix + (key,),
                        section=f"{nested.parent.value}.{child_name}",
                        key=key,
                        allowed_keys=tuple(sorted(allowed_child_keys)),
                        suggestion=suggestion,
                    )
                )

        return tuple(issues)


def _suggest_key(
    key: str,
    allowed_keys: frozenset[str],
) -> str | None:
    """Return a close-match suggestion for a TOML key.

    Args:
        key: Unknown key entered by the user.
        allowed_keys: Candidate keys valid in the current schema context.

    Returns:
        Best suggestion when a close match exists, otherwise `None`.
    """
    matches: list[str] = get_close_matches(key, sorted(allowed_keys), n=1, cutoff=0.6)
    if matches:
        return matches[0]
    return None


_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        Toml.KEY_POLICY_HEADER_MUTATION_MODE,
        Toml.KEY_POLICY_ALLOW_HEADER_IN_EMPTIES,
        Toml.KEY_POLICY_EMPTIES_INSERT_MODE,
        Toml.KEY_POLICY_ALLOW_EMPTY_HEADER,
        Toml.KEY_POLICY_ALLOW_REFLOW,
        Toml.KEY_POLICY_ALLOW_CONTENT_PROBE,
    }
)

TOPMARK_TOML_SCHEMA: Final[TomlSchema] = TomlSchema(
    sections={
        TomlSection.CONFIG: TomlSchemaSection(
            name=TomlSection.CONFIG,
            allowed_keys=frozenset(
                {
                    Toml.KEY_ROOT,
                    Toml.KEY_STRICT_CONFIG_CHECKING,
                }
            ),
            open_keys=False,
            dump_only_keys=frozenset({Toml.KEY_CONFIG_FILES}),
        ),
        TomlSection.HEADER: TomlSchemaSection(
            name=TomlSection.HEADER,
            allowed_keys=frozenset(
                {
                    Toml.KEY_FIELDS,
                    Toml.KEY_RELATIVE_TO,
                }
            ),
        ),
        TomlSection.FIELDS: TomlSchemaSection(
            name=TomlSection.FIELDS,
            allowed_keys=frozenset(),
            open_keys=True,
        ),
        TomlSection.FORMATTING: TomlSchemaSection(
            name=TomlSection.FORMATTING,
            allowed_keys=frozenset({Toml.KEY_ALIGN_FIELDS}),
        ),
        TomlSection.WRITER: TomlSchemaSection(
            name=TomlSection.WRITER,
            allowed_keys=frozenset({Toml.KEY_STRATEGY}),
        ),
        TomlSection.POLICY: TomlSchemaSection(
            name=TomlSection.POLICY,
            allowed_keys=_POLICY_KEYS,
        ),
        TomlSection.POLICY_BY_TYPE: TomlSchemaSection(
            name=TomlSection.POLICY_BY_TYPE,
            allowed_keys=frozenset(),
            open_keys=True,
        ),
        TomlSection.FILES: TomlSchemaSection(
            name=TomlSection.FILES,
            allowed_keys=frozenset(
                {
                    Toml.KEY_INCLUDE_FILE_TYPES,
                    Toml.KEY_EXCLUDE_FILE_TYPES,
                    Toml.KEY_INCLUDE_FROM,
                    Toml.KEY_EXCLUDE_FROM,
                    Toml.KEY_INCLUDE_PATTERNS,
                    Toml.KEY_EXCLUDE_PATTERNS,
                    Toml.KEY_FILES_FROM,
                    Toml.KEY_FILES,
                }
            ),
            dump_only_keys=frozenset(
                {
                    Toml.KEY_INCLUDE_PATTERN_GROUPS,
                    Toml.KEY_EXCLUDE_PATTERN_GROUPS,
                    Toml.KEY_INCLUDE_FROM_SOURCES,
                    Toml.KEY_EXCLUDE_FROM_SOURCES,
                    Toml.KEY_FILES_FROM_SOURCES,
                }
            ),
        ),
    },
    policy_by_type_nested=TomlNestedSchema(
        parent=TomlSection.POLICY_BY_TYPE,
        allowed_child_keys=_POLICY_KEYS,
        child_label="file type",
    ),
)

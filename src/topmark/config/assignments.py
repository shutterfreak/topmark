# topmark:header:start
#
#   project      : TopMark
#   file         : assignments.py
#   file_relpath : src/topmark/config/assignments.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Ordered, source-relative rules assigning registered file types."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal
from typing import TypeAlias

from topmark.config.types import compile_gitignore_pathspec
from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.errors import InvalidRegistryIdentityError
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping
from topmark.core.typing_guards import is_str_list
from topmark.registry.filetypes import FileTypeRegistry
from topmark.utils.path import format_config_source_path

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.config.resolution.synthetic import SyntheticConfigSource
    from topmark.diagnostic.model import MutableDiagnosticLog
    from topmark.filetypes.model import FileType
    from topmark.toml.types import TomlTable


class FileTypeRuleAction(StrEnum):
    """Supported discriminants for explicit type-selection rules."""

    ASSIGN = "assign"
    INFER = "infer"


@dataclass(frozen=True, kw_only=True, slots=True)
class AssignmentRule:
    """Assign a registered type while retaining definition provenance."""

    file_type: str
    patterns: tuple[str, ...]
    base: Path
    source: Path | SyntheticConfigSource | str
    scope: Path | None
    order: int
    precedence: int = 0
    action: Literal[FileTypeRuleAction.ASSIGN] = FileTypeRuleAction.ASSIGN


@dataclass(frozen=True, kw_only=True, slots=True)
class InferenceRule:
    """Cancel earlier matching assignments and restore automatic recognition."""

    patterns: tuple[str, ...]
    base: Path
    source: Path | SyntheticConfigSource | str
    scope: Path | None
    order: int
    precedence: int = 0
    action: Literal[FileTypeRuleAction.INFER] = FileTypeRuleAction.INFER


FileTypeRule: TypeAlias = AssignmentRule | InferenceRule


def validate_assignment_pattern(
    pattern: str,
) -> None:
    """Reject empty, negative, comment, control-character, and malformed patterns.

    Compile positive gitignore-style patterns without trimming or rewriting their
    spelling. Invalid expressions become actionable configuration errors.

    Args:
        pattern: Gitignore-style positive matching pattern, preserved verbatim.

    Raises:
        ValueError: If the pattern cannot select paths unambiguously.
    """
    if (
        not pattern
        or not pattern.strip()
        or pattern.startswith(("!", "#"))
        or any(ord(char) < 32 or ord(char) == 127 for char in pattern)
    ):
        raise ValueError(f"Invalid assignment pattern: {pattern!r}")
    try:
        compile_gitignore_pathspec((pattern,))
    except (ValueError, re.error) as exc:
        raise ValueError(f"Invalid assignment pattern: {pattern!r}") from exc


def parse_file_type_rules(
    value: object,
    *,
    base: Path,
    source: Path | SyntheticConfigSource | str,
    scope: Path | None,
    diagnostics: MutableDiagnosticLog,
) -> list[FileTypeRule]:
    """Validate and normalize a structured rule list without filesystem traversal.

    Validate each variant independently and normalize registered type identities.
    Preserve valid declaration order while recording malformed entries and
    contradictory duplicates through the supplied diagnostic log.

    Args:
        value: Raw configuration entries.
        base: Definition directory for relative patterns.
        source: Stable source identity.
        scope: Applicability directory, independently of pattern base.
        diagnostics: Validation destination.

    Returns:
        Valid immutable variants in declaration order.
    """
    if not is_any_list(value):
        diagnostics.add_error("files.file_type_assignments must be a list of tables")
        return []
    rules: list[FileTypeRule] = []
    # Keep compatibility identity: serialized label, base, scope and pattern.
    # Typed origins and legacy dump strings with equal labels diagnose identically.
    seen: dict[tuple[str, Path, Path | None, str], FileTypeRule] = {}
    for order, item in enumerate(value):
        if not is_mapping(item) or not all(isinstance(key, str) for key in item):
            diagnostics.add_error(
                f"files.file_type_assignments[{order}]: entry must be a table with string keys"
            )
            continue
        entry: dict[str, object] = {
            key: value for key, value in item.items() if isinstance(key, str)
        }
        try:
            rule: FileTypeRule = _parse_rule(
                entry,
                base=base,
                source=source,
                scope=scope,
                order=order,
                diagnostics=diagnostics,
            )
        except (
            TypeError,
            ValueError,
            AmbiguousFileTypeIdentifierError,
            InvalidRegistryIdentityError,
        ) as exc:
            diagnostics.add_error(f"files.file_type_assignments[{order}]: {exc}")
            continue
        warned: set[FileTypeRule] = set()
        for pattern in rule.patterns:
            identity: tuple[str, Path, Path | None, str] = (
                format_config_source_path(rule.source),
                rule.base,
                rule.scope,
                pattern,
            )
            previous: FileTypeRule | None = seen.get(identity)
            if (
                previous is not None
                and previous not in warned
                and (
                    previous.action != rule.action
                    or isinstance(previous, AssignmentRule)
                    and isinstance(rule, AssignmentRule)
                    and previous.file_type != rule.file_type
                )
            ):
                diagnostics.add_warning(
                    "Contradictory duplicate file_type_assignments in "
                    f"{format_config_source_path(rule.source)}: "
                    f"{pattern!r}; last rule wins"
                )
                warned.add(previous)
            seen[identity] = rule
        rules.append(rule)
    return rules


def _parse_rule(
    item: Mapping[str, object],
    *,
    base: Path,
    source: Path | SyntheticConfigSource | str,
    scope: Path | None,
    order: int,
    diagnostics: MutableDiagnosticLog,
) -> FileTypeRule:
    """Validate a single mutually exclusive rule variant."""
    unknown: set[str] = set(item) - {
        "action",
        "file_type",
        "patterns",
        "base",
        "scope",
        "source",
        "order",
        "precedence",
    }
    if unknown:
        diagnostics.add_warning(f"Unknown file_type_assignments keys: {sorted(map(str, unknown))}")
    action: object = item.get("action", FileTypeRuleAction.ASSIGN)
    if action not in (FileTypeRuleAction.ASSIGN, FileTypeRuleAction.INFER):
        raise ValueError(
            f"action must be '{FileTypeRuleAction.ASSIGN}' or '{FileTypeRuleAction.INFER}'"
        )
    patterns: object | None = item.get("patterns")
    if not is_str_list(patterns) or not patterns:
        raise ValueError("patterns must be a nonempty list of nonempty patterns")
    for pattern in patterns:
        validate_assignment_pattern(pattern)
    for key in ("base", "scope", "source"):
        if key in item and not isinstance(item[key], str):
            raise TypeError(f"{key} must be a string")
    base_value: object | None = item.get("base")
    scope_value: object | None = item.get("scope")
    source_value: object | None = item.get("source")
    rule_base: Path = (base / base_value).resolve() if isinstance(base_value, str) else base
    rule_scope: Path | None = (
        ((base / scope_value).resolve() if scope_value else None)
        if isinstance(scope_value, str)
        else scope
    )
    # Dump source metadata is opaque: never guess filesystem paths or API ownership.
    rule_source: Path | SyntheticConfigSource | str = (
        source_value if isinstance(source_value, str) else source
    )
    precedence: object = item.get("precedence", 0)
    declared_order: object = item.get("order", order)
    if (
        not isinstance(precedence, int)
        or isinstance(precedence, bool)
        or not isinstance(declared_order, int)
        or isinstance(declared_order, bool)
    ):
        raise TypeError("order and precedence must be integers")
    if action == FileTypeRuleAction.INFER:
        if "file_type" in item:
            raise ValueError("action='infer' forbids file_type")
        return InferenceRule(
            patterns=tuple(patterns),
            base=rule_base,
            source=rule_source,
            scope=rule_scope,
            order=declared_order,
            precedence=precedence,
        )
    target: object | None = item.get("file_type")
    if not isinstance(target, str) or not target or target != target.strip():
        raise ValueError("assignment requires a nonempty file_type identifier")
    ft: FileType | None = FileTypeRegistry.resolve_filetype_id(target)
    if ft is None:
        raise ValueError(f"Unknown file type identifier: {target!r}")
    return AssignmentRule(
        file_type=ft.qualified_key,
        patterns=tuple(patterns),
        base=rule_base,
        source=rule_source,
        scope=rule_scope,
        order=declared_order,
        precedence=precedence,
    )


def matching_file_type_rules(
    path: Path, rules: tuple[FileTypeRule, ...]
) -> tuple[tuple[FileTypeRule, str], ...]:
    """Collect actual matching rules in precedence order without probing content.

    Evaluate patterns against the resolved target within each definition base
    and applicability scope. Preserve rule order so the final match wins.

    Args:
        path: Selected processing path or synthetic filename.
        rules: Applicable configuration rules.

    Returns:
        Matches with the last matching pattern from each rule.
    """
    target: Path = path.resolve()
    matches: list[tuple[FileTypeRule, str]] = []
    for rule in rules:
        if rule.scope is not None and not target.is_relative_to(rule.scope):
            continue
        try:
            relative: str = target.relative_to(rule.base).as_posix()
        except ValueError:
            continue
        patterns: list[str] = [
            p for p in rule.patterns if compile_gitignore_pathspec((p,)).match_file(relative)
        ]
        if patterns:
            matches.append((rule, patterns[-1]))
    return tuple(matches)


def file_type_rule_to_table(
    rule: FileTypeRule,
) -> TomlTable:
    """Serialize a rule with absolute bases for relocation-safe round trips.

    Retain definition provenance without rebasing pattern text. The resulting
    entry can be read back through the same structured variant validator.

    Args:
        rule: Rule to serialize.

    Returns:
        Configuration table retaining provenance and matching semantics.
    """
    result: TomlTable = {
        "action": rule.action.value,
        "patterns": list(rule.patterns),
        "base": rule.base.as_posix(),
        "source": format_config_source_path(rule.source),
        "order": rule.order,
        "precedence": rule.precedence,
    }
    result["scope"] = rule.scope.as_posix() if rule.scope is not None else ""
    if isinstance(rule, AssignmentRule):
        result["file_type"] = rule.file_type
    return result

# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_snapshot_generator.py
#   file_relpath : tests/api/test_api_snapshot_generator.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Focused contracts for the structured public API snapshot generator."""

# The fixtures intentionally include unannotated parameters to exercise the
# absence of annotations in public callable records.
# pyright: reportMissingParameterType=false, reportUnknownParameterType=false, reportUndefinedVariable=false

from __future__ import annotations

import json
import sys
import typing
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from types import ModuleType
from typing import Literal
from typing import TypeAlias
from typing import TypedDict
from typing import Union

import pytest
from typing_extensions import NotRequired
from typing_extensions import Required

from tools.api_snapshot import SnapshotDocument
from tools.api_snapshot import SnapshotError
from tools.api_snapshot import collect_module_snapshot
from tools.api_snapshot import collect_snapshot
from tools.api_snapshot import describe_snapshot_mismatch
from tools.api_snapshot import write_snapshot

if typing.TYPE_CHECKING:
    from pathlib import Path

BuiltinAlias: TypeAlias = list[str] | dict[str, tuple[int, ...]]
TypingAlias: TypeAlias = Union[str, None]  # noqa: UP007
LiteralAlias: TypeAlias = Literal["one", 2, True]
NestedAlias: TypeAlias = BuiltinAlias | TypingAlias
RecursiveAlias: TypeAlias = list["RecursiveAlias"]


class FixtureEnum(str, Enum):
    """Enum used to exercise stable enum defaults and member serialization."""

    ONE = "one"
    TWO = "two"
    ALIAS = "two"


def all_parameter_kinds(
    positional_only: int,
    /,
    positional_or_keyword: str = "value",
    *variadic_positional: float,
    keyword_only: bool,
    optional_keyword: None = None,
    **variadic_keyword: tuple[int, ...],
) -> list[str]:
    """Fixture containing every ``inspect.Parameter`` kind."""
    return []


def literal_defaults(
    none=None,
    flag=True,
    integer=3,
    number=1.5,
    text="text",
    values=(1, "two"),
    member=FixtureEnum.ONE,
):
    """Exercise every supported immutable default without annotations.

    The missing parameter and return annotations are part of the fixture's contract.
    """


def annotated_literal_defaults(
    none: object | None = None,
    flag: bool = True,
    integer: int = 3,
    number: float = 1.5,
    text: str = "text",
    values: tuple[object, ...] = (1, "two"),
    member: FixtureEnum = FixtureEnum.ONE,
) -> None:
    """Exercise every supported immutable default with explicit annotations."""


_UNSTABLE_DEFAULT = object()


def unstable_default(
    value: object = _UNSTABLE_DEFAULT,
) -> None:
    """Fixture containing an intentionally unsupported default."""


def unresolved_annotation(
    value: list["MissingPublicType"],  # noqa: F821, UP037
) -> None:
    """Fixture containing an unresolved public annotation."""


def unresolved_qualified_annotation(
    value: missing.PublicType,  # pyright: ignore[reportUnknownMemberType]  # noqa: F821
) -> None:
    """Fixture containing an unresolved qualified public annotation."""


def stable_factory() -> tuple[str, ...]:
    """Return a stable dataclass default value without being executed."""
    raise AssertionError("snapshotting must not execute default factories")


@dataclass(frozen=True, kw_only=True, slots=True)
class BaseDataclass:
    """Base fixture for effective inherited dataclass field order."""

    inherited: int


@dataclass(frozen=True, kw_only=True, slots=True)
class StructuredDataclass(BaseDataclass):
    """Fixture for frozen, slotted, keyword-only fields and defaults."""

    explicit_none: str | None = None
    literal: tuple[int, str] = (1, "two")
    generated: tuple[str, ...] = field(default_factory=stable_factory)


class RequiredBase(TypedDict):
    """Required TypedDict base fixture."""

    inherited: int


class MixedTypedDict(RequiredBase, total=False):
    """Fixture for inheritance, totality, and explicit key requiredness."""

    optional: str
    forced_required: Required[list[int]]
    forced_optional: NotRequired[dict[str, tuple[int, ...]]]


class ExtraItemsTypedDict(TypedDict, total=False):
    """Fixture for TopMark's authored ``__extra_items__`` convention."""

    __extra_items__: str


def _fixture_snapshot(*names: str) -> dict[str, dict[str, typing.Any]]:
    """Collect selected module-level fixtures through an explicit boundary."""
    module: ModuleType = sys.modules[__name__]
    snapshot: SnapshotDocument = collect_module_snapshot(module, exports=names)
    return typing.cast("dict[str, dict[str, typing.Any]]", snapshot["symbols"])


def _public_symbols() -> dict[str, dict[str, typing.Any]]:
    """Return public symbol records narrowed for concise contract assertions."""
    return typing.cast(
        "dict[str, dict[str, typing.Any]]",
        collect_snapshot()["symbols"],
    )


def test_callable_contract_covers_all_parameter_kinds_and_annotations() -> None:
    """Callable records retain parameter order, kinds, annotations, and defaults."""
    record: dict[str, typing.Any] = _fixture_snapshot(
        "all_parameter_kinds",
    )["all_parameter_kinds"]
    assert [parameter["kind"] for parameter in record["parameters"]] == [
        "positional_only",
        "positional_or_keyword",
        "variadic_positional",
        "keyword_only",
        "keyword_only",
        "variadic_keyword",
    ]
    assert record["parameters"][1]["default"] == {
        "kind": "literal",
        "value": "value",
    }
    assert record["parameters"][4]["default"] == {
        "kind": "literal",
        "value": None,
    }
    assert "default" not in record["parameters"][0]
    assert record["return"] == "list[str]"


def test_callable_defaults_are_json_safe_and_missing_annotations_stay_absent() -> None:
    """Literal, tuple, and enum defaults use explicit deterministic records."""
    record: dict[str, typing.Any] = _fixture_snapshot(
        "literal_defaults",
    )["literal_defaults"]
    parameters = record["parameters"]
    assert "annotation" not in parameters[0]
    assert [parameter["default"]["kind"] for parameter in parameters] == [
        "literal",
        "literal",
        "literal",
        "literal",
        "literal",
        "tuple",
        "enum",
    ]
    assert parameters[-1]["default"] == {
        "kind": "enum",
        "type": "FixtureEnum",
        "member": "ONE",
    }
    assert "return" not in record


def test_callable_annotated_defaults_are_json_safe() -> None:
    """Literal, tuple, and enum defaults use explicit deterministic records."""
    record: dict[str, typing.Any] = _fixture_snapshot(
        "annotated_literal_defaults",
    )["annotated_literal_defaults"]
    parameters = record["parameters"]
    assert [parameter["annotation"] for parameter in parameters] == [
        "object | None",
        "bool",
        "int",
        "float",
        "str",
        "tuple[object, ...]",
        "FixtureEnum",
    ]
    assert [parameter["default"]["kind"] for parameter in parameters] == [
        "literal",
        "literal",
        "literal",
        "literal",
        "literal",
        "tuple",
        "enum",
    ]
    assert parameters[-1]["default"] == {
        "kind": "enum",
        "type": "FixtureEnum",
        "member": "ONE",
    }
    assert "return" in record
    assert record["return"] == "None"


def test_unsupported_callable_default_fails_clearly() -> None:
    """Arbitrary runtime objects never fall back to unstable repr output."""
    with pytest.raises(SnapshotError, match="Unsupported default value type: object"):
        _fixture_snapshot(
            "unstable_default",
        )


def test_unresolved_public_annotation_fails_clearly() -> None:
    """Unknown simple and qualified names identify the failed annotation."""
    with pytest.raises(SnapshotError, match="Unresolved public annotation name: MissingPublicType"):
        _fixture_snapshot(
            "unresolved_annotation",
        )
    with pytest.raises(SnapshotError, match="Unresolved public annotation name: missing"):
        _fixture_snapshot(
            "unresolved_qualified_annotation",
        )


def test_dataclass_contract_includes_effective_order_flags_defaults_and_factory() -> None:
    """Dataclass records expose inherited fields and compatibility metadata."""
    record: dict[str, typing.Any] = _fixture_snapshot(
        "StructuredDataclass",
    )["StructuredDataclass"]
    assert record == {
        "kind": "dataclass",
        "frozen": True,
        "slots": True,
        "fields": [
            {
                "name": "inherited",
                "annotation": "int",
                "init": True,
                "kw_only": True,
            },
            {
                "name": "explicit_none",
                "annotation": "str | None",
                "init": True,
                "kw_only": True,
                "default": {"kind": "literal", "value": None},
            },
            {
                "name": "literal",
                "annotation": "tuple[int, str]",
                "init": True,
                "kw_only": True,
                "default": {
                    "kind": "tuple",
                    "items": [
                        {"kind": "literal", "value": 1},
                        {"kind": "literal", "value": "two"},
                    ],
                },
            },
            {
                "name": "generated",
                "annotation": "tuple[str, ...]",
                "init": True,
                "kw_only": True,
                "default_factory": f"{__name__}.stable_factory",
            },
        ],
    }


def test_typed_dict_contract_handles_inheritance_total_and_requiredness() -> None:
    """TypedDict records retain effective declaration order and key semantics."""
    record: dict[str, typing.Any] = _fixture_snapshot(
        "MixedTypedDict",
    )["MixedTypedDict"]
    assert record == {
        "kind": "typed_dict",
        "total": False,
        "fields": [
            {
                "name": "inherited",
                "annotation": "int",
                "required": True,
            },
            {
                "name": "optional",
                "annotation": "str",
                "required": False,
            },
            {
                "name": "forced_required",
                "annotation": "list[int]",
                "required": True,
            },
            {
                "name": "forced_optional",
                "annotation": "dict[str, tuple[int, ...]]",
                "required": False,
            },
        ],
    }


def test_typed_dict_extra_items_are_explicit_not_an_effective_key() -> None:
    """The existing authored extra-items convention has an explicit record."""
    record: dict[str, typing.Any] = _fixture_snapshot(
        "ExtraItemsTypedDict",
    )["ExtraItemsTypedDict"]
    assert record == {
        "kind": "typed_dict",
        "total": False,
        "fields": [],
        "extra_items": "str",
    }


def test_alias_normalization_covers_generics_unions_literals_nesting_and_cycles() -> None:
    """Assignment aliases normalize from declarations without runtime alias identity."""
    symbols: dict[str, dict[str, typing.Any]] = _fixture_snapshot(
        "BuiltinAlias",
        "LiteralAlias",
        "NestedAlias",
        "RecursiveAlias",
        "TypingAlias",
    )
    assert symbols["BuiltinAlias"]["expression"] == "list[str] | dict[str, tuple[int, ...]]"
    assert symbols["TypingAlias"]["expression"] == "str | None"
    assert symbols["LiteralAlias"]["expression"] == 'Literal["one", 2, True]'
    assert symbols["NestedAlias"]["expression"] == "BuiltinAlias | TypingAlias"
    assert symbols["RecursiveAlias"]["expression"] == "list[RecursiveAlias]"


def test_enums_exclude_alias_members_and_ordinary_classes_stay_narrow() -> None:
    """Enum declaration order is stable while ordinary classes stay opaque."""

    class Ordinary:
        pass

    module: ModuleType = sys.modules[__name__]
    vars(module)["OrdinaryFixture"] = Ordinary
    try:
        document: SnapshotDocument = collect_module_snapshot(
            module,
            exports=(
                "FixtureEnum",
                "OrdinaryFixture",
            ),
        )
        symbols: dict[str, dict[str, typing.Any]] = typing.cast(
            "dict[str, dict[str, typing.Any]]",
            document["symbols"],
        )
    finally:
        del vars(module)["OrdinaryFixture"]
    assert symbols["FixtureEnum"]["members"] == [
        {
            "name": "ONE",
            "value": {
                "kind": "literal",
                "value": "one",
            },
        },
        {
            "name": "TWO",
            "value": {
                "kind": "literal",
                "value": "two",
            },
        },
    ]
    assert symbols["OrdinaryFixture"] == {"kind": "class"}


def test_unsupported_export_and_missing_boundary_fail_clearly() -> None:
    """Unsupported public values and absent export boundaries do not degrade silently."""
    module: ModuleType = sys.modules[__name__]
    with pytest.raises(SnapshotError, match="Unsupported public export '_UNSTABLE_DEFAULT'"):
        collect_module_snapshot(module, exports=("_UNSTABLE_DEFAULT",))
    without_boundary = ModuleType("without_boundary")
    with pytest.raises(SnapshotError, match="does not define __all__"):
        collect_module_snapshot(without_boundary)


def test_serialization_is_deterministic_sorted_and_newline_terminated(tmp_path: Path) -> None:
    """The committed JSON encoding is stable and POSIX-newline terminated."""
    output: Path = tmp_path / "snapshot.json"
    write_snapshot(str(output))
    first: bytes = output.read_bytes()
    write_snapshot(str(output))
    assert output.read_bytes() == first
    assert first.endswith(b"\n")
    document = json.loads(first)
    assert list(document["symbols"]) == sorted(document["symbols"])


def test_mismatch_diagnostics_report_symbols_and_nested_leaf_paths() -> None:
    """Review diagnostics identify both symbol sets and the changed contract leaf."""
    expected: dict[str, object] = {
        "schema_version": 1,
        "symbols": {
            "RunResult": {
                "kind": "dataclass",
                "fields": [
                    {
                        "name": "files",
                        "default": None,
                    }
                ],
            },
            "Removed": {
                "kind": "class",
            },
        },
    }
    current: dict[str, object] = {
        "schema_version": 1,
        "symbols": {
            "RunResult": {
                "kind": "dataclass",
                "fields": [
                    {
                        "name": "files",
                        "default": 0,
                    }
                ],
            },
            "Added": {
                "kind": "class",
            },
        },
    }
    message: str = describe_snapshot_mismatch(expected, current)
    assert "missing_symbols=['Removed']" in message
    assert "added_symbols=['Added']" in message
    assert "changed_symbols=['RunResult']" in message
    assert "RunResult.fields[0].default" in message


def test_real_public_surface_contains_structured_contracts() -> None:
    """Representative aliases, DTOs, TypedDicts, and callables are fully described."""
    symbols: dict[str, dict[str, typing.Any]] = _public_symbols()
    assert symbols["ContentStreamEvent"] == {
        "kind": "type_alias",
        "expression": "RunStartedEvent | FileResultEvent | RunCompletedEvent",
    }
    run_result: dict[str, typing.Any] = symbols["RunResult"]
    assert run_result["kind"] == "dataclass"
    assert run_result["frozen"] is True
    assert run_result["slots"] is True
    assert [field["name"] for field in run_result["fields"]][:4] == [
        "files",
        "summary",
        "had_errors",
        "skipped",
    ]
    diagnostic: dict[str, typing.Any] = symbols["DiagnosticEntry"]
    assert diagnostic["fields"] == [
        {
            "name": "level",
            "annotation": "DiagnosticLevelLiteral",
            "required": True,
        },
        {
            "name": "message",
            "annotation": "str",
            "required": True,
        },
    ]
    check: dict[str, typing.Any] = symbols["check"]
    assert [parameter["name"] for parameter in check["parameters"]][:3] == [
        "paths",
        "apply",
        "diff",
    ]
    assert check["parameters"][1]["kind"] == "keyword_only"
    assert check["return"] == "RunResult"

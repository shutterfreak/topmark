# topmark:header:start
#
#   project      : TopMark
#   file         : api_snapshot.py
#   file_relpath : tools/api_snapshot.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end
"""Generate TopMark's structured public API compatibility snapshot.

The authoritative boundary is ``topmark.api.__all__``. The generator records a
small, explicitly versioned contract for aliases, TypedDicts, dataclasses,
enums, ordinary classes, and callables. It deliberately rejects unsupported
exports instead of serializing unstable runtime representations.
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import enum
import importlib
import inspect
import json
import math
import types
import typing
from argparse import Namespace
from pathlib import Path
from typing import TypeAlias

from topmark import api

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
SymbolRecord: TypeAlias = dict[str, JSONValue]


class SnapshotDocument(typing.TypedDict):
    """Top-level JSON snapshot schema."""

    schema_version: int
    symbols: dict[str, JSONValue]


SCHEMA_VERSION = 1

_PARAMETER_KINDS: dict[object, str] = {
    inspect.Parameter.POSITIONAL_ONLY: "positional_only",
    inspect.Parameter.POSITIONAL_OR_KEYWORD: "positional_or_keyword",
    inspect.Parameter.VAR_POSITIONAL: "variadic_positional",
    inspect.Parameter.KEYWORD_ONLY: "keyword_only",
    inspect.Parameter.VAR_KEYWORD: "variadic_keyword",
}
_GENERIC_NAMES: dict[str, str] = {
    "Dict": "dict",
    "FrozenSet": "frozenset",
    "List": "list",
    "Set": "set",
    "Tuple": "tuple",
}
_TYPING_NAMES: frozenset[str] = frozenset(vars(typing))


class SnapshotError(RuntimeError):
    """Raised when a public contract cannot be represented deterministically."""


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class _SourceInfo:
    """Parsed declaration information for one defining module."""

    tree: ast.Module
    imports: Mapping[str, str]
    known_names: frozenset[str]


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class _AliasDeclaration:
    """Source declaration for a public type alias."""

    module: types.ModuleType
    expression: ast.expr


def _source_info(module: types.ModuleType) -> _SourceInfo:
    """Return parsed declaration information for ``module``.

    Args:
        module: Module whose authored declarations should be inspected.

    Returns:
        Parsed source, import aliases, and names known to the module.

    Raises:
        SnapshotError: If source for the module cannot be inspected.
    """
    try:
        tree: ast.Module = ast.parse(inspect.getsource(module))
    except (OSError, TypeError, SyntaxError) as exc:
        raise SnapshotError(f"Cannot inspect declarations in module {module.__name__!r}") from exc

    imports: dict[str, str] = {}
    known_names: set[str] = set(vars(module))
    known_names.update(vars(builtins))
    known_names.update(_TYPING_NAMES)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name: str = alias.asname or alias.name.split(".", maxsplit=1)[0]
                imports[local_name] = alias.name
                known_names.add(local_name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                local_name = alias.asname or alias.name
                imports[local_name] = f"{node.module}.{alias.name}"
                known_names.add(local_name)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            known_names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            known_names.add(node.target.id)

    return _SourceInfo(
        tree=tree,
        imports=imports,
        known_names=frozenset(known_names),
    )


def _tail_name(node: ast.expr) -> str | None:
    """Return the final identifier in a name or attribute expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _root_name(node: ast.expr) -> str | None:
    """Return the leading identifier in a name or attribute expression."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _normalize_reference(
    node: ast.expr,
    *,
    known_names: frozenset[str],
    allow_unknown: bool,
) -> str:
    """Normalize a named annotation reference after validating its root."""
    root: str | None = _root_name(node)
    name: str | None = _tail_name(node)
    if root is None or name is None:
        raise SnapshotError("Unsupported named reference in public annotation")
    if not allow_unknown and root not in known_names:
        raise SnapshotError(f"Unresolved public annotation name: {root}")
    return _GENERIC_NAMES.get(name, name)


def _find_imported_module(
    export_module: types.ModuleType, export_name: str
) -> types.ModuleType | None:
    """Return the module from which ``export_name`` was imported, when explicit."""
    source: _SourceInfo = _source_info(export_module)
    qualified: str | None = source.imports.get(export_name)
    if qualified is None:
        return None
    module_name, _, imported_name = qualified.rpartition(".")
    if imported_name != export_name or not module_name:
        return None
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise SnapshotError(
            f"Cannot import defining module {module_name!r} for public export {export_name!r}"
        ) from exc


def _find_alias_in_module(module: types.ModuleType, name: str) -> _AliasDeclaration | None:
    """Return an authored type-alias declaration named ``name`` from ``module``."""
    for node in _source_info(module).tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and _tail_name(node.annotation) == "TypeAlias"
            and node.value is not None
        ):
            return _AliasDeclaration(module=module, expression=node.value)

        # Python 3.12+ ``type Alias = ...`` declarations are accepted when
        # encountered, although TopMark intentionally retains assignment-based
        # aliases for Python 3.10 compatibility.
        type_alias_node: typing.Any = getattr(ast, "TypeAlias", None)
        if type_alias_node is not None and isinstance(node, type_alias_node):
            alias_name: typing.Any = getattr(node, "name", None)
            if isinstance(alias_name, ast.Name) and alias_name.id == name:
                value: typing.Any = getattr(node, "value", None)
                if isinstance(value, ast.expr):
                    return _AliasDeclaration(module=module, expression=value)
    return None


def _find_alias_declaration(export_module: types.ModuleType, name: str) -> _AliasDeclaration | None:
    """Find declaration metadata proving that an export is a type alias."""
    direct: _AliasDeclaration | None = _find_alias_in_module(export_module, name)
    if direct is not None:
        return direct
    defining_module: types.ModuleType | None = _find_imported_module(export_module, name)
    if defining_module is not None:
        return _find_alias_in_module(defining_module, name)
    return None


def _normalize_ast(
    node: ast.expr,
    *,
    known_names: frozenset[str],
    allow_unknown: bool = False,
    literal_context: bool = False,
) -> str:
    """Normalize an authored annotation expression into public logical syntax."""
    if isinstance(node, ast.Name | ast.Attribute):
        return _normalize_reference(
            node,
            known_names=known_names,
            allow_unknown=allow_unknown,
        )
    if isinstance(node, ast.Constant):
        return _normalize_constant(
            node.value,
            literal_context=literal_context,
            known_names=known_names,
            allow_unknown=allow_unknown,
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _normalize_union_parts(
            [node],
            known_names=known_names,
            allow_unknown=allow_unknown,
        )
    if isinstance(node, ast.Subscript):
        base: str = _normalize_reference(
            node.value,
            known_names=known_names,
            allow_unknown=allow_unknown,
        )
        slice_nodes: list[ast.expr] = (
            list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
        )
        if base in {"Union", "Optional"}:
            if base == "Optional":
                slice_nodes.append(ast.Constant(value=None))
            return _normalize_union_parts(
                slice_nodes,
                known_names=known_names,
                allow_unknown=allow_unknown,
            )
        normalized: list[str] = [
            _normalize_ast(
                item,
                known_names=known_names,
                allow_unknown=allow_unknown,
                literal_context=base == "Literal",
            )
            for item in slice_nodes
        ]
        return f"{base}[{', '.join(normalized)}]"
    if isinstance(node, ast.Tuple):
        values: list[str] = [
            _normalize_ast(
                item,
                known_names=known_names,
                allow_unknown=allow_unknown,
                literal_context=literal_context,
            )
            for item in node.elts
        ]
        return f"tuple[{', '.join(values)}]"
    if isinstance(node, ast.List):
        values = [
            _normalize_ast(
                item,
                known_names=known_names,
                allow_unknown=allow_unknown,
            )
            for item in node.elts
        ]
        return f"[{', '.join(values)}]"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        sign = "-" if isinstance(node.op, ast.USub) else "+"
        return sign + _normalize_ast(
            node.operand,
            known_names=known_names,
            allow_unknown=allow_unknown,
            literal_context=literal_context,
        )
    raise SnapshotError(f"Unsupported public annotation syntax: {type(node).__name__}")


def _normalize_constant(
    value: object,
    *,
    literal_context: bool,
    known_names: frozenset[str] = frozenset(),
    allow_unknown: bool = False,
) -> str:
    """Normalize an annotation constant without using arbitrary ``repr``."""
    if value is None:
        return "None"
    if value is Ellipsis:
        return "..."
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        if literal_context:
            return json.dumps(value, ensure_ascii=False)
        try:
            parsed: ast.Expression = ast.parse(value, mode="eval")
        except SyntaxError as exc:
            raise SnapshotError(f"Invalid forward annotation {value!r}") from exc
        return _normalize_ast(
            parsed.body,
            known_names=known_names,
            allow_unknown=allow_unknown,
        )
    if isinstance(value, int | float):
        return str(value)
    raise SnapshotError(f"Unsupported annotation constant type: {type(value).__name__}")


def _normalize_union_parts(
    nodes: list[ast.expr],
    *,
    known_names: frozenset[str],
    allow_unknown: bool,
) -> str:
    """Normalize and flatten authored union members while preserving their order."""
    parts: list[str] = []

    def add(node: ast.expr) -> None:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            add(node.left)
            add(node.right)
            return
        part: str = _normalize_ast(
            node,
            known_names=known_names,
            allow_unknown=allow_unknown,
        )
        if part not in parts:
            parts.append(part)

    for node in nodes:
        add(node)
    return " | ".join(parts)


def _runtime_type_name(annotation: object) -> str | None:
    """Return a stable logical name for a runtime type-like object."""
    if annotation is None or annotation is type(None):
        return "None"
    if annotation is typing.Any:
        return "Any"
    if isinstance(annotation, typing.ForwardRef):
        return annotation.__forward_arg__
    if isinstance(annotation, type):
        return annotation.__name__
    name: typing.Any = getattr(annotation, "__name__", None)
    return name if isinstance(name, str) else None


def _normalize_runtime_annotation(annotation: object, *, seen: frozenset[int]) -> str:
    """Normalize a resolved runtime annotation without relying on its string form."""
    direct_name: str | None = _runtime_type_name(annotation)
    origin: typing.Any = typing.get_origin(annotation)
    args: tuple[typing.Any, ...] = typing.get_args(annotation)
    if origin is None:
        if direct_name is not None:
            return _GENERIC_NAMES.get(direct_name, direct_name)
        raise SnapshotError(f"Unsupported runtime annotation type: {type(annotation).__name__}")

    identity: int = id(annotation)
    alias_name: typing.Any = getattr(annotation, "__name__", None)
    if identity in seen:
        if isinstance(alias_name, str):
            return alias_name
        raise SnapshotError("Recursive anonymous public annotation")
    next_seen: frozenset[int] = seen | {identity}

    origin_name: str | None = _runtime_type_name(origin)
    if origin in {typing.Union, types.UnionType} or origin_name == "Union":
        parts: list[str] = []
        for arg in args:
            part: str = _normalize_runtime_annotation(arg, seen=next_seen)
            if part not in parts:
                parts.append(part)
        return " | ".join(parts)
    if origin_name == "Literal":
        values: list[str] = [
            _normalize_constant(
                value,
                literal_context=True,
                allow_unknown=True,
            )
            for value in args
        ]
        return f"Literal[{', '.join(values)}]"
    if origin_name in {"Required", "NotRequired"}:
        inner: str = _normalize_runtime_annotation(args[0], seen=next_seen)
        return f"{origin_name}[{inner}]"
    if origin_name is None:
        raise SnapshotError(f"Unsupported runtime annotation origin: {type(origin).__name__}")
    normalized_origin: str = _GENERIC_NAMES.get(origin_name, origin_name)
    normalized_args: list[str] = [
        _normalize_runtime_annotation(arg, seen=next_seen) for arg in args
    ]
    return f"{normalized_origin}[{', '.join(normalized_args)}]"


def _normalize_annotation(annotation: object, *, module: types.ModuleType) -> str:
    """Normalize an authored or resolved annotation for one defining module."""
    if isinstance(annotation, str):
        try:
            parsed: ast.Expression = ast.parse(annotation, mode="eval")
        except SyntaxError as exc:
            raise SnapshotError(f"Invalid public annotation {annotation!r}") from exc
        source: _SourceInfo = _source_info(module)
        return _normalize_ast(
            parsed.body,
            known_names=source.known_names,
        )
    return _normalize_runtime_annotation(annotation, seen=frozenset())


def _literal_default(value: object) -> SymbolRecord:
    """Return a deterministic JSON-safe representation of a supported default."""
    if isinstance(value, enum.Enum):
        return {
            "kind": "enum",
            "type": type(value).__name__,
            "member": value.name,
        }
    if value is None or isinstance(value, (bool, int, str)):
        return {"kind": "literal", "value": typing.cast("JSONScalar", value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SnapshotError("Non-finite float defaults are not supported")
        return {"kind": "literal", "value": value}
    if isinstance(value, tuple):
        items: tuple[object, ...] = typing.cast("tuple[object, ...]", value)
        return {
            "kind": "tuple",
            "items": [typing.cast("JSONValue", _literal_default(item)) for item in items],
        }
    raise SnapshotError(f"Unsupported default value type: {type(value).__name__}")


def _factory_name(factory: object) -> str:
    """Return a stable qualified identity for a dataclass default factory."""
    module_name: typing.Any = getattr(factory, "__module__", None)
    qualname: typing.Any = getattr(factory, "__qualname__", None)
    if not isinstance(module_name, str) or not isinstance(qualname, str):
        raise SnapshotError("Default factory has no stable qualified name")
    if "<lambda>" in qualname or "<locals>" in qualname:
        raise SnapshotError("Anonymous or local default factories are not stable")
    return qualname if module_name == "builtins" else f"{module_name}.{qualname}"


def _callable_record(obj: object) -> SymbolRecord:
    """Return the structured contract for a public callable."""
    try:
        signature: inspect.Signature = inspect.signature(
            typing.cast("typing.Callable[..., object]", obj)
        )
    except (TypeError, ValueError) as exc:
        raise SnapshotError("Public callable has no inspectable signature") from exc
    module: types.ModuleType | None = inspect.getmodule(obj)
    if module is None:
        raise SnapshotError("Public callable has no defining module")

    parameters: list[JSONValue] = []
    for parameter in signature.parameters.values():
        record: SymbolRecord = {
            "name": parameter.name,
            "kind": _PARAMETER_KINDS[parameter.kind],
        }
        if parameter.annotation is not inspect.Parameter.empty:
            record["annotation"] = _normalize_annotation(parameter.annotation, module=module)
        if parameter.default is not inspect.Parameter.empty:
            record["default"] = _literal_default(parameter.default)
        parameters.append(record)

    result: SymbolRecord = {
        "kind": "callable",
        "parameters": parameters,
    }
    if signature.return_annotation is not inspect.Signature.empty:
        result["return"] = _normalize_annotation(signature.return_annotation, module=module)
    return result


def _dataclass_record(cls: type[object]) -> SymbolRecord:
    """Return the effective ordered field contract for a public dataclass."""
    module: types.ModuleType | None = inspect.getmodule(cls)
    if module is None:
        raise SnapshotError(f"Dataclass {cls.__name__!r} has no defining module")
    params: typing.Any = getattr(cls, "__dataclass_params__", None)
    if params is None:
        raise SnapshotError(f"Dataclass {cls.__name__!r} has no dataclass parameters")

    field_records: list[JSONValue] = []
    dataclass_fields: tuple[dataclasses.Field[typing.Any], ...] = dataclasses.fields(
        typing.cast("typing.Any", cls)
    )
    for field in dataclass_fields:
        field_record: SymbolRecord = {
            "name": field.name,
            "annotation": _normalize_annotation(field.type, module=module),
            "init": field.init,
            "kw_only": bool(field.kw_only),
        }
        if field.default is not dataclasses.MISSING:
            field_record["default"] = _literal_default(field.default)
        elif field.default_factory is not dataclasses.MISSING:
            field_record["default_factory"] = _factory_name(field.default_factory)
        field_records.append(field_record)

    return {
        "kind": "dataclass",
        "frozen": bool(params.frozen),
        "slots": "__slots__" in vars(cls),
        "fields": field_records,
    }


def _find_class_node(module: types.ModuleType, name: str) -> ast.ClassDef:
    """Return the authored class declaration named ``name``."""
    for node in _source_info(module).tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise SnapshotError(f"Cannot find declaration for class {module.__name__}.{name}")


def _typed_dict_total(node: ast.ClassDef) -> bool:
    """Return the totality declared by one TypedDict class statement."""
    for keyword in node.keywords:
        if keyword.arg == "total":
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, bool):
                return keyword.value.value
            raise SnapshotError(f"TypedDict {node.name!r} has non-literal total=")
    return True


def _typed_dict_fields(
    module: types.ModuleType,
    node: ast.ClassDef,
    *,
    seen: frozenset[str],
) -> tuple[list[SymbolRecord], str | None]:
    """Return effective ordered fields and any PEP 728-style extra-items contract."""
    qualified_name = f"{module.__name__}.{node.name}"
    if qualified_name in seen:
        raise SnapshotError(f"Recursive TypedDict inheritance: {qualified_name}")
    next_seen: frozenset[str] = seen | {qualified_name}

    ordered: dict[str, SymbolRecord] = {}
    extra_items: str | None = None
    for base in node.bases:
        base_name: str | None = _tail_name(base)
        if base_name is None or base_name == "TypedDict":
            continue
        try:
            base_node: ast.ClassDef = _find_class_node(module, base_name)
        except SnapshotError:
            imported: str | None = _source_info(module).imports.get(base_name)
            if imported is None:
                raise
            imported_module_name, _, imported_class_name = imported.rpartition(".")
            base_module: types.ModuleType = importlib.import_module(imported_module_name)
            base_node = _find_class_node(base_module, imported_class_name)
            inherited, inherited_extra = _typed_dict_fields(
                base_module,
                base_node,
                seen=next_seen,
            )
        else:
            inherited, inherited_extra = _typed_dict_fields(
                module,
                base_node,
                seen=next_seen,
            )
        for record in inherited:
            ordered[typing.cast("str", record["name"])] = record
        if inherited_extra is not None:
            extra_items = inherited_extra

    total: bool = _typed_dict_total(node)
    source: _SourceInfo = _source_info(module)
    for statement in node.body:
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
            continue
        name: str = statement.target.id
        annotation_node: ast.expr = statement.annotation
        required: bool = total
        if isinstance(annotation_node, ast.Subscript):
            wrapper: str | None = _tail_name(annotation_node.value)
            if wrapper == "Required":
                required = True
                annotation_node = annotation_node.slice
            elif wrapper == "NotRequired":
                required = False
                annotation_node = annotation_node.slice
        annotation: str = _normalize_ast(
            annotation_node,
            known_names=source.known_names,
        )
        if name == "__extra_items__":
            extra_items = annotation
            continue
        ordered[name] = {
            "name": name,
            "annotation": annotation,
            "required": required,
        }
    return list(ordered.values()), extra_items


def _typed_dict_record(cls: type[object]) -> SymbolRecord:
    """Return a source-backed effective TypedDict contract."""
    module: types.ModuleType | None = inspect.getmodule(cls)
    if module is None:
        raise SnapshotError(f"TypedDict {cls.__name__!r} has no defining module")
    node: ast.ClassDef = _find_class_node(module, cls.__name__)
    fields, extra_items = _typed_dict_fields(module, node, seen=frozenset())
    result: SymbolRecord = {
        "kind": "typed_dict",
        "total": _typed_dict_total(node),
        "fields": typing.cast("list[JSONValue]", fields),
    }
    if extra_items is not None:
        result["extra_items"] = extra_items
    return result


def _enum_record(cls: type[enum.Enum]) -> SymbolRecord:
    """Return ordered, non-alias members of a public enum."""
    members: list[JSONValue] = []
    for name, member in cls.__members__.items():
        if member.name != name:
            continue
        members.append(
            {
                "name": name,
                "value": _literal_default(member.value),
            }
        )
    return {"kind": "enum", "members": members}


def _is_typed_dict(obj: object) -> bool:
    """Return whether ``obj`` is a TypedDict class across supported Pythons."""
    is_typeddict: typing.Callable[[object], bool] | None = typing.cast(
        "typing.Callable[[object], bool] | None",
        getattr(typing, "is_typeddict", None),
    )
    return bool(is_typeddict is not None and is_typeddict(obj))


def _symbol_record(export_module: types.ModuleType, name: str, obj: object) -> SymbolRecord:
    """Classify and normalize one exported symbol.

    Classification precedence is alias, TypedDict, dataclass, enum, ordinary
    class, callable, then unsupported value.
    """
    stable_obj: object = obj
    alias: _AliasDeclaration | None = _find_alias_declaration(export_module, name)
    if alias is not None:
        source: _SourceInfo = _source_info(alias.module)
        return {
            "kind": "type_alias",
            "expression": _normalize_ast(
                alias.expression,
                known_names=source.known_names,
            ),
        }
    if isinstance(stable_obj, type):
        if _is_typed_dict(stable_obj):
            return _typed_dict_record(stable_obj)
        if dataclasses.is_dataclass(stable_obj):
            return _dataclass_record(stable_obj)
        if issubclass(stable_obj, enum.Enum):
            return _enum_record(stable_obj)
        return {"kind": "class"}
    if callable(stable_obj):
        return _callable_record(stable_obj)
    obj_type = type(stable_obj)
    raise SnapshotError(
        f"Unsupported public export {name!r}: {obj_type.__module__}.{obj_type.__qualname__}"
    )


def collect_module_snapshot(
    module: types.ModuleType,
    *,
    exports: typing.Iterable[str] | None = None,
) -> SnapshotDocument:
    """Collect a structured compatibility snapshot for an explicit module boundary.

    Args:
        module: Module containing or re-exporting the public symbols.
        exports: Explicit export names. When omitted, ``module.__all__`` is
            required and used as the authoritative boundary.

    Returns:
        Versioned snapshot document with deterministically ordered symbol keys.

    Raises:
        SnapshotError: If the export boundary is absent or a symbol cannot be
            represented deterministically.
    """
    if exports is None:
        module_exports: typing.Any = getattr(module, "__all__", None)
        if module_exports is None:
            raise SnapshotError(f"Module {module.__name__!r} does not define __all__")
        exports = typing.cast("typing.Iterable[str]", module_exports)

    symbol_records: dict[str, JSONValue] = {}
    for name in sorted(exports):
        if not hasattr(module, name):
            raise SnapshotError(f"Public export {name!r} is absent from {module.__name__}")
        symbol_records[name] = _symbol_record(module, name, getattr(module, name))
    return {
        "schema_version": SCHEMA_VERSION,
        "symbols": symbol_records,
    }


def collect_snapshot() -> SnapshotDocument:
    """Collect the current ``topmark.api.__all__`` compatibility snapshot."""
    return collect_module_snapshot(api)


def _changed_paths(expected: JSONValue, current: JSONValue, *, path: str = "") -> list[str]:
    """Return concise leaf paths whose snapshot values differ."""
    if type(expected) is not type(current):
        return [path]
    if isinstance(expected, dict) and isinstance(current, dict):
        paths: list[str] = []
        keys: list[str] = sorted(set(expected) | set(current))
        for key in keys:
            child = f"{path}.{key}" if path else key
            if key not in expected or key not in current:
                paths.append(child)
            else:
                paths.extend(_changed_paths(expected[key], current[key], path=child))
        return paths
    if isinstance(expected, list) and isinstance(current, list):
        paths = []
        for index in range(max(len(expected), len(current))):
            child: str = f"{path}[{index}]"
            if index >= len(expected) or index >= len(current):
                paths.append(child)
            else:
                paths.extend(_changed_paths(expected[index], current[index], path=child))
        return paths
    return [] if expected == current else [path]


def describe_snapshot_mismatch(
    expected: Mapping[str, object],
    current: Mapping[str, object],
) -> str:
    """Return actionable symbol and nested-path diagnostics for unequal snapshots."""
    expected_symbols: typing.Mapping[str, JSONValue] = typing.cast(
        "Mapping[str, JSONValue]",
        expected.get("symbols", {}),
    )
    current_symbols: typing.Mapping[str, JSONValue] = typing.cast(
        "Mapping[str, JSONValue]",
        current.get("symbols", {}),
    )
    expected_names: set[str] = set(expected_symbols)
    current_names: set[str] = set(current_symbols)
    missing: list[str] = sorted(expected_names - current_names)
    added: list[str] = sorted(current_names - expected_names)
    changed: list[str] = sorted(
        name
        for name in expected_names & current_names
        if expected_symbols[name] != current_symbols[name]
    )

    lines: list[str] = [
        "Public API snapshot changed.",
        "Run 'make api-snapshot-update', review the JSON diff, and update CHANGELOG.md.",
    ]
    if expected.get("schema_version") != current.get("schema_version"):
        lines.append("changed_paths=['schema_version']")
    if missing:
        lines.append(f"missing_symbols={missing}")
    if added:
        lines.append(f"added_symbols={added}")
    if changed:
        lines.append(f"changed_symbols={changed}")
        paths: list[str] = []
        for name in changed:
            paths.extend(
                _changed_paths(
                    expected_symbols[name],
                    current_symbols[name],
                    path=name,
                )
            )
        lines.append(f"changed_paths={paths}")
    return "\n".join(lines)


def write_snapshot(path: str) -> None:
    """Write the deterministic public API snapshot JSON to ``path``.

    Args:
        path: Destination file path for the JSON snapshot.
    """
    snapshot: SnapshotDocument = collect_snapshot()
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(snapshot, file, indent=2, sort_keys=True, ensure_ascii=False)
        file.write("\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate TopMark's structured public API compatibility snapshot",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="tests/api/public_api_snapshot.json",
        help="Output path for the snapshot JSON (default: tests/api/public_api_snapshot.json)",
    )
    args: Namespace = parser.parse_args()
    write_snapshot(args.path)

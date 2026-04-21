# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_machine.py
#   file_relpath : tests/cli/machine/test_registry_machine.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output contract tests for TopMark registry CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import ClassVar

import pytest

from tests.cli.conftest import assert_SUCCESS
from tests.cli.conftest import run_cli
from tests.helpers.json import parse_json_object
from tests.helpers.ndjson import assert_ndjson_meta
from tests.helpers.ndjson import parse_ndjson_records
from tests.helpers.ndjson import record_kinds
from tests.helpers.ndjson import record_payload
from tests.helpers.registry import make_file_type
from tests.helpers.registry import patched_effective_registries
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping
from topmark.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from click.testing import Result

    from topmark.filetypes.model import FileType


class BoundRegistryProcessor(HeaderProcessor):
    """Concrete processor used for the effective bound registry entry."""

    local_key: ClassVar[str] = "bound_processor"
    namespace: ClassVar[str] = "pytest"
    description: ClassVar[str] = "Processor bound to the test file type."


class UnusedRegistryProcessor(HeaderProcessor):
    """Concrete processor used for the effective unused registry entry."""

    local_key: ClassVar[str] = "unused_processor"
    namespace: ClassVar[str] = "pytest"
    description: ClassVar[str] = "Processor left intentionally unused in registry tests."


pytestmark = pytest.mark.cli


FILETYPE_BRIEF_KEYS: frozenset[str] = frozenset(
    {"local_key", "namespace", "qualified_key", "description"}
)
FILETYPE_DETAIL_KEYS: frozenset[str] = frozenset(
    {
        "local_key",
        "namespace",
        "qualified_key",
        "description",
        "bound",
        "extensions",
        "filenames",
        "patterns",
        "skip_processing",
        "has_content_matcher",
        "has_insert_checker",
        "policy",
    }
)
FILETYPE_POLICY_KEYS: frozenset[str] = frozenset(
    {
        "supports_shebang",
        "encoding_line_regex",
        "pre_header_blank_after_block",
        "ensure_blank_after_header",
        "blank_collapse_mode",
        "blank_collapse_extra",
    }
)
PROCESSOR_BRIEF_KEYS: frozenset[str] = frozenset(
    {"local_key", "namespace", "qualified_key", "description"}
)
PROCESSOR_DETAIL_KEYS: frozenset[str] = frozenset(
    {
        "local_key",
        "namespace",
        "qualified_key",
        "description",
        "bound",
        "line_indent",
        "line_prefix",
        "line_suffix",
        "block_prefix",
        "block_suffix",
    }
)
BINDING_BRIEF_KEYS: frozenset[str] = frozenset({"file_type_key", "processor_key"})
BINDING_DETAIL_KEYS: frozenset[str] = frozenset(
    {
        "file_type_key",
        "file_type_local_key",
        "file_type_namespace",
        "processor_key",
        "processor_local_key",
        "processor_namespace",
        "file_type_description",
        "processor_description",
    }
)
REF_DETAIL_KEYS: frozenset[str] = frozenset(
    {"local_key", "namespace", "qualified_key", "description"}
)


@pytest.fixture
def registry_snapshot() -> Iterator[None]:
    """Patch a tiny deterministic effective registry for CLI contract tests."""
    bound_filetype: FileType = make_file_type(
        local_key="bound_ft",
        namespace="pytest",
        description="Bound registry test file type.",
        extensions=[".bound"],
        filenames=["BoundFile"],
        patterns=[r".*\\.bound"],
    )
    unbound_filetype: FileType = make_file_type(
        local_key="unbound_ft",
        namespace="pytest",
        description="Unbound registry test file type.",
        extensions=[".unbound"],
        filenames=["UnboundFile"],
        patterns=[r".*\\.unbound"],
    )

    processors: dict[str, HeaderProcessor] = {
        "bound_ft": BoundRegistryProcessor(
            line_prefix="# ",
            line_suffix="",
            line_indent="  ",
            block_prefix="",
            block_suffix="",
        ),
        "missing_ft": UnusedRegistryProcessor(
            line_prefix="// ",
            line_suffix="",
            line_indent=" ",
            block_prefix="/*",
            block_suffix="*/",
        ),
    }

    with patched_effective_registries(
        filetypes={
            "bound_ft": bound_filetype,
            "unbound_ft": unbound_filetype,
        },
        processors=processors,
    ):
        yield


def _run_registry_command(*, subcommand: str, fmt: str, show_details: bool) -> Result:
    """Run one registry CLI command in machine-output mode."""
    args: list[str] = [
        CliCmd.REGISTRY,
        subcommand,
        CliOpt.NO_COLOR_MODE,
        CliOpt.OUTPUT_FORMAT,
        fmt,
    ]
    if show_details:
        args.append(CliOpt.SHOW_DETAILS)

    result: Result = run_cli(args)
    assert_SUCCESS(result)
    return result


def _entry_by_qualified_key(
    entries: list[dict[str, object]],
    qualified_key: str,
) -> dict[str, object]:
    """Return one entry from a list of registry objects by qualified key."""
    for entry in entries:
        if entry.get("qualified_key") == qualified_key:
            return entry
    raise AssertionError(f"Entry with qualified_key={qualified_key!r} not found: {entries!r}")


def _binding_entry_by_file_type_key(
    entries: list[dict[str, object]],
    file_type_key: str,
) -> dict[str, object]:
    """Return one binding entry from a list by file type key."""
    for entry in entries:
        if entry.get("file_type_key") == file_type_key:
            return entry
    raise AssertionError(f"Binding with file_type_key={file_type_key!r} not found: {entries!r}")


def _string_ref_record_payload(record: dict[str, object]) -> str:
    """Return the string payload for NDJSON reference-style registry records."""
    kind_obj: object | None = record.get("kind")
    assert isinstance(kind_obj, str)
    payload_obj: object | None = record.get(kind_obj)
    assert isinstance(payload_obj, str)
    return payload_obj


def _assert_default_brief_detail_level(payload: dict[str, object]) -> None:
    """Assert that machine JSON metadata defaults to brief detail level."""
    assert_ndjson_meta(payload.get("meta"), expected_detail_level="brief")


@pytest.mark.parametrize(
    ("show_details", "expected_detail_level"),
    [(False, "brief"), (True, "long")],
)
def test_registry_filetypes_machine_json(
    registry_snapshot: None,
    show_details: bool,
    expected_detail_level: str,
) -> None:
    """`topmark registry filetypes` emits the expected JSON machine contract."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_FILETYPES,
        fmt="json",
        show_details=show_details,
    )
    payload: dict[str, object] = parse_json_object(result.output)

    assert set(payload.keys()) == {"meta", "filetypes"}
    assert_ndjson_meta(payload.get("meta"), expected_detail_level=expected_detail_level)

    filetypes_obj: object | None = payload.get("filetypes")
    assert is_any_list(filetypes_obj)
    assert len(filetypes_obj) == 2

    entries: list[dict[str, object]] = []
    for item in filetypes_obj:
        assert is_mapping(item)
        entries.append(as_object_dict(item))

    assert [entry["qualified_key"] for entry in entries] == [
        "pytest:bound_ft",
        "pytest:unbound_ft",
    ]

    bound_entry: dict[str, object] = _entry_by_qualified_key(entries, "pytest:bound_ft")
    unbound_entry: dict[str, object] = _entry_by_qualified_key(entries, "pytest:unbound_ft")

    if show_details:
        assert set(bound_entry.keys()) == set(FILETYPE_DETAIL_KEYS)
        assert set(unbound_entry.keys()) == set(FILETYPE_DETAIL_KEYS)
        assert bound_entry.get("bound") is True
        assert unbound_entry.get("bound") is False
        assert bound_entry.get("extensions") == [".bound"]
        assert unbound_entry.get("extensions") == [".unbound"]

        bound_policy_obj: object | None = bound_entry.get("policy")
        assert is_mapping(bound_policy_obj)
        assert set(as_object_dict(bound_policy_obj).keys()) == set(FILETYPE_POLICY_KEYS)
    else:
        assert set(bound_entry.keys()) == set(FILETYPE_BRIEF_KEYS)
        assert set(unbound_entry.keys()) == set(FILETYPE_BRIEF_KEYS)


@pytest.mark.parametrize(
    ("show_details", "expected_detail_level"),
    [(False, "brief"), (True, "long")],
)
def test_registry_processors_machine_json(
    registry_snapshot: None,
    show_details: bool,
    expected_detail_level: str,
) -> None:
    """`topmark registry processors` emits the expected flattened JSON contract."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_PROCESSORS,
        fmt="json",
        show_details=show_details,
    )
    payload: dict[str, object] = parse_json_object(result.output)

    assert set(payload.keys()) == {"meta", "processors"}
    assert_ndjson_meta(payload.get("meta"), expected_detail_level=expected_detail_level)

    processors_obj: object | None = payload.get("processors")
    assert is_any_list(processors_obj)
    assert len(processors_obj) == 2

    entries: list[dict[str, object]] = []
    for item in processors_obj:
        assert is_mapping(item)
        entries.append(as_object_dict(item))

    assert [entry["qualified_key"] for entry in entries] == [
        "pytest:bound_processor",
        "pytest:unused_processor",
    ]

    bound_entry: dict[str, object] = _entry_by_qualified_key(entries, "pytest:bound_processor")
    unused_entry: dict[str, object] = _entry_by_qualified_key(entries, "pytest:unused_processor")

    if show_details:
        assert set(bound_entry.keys()) == set(PROCESSOR_DETAIL_KEYS)
        assert set(unused_entry.keys()) == set(PROCESSOR_DETAIL_KEYS)
        assert bound_entry.get("bound") is True
        assert unused_entry.get("bound") is False
        assert isinstance(bound_entry.get("line_indent"), str)
        assert isinstance(bound_entry.get("line_prefix"), str)
        assert isinstance(bound_entry.get("line_suffix"), str)
        assert isinstance(bound_entry.get("block_prefix"), str)
        assert isinstance(bound_entry.get("block_suffix"), str)
        assert isinstance(unused_entry.get("line_indent"), str)
        assert isinstance(unused_entry.get("line_prefix"), str)
        assert isinstance(unused_entry.get("line_suffix"), str)
        assert isinstance(unused_entry.get("block_prefix"), str)
        assert isinstance(unused_entry.get("block_suffix"), str)
    else:
        assert set(bound_entry.keys()) == set(PROCESSOR_BRIEF_KEYS)
        assert set(unused_entry.keys()) == set(PROCESSOR_BRIEF_KEYS)


@pytest.mark.parametrize(
    ("show_details", "expected_detail_level"),
    [(False, "brief"), (True, "long")],
)
def test_registry_bindings_machine_json(
    registry_snapshot: None,
    show_details: bool,
    expected_detail_level: str,
) -> None:
    """`topmark registry bindings` emits the expected flattened JSON contract."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_BINDINGS,
        fmt="json",
        show_details=show_details,
    )
    payload: dict[str, object] = parse_json_object(result.output)

    assert set(payload.keys()) == {
        "meta",
        "bindings",
        "unbound_filetypes",
        "unused_processors",
    }
    assert_ndjson_meta(payload.get("meta"), expected_detail_level=expected_detail_level)

    bindings_obj: object | None = payload.get("bindings")
    assert is_any_list(bindings_obj)
    assert len(bindings_obj) == 1
    assert is_mapping(bindings_obj[0])
    binding_entry: dict[str, object] = as_object_dict(bindings_obj[0])

    if show_details:
        assert set(binding_entry.keys()) == set(BINDING_DETAIL_KEYS)
        assert binding_entry.get("file_type_key") == "pytest:bound_ft"
        assert binding_entry.get("processor_key") == "pytest:bound_processor"
        assert binding_entry.get("file_type_local_key") == "bound_ft"
        assert binding_entry.get("processor_local_key") == "bound_processor"
    else:
        assert set(binding_entry.keys()) == set(BINDING_BRIEF_KEYS)
        assert binding_entry.get("file_type_key") == "pytest:bound_ft"
        assert binding_entry.get("processor_key") == "pytest:bound_processor"

    unbound_obj: object | None = payload.get("unbound_filetypes")
    unused_obj: object | None = payload.get("unused_processors")
    assert is_any_list(unbound_obj)
    assert is_any_list(unused_obj)
    assert len(unbound_obj) == 1
    assert len(unused_obj) == 1

    if show_details:
        assert is_mapping(unbound_obj[0])
        assert is_mapping(unused_obj[0])
        unbound_entry: dict[str, object] = as_object_dict(unbound_obj[0])
        unused_entry: dict[str, object] = as_object_dict(unused_obj[0])
        assert set(unbound_entry.keys()) == set(REF_DETAIL_KEYS)
        assert set(unused_entry.keys()) == set(REF_DETAIL_KEYS)
        assert unbound_entry.get("qualified_key") == "pytest:unbound_ft"
        assert unused_entry.get("qualified_key") == "pytest:unused_processor"
    else:
        assert unbound_obj == ["pytest:unbound_ft"]
        assert unused_obj == ["pytest:unused_processor"]


# --- JSON smoke tests for default brief detail level ---


def test_registry_filetypes_machine_json_defaults_to_brief_detail_level(
    registry_snapshot: None,
) -> None:
    """`topmark registry filetypes` defaults machine JSON metadata to brief detail level."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_FILETYPES,
        fmt="json",
        show_details=False,
    )
    payload: dict[str, object] = parse_json_object(result.output)
    _assert_default_brief_detail_level(payload)


def test_registry_processors_machine_json_defaults_to_brief_detail_level(
    registry_snapshot: None,
) -> None:
    """`topmark registry processors` defaults machine JSON metadata to brief detail level."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_PROCESSORS,
        fmt="json",
        show_details=False,
    )
    payload: dict[str, object] = parse_json_object(result.output)
    _assert_default_brief_detail_level(payload)


def test_registry_bindings_machine_json_defaults_to_brief_detail_level(
    registry_snapshot: None,
) -> None:
    """`topmark registry bindings` defaults machine JSON metadata to brief detail level."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_BINDINGS,
        fmt="json",
        show_details=False,
    )
    payload: dict[str, object] = parse_json_object(result.output)
    _assert_default_brief_detail_level(payload)


@pytest.mark.parametrize(
    ("show_details", "expected_detail_level"),
    [(False, "brief"), (True, "long")],
)
def test_registry_filetypes_machine_ndjson(
    registry_snapshot: None,
    show_details: bool,
    expected_detail_level: str,
) -> None:
    """`topmark registry filetypes` emits one filetype NDJSON record per entry."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_FILETYPES,
        fmt="ndjson",
        show_details=show_details,
    )
    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    assert len(records) == 2
    assert {record.get("kind") for record in records} == {"filetype"}

    payloads: list[dict[str, object]] = []
    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level=expected_detail_level)
        payloads.append(record_payload(record))

    assert [payload["qualified_key"] for payload in payloads] == [
        "pytest:bound_ft",
        "pytest:unbound_ft",
    ]

    bound_payload: dict[str, object] = _entry_by_qualified_key(payloads, "pytest:bound_ft")
    if show_details:
        assert set(bound_payload.keys()) == set(FILETYPE_DETAIL_KEYS)
        assert bound_payload.get("bound") is True
    else:
        assert set(bound_payload.keys()) == set(FILETYPE_BRIEF_KEYS)


@pytest.mark.parametrize(
    ("show_details", "expected_detail_level"),
    [(False, "brief"), (True, "long")],
)
def test_registry_processors_machine_ndjson(
    registry_snapshot: None,
    show_details: bool,
    expected_detail_level: str,
) -> None:
    """`topmark registry processors` emits one processor NDJSON record per entry."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_PROCESSORS,
        fmt="ndjson",
        show_details=show_details,
    )
    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    assert len(records) == 2
    assert {record.get("kind") for record in records} == {"processor"}

    payloads: list[dict[str, object]] = []
    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level=expected_detail_level)
        payloads.append(record_payload(record))

    assert [payload["qualified_key"] for payload in payloads] == [
        "pytest:bound_processor",
        "pytest:unused_processor",
    ]

    unused_payload: dict[str, object] = _entry_by_qualified_key(payloads, "pytest:unused_processor")
    if show_details:
        assert set(unused_payload.keys()) == set(PROCESSOR_DETAIL_KEYS)
        assert unused_payload.get("bound") is False
        assert isinstance(unused_payload.get("line_indent"), str)
        assert isinstance(unused_payload.get("line_prefix"), str)
        assert isinstance(unused_payload.get("line_suffix"), str)
        assert isinstance(unused_payload.get("block_prefix"), str)
        assert isinstance(unused_payload.get("block_suffix"), str)
    else:
        assert set(unused_payload.keys()) == set(PROCESSOR_BRIEF_KEYS)


@pytest.mark.parametrize(
    ("show_details", "expected_detail_level"),
    [(False, "brief"), (True, "long")],
)
def test_registry_bindings_machine_ndjson(
    registry_snapshot: None,
    show_details: bool,
    expected_detail_level: str,
) -> None:
    """`topmark registry bindings` emits binding, unbound-filetype, and unused-processor records."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_BINDINGS,
        fmt="ndjson",
        show_details=show_details,
    )
    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    assert len(records) == 3
    assert {record.get("kind") for record in records} == {
        "binding",
        "unbound_filetype",
        "unused_processor",
    }

    binding_entries: list[dict[str, object]] = []
    unbound_refs: list[str] = []
    unused_refs: list[str] = []
    unbound_entries: list[dict[str, object]] = []
    unused_entries: list[dict[str, object]] = []

    for record in records:
        assert_ndjson_meta(record.get("meta"), expected_detail_level=expected_detail_level)
        kind_obj: object | None = record.get("kind")
        assert isinstance(kind_obj, str)

        if kind_obj == "binding":
            binding_entries.append(record_payload(record))
        elif kind_obj == "unbound_filetype":
            if show_details:
                unbound_entries.append(record_payload(record))
            else:
                unbound_refs.append(_string_ref_record_payload(record))
        elif kind_obj == "unused_processor":
            if show_details:
                unused_entries.append(record_payload(record))
            else:
                unused_refs.append(_string_ref_record_payload(record))
        else:
            raise AssertionError(f"Unexpected registry record kind: {kind_obj!r}")

    assert len(binding_entries) == 1
    binding_entry: dict[str, object] = _binding_entry_by_file_type_key(
        binding_entries,
        "pytest:bound_ft",
    )

    if show_details:
        assert len(unbound_entries) == 1
        assert len(unused_entries) == 1
        assert set(binding_entry.keys()) == set(BINDING_DETAIL_KEYS)
        assert binding_entry.get("processor_key") == "pytest:bound_processor"
        assert set(unbound_entries[0].keys()) == set(REF_DETAIL_KEYS)
        assert set(unused_entries[0].keys()) == set(REF_DETAIL_KEYS)
        assert unbound_entries[0].get("qualified_key") == "pytest:unbound_ft"
        assert unused_entries[0].get("qualified_key") == "pytest:unused_processor"
    else:
        assert set(binding_entry.keys()) == set(BINDING_BRIEF_KEYS)
        assert binding_entry.get("processor_key") == "pytest:bound_processor"
        assert unbound_refs == ["pytest:unbound_ft"]
        assert unused_refs == ["pytest:unused_processor"]


# --- NDJSON ordering tests ---


def test_registry_filetypes_machine_ndjson_emits_filetypes_in_sorted_order(
    registry_snapshot: None,
) -> None:
    """`topmark registry filetypes` emits NDJSON records in sorted qualified-key order."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_FILETYPES,
        fmt="ndjson",
        show_details=False,
    )
    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    assert record_kinds(records) == ["filetype", "filetype"]
    payloads: list[dict[str, object]] = [record_payload(record) for record in records]
    assert [payload["qualified_key"] for payload in payloads] == [
        "pytest:bound_ft",
        "pytest:unbound_ft",
    ]


def test_registry_processors_machine_ndjson_emits_processors_in_sorted_order(
    registry_snapshot: None,
) -> None:
    """`topmark registry processors` emits NDJSON records in sorted qualified-key order."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_PROCESSORS,
        fmt="ndjson",
        show_details=False,
    )
    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    assert record_kinds(records) == ["processor", "processor"]
    payloads: list[dict[str, object]] = [record_payload(record) for record in records]
    assert [payload["qualified_key"] for payload in payloads] == [
        "pytest:bound_processor",
        "pytest:unused_processor",
    ]


def test_registry_bindings_machine_ndjson_emits_bindings_then_refs_in_sorted_order(
    registry_snapshot: None,
) -> None:
    """`topmark registry bindings` emits bindings before sorted auxiliary reference records."""
    result: Result = _run_registry_command(
        subcommand=CliCmd.REGISTRY_BINDINGS,
        fmt="ndjson",
        show_details=False,
    )
    records: list[dict[str, object]] = parse_ndjson_records(result.output)

    assert record_kinds(records) == ["binding", "unbound_filetype", "unused_processor"]

    binding_payload: dict[str, object] = record_payload(records[0])
    assert binding_payload == {
        "file_type_key": "pytest:bound_ft",
        "processor_key": "pytest:bound_processor",
    }
    assert _string_ref_record_payload(records[1]) == "pytest:unbound_ft"
    assert _string_ref_record_payload(records[2]) == "pytest:unused_processor"

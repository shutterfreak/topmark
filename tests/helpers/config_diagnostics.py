# topmark:header:start
#
#   project      : TopMark
#   file         : config_diagnostics.py
#   file_relpath : tests/helpers/config_diagnostics.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared assertions for configuration diagnostics test payloads.

The helpers in this module intentionally assert on public CLI/machine-output
contracts rather than implementation details. They are used by CLI tests that
need to verify config diagnostics remain visible when validation stops command
execution before normal probe or processing results are produced.
"""

from __future__ import annotations

from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping


def assert_overlap_warning_text(
    text: str,
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """Assert text contains the include/exclude overlap warning.

    Args:
        text: Serialized diagnostic text or joined diagnostic messages.
        expected_removed_file_types: Canonical file-type identifiers expected to be
            reported as removed from the include set.
    """
    lowered: str = text.lower()
    expected_lowered: tuple[str, ...] = tuple(
        file_type.lower() for file_type in expected_removed_file_types
    )
    assert "file types specified in both include and exclude filters" in lowered
    assert "exclusion wins" in lowered
    for expected_removed_file_type in expected_lowered:
        assert expected_removed_file_type in lowered


def assert_config_diagnostics_warning_payload(
    payload: dict[str, object],
    expected_removed_file_types: tuple[str, ...],
) -> None:
    """Assert a JSON config-diagnostics envelope carries overlap diagnostics.

    Args:
        payload: Parsed JSON object emitted by a machine-output command.
        expected_removed_file_types: Canonical file-type identifiers expected to be
            reported as removed from the include set.
    """
    assert "meta" in payload

    diagnostics_obj: object | None = payload.get("config_diagnostics")
    assert diagnostics_obj is not None
    assert is_mapping(diagnostics_obj)
    diagnostics_payload: dict[str, object] = as_object_dict(diagnostics_obj)

    counts_obj: object | None = diagnostics_payload.get("diagnostic_counts")
    assert is_mapping(counts_obj)
    counts: dict[str, object] = as_object_dict(counts_obj)
    warning_count_obj: object | None = counts.get("warning")
    assert isinstance(warning_count_obj, int)
    assert warning_count_obj >= 1

    entries_obj: object | None = diagnostics_payload.get("diagnostics")
    assert is_any_list(entries_obj)
    entries: list[object] = entries_obj
    assert entries

    messages: list[str] = []
    for entry_obj in entries:
        assert is_mapping(entry_obj)
        entry: dict[str, object] = as_object_dict(entry_obj)
        level_obj: object | None = entry.get("level")
        message_obj: object | None = entry.get("message")
        assert level_obj == "warning"
        assert isinstance(message_obj, str)
        messages.append(message_obj)

    assert_overlap_warning_text(
        "\n".join(messages),
        expected_removed_file_types,
    )

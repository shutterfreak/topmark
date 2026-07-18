# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_machine_serializers.py
#   file_relpath : tests/registry/machine/test_registry_machine_serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit contract tests for registry machine serializers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import MetaPayload
from topmark.registry.machine.serializers import serialize_bindings
from topmark.registry.machine.serializers import serialize_filetypes
from topmark.registry.machine.serializers import serialize_processors

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator


def _machine_meta() -> MetaPayload:
    """Return stable test metadata payload."""
    return MetaPayload(tool="topmark", version="test", platform="test")


@pytest.mark.parametrize(
    "serializer",
    [serialize_filetypes, serialize_processors, serialize_bindings],
)
@pytest.mark.parametrize(
    "fmt",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
    ],
)
def test_registry_serializers_reject_human_output_formats(
    serializer: Callable[..., str | Iterator[str]],
    fmt: OutputFormat,
) -> None:
    """Registry serializers should not silently accept human formats."""
    with pytest.raises(ValueError) as exc_info:
        serializer(fmt=fmt, meta=_machine_meta(), show_details=False)

    assert str(exc_info.value) == f"Unsupported machine-readable output format: {fmt!r}"

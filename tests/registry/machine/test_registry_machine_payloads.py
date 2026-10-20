# topmark:header:start
#
#   project      : TopMark
#   file         : test_registry_machine_payloads.py
#   file_relpath : tests/registry/machine/test_registry_machine_payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for registry machine payload builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.registry import make_file_type
from topmark.filetypes.model import FileTypeActivation
from topmark.registry.machine.payloads import build_bindings_payload
from topmark.registry.machine.payloads import build_filetypes_payload

if TYPE_CHECKING:
    from tests.conftest import EffectiveRegistries
    from topmark.filetypes.model import FileType
    from topmark.registry.machine.schemas import BindingsPayload
    from topmark.registry.machine.schemas import FileTypeBriefEntry
    from topmark.registry.machine.schemas import FileTypeDetailEntry


def test_registry_machine_payloads_filter_by_declared_activation(
    effective_registries: EffectiveRegistries,
) -> None:
    """Activation filters select only declared types without filtering processors."""
    default: FileType = make_file_type(
        local_key="default",
        namespace="test",
        description="Default type",
    )
    opt_in: FileType = make_file_type(
        local_key="opt-in",
        namespace="test",
        description="Opt-in type",
        activation=FileTypeActivation.OPT_IN,
    )

    with effective_registries({"default": default, "opt-in": opt_in}, {}):
        filetypes: list[FileTypeBriefEntry] | list[FileTypeDetailEntry] = build_filetypes_payload(
            show_details=False,
            activation=frozenset(
                {FileTypeActivation.DEFAULT.value, FileTypeActivation.OPT_IN.value},
            ),
        )
        bindings: BindingsPayload = build_bindings_payload(
            show_details=True,
            activation=frozenset(
                {FileTypeActivation.DEFAULT.value, FileTypeActivation.OPT_IN.value},
            ),
        )

    assert filetypes == [
        {
            "local_key": "default",
            "namespace": "test",
            "qualified_key": "test:default",
            "description": "Default type",
            "activation": "default",
        },
        {
            "local_key": "opt-in",
            "namespace": "test",
            "qualified_key": "test:opt-in",
            "description": "Opt-in type",
            "activation": "opt-in",
        },
    ]
    assert bindings == {
        "bindings": [],
        "unbound_filetypes": [
            {
                "local_key": "default",
                "namespace": "test",
                "qualified_key": "test:default",
                "description": "Default type",
                "activation": "default",
            },
            {
                "local_key": "opt-in",
                "namespace": "test",
                "qualified_key": "test:opt-in",
                "description": "Opt-in type",
                "activation": "opt-in",
            },
        ],
        "unused_processors": [],
    }

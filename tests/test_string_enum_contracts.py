# topmark:header:start
#
#   project      : TopMark
#   file         : test_string_enum_contracts.py
#   file_relpath : tests/test_string_enum_contracts.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contracts for TopMark token-based enum vocabularies."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.cli.cli_types import CliWriteMode
from topmark.cli.console.color import ColorMode
from topmark.cli.io import StdinMode
from topmark.cli.options import StdinUse
from topmark.config.machine.schemas import ConfigKey
from topmark.config.machine.schemas import ConfigKind
from topmark.config.policy import BomBeforeShebangMode
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import HeaderMutationMode
from topmark.config.policy import MixedLineEndingsMode
from topmark.config.resolution.layers import ConfigLayerKind
from topmark.config.types import FileWriteStrategy
from topmark.config.types import OutputTarget
from topmark.config.validation import ValidationStage
from topmark.core.formats import OutputFormat
from topmark.core.keys import ArgKey
from topmark.core.machine.schemas import DetailLevel
from topmark.core.machine.schemas import MachineDomain
from topmark.core.machine.schemas import MachineKey
from topmark.core.machine.schemas import MachineMetaKey
from topmark.core.outcomes import Outcome
from topmark.core.presentation import StyleRole
from topmark.diagnostic.machine.schemas import DiagnosticKey
from topmark.diagnostic.machine.schemas import DiagnosticKind
from topmark.diagnostic.model import DiagnosticLevel
from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import FileTypeActivation
from topmark.filetypes.model import InsertCapability
from topmark.filetypes.policy import BlankCollapseMode
from topmark.pipeline.events import StreamEventKind
from topmark.pipeline.hints import Axis
from topmark.pipeline.hints import Cluster
from topmark.pipeline.hints import KnownCode
from topmark.pipeline.machine.schemas import PipelineKey
from topmark.pipeline.machine.schemas import PipelineRecordKind
from topmark.pipeline.outcomes import ResultActionIntent
from topmark.pipeline.pipelines import Pipeline
from topmark.pipeline.reporting import ReportScope
from topmark.pipeline.status import BaseStatus
from topmark.pipeline.views import PlanEditKind
from topmark.pipeline.views import ViewSlot
from topmark.registry.machine.schemas import RegistryKey
from topmark.registry.machine.schemas import RegistryKind
from topmark.resolution.discovery import FileSelectionReason
from topmark.resolution.discovery import FileSelectionStatus
from topmark.resolution.probe import ResolutionProbeReason
from topmark.resolution.probe import ResolutionProbeStatus
from topmark.toml.enums import FilesSerializationMode
from topmark.toml.machine.schemas import TomlKey
from topmark.toml.schema import TomlSection
from topmark.toml.schema import TomlValidationMode
from topmark.toml.validation import TomlDiagnosticCode
from topmark.version.machine.schemas import VersionKey
from topmark.version.machine.schemas import VersionKind

if TYPE_CHECKING:
    from enum import StrEnum

TOKEN_ENUM_TYPES: tuple[type[StrEnum], ...] = (
    CliWriteMode,
    ColorMode,
    StdinMode,
    StdinUse,
    ConfigKey,
    ConfigKind,
    BomBeforeShebangMode,
    EmptyInsertMode,
    HeaderMutationMode,
    MixedLineEndingsMode,
    ConfigLayerKind,
    FileWriteStrategy,
    OutputTarget,
    ValidationStage,
    OutputFormat,
    ArgKey,
    DetailLevel,
    MachineDomain,
    MachineKey,
    MachineMetaKey,
    Outcome,
    StyleRole,
    DiagnosticKey,
    DiagnosticKind,
    DiagnosticLevel,
    ContentGate,
    FileTypeActivation,
    InsertCapability,
    BlankCollapseMode,
    StreamEventKind,
    Axis,
    Cluster,
    KnownCode,
    PipelineKey,
    PipelineRecordKind,
    ResultActionIntent,
    Pipeline,
    ReportScope,
    *BaseStatus.__subclasses__(),
    PlanEditKind,
    ViewSlot,
    RegistryKey,
    RegistryKind,
    FileSelectionReason,
    FileSelectionStatus,
    ResolutionProbeReason,
    ResolutionProbeStatus,
    FilesSerializationMode,
    TomlKey,
    TomlSection,
    TomlValidationMode,
    TomlDiagnosticCode,
    VersionKey,
    VersionKind,
)


@pytest.mark.parametrize("enum_type", TOKEN_ENUM_TYPES, ids=lambda enum_type: enum_type.__name__)
def test_token_enum_members_render_their_declared_values(
    enum_type: type[StrEnum],
) -> None:
    """Token enums should never expose Python enum names in rendered output."""
    for member in enum_type:
        assert str(member) == member.value
        assert f"{member}" == member.value

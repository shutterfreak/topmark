# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_machine_serializers.py
#   file_relpath : tests/config/machine/test_config_machine_serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for config-domain machine serializers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

import topmark.config.machine.serializers as config_serializers
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.machine.payloads import build_config_diagnostics_counts_payload
from topmark.config.machine.serializers import serialize_config
from topmark.config.machine.serializers import serialize_config_check
from topmark.config.machine.serializers import serialize_config_diagnostics
from topmark.config.machine.serializers import serialize_config_diagnostics_ndjson
from topmark.config.machine.serializers import serialize_config_json
from topmark.core.formats import OutputFormat
from topmark.core.machine.schemas import MetaPayload
from topmark.toml.resolution import ResolvedTopmarkTomlSources

if TYPE_CHECKING:
    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts
    from topmark.toml.machine.schemas import TomlProvenancePayload


def _machine_meta() -> MetaPayload:
    """Return stable test metadata payload."""
    return MetaPayload(tool="topmark", version="test", platform="test")


def _empty_resolved_toml_sources() -> ResolvedTopmarkTomlSources:
    """Return an empty TOML resolution result."""
    return ResolvedTopmarkTomlSources(sources=[], writer_options=None, strict=None)


def _default_config() -> FrozenConfig:
    """Return a frozen default config."""
    return mutable_config_from_defaults().freeze()


@pytest.mark.parametrize("fmt", [OutputFormat.TEXT, OutputFormat.MARKDOWN])
def test_config_serializers_reject_human_output_formats(fmt: OutputFormat) -> None:
    """Config machine serializers should fail closed for human formats."""
    config: FrozenConfig = _default_config()
    resolved_toml: ResolvedTopmarkTomlSources = _empty_resolved_toml_sources()

    with pytest.raises(ValueError, match="Unsupported machine-readable output format"):
        serialize_config(
            meta=_machine_meta(),
            config=config,
            fmt=fmt,
            resolved_toml=resolved_toml,
        )

    with pytest.raises(ValueError, match="Unsupported machine-readable output format"):
        serialize_config_check(
            meta=_machine_meta(),
            config=config,
            resolved_toml=resolved_toml,
            strict=False,
            ok=True,
            fmt=fmt,
        )

    with pytest.raises(ValueError, match="Unsupported machine-readable output format"):
        serialize_config_diagnostics(
            meta=_machine_meta(),
            config=config,
            fmt=fmt,
        )


def test_config_diagnostics_ndjson_streams_counts_before_diagnostics() -> None:
    """Diagnostics NDJSON keeps the summary-first streaming contract."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_warning("sample warning")
    config: FrozenConfig = draft.freeze()

    records = [
        json.loads(line)
        for line in serialize_config_diagnostics_ndjson(
            meta=_machine_meta(),
            config=config,
        )
    ]

    assert [record["kind"] for record in records] == ["config_diagnostics", "diagnostic"]
    assert records[0]["config_diagnostics"]["diagnostic_counts"] == {
        "info": 0,
        "warning": 1,
        "error": 0,
    }
    assert records[1]["diagnostic"] == {
        "domain": "config",
        "level": "warning",
        "message": "sample warning",
    }


def test_config_json_requires_resolved_toml_for_layered_output() -> None:
    """Layered config JSON should fail loudly without resolved TOML sources."""
    with pytest.raises(
        ValueError,
        match="resolved_toml is required when show_config_layers=True",
    ):
        serialize_config_json(
            meta=_machine_meta(),
            config=_default_config(),
            resolved_toml=None,  # type: ignore[arg-type] - runtime guard for untyped callers.
            show_config_layers=True,
        )


def test_config_json_wraps_toml_provenance_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layered config JSON should preserve provenance failures as the cause."""

    def _raise_provenance_error(
        resolved_toml: ResolvedTopmarkTomlSources,
    ) -> TomlProvenancePayload:
        raise ValueError("broken provenance")

    monkeypatch.setattr(
        config_serializers,
        "build_toml_provenance_payload",
        _raise_provenance_error,
    )

    with pytest.raises(
        ValueError,
        match="Unable to serialize config provenance for machine-readable output",
    ) as exc_info:
        serialize_config_json(
            meta=_machine_meta(),
            config=_default_config(),
            resolved_toml=_empty_resolved_toml_sources(),
            show_config_layers=True,
        )

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "broken provenance"


def test_config_diagnostics_counts_payload_counts_flattened_logs() -> None:
    """Counts-only diagnostics should flatten staged config validation logs."""
    draft: MutableConfig = mutable_config_from_defaults()
    draft.validation_logs.merged_config.add_warning("sample warning")

    counts: MachineDiagnosticCounts = build_config_diagnostics_counts_payload(
        draft.freeze(),
    )

    assert counts.info == 0
    assert counts.warning == 1
    assert counts.error == 0

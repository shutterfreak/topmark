# topmark:header:start
#
#   project      : TopMark
#   file         : test_config_machine_payloads.py
#   file_relpath : tests/config/machine/test_config_machine_payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for config-domain machine payload builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.config.machine.payloads import build_config_check_summary_payload
from topmark.config.machine.schemas import ConfigDiagnosticsPayload
from topmark.diagnostic.machine.schemas import MachineDiagnosticCounts

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.machine.schemas import ConfigCheckSummary
    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig


@pytest.mark.pipeline
def test_config_check_summary_reuses_precomputed_diagnostic_counts(
    tmp_path: Path,
) -> None:
    """Config-check summaries should reuse precomputed diagnostic counts."""
    config_file: Path = tmp_path / "workspace" / "topmark.toml"
    draft: MutableConfig = mutable_config_from_defaults()
    draft.config_files = [config_file]
    config: FrozenConfig = draft.freeze()

    diagnostic_counts = MachineDiagnosticCounts(
        info=1,
        warning=2,
        error=3,
    )
    diagnostics_payload = ConfigDiagnosticsPayload(
        diagnostics=[],
        diagnostic_counts=diagnostic_counts,
    )

    summary: ConfigCheckSummary = build_config_check_summary_payload(
        config=config,
        cfg_diag_payload=diagnostics_payload,
        strict=True,
        ok=False,
    )

    assert summary.diagnostic_counts is diagnostic_counts
    assert summary.strict is True
    assert summary.ok is False
    assert summary.config_files == [config_file.as_posix()]


@pytest.mark.pipeline
def test_config_check_summary_builds_diagnostic_counts_when_missing() -> None:
    """Config-check summaries should compute diagnostic counts when not precomputed."""
    config: FrozenConfig = mutable_config_from_defaults().freeze()

    summary: ConfigCheckSummary = build_config_check_summary_payload(
        config=config,
        cfg_diag_payload=None,
        strict=False,
        ok=True,
    )

    assert summary.diagnostic_counts.info == 0
    assert summary.diagnostic_counts.warning == 0
    assert summary.diagnostic_counts.error == 0
    assert summary.strict is False
    assert summary.ok is True

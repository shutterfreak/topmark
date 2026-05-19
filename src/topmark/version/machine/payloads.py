# topmark:header:start
#
#   project      : TopMark
#   file         : payloads.py
#   file_relpath : src/topmark/version/machine/payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Payload builders for machine-readable output.

"Payload" here means: the *domain object* that will be inserted into a JSON
envelope (top-level JSON output) or into an NDJSON record (streaming output).

This module is intentionally:
- Click-free
- Console-free
- serialization-free (no `json.dumps`)

It provides small, stable "global" payloads used across multiple commands:

- `build_version_payload()`:
    Version information suitable for JSON envelopes and NDJSON records, including
    the effective version format when SemVer conversion is requested.

If a payload needs keys/kinds/domains, import those from
[`topmark.core.machine.schemas`][topmark.core.machine.schemas] (not from a serializer/emitter).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from topmark.version.machine.schemas import VersionKey
from topmark.version.runtime import compute_version_info

if TYPE_CHECKING:
    from topmark.version.types import VersionInfo


@dataclass(frozen=True, kw_only=True, slots=True)
class VersionPayloadResult:
    """Payload build result for machine-readable version output.

    Attributes:
        payload: Mapping with version information for machine envelopes.
        err: Conversion exception when SemVer was requested and failed; otherwise `None`.
    """

    payload: dict[str, object]
    err: Exception | None = None


def build_version_payload(
    *,
    semver: bool,
) -> VersionPayloadResult:
    """Build the version payload for machine-readable output.

    This helper never raises on SemVer conversion failure. If SemVer conversion
    was requested and fails, it falls back to the original PEP 440 version
    string and returns the conversion error alongside the payload.

    Args:
        semver: Whether to attempt SemVer conversion.

    Returns:
        A typed result containing the payload and any SemVer conversion error.
    """
    version_info: VersionInfo = compute_version_info(semver=semver)

    return VersionPayloadResult(
        payload={
            VersionKey.VERSION.value: version_info.version_text,
            VersionKey.VERSION_FORMAT.value: version_info.version_format,
        },
        err=version_info.err,
    )

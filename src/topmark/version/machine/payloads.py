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

“Payload” here means: the *domain object* that will be inserted into a JSON
envelope (top-level JSON output) or into an NDJSON record (streaming output).

This module is intentionally:
- Click-free
- Console-free
- serialization-free (no `json.dumps`)

It provides small, stable “global” payloads used across multiple commands:

- `build_version_payload()`:
    Version information suitable for JSON envelopes and NDJSON records, including
    the effective version format when SemVer conversion is requested.

If a payload needs keys/kinds/domains, import those from
[`topmark.core.machine.schemas`][topmark.core.machine.schemas] (not from a serializer/emitter).
"""

from __future__ import annotations

from topmark.core.machine.schemas import MachineKey
from topmark.utils.version import compute_version_text


def build_version_payload(
    *,
    semver: bool,
) -> tuple[dict[str, object], Exception | None]:
    """Build the version payload for machine output.

    This helper never raises on SemVer conversion failure. If SemVer conversion
    was requested and fails, it falls back to the original PEP 440 version
    string and returns the conversion error alongside the payload.

    Args:
        semver: Whether to attempt SemVer conversion.

    Returns:
        A tuple of:
            - payload: Mapping with keys:
                - `MachineKey.VERSION`: version string (SemVer if successful, else PEP 440).
                - `MachineKey.VERSION_FORMAT`: `"semver"` or `"pep440"` (effective format).
            - error: Conversion exception when SemVer was requested and failed; otherwise None.
    """
    version_text, version_format, err = compute_version_text(semver=semver)

    return {
        MachineKey.VERSION: version_text,
        MachineKey.VERSION_FORMAT: version_format,
    }, err

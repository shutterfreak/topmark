# topmark:header:start
#
#   project      : TopMark
#   file         : payloads.py
#   file_relpath : src/topmark/core/machine/payloads.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Payload builders for core machine-readable output.

“Payload” here means: the *domain object* that will be inserted into a JSON
envelope (top-level JSON output) or into an NDJSON record (streaming output).

This module is intentionally:
- Click-free
- Console-free
- serialization-free (no `json.dumps`)

It provides small, stable “global” payloads used across multiple commands:

- `build_meta_payload()`:
    A minimal `{tool, version}` mapping. This is stable for the lifetime of the
    process and is therefore cached.

If a payload needs keys/kinds/domains, import those from
[`topmark.core.machine.schemas`][topmark.core.machine.schemas] (not from a serializer/emitter).
"""

from __future__ import annotations

from functools import lru_cache

from topmark.constants import TOPMARK, TOPMARK_VERSION
from topmark.core.machine.schemas import MetaPayload


@lru_cache(maxsize=1)
def build_meta_payload() -> MetaPayload:
    """Build a small metadata payload with tool name and version.

    This payload is stable for the lifetime of the running process, so it is
    cached to avoid recreating identical dict objects across serializers.

    Returns:
        Mapping with keys `"tool"`, `"version"`, and `"platform"`.
    """
    import sys

    return MetaPayload(
        tool=TOPMARK,
        version=TOPMARK_VERSION,
        platform=sys.platform,
    )

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

from topmark.constants import TOPMARK
from topmark.constants import TOPMARK_VERSION
from topmark.core.machine.schemas import DetailedMetaPayload
from topmark.core.machine.schemas import DetailLevel
from topmark.core.machine.schemas import MetaPayload


@lru_cache(maxsize=1)
def build_meta_payload() -> MetaPayload:
    """Build the base metadata payload for machine output.

    This payload contains **process-stable information** about the running
    TopMark instance and is reused across all machine-format serializers.

    The result is cached because its content does not change during the
    lifetime of the process.

    Returns:
        A `BaseMetaPayload` mapping with keys:
        - `tool`: Tool name
        - `version`: Tool version
        - `platform`: Execution platform

    Notes:
        - This function deliberately excludes output-specific fields such as
          `detail_level`.
        - Use `with_detail_level()` to derive a full `MetaPayload` when needed.
    """
    import sys

    return MetaPayload(
        tool=TOPMARK,
        version=TOPMARK_VERSION,
        platform=sys.platform,
    )


def with_detail_level(
    meta: MetaPayload,
    *,
    show_details: bool,
) -> DetailedMetaPayload:
    """Derive a full machine metadata payload with detail-level information.

    This helper augments a cached [`BaseMetaPayload`] with a
    [`DetailLevel`] derived from CLI options.

    Args:
        meta: Base metadata payload (typically from `build_meta_payload()`).
        show_details: Whether the CLI is operating in detailed mode
            (e.g. `--long`).

    Returns:
        A `MetaPayload` including `detail_level` set to either
        `DetailLevel.BRIEF` or `DetailLevel.LONG`.

    Notes:
        - This function should be called at the **command boundary**, where
          output format decisions are known.
        - It keeps `build_meta_payload()` pure and cacheable.
    """
    return DetailedMetaPayload(
        tool=meta["tool"],
        version=meta["version"],
        platform=meta["platform"],
        detail_level=DetailLevel.LONG if show_details else DetailLevel.BRIEF,
    )

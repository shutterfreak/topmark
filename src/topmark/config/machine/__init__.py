# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/config/machine/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Machine-output support for config-related commands.

This package defines the machine-readable payload schemas and envelope builders
used by TopMark config commands (`config dump`, `config check`, `config init`,
`config defaults`).

Responsibilities:

- Define payload schemas (in `schemas.py`) for:
  - flattened config (`config`)
  - layered provenance (`config_provenance`)
  - config diagnostics (`config_diagnostics`)
  - config check summary (`config_check`)
- Build JSON envelopes and NDJSON record streams (in `envelopes.py`)
- Provide a stable contract for machine-readable output (`json`, `ndjson`)

Design notes:

- This package belongs to the *config domain*, not the TOML domain.
  Although provenance payloads may include TOML fragments, the machine
  schemas represent command outputs rather than TOML documents.
- The payload structure aligns with `topmark.core.machine.schemas`
  (MachineKey, MachineKind, MachineDomain).
- Envelope builders are pure and side-effect free; serialization is handled
  by higher-level emitters.

Future considerations:

- TOML-fragment normalization helpers may be factored into `topmark.toml.*`
  over time, but command payload schemas remain defined here.
"""

from __future__ import annotations

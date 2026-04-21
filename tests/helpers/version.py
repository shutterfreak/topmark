# topmark:header:start
#
#   project      : TopMark
#   file         : version.py
#   file_relpath : tests/helpers/version.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for version-related CLI tests."""

from __future__ import annotations

import re

SEMVER_RE: re.Pattern[str] = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z.-]+)?$"
)
"""Relaxed SemVer pattern used by version-command tests.

Accepted forms:
- `X.Y.Z`
- `X.Y.Z-<ident>(.<ident>)*`   (pre/dev like rc.N, alpha.N, dev.N)
- `X.Y.Z+<build>(.<build>)*`   (optional build metadata)
"""

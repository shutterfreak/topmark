# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_strip_skip_unsupported.py
#   file_relpath : tests/api/test_api_strip_skip_unsupported.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API test dedicated to strip(…, skip_unsupported=True) view filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api

if TYPE_CHECKING:
    from pathlib import Path


def test_strip_skip_unsupported_filters_view(repo_py_with_header_and_xyz: Path) -> None:
    """strip(..., skip_unsupported=True) should hide unsupported files from view results."""
    src = repo_py_with_header_and_xyz / "src"
    paths = [src / "with_header.py", src / "notes.xyz"]

    res_no_skip = api.strip(paths, apply=False, file_types=None, skip_unsupported=False)
    view_no_skip = {fr.path for fr in res_no_skip.files}
    assert src / "with_header.py" in view_no_skip
    # When not skipping, unsupported may still be listed in the view
    assert src / "notes.xyz" in view_no_skip

    res_skip = api.strip(paths, apply=False, file_types=None, skip_unsupported=True)
    view_skip = {fr.path for fr in res_skip.files}
    assert src / "with_header.py" in view_skip
    # Now the unsupported file should be filtered out of the results view
    assert src / "notes.xyz" not in view_skip

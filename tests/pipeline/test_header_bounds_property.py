# topmark:header:start
#
#   project      : TopMark
#   file         : test_header_bounds_property.py
#   file_relpath : tests/pipeline/test_header_bounds_property.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# pyright: strict

"""Property tests for header insert/strip idempotence across common file types.

This suite generates plausible file contents (shebangs/BOMs/junk) and asserts:
1) insert → strip → insert is idempotent, and
2) the result stays within a reasonable size bound of the original content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from hypothesis import HealthCheck, given, settings

from tests.pipeline.conftest import run_insert, run_strip
from tests.strategies_topmark import s_source_envelope_for_ext
from topmark.config import Config, MutableConfig

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from _pytest.tmpdir import TempPathFactory

    from topmark.pipeline.context import ProcessingContext

# If resolve depends on path suffix, we’ll simulate by extension choice.
EXTENSIONS: Sequence[str] = [".py", ".sh", ".js", ".ts", ".cpp", ".h", ".xml", ".html"]


# Mark the entire test module
pytestmark: pytest.MarkDecorator = pytest.mark.hypothesis_slow


@settings(
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,  # property tests can be a bit heavier
    max_examples=30,
)
@given(sample=s_source_envelope_for_ext(EXTENSIONS))
def test_insert_strip_idempotent_roundtrip(
    tmp_path_factory: TempPathFactory,
    sample: tuple[str, object, str, str],
) -> None:
    r"""Insert→strip→insert is idempotent and local.

    This property test generates files with various content, styles, and line endings,
    then applies an insert-strip-insert sequence to verify that the final output matches
    the first insertion. It also checks that the size of the modified content remains
    within reasonable bounds of the original content size.

    Args:
        tmp_path_factory (TempPathFactory): Factory to create temporary directories for testing.
        sample (tuple[str, object, str, str]): A tuple containing:
            - The original file content as a string.
            - The style object (not used in this test).
            - The line ending style as a string (e.g., "\n", "\r\n").
            - The file extension used for the temporary file (e.g., ``.py``).
    """
    content: str
    _style: object
    _le: str
    ext: str
    content, _style, _le, ext = sample

    # Write the generated content to a temporary file with the chosen extension
    base_dir: Path = tmp_path_factory.mktemp("prop-cases")
    f: Path = base_dir / f"{uuid4().hex}{ext}"
    # f.write_text(content, encoding="utf-8")
    # Preserve line endings
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    # Use a default frozen config
    cfg: Config = MutableConfig.from_defaults().freeze()

    # 1) Insert/update a header
    ctx1: ProcessingContext = run_insert(f, cfg)
    # If insertion is refused (e.g., empty XML, prolog-only, or guarded by checker),
    # idempotence doesn't apply for this sample.
    if ctx1.updated_file_lines is None:
        pytest.skip("Pre-insert advisory refused insertion for this sample.")
    updated1: str = "".join(ctx1.updated_file_lines)

    # f.write_text(updated1, encoding="utf-8")
    # Preserve line endings
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(updated1)

    # 2) Strip the header back out
    ctx_strip: ProcessingContext = run_strip(f, cfg)
    if ctx_strip.updated_file_lines is None:
        # This happens if there wasn't a header to strip (should be rare here),
        # but keep the property total by skipping such samples.
        pytest.skip("No header to strip after first insertion.")
    stripped: str = "".join(ctx_strip.updated_file_lines)
    # f.write_text(stripped, encoding="utf-8")
    # Preserve line endings
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(stripped)

    # 3) Insert again
    ctx2: ProcessingContext = run_insert(f, cfg)
    updated2: str = "".join(ctx2.updated_file_lines or [])

    # Idempotence: applying insert→strip→insert yields stable output
    assert updated1 == updated2

    # Locality: body content size should remain in a reasonable bound vs. original
    assert abs(len(updated1) - len(content)) < max(4096, len(content) // 2)

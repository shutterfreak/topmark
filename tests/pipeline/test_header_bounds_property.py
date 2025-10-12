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
from hypothesis import HealthCheck, assume, given, settings

from tests.pipeline.conftest import materialize_updated_lines, run_insert, run_strip
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

    # Use a config that allows inserting headers into empty files (for property tests)
    mcfg: MutableConfig = MutableConfig.from_defaults()
    mcfg.policy.allow_header_in_empty_files = True
    cfg: Config = mcfg.freeze()

    # 1) Insert/update a header
    ctx1: ProcessingContext = run_insert(f, cfg)
    # Require that the first pass actually performed an insert/replace; otherwise
    # this sample is out-of-scope for the roundtrip property.
    assume(ctx1.updated is not None and ctx1.updated.lines is not None)
    updated1: str = "".join(materialize_updated_lines(ctx1))
    # Ensure that the header was actually inserted in the first pass.
    assume("topmark:header:start" in updated1)

    # f.write_text(updated1, encoding="utf-8")
    # Preserve line endings
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(updated1)

    # 2) Strip the header back out
    ctx_strip: ProcessingContext = run_strip(f, cfg)
    assume(ctx_strip.updated is not None and ctx_strip.updated.lines is not None)
    # Use helper to materialize a concrete list[str] for typing clarity.
    stripped: str = "".join(materialize_updated_lines(ctx_strip))

    # Ensure the header markers are actually gone in the updated image.
    assume("topmark:header:start" not in stripped)

    # f.write_text(stripped, encoding="utf-8")
    # Preserve line endings
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(stripped)

    # 3) Insert again
    ctx2: ProcessingContext = run_insert(f, cfg)
    updated2: str = "".join(materialize_updated_lines(ctx2))

    # Idempotence: applying insert→strip→insert yields stable output
    assert updated1 == updated2

    # Locality: body content size should remain in a reasonable bound vs. original
    assert abs(len(updated1) - len(content)) < max(4096, len(content) // 2)

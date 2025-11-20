# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.pyi
#   file_relpath : typings/mkdocs_gen_files/__init__.pyi
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Local stub for mkdocs-gen-files (validation of script in docs/)."""

from collections.abc import Iterable
from typing import TextIO

def open(path: str, mode: str = "w") -> TextIO: ...
def set_edit_path(doc_path: str, src_path: str) -> None: ...
def files() -> Iterable[str]: ...  # optional; include if you call it

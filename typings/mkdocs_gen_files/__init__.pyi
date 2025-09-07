"""Local stub for mkdocs-gen-files (validation of script in docs/)."""

from typing import Iterable, TextIO

def open(path: str, mode: str = "w") -> TextIO: ...
def set_edit_path(doc_path: str, src_path: str) -> None: ...
def files() -> Iterable[str]: ...  # optional; include if you call it

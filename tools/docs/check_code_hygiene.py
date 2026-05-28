# topmark:header:start
#
#   project      : TopMark
#   file         : check_code_hygiene.py
#   file_relpath : tools/docs/check_code_hygiene.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Check prose hygiene in Python source files."""

from __future__ import annotations

import argparse
import io
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Final

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Sequence

DEFAULT_ROOTS: Final[tuple[Path, ...]] = (
    Path("src/topmark"),
    Path("tests"),
    Path("tools"),
)

EXCLUDED_DIR_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".nox",
        ".pytest_cache",
        ".tox",  # defensive exclusion for legacy/local environments
        ".uv-release-test-env",
        ".venv",
        ".venv-docs",
        "__pycache__",
        "build",
        "dist",
        "site",
    }
)

SMART_PUNCTUATION_REPLACEMENTS: dict[str, str] = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2026": "...",
}

CHECKED_TOKEN_TYPES: Final[frozenset[int]] = frozenset({tokenize.COMMENT, tokenize.STRING})


@dataclass(frozen=True)
class Diagnostic:
    """Single code-hygiene diagnostic."""

    path: Path
    line: int
    character: str
    replacement: str

    def format(self) -> str:
        """Return a grep-like diagnostic line."""
        return f"{self.path}:{self.line}: replace {self.character!r} with {self.replacement!r}"


def path_is_excluded(path: Path) -> bool:
    """Return whether a path is under an excluded directory."""
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def iter_python_files(roots: Iterable[Path]) -> Iterator[Path]:
    """Yield Python files below the configured roots."""
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix == ".py" and not path_is_excluded(root):
                yield root
            continue
        for path in root.rglob("*.py"):
            if not path_is_excluded(path):
                yield path


def iter_smart_punctuation(text: str) -> Iterator[tuple[str, str]]:
    """Yield smart-punctuation characters and their replacements."""
    for character in text:
        replacement = SMART_PUNCTUATION_REPLACEMENTS.get(character)
        if replacement is not None:
            yield character, replacement


def check_python_file(path: Path) -> list[Diagnostic]:
    """Check one Python file for smart punctuation in comments and strings."""
    text = path.read_text(encoding="utf-8")
    diagnostics: list[Diagnostic] = []
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)

    for token in tokens:
        if token.type not in CHECKED_TOKEN_TYPES:
            continue
        for character, replacement in iter_smart_punctuation(token.string):
            diagnostics.append(
                Diagnostic(
                    path=path,
                    line=token.start[0],
                    character=character,
                    replacement=replacement,
                )
            )

    return diagnostics


def check_code_hygiene(roots: Iterable[Path]) -> list[Diagnostic]:
    """Check Python source files below the given roots."""
    diagnostics: list[Diagnostic] = []
    for path in iter_python_files(roots):
        diagnostics.extend(check_python_file(path))
    return diagnostics


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Python files or directories to check. Defaults to src/topmark, tests, and tools.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the code-hygiene checker."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    roots: tuple[Path, ...] = tuple(args.paths) if args.paths else DEFAULT_ROOTS
    diagnostics = check_code_hygiene(roots)

    for diagnostic in diagnostics:
        print(diagnostic.format())

    return 1 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())

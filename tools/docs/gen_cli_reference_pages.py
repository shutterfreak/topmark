# topmark:header:start
#
#   project      : TopMark
#   file         : gen_cli_reference_pages.py
#   file_relpath : tools/docs/gen_cli_reference_pages.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Generate TopMark-specific CLI reference pages and audit API docstrings.

Zensical's native ``api-autonav`` generates all Python-module pages and navigation. This script
retains only TopMark-specific generated content:

* CLI-derived reference pages under `usage/` and `configuration/`.

In debug/strict modes it also scans *module docstrings* in `src/` for unlinked backticked
`topmark.*` symbol references and reports actionable `src/...` locations.

The production staging command imports this module and explicitly supplies a filesystem writer.
"""

# pyright: reportMissingModuleSource=false

from __future__ import annotations

import ast
import importlib
import logging
import pkgutil
import subprocess
import sys
from pathlib import Path
from pathlib import PureWindowsPath
from typing import TYPE_CHECKING
from typing import Protocol
from typing import cast

import topmark

# Use an absolute module reference from the documentation preparation command:
from tools.docs.docs_utils import NONLINKED_SYMBOLS
from tools.docs.docs_utils import context_lines
from tools.docs.docs_utils import env_flag
from tools.docs.docs_utils import find_unlinked_backticked_symbols_with_locations
from tools.docs.docs_utils import fix_backticked_reference_links
from tools.docs.docs_utils import format_inline_symbols
from tools.docs.docs_utils import format_line_numbers
from tools.docs.docs_utils import format_repo_path
from tools.docs.docs_utils import strip_repo_prefix

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Final
    from typing import TextIO

logger: logging.Logger = logging.getLogger(__name__)


class DocsWriter(Protocol):
    """Write generated documentation using a virtual or filesystem-backed destination."""

    def open(
        self,
        path: str,
        mode: str = "w",
    ) -> TextIO:
        """Open a documentation file relative to the configured documentation root."""
        ...


class FilesystemDocsWriter:
    """Write generated pages into an explicit disposable documentation directory.

    Zensical does not run ``mkdocs-gen-files``, so this writer materializes the pages in the
    disposable production staging tree instead.

    Args:
        docs_dir: Existing staging documentation directory that receives generated pages.
    """

    def __init__(
        self,
        docs_dir: Path,
    ) -> None:
        self.docs_dir: Path = docs_dir.resolve()

    def open(
        self,
        path: str,
        mode: str = "w",
    ) -> TextIO:
        """Open a staging file while rejecting paths outside the staging tree.

        Args:
            path: POSIX documentation path relative to ``docs_dir``.
            mode: File mode, passed to :func:`open`.

        Returns:
            Open text file handle for the generated page.

        Raises:
            ValueError: If ``path`` is absolute or attempts to escape ``docs_dir``.
        """
        relative_path: Path = Path(path)
        windows_path: PureWindowsPath = PureWindowsPath(path)
        if (
            relative_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or windows_path.root
            or ".." in relative_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError(f"Generated documentation path must be relative: {path!r}")

        destination: Path = self.docs_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        return cast("TextIO", destination.open(mode, encoding="utf-8"))


# --- Constants for Directory Structure ---
ROOT_PKG: Final = "topmark"
API_INTERNALS_DIR: Final = "api/internals"

# --- Configuration via Environment Variables ---

# Generate debug logging
# Also enables extra debug checks during the docs build.
TOPMARK_DOCS_DEBUG: bool = env_flag("TOPMARK_DOCS_DEBUG", default=False)
if TOPMARK_DOCS_DEBUG is True:
    logger.info("Debug logging enabled (TOPMARK_DOCS_DEBUG resolves to True)")

# Fail the docs build when unlinked backticked symbol references are found in docstrings.
# Useful with the strict Zensical build to enforce reference hygiene.
TOPMARK_DOCS_STRICT_REFS: bool = env_flag("TOPMARK_DOCS_STRICT_REFS", default=False)
if TOPMARK_DOCS_STRICT_REFS is True:
    logger.info(
        "Strict symbol reference checking enabled (TOPMARK_DOCS_STRICT_REFS resolves to True)"
    )

if TOPMARK_DOCS_DEBUG and NONLINKED_SYMBOLS:
    logger.info(
        "Non-linked symbol whitelist enabled (%d): %s",
        len(NONLINKED_SYMBOLS),
        ", ".join(sorted(NONLINKED_SYMBOLS)),
    )


# Track issues found in docstrings to report them at the end of the build.
# Each entry: (src_path, {symbol -> set(line_numbers)})
_DOCSTRING_REF_FINDINGS: list[tuple[str, dict[str, set[int]]]] = []


def _run_topmark_markdown(*args: str) -> str:
    """Run the TopMark CLI and capture its Markdown output.

    We use `python -m topmark` to ensure we use the version of the code currently
    being documented, rather than a globally installed version.

    Args:
        *args: Command line arguments to pass to topmark.

    Returns:
        The generated Markdown string from stdout.

    Raises:
        RuntimeError: If the CLI command fails.
    """
    cmd: list[str] = [sys.executable, "-m", ROOT_PKG, *args]
    proc: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        # Fail hard so 'strict: true' builds don't silently publish stale docs.
        joined: str = " ".join(cmd)
        raise RuntimeError(
            f"Command failed: {joined}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        )
    return proc.stdout


def generate_cli_reference_pages(docs_writer: DocsWriter) -> None:
    """Generate documentation for TopMark CLI features.

    This invokes the app's own 'filetypes' and 'processors' commands which
    have built-in Markdown exporters.
    """
    filetypes_md: str = _run_topmark_markdown(
        "registry",
        "filetypes",
        "--long",
        "--output-format",
        "markdown",
    )
    processors_md: str = _run_topmark_markdown(
        "registry",
        "processors",
        "--long",
        "--output-format",
        "markdown",
    )
    bindings_md: str = _run_topmark_markdown(
        "registry",
        "bindings",
        "--long",
        "--output-format",
        "markdown",
    )
    example_config_md: str = _run_topmark_markdown(
        "config",
        "init",
        "--output-format",
        "markdown",
    )
    config_defaults_md: str = _run_topmark_markdown(
        "config",
        "defaults",
        "--output-format",
        "markdown",
    )

    def _write_generated_page(dest: str, title: str, body: str) -> None:
        """Write a standalone generated Markdown page under `docs/`.

        Args:
            dest: Docs-relative output path (e.g. `usage/generated/filetypes.md`).
            title: Page title to render at the top.
            body: Pre-rendered Markdown emitted by `topmark ... --output-format markdown`.
        """
        # Open a materialized file in the Zensical staging environment.
        with docs_writer.open(dest, "w") as f:
            f.write(f"# {title}\n\n")
            f.write("<!-- This page is generated. Do not edit manually. -->\n\n")
            # `body` is already Markdown; write verbatim.
            f.write(body)

    _write_generated_page(
        "usage/generated/filetypes.md",
        "Supported file types (generated)",
        filetypes_md,
    )
    _write_generated_page(
        "usage/generated/processors.md",
        "Registered processors (generated)",
        processors_md,
    )
    _write_generated_page(
        "usage/generated/bindings.md",
        "Registered bindings (generated)",
        bindings_md,
    )
    _write_generated_page(
        "configuration/generated/example-config.md",
        "Example TOML configuration (generated)",
        example_config_md,
    )
    _write_generated_page(
        "configuration/generated/config-defaults.md",
        "Default TOML configuration (generated)",
        config_defaults_md,
    )


def _exists_in_src(modname: str) -> bool:
    """Check if a module corresponds to a physical file in the src directory.

    Args:
        modname: The dotted module path.

    Returns:
        True if a .py file or a directory with __init__.py exists.
    """
    rel = Path(*modname.split("."))
    return (Path("src") / f"{rel}.py").exists() or (Path("src") / rel / "__init__.py").exists()


def _is_package(modname: str) -> bool:
    """Check if the module is a Python package (a directory containing __init__.py).

    Args:
        modname: The dotted module path.

    Returns:
        True if directory with __init__.py exists.
    """
    rel = Path(*modname.split("."))
    pkg_dir: Path = Path("src") / rel
    return pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists()


def _api_autonav_doc_path(modname: str) -> str:
    """Return the ``api-autonav`` documentation path for a module or package.

    Args:
        modname: Dotted module or package name.

    Returns:
        Docs-relative Markdown path generated by ``api-autonav``.
    """
    package_path: str = modname.replace(".", "/")
    if _is_package(modname):
        return f"{API_INTERNALS_DIR}/{package_path}/index.md"
    return f"{API_INTERNALS_DIR}/{package_path}.md"


def _scan_module_docstring(modname: str, src_path: str, current_doc: str) -> None:
    """Audit the module docstring for unlinked symbol references.

    This function parses the Python source to find the docstring, then checks
    if backticked text (e.g. `topmark.some_func`) has a matching API anchor.

    Args:
        modname: Name of the module.
        src_path: Path to the physical source file.
        current_doc: The virtual documentation path where this is being rendered.
    """
    try:
        py_text: str = Path(src_path).read_text(encoding="utf-8")
    except OSError:
        return

    try:
        tree: ast.Module = ast.parse(py_text, filename=src_path)
    except SyntaxError:
        return

    # Identify module docstring node (first statement).
    doc_node: ast.Expr | None = None
    if tree.body and isinstance(tree.body[0], ast.Expr):
        v: ast.expr = tree.body[0].value
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            doc_node = tree.body[0]

    if doc_node is None:
        return

    doc: str | None = ast.get_docstring(tree, clean=False)
    if not doc:
        return

    # Find symbols that aren't properly linked.
    doc_fixed: str = fix_backticked_reference_links(doc)

    findings: dict[str, set[int]] = find_unlinked_backticked_symbols_with_locations(doc_fixed)
    if not findings:
        return

    # Approximate docstring starting line: ast gives the line where the string literal starts.
    base_line: int = getattr(doc_node, "lineno", 1)

    # Convert docstring-relative line numbers to file line numbers.
    findings_abs: dict[str, set[int]] = {
        sym: {base_line + (ln - 1) for ln in rel_lines} for sym, rel_lines in findings.items()
    }

    # Aggregate for strict-mode failure.
    _DOCSTRING_REF_FINDINGS.append((src_path, findings_abs))

    # If we're neither debugging nor enforcing strict refs, stay silent.
    if TOPMARK_DOCS_DEBUG is not True and TOPMARK_DOCS_STRICT_REFS is not True:
        return

    symbols_sorted: list[str] = sorted(findings_abs)
    inline_syms: str = format_inline_symbols(
        symbols_sorted,
        debug=TOPMARK_DOCS_DEBUG is True,
    )

    # Match hooks.py severity:
    # - In debug mode, emit a DEBUG summary line.
    # - In strict mode, also emit an ERROR summary line.
    # - Per-symbol details are always WARNING (actionable even without debug).
    rel_src: str = strip_repo_prefix(src_path, "src")

    if TOPMARK_DOCS_DEBUG is True:
        logger.debug(
            "src/%s - Found %d unlinked symbol(s): %s",
            rel_src,
            len(symbols_sorted),
            inline_syms,
        )

    if TOPMARK_DOCS_STRICT_REFS is True:
        logger.error(
            "src/%s - Unlinked TopMark symbol(s) in docstring: %s",
            rel_src,
            inline_syms,
        )

    if TOPMARK_DOCS_DEBUG is True:
        for line in context_lines(
            edit_url=None,
            rendered_on=current_doc,
            source_file=format_repo_path(rel_src, root="src"),
        ):
            logger.info("src/%s - %s", rel_src, line)

    for seq, sym in enumerate(symbols_sorted, start=1):
        logger.warning(
            "src/%s - [%d] (%s) %s - Fix: [`%s`][%s]",
            rel_src,
            seq,
            format_line_numbers(findings_abs[sym]),
            sym,
            sym,
            sym,
        )


def _should_skip(modname: str) -> bool:
    """Determine if a module should be excluded from API documentation.

    Args:
        modname: Dotted module name.

    Returns:
        True if any module-path segment is private.
    """
    # Skip dunder/private segments anywhere in the dotted path.
    return any(part.startswith("_") for part in modname.split("."))


def _walk() -> Iterable[str]:
    """Iterate through all importable modules in the topmark package."""
    if _exists_in_src(ROOT_PKG):
        yield ROOT_PKG
    for m in pkgutil.walk_packages(topmark.__path__, topmark.__name__ + "."):
        if _should_skip(m.name):
            continue
        if not _exists_in_src(m.name):
            continue
        yield m.name


skipped_import: list[tuple[str, str]] = []  # (module, reason)


def validate_docstring_links() -> None:
    """Validate reference links in importable TopMark module docstrings.

    The audit runs independently from Python-module page generation, which belongs to
    ``api-autonav``. In strict mode it collects all findings before aborting the build so that
    contributors can repair them in one pass.

    Raises:
        RuntimeError: When strict reference hygiene is enabled and unlinked backticked symbols are
            found.
    """
    _DOCSTRING_REF_FINDINGS.clear()
    skipped_import.clear()

    # Audit every importable public and internal module. Page generation belongs to api-autonav.
    for name in sorted(set(_walk())):
        try:
            importlib.import_module(name)
        except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover - generation-time guard
            skipped_import.append((name, f"import failed: {type(e).__name__}: {e}"))
            continue

        current_doc: str = _api_autonav_doc_path(name)
        src_rel: str = name.replace(".", "/")
        src_path: str = f"src/{src_rel}/__init__.py" if _is_package(name) else f"src/{src_rel}.py"
        _scan_module_docstring(name, src_path, current_doc)

    # Fail the build after collecting every finding.
    if TOPMARK_DOCS_STRICT_REFS is True and _DOCSTRING_REF_FINDINGS:
        total: int = sum(len(d) for (_src, d) in _DOCSTRING_REF_FINDINGS)
        message: str = (
            f"Found {total} unlinked backticked symbol(s) in source docstrings "
            f"(TOPMARK_DOCS_STRICT_REFS={TOPMARK_DOCS_STRICT_REFS!r}).\n"
            "See error/warning output above for file/line details.\n"
            "Set TOPMARK_DOCS_STRICT_REFS=0 to disable strict mode."
        )

        raise RuntimeError(message)

    # --- Summary (printed only if TOPMARK_DOCS_DEBUG is set) ---
    if TOPMARK_DOCS_DEBUG is True:
        logger.info(
            "summary: api-autonav owns module pages; %d modules skipped due to import errors; "
            "%d docstring-ref issue(s)",
            len(skipped_import),
            sum(len(d) for (_src, d) in _DOCSTRING_REF_FINDINGS),
        )
        if skipped_import:
            for mod, reason in skipped_import[:20]:
                logger.info("  - skipped: %s -> %s", mod, reason)
            if len(skipped_import) > 20:
                logger.info("  ... and %d more", len(skipped_import) - 20)


def main(
    docs_writer: DocsWriter | None = None,
) -> None:
    """Generate TopMark-owned pages and optionally enforce reference hygiene.

    Zensical's native ``api-autonav`` owns Python-module page generation. This function writes
    CLI/configuration exports while retaining the source-docstring audit.

    Args:
        docs_writer: Destination for the generated staging pages.

    Raises:
        ValueError: If no filesystem writer is supplied.

    """
    if docs_writer is None:
        raise ValueError("A filesystem documentation writer is required for Zensical staging")

    # Enforce source-docstring reference hygiene before generating CLI/configuration pages.
    validate_docstring_links()

    # TopMark CLI/configuration exports:
    generate_cli_reference_pages(docs_writer)

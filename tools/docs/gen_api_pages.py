# topmark:header:start
#
#   project      : TopMark
#   file         : gen_api_pages.py
#   file_relpath : tools/docs/gen_api_pages.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Generate API documentation pages for TopMark modules.

This script is executed as a script via runpy.run_path by mkdocs-gen-files
during the MkDocs build.

It generates:
- Internals pages under `API_INTERNALS_DIR/` (one page per importable module)
- Public reference pages under `API_REFERENCE_DIR/` for selected public surfaces
- CLI-derived reference pages under `usage/`

To avoid mkdocs-autorefs duplicate-anchor warnings, it skips generating internals pages for the
*exact* public surfaces listed in `PUBLIC_API_PREFIXES` (e.g. [`topmark.api`][topmark.api],
[`topmark.registry`][topmark.registry]), while still generating pages for their submodules.

In debug/strict modes it also scans *module docstrings* in `src/` for unlinked backticked
`topmark.*` symbol references and reports actionable `src/...` locations.

Because it’s executed as a script (not imported as a package), helpers must be imported via
absolute module paths (e.g. tools.docs.…).
"""

# pyright: reportMissingModuleSource=false

from __future__ import annotations

import ast
import importlib
import pkgutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import mkdocs_gen_files
from mkdocs.plugins import PrefixedLogger
from mkdocs.plugins import get_plugin_logger as get_logger

import topmark

# Use absolute module reference (MkDocs):
from tools.docs.docs_utils import (
    NONLINKED_SYMBOLS,
    PUBLIC_API_PREFIXES,
    context_lines,
    env_flag,
    find_unlinked_backticked_symbols_with_locations,
    fix_backticked_reference_links,
    format_inline_symbols,
    format_line_numbers,
    format_repo_path,
    public_ref_doc_for_symbol,
    rel_href,
    strip_repo_prefix,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import ModuleType

logger: PrefixedLogger = get_logger("gen_api_pages")

# --- Constants for Directory Structure ---
ROOT_PKG: Final[str] = "topmark"
API_INTERNALS_DIR: Final[str] = "api/internals"
API_REFERENCE_DIR: Final[str] = "api/reference"
TOP_INDEX_DIR: Final[str] = f"{API_INTERNALS_DIR}/topmark"
TOP_INDEX: Final[str] = f"{TOP_INDEX_DIR}/index.md"

# --- Configuration via Environment Variables ---

# Generate debug logging
# Also enables extra debug checks during the docs build.
TOPMARK_DOCS_DEBUG: bool = env_flag("TOPMARK_DOCS_DEBUG", default=False)
if TOPMARK_DOCS_DEBUG is True:
    logger.info("Debug logging enabled (TOPMARK_DOCS_DEBUG resolves to True)")

# Fail the docs build when unlinked backticked symbol references are found in docstrings.
# Useful with `mkdocs build --strict` to enforce reference hygiene.
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
        # Fail hard so 'strict: true' builds don’t silently publish stale docs.
        joined: str = " ".join(cmd)
        raise RuntimeError(
            f"Command failed: {joined}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        )
    return proc.stdout


def generate_cli_reference_pages() -> None:
    """Generate documentation for TopMark CLI features.

    This invokes the app's own 'filetypes' and 'processors' commands which
    have built-in Markdown exporters.
    """
    filetypes_md: str = _run_topmark_markdown(
        "filetypes",
        "--long",
        "--output-format",
        "markdown",
    )
    processors_md: str = _run_topmark_markdown(
        "processors",
        "--long",
        "--output-format",
        "markdown",
    )

    def _write_generated_page(dest: str, title: str, body: str) -> None:
        """Write a standalone generated Markdown page under `docs/`.

        Args:
            dest: Docs-relative output path (e.g. `usage/generated-filetypes.md`).
            title: Page title to render at the top.
            body: Pre-rendered Markdown emitted by `topmark ... --output-format markdown`.
        """
        # Open a virtual file in the MkDocs build environment.
        with mkdocs_gen_files.open(dest, "w") as f:
            f.write(f"# {title}\n\n")
            f.write("<!-- This page is generated. Do not edit manually. -->\n\n")
            # `body` is already Markdown; write verbatim.
            f.write(body)

    _write_generated_page(
        "usage/generated-filetypes.md",
        "Supported file types (generated)",
        filetypes_md,
    )
    _write_generated_page(
        "usage/generated-processors.md",
        "Registered processors (generated)",
        processors_md,
    )


# Tracks relationships between parent packages and their contents.
packages: defaultdict[str, set[str]] = defaultdict(set)


def _parent_package(modname: str) -> str | None:
    """Determine the parent dotted path of a module.

    Args:
        modname: The full dotted name (e.g., 'topmark.cli.main').

    Returns:
        The parent path (e.g., 'topmark.cli') or None if at the root.
    """
    return modname.rsplit(".", 1)[0] if "." in modname else None


def _child_segment(modname: str) -> str:
    """Extract the specific name of the module/package from a dotted path.

    Args:
        modname: The full dotted name (e.g., 'topmark.cli.main').

    Returns:
        The last segment (e.g., 'main').
    """
    return modname.rsplit(".", 1)[-1]


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


def _get_member_icon(modname: str) -> str:
    """Pick a visual icon for the documentation navigation lists.

    This helps users distinguish between folders (packages) and files (modules).

    Args:
        modname: The module path.

    Returns:
        A Material Design icon shortcode string.
    """
    if _is_package(modname):
        return ":material-folder-outline:"

    # If it's a file on disk, it's a module.
    rel = Path(*modname.split("."))
    if (Path("src") / f"{rel}.py").exists():
        return ":material-file-code-outline:"

    return ":material-symbol:"


def _scan_module_docstring(modname: str, src_path: str, current_doc: str) -> None:
    """Audit the module docstring for unlinked symbol references.

    This function parses the Python source to find the docstring, then checks
    if backticked text (e.g. `topmark.some_func`) has a matching MkDocs anchor.

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
            "src/%s - [%d] (%s) %s — Fix: [`%s`][%s]",
            rel_src,
            seq,
            format_line_numbers(findings_abs[sym]),
            sym,
            sym,
            sym,
        )

        # Only suggest inline-link alternatives in debug mode.
        if TOPMARK_DOCS_DEBUG is True:
            ref_doc: str | None = public_ref_doc_for_symbol(sym)
            if ref_doc is not None:
                href: str = rel_href(current_doc, ref_doc)
                logger.info(
                    "src/%s - Alt: [`%s`](%s#%s)",
                    rel_src,
                    sym,
                    href,
                    sym,
                )


def _breadcrumbs_for_parts(parts: list[str], current_doc: str) -> list[tuple[str, str | None]]:
    """Create a list of breadcrumb links for the page header.

    Args:
        parts: The dotted segments after 'topmark'.
        current_doc: The path of the page currently being generated.

    Returns:
        List of (label, url) tuples.
    """
    depth: int = len(parts)
    if depth == 0:
        return [(ROOT_PKG, None)]

    # top-level: 'topmark' index
    crumbs: list[tuple[str, str | None]] = [
        (ROOT_PKG, rel_href(current_doc, TOP_INDEX)),
    ]
    # intermediate ancestors (labels are segment-only)
    for i in range(1, depth):
        ancestor: str = f"{TOP_INDEX_DIR}/{'/'.join(parts[:i])}/index.md"
        crumbs.append(
            (
                parts[i - 1],
                rel_href(current_doc, ancestor),
            )
        )
    # current page label (last segment), no link
    crumbs.append((parts[-1], None))
    return crumbs


def _breadcrumbs_for_package(pkg: str, current_doc: str) -> list[tuple[str, str | None]]:
    """Wrapper to generate breadcrumbs for a package index page."""
    assert pkg.startswith(ROOT_PKG), pkg
    if pkg == ROOT_PKG:
        return [(ROOT_PKG, None)]
    segs: list[str] = pkg.split(".")[1:]  # after 'topmark'
    return _breadcrumbs_for_parts(segs, current_doc)


def _breadcrumbs_for_module(modname: str, current_doc: str) -> list[tuple[str, str | None]]:
    """Wrapper to generate breadcrumbs for a module page."""
    assert modname.startswith(ROOT_PKG), modname
    segs: list[str] = modname.split(".")[1:]  # after 'topmark'
    return _breadcrumbs_for_parts(segs, current_doc)


def _first_line_summary(modname: str) -> str | None:
    """Get the first line of a module's docstring for summary lists.

    Args:
        modname: The module to inspect.

    Returns:
        The first non-empty line of the docstring, or None.
    """
    try:
        mod: ModuleType = importlib.import_module(modname)
    except (ImportError, ModuleNotFoundError):
        # Catch import failures only
        return None

    doc_obj: Any | None = getattr(mod, "__doc__", None)
    if not isinstance(doc_obj, str):
        return None
    for line in doc_obj.splitlines():
        if s := line.strip():
            return s
    return None


def _write_child_list(fd: Any, items: list[str]) -> None:
    """Write a Markdown list of child modules with icons and summaries.

    Args:
        fd: The file handle to write to.
        items: List of full dotted module names.
    """
    for child_full in items:
        child_name: str = _child_segment(child_full)
        icon: str = _get_member_icon(child_full)
        is_pkg: bool = _exists_in_src(child_full) and _is_package(child_full)

        # Packages link to an index.md, modules link to the .md file directly.
        link: str = f"./{child_name}/index.md" if is_pkg else f"./{child_name}.md"
        summary: str | None = _first_line_summary(child_full)

        fd.write(f"{icon} [{child_full}]({link})\n")
        if summary:
            fd.write(f"  :    {summary}\n")


def _should_skip(modname: str) -> bool:
    """Determine if a module should be excluded from 'Internals' documentation.

    We skip only the *exact* public-facing surfaces (to avoid duplicate anchors),
    but we still generate pages for their submodules so mkdocs-autorefs can resolve
    links like [`topmark.registry.processors`][topmark.registry.processors].

    Args:
        modname: Dotted module name.

    Returns:
        True if the module is private (starts with _) or is already a public API surface.
    """
    # Skip exact public modules (but allow their submodules).
    if modname in PUBLIC_API_PREFIXES:
        return True

    # Skip dunder/private segments anywhere in the dotted path.
    return any(part.startswith("_") for part in modname.split("."))


def _walk() -> Iterable[str]:
    """Iterate through all importable modules in the topmark package."""
    for m in pkgutil.walk_packages(topmark.__path__, topmark.__name__ + "."):
        if _should_skip(m.name):
            continue
        if not _exists_in_src(m.name):
            continue
        yield m.name


# Group modules by their first segment after `topmark` (e.g. cli, pipeline, filetypes)
groups: dict[str, list[str]] = defaultdict(list)

skipped_import: list[tuple[str, str]] = []  # (module, reason)
written_pages: int = 0


# --- Refactored main generation logic ---
def _write_module_page(name: str, current_doc: str) -> None:
    """Write a Markdown file that uses 'mkdocstrings' to render a module.

    The ':::' directive tells mkdocstrings to find this module and auto-generate
    documentation from its classes and functions.
    """
    with mkdocs_gen_files.open(current_doc, "w") as fd:
        fd.write(f"# {name}\n\n")
        # Breadcrumbs for module pages
        bc: list[tuple[str, str | None]] = _breadcrumbs_for_module(name, current_doc)
        if bc:
            rendered: list[str] = []
            label: str
            href: str | None
            for label, href in bc:
                if href is None:
                    rendered.append(label)
                else:
                    rendered.append(f"[{label}]({href})")
            fd.write(" / ".join(rendered) + "\n\n")

        # The 'mkdocstrings' identifier.
        fd.write(f"::: {name}\n")
        fd.write("    options:\n")
        fd.write("      heading_level: 2\n")
        fd.write("      show_root_heading: false\n")
        fd.write("      members_order: source\n")
        fd.write("      filters:\n")
        fd.write('        - "!^_"\n')


def _write_internals_index(index_path: str, groups: dict[str, list[str]]) -> None:
    """Write the main index page for all internal modules."""
    with mkdocs_gen_files.open(index_path, "w") as fd:
        fd.write("# topmark internals index\n\n")
        fd.write(
            "This index groups internal modules by top-level package. "
            "Use the search box for symbols, or browse below.\n\n"
        )
        for group in sorted(groups):
            fd.write(f"## {group}\n\n")
            for mod in sorted(groups[group]):
                link: str = rel_href(index_path, f"{API_INTERNALS_DIR}/{mod.replace('.', '/')}.md")
                # Link label is full dotted path for clarity
                fd.write(f"- [{mod}]({link})\n")
            fd.write("\n")


def _write_internals_summary(summary_path: str, groups: dict[str, list[str]]) -> None:
    """Generate a SUMMARY.md file used by 'mkdocs-literate-nav'.

    This file determines the structure of the sidebar menu in the browser.

    Links are relative to `docs/API_INTERNALS_DIR/`.
    """
    with mkdocs_gen_files.open(summary_path, "w") as fd:
        fd.write("# Internals navigation (generated)\n\n")
        fd.write("<!-- This file is generated. Do not edit manually. -->\n\n")

        # Entry point / landing index for internals:
        fd.write("- [Internals index](topmark/index.md)\n")

        # One bullet per top-level group (topmark.<group>)
        for group in sorted(groups):
            pkg: str = f"{ROOT_PKG}.{group}"

            # Some top-level groups are *modules* (e.g. topmark.constants), not packages.
            # Only packages have a generated `.../index.md` page; modules have `....md`.
            if _is_package(pkg):
                rel_pkg_entry: str = f"{pkg.replace('.', '/')}/index.md"
            else:
                rel_pkg_entry = f"{pkg.replace('.', '/')}.md"

            fd.write(f"- [{pkg}]({rel_pkg_entry})\n")

            # Under each group, list modules in that group.
            for mod in sorted(groups[group]):
                if mod == pkg:
                    continue

                # Packages have their own `index.md` (generated by _write_package_index).
                if _is_package(mod):
                    rel_mod_path: str = f"{mod.replace('.', '/')}/index.md"
                else:
                    rel_mod_path = f"{mod.replace('.', '/')}.md"

                fd.write(f"  - [{mod}]({rel_mod_path})\n")

        fd.write("\n")


# Public (reference) API
def _write_public_reference_pages() -> None:
    """Generate high-level documentation for the library's public API."""
    for mod in PUBLIC_API_PREFIXES:
        mod_ref_doc: str = f"{API_REFERENCE_DIR}/{mod}.md"
        mod_ref_md: str = f"""# [`{mod}`][{mod}]

::: {mod}
options:
  heading_level: 1
  show_root_heading: true
  members_order: source
  filters:
    - "!^_"
"""
        with mkdocs_gen_files.open(mod_ref_doc, "w") as fd:
            fd.write(mod_ref_md)
        src_candidate: str = "src/" + mod.replace(".", "/") + ".py"
        # Link back to the physical source code for "Edit this page" links.
        src_pkg_init: str = "src/" + mod.replace(".", "/") + "/__init__.py"
        edit_path: str = src_candidate if Path(src_candidate).exists() else src_pkg_init
        mkdocs_gen_files.set_edit_path(mod_ref_doc, edit_path)  # generated only
        # Scan public API module docstring for unlinked symbol references.
        _scan_module_docstring(mod, edit_path, mod_ref_doc)


def _write_package_index(pkg: str, children: set[str]) -> None:
    """Write a landing page (index.md) for a Python package folder.

    Writes per-package indices with links to immediate children.

    Notes:
        - Package indices live at `API_INTERNALS_DIR/<pkg>/index.md`.
        - For the top-level `topmark` package, we split immediate children into
          packages vs modules so that top-level modules (e.g. `topmark.constants`)
          are visible.
    """
    pkg_path: str = pkg.replace(".", "/")
    pkg_index_path: str = f"{API_INTERNALS_DIR}/{pkg_path}/index.md"
    current_doc: str = pkg_index_path

    # Keep edit links correct for packages.
    pkg_src_rel: str = pkg.replace(".", "/")
    mkdocs_gen_files.set_edit_path(pkg_index_path, f"src/{pkg_src_rel}/__init__.py")

    with mkdocs_gen_files.open(pkg_index_path, "w") as fd:
        fd.write(f"# {pkg} package index\n\n")

        # Breadcrumbs (from topmark down to the parent of `pkg`)
        bc: list[tuple[str, str | None]] = _breadcrumbs_for_package(pkg, current_doc)
        if bc:
            crumbs_rendered: list[str] = []
            for label, href in bc:
                if href is None:
                    crumbs_rendered.append(label)
                else:
                    crumbs_rendered.append(f"[{label}]({href})")
            fd.write(" / ".join(crumbs_rendered) + "\n\n")

        # Link to Public API page if this is a public surface.
        # Public surfaces are documented under API_REFERENCE_DIR/*.
        # IMPORTANT: avoid duplicate mkdocs-autorefs identifiers.
        if pkg in PUBLIC_API_PREFIXES:
            pub_ref_doc: str = f"{API_REFERENCE_DIR}/{pkg}.md"
            pub_href: str = rel_href(current_doc, pub_ref_doc)
            fd.write(f"This is part of the **public API**: [`{pkg}`]({pub_href}).\n\n")
        else:
            # Render the package module docstring at the top via mkdocstrings.
            fd.write(f"::: {pkg}\n")
            fd.write("    options:\n")
            fd.write("      heading_level: 2\n")
            fd.write("      show_root_heading: false\n")
            fd.write("      members_order: source\n")
            fd.write("      filters:\n")
            fd.write('        - "!^_"\n')
            fd.write("\n")

        # Organize the children list for the top-level index.
        # For the top-level `topmark` package, split immediate children into
        # packages vs modules to make top-level modules visible.
        if pkg == ROOT_PKG:
            child_pkgs: list[str] = []
            child_mods: list[str] = []
            for child_full in sorted(children):
                if _exists_in_src(child_full) and _is_package(child_full):
                    child_pkgs.append(child_full)
                else:
                    child_mods.append(child_full)

            fd.write("## Top-level packages\n\n")
            _write_child_list(fd, child_pkgs or ["(none)\n"])

            fd.write("\n## Top-level modules\n\n")
            _write_child_list(fd, child_mods or ["(none)\n"])

        else:
            # Default: single mixed list for non-top-level packages.
            fd.write("## Immediate children in this package\n\n")
            _write_child_list(fd, sorted(children))


def main() -> None:
    """Generate MkDocs pages for TopMark and optionally enforce reference hygiene.

    This is the entry point invoked during the MkDocs build via mkdocs-gen-files.

    It:
    - Walks TopMark modules under `src/` and generates internals pages under `API_INTERNALS_DIR/`
    - Writes a grouped internals index
    - Writes public reference pages for `PUBLIC_API_PREFIXES` under `API_REFERENCE_DIR/`
    - Writes per-package indices linking immediate children
    - Generates CLI reference pages under `usage/`
    - Scans module docstrings for unlinked backticked `topmark.*` symbol references

    In strict mode (`TOPMARK_DOCS_STRICT_REFS=1`), the build aborts after generation if any
    unlinked backticked TopMark symbols were found in docstrings.

    Raises:
        Abort: When strict reference hygiene is enabled and unlinked backticked symbols are found.
        RuntimeError: Fallback when MkDocs Abort cannot be imported.
    """
    global written_pages
    groups: dict[str, list[str]] = defaultdict(list)

    # 1. Generate pages for every discovered module.
    for name in sorted(set(_walk())):
        # Only generate a page if the module imports cleanly; otherwise skip.
        try:
            importlib.import_module(name)
        except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover - generation-time guard
            # Record import failures so we can surface them in debug summaries.
            skipped_import.append((name, f"import failed: {type(e).__name__}: {e}"))
            continue

        current_doc: str = f"{API_INTERNALS_DIR}/{name.replace('.', '/')}.md"
        _write_module_page(name, current_doc)
        written_pages += 1

        src_rel: str = name.replace(".", "/")
        src_path: str = f"src/{src_rel}/__init__.py" if _is_package(name) else f"src/{src_rel}.py"
        mkdocs_gen_files.set_edit_path(current_doc, src_path)

        # Scan module docstring for unlinked backticked TopMark symbol references.
        _scan_module_docstring(name, src_path, current_doc)

        # Track groups and package children for the index pages.

        if name != ROOT_PKG and name.startswith(ROOT_PKG + "."):
            top: str = name.split(".", 2)[1] if "." in name else name
            groups[top].append(name)

        # Record this module under its parent package for index generation
        if parent := _parent_package(name):
            packages[parent].add(name)

    # 2. Write structural index files.
    # Write an optional grouped index (kept out of the sidebar to avoid duplication with
    # the per-package index at TOP_INDEX_DIR/index.md).
    _write_internals_index(f"{TOP_INDEX_DIR}/groups.md", groups)

    # Write a literate-nav SUMMARY.md so mkdocs.yml can include the generated internals tree.
    _write_internals_summary(f"{API_INTERNALS_DIR}/SUMMARY.md", groups)

    # Public (reference) API:
    _write_public_reference_pages()

    # Write per-package indices with links to immediate children
    for pkg, children in sorted(packages.items()):
        _write_package_index(pkg, children)

    # 3. Generate non-API pages (CLI).
    generate_cli_reference_pages()

    # 4. Strict Mode check: fail build if docstrings have issues.
    if TOPMARK_DOCS_STRICT_REFS is True and _DOCSTRING_REF_FINDINGS:
        total: int = sum(len(d) for (_src, d) in _DOCSTRING_REF_FINDINGS)
        message: str = (
            f"Found {total} unlinked backticked symbol(s) in source docstrings "
            f"(TOPMARK_DOCS_STRICT_REFS={TOPMARK_DOCS_STRICT_REFS!r}).\n"
            "See error/warning output above for file/line details.\n"
            "Set TOPMARK_DOCS_STRICT_REFS=0 to disable strict mode."
        )

        # Prefer MkDocs' Abort for a clean failure without a traceback.
        try:
            from mkdocs.exceptions import Abort
        except Exception as err:  # pragma: no cover
            raise RuntimeError(message) from err

        raise Abort(message)

    # --- Summary (printed only if TOPMARK_DOCS_DEBUG is set) ---
    if TOPMARK_DOCS_DEBUG is True:
        logger.info(
            "summary: wrote %d pages; %d modules skipped due to import errors; "
            "%d docstring-ref issue(s)",
            written_pages,
            len(skipped_import),
            sum(len(d) for (_src, d) in _DOCSTRING_REF_FINDINGS),
        )
        if skipped_import:
            for mod, reason in skipped_import[:20]:
                logger.info("  - skipped: %s -> %s", mod, reason)
            if len(skipped_import) > 20:
                logger.info("  ... and %d more", len(skipped_import) - 20)


def _run() -> None:
    main()


_run()

if __name__ == "__main__":
    # Already ran via mkdocs-gen-files/run_path; running directly should still work.
    pass

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
- Internals pages under `api/internals/` (one page per importable module)
- Public reference pages under `api/reference/` for selected public surfaces
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
from typing import TYPE_CHECKING, Any

import mkdocs_gen_files
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

logger = get_logger("gen_api_pages")

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


# Accumulate docstring findings so we can fail once after generation.
# Each entry: (src_path, {symbol -> set(line_numbers)})
_DOCSTRING_REF_FINDINGS: list[tuple[str, dict[str, set[int]]]] = []


def _run_topmark_markdown(*args: str) -> str:
    """Run TopMark via `python -m topmark ...` and return stdout.

    We intentionally execute TopMark as a module to avoid relying on an
    installed console-script entry point when building docs.

    Args:
        *args: CLI arguments passed to `python -m topmark`.

    Returns:
        The command's stdout.

    Raises:
        RuntimeError: If the command exits non-zero.
    """
    cmd: list[str] = [sys.executable, "-m", "topmark", *args]
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
    """Generate version-accurate CLI reference pages.

    Pages are generated from `python -m topmark ... --output-format markdown` output.
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


# Map a package module name to the set of its immediate children (module or package names)
packages: defaultdict[str, set[str]] = defaultdict(set)


def _parent_package(modname: str) -> str | None:
    """Return the parent package name for a module, or None for top-level.

    Examples:
        topmark.cli.commands.check -> topmark.cli.commands
        topmark.cli -> topmark
        topmark -> None

    Args:
        modname: The module name.

    Returns:
        The parent package name for the module or None for top-level.
    """
    if "." not in modname:
        return None
    return modname.rsplit(".", 1)[0]


def _child_segment(modname: str) -> str:
    """Return the last dotted segment of the module name.

    Example: topmark.cli.commands.check -> "check"
    """
    return modname.rsplit(".", 1)[-1]


def _exists_in_src(modname: str) -> bool:
    """Return True if the module's source exists under ./src.

    Accepts either a module (src/topmark/foo.py) or a package
    (src/topmark/foo/__init__.py).
    """
    rel = Path(*modname.split("."))
    return (Path("src") / f"{rel}.py").exists() or (Path("src") / rel / "__init__.py").exists()


def _is_package(modname: str) -> bool:
    """Return True if the module is a package with an ``__init__.py`` under ./src."""
    rel = Path(*modname.split("."))
    pkg_dir: Path = Path("src") / rel
    return pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists()


if TOPMARK_DOCS_DEBUG and NONLINKED_SYMBOLS:
    logger.info(
        "Non-linked symbol whitelist enabled (%d): %s",
        len(NONLINKED_SYMBOLS),
        ", ".join(sorted(NONLINKED_SYMBOLS)),
    )


def _scan_module_docstring(modname: str, src_path: str, current_doc: str) -> None:
    """Scan a module's docstring in its source file and log unlinked symbol refs.

    It reports actionable `src/...` file/line locations.
    It does *not* depend on whether the corresponding internals page is present in `nav`.
    """
    try:
        py_text: str = Path(src_path).read_text(encoding="utf-8")
    except OSError:
        return

    try:
        tree = ast.parse(py_text, filename=src_path)
    except SyntaxError:
        return

    # Identify module docstring node (first statement).
    doc_node: ast.Expr | None = None
    if tree.body and isinstance(tree.body[0], ast.Expr):
        v = tree.body[0].value

        # Python 3.8+ represents string literals as ast.Constant.
        is_str_const: bool = isinstance(v, ast.Constant) and isinstance(v.value, str)
        if is_str_const:
            doc_node = tree.body[0]

    if doc_node is None:
        return

    doc: str | None = ast.get_docstring(tree, clean=False)
    if not doc:
        return

    # Normalize obvious backticked-reference link issues first.
    doc_fixed: str = fix_backticked_reference_links(doc)

    findings: dict[str, set[int]] = find_unlinked_backticked_symbols_with_locations(doc_fixed)
    if not findings:
        return

    # Approximate docstring starting line: ast gives the line where the string literal starts.
    base_line: int = getattr(doc_node, "lineno", 1)

    # Convert docstring-relative line numbers to file line numbers.
    findings_abs: dict[str, set[int]] = {}
    for sym, rel_lines in findings.items():
        abs_lines: set[int] = {base_line + (ln - 1) for ln in rel_lines}
        findings_abs[sym] = abs_lines

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
            "src/%s - Found %d unlinked backticked TopMark symbol reference(s): %s",
            rel_src,
            len(symbols_sorted),
            inline_syms,
        )

    if TOPMARK_DOCS_STRICT_REFS is True:
        logger.error(
            "src/%s - Unlinked backticked TopMark symbol reference(s) in module docstring: %s",
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
    """Build compact breadcrumbs for parts under `topmark` relative to current doc."""
    depth: int = len(parts)
    crumbs: list[tuple[str, str | None]] = []
    if depth == 0:
        return [("topmark", None)]
    # top-level: 'topmark' index
    top_index = "api/internals/topmark/index.md"
    crumbs.append(("topmark", rel_href(current_doc, top_index)))
    # intermediate ancestors (labels are segment-only)
    for i in range(1, depth):
        ancestor: str = "api/internals/topmark/" + "/".join(parts[:i]) + "/index.md"
        href: str = rel_href(current_doc, ancestor)
        crumbs.append((parts[i - 1], href))
    # current page label (last segment), no link
    crumbs.append((parts[-1], None))
    return crumbs


def _breadcrumbs_for_package(pkg: str, current_doc: str) -> list[tuple[str, str | None]]:
    assert pkg.startswith("topmark"), pkg
    if pkg == "topmark":
        return [("topmark", None)]
    segs: list[str] = pkg.split(".")[1:]  # after 'topmark'
    return _breadcrumbs_for_parts(segs, current_doc)


def _breadcrumbs_for_module(modname: str, current_doc: str) -> list[tuple[str, str | None]]:
    assert modname.startswith("topmark"), modname
    segs: list[str] = modname.split(".")[1:]  # after 'topmark'
    return _breadcrumbs_for_parts(segs, current_doc)


def _first_line_summary(modname: str) -> str | None:
    """Return the first non-empty line of the module's docstring, if available."""
    try:
        mod = importlib.import_module(modname)
    except (ImportError, ModuleNotFoundError):
        # Catch import failures only
        return None

    doc_obj: Any | None = getattr(mod, "__doc__", None)
    if not isinstance(doc_obj, str):
        return None
    for line in doc_obj.splitlines():
        s: str = line.strip()
        if s:
            return s
    return None


def _should_skip(modname: str) -> bool:
    """Return True for modules we do not want to generate internals pages for.

    We skip only the *exact* public-facing surfaces (to avoid duplicate anchors),
    but we still generate pages for their submodules so mkdocs-autorefs can resolve
    links like [`topmark.registry.processors`][topmark.registry.processors].
    """
    # Skip exact public modules (but allow their submodules).
    if modname in PUBLIC_API_PREFIXES:
        return True

    # Skip dunder/private segments anywhere in the dotted path.
    return bool(any(part.startswith("_") for part in modname.split(".")))


def _walk(package: object) -> Iterable[str]:
    for m in pkgutil.walk_packages(topmark.__path__, topmark.__name__ + "."):
        name: str = m.name
        if _should_skip(name):
            continue
        if not _exists_in_src(name):
            continue
        yield name


# Group modules by their first segment after `topmark` (e.g. cli, pipeline, filetypes)
groups: dict[str, list[str]] = defaultdict(list)

skipped_import: list[tuple[str, str]] = []  # (module, reason)
written_pages: int = 0


# --- Refactored main generation logic ---
def _write_module_page(name: str, current_doc: str) -> None:
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
        fd.write("::: " + name + "\n")
        fd.write("    options:\n")
        fd.write("      heading_level: 2\n")
        fd.write("      show_root_heading: false\n")
        fd.write("      members_order: source\n")
        fd.write("      filters:\n")
        fd.write('        - "!^_"\n')


def _write_internals_index(index_path: str, groups: dict[str, list[str]]) -> None:
    with mkdocs_gen_files.open(index_path, "w") as fd:
        fd.write("# topmark internals index\n\n")
        fd.write(
            "This index groups internal modules by top-level package. "
            "Use the search box for symbols, or browse below.\n\n"
        )
        for group in sorted(groups):
            fd.write(f"## {group}\n\n")
            for mod in sorted(groups[group]):
                link: str = rel_href(index_path, f"api/internals/{mod.replace('.', '/')}.md")
                label = mod  # full dotted path for clarity
                fd.write(f"- [{label}]({link})\n")
            fd.write("\n")


# Public (reference) API
def _write_public_reference_pages() -> None:
    for mod in PUBLIC_API_PREFIXES:
        mod_ref_doc: str = f"api/reference/{mod}.md"
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
        src_pkg_init: str = "src/" + mod.replace(".", "/") + "/__init__.py"
        edit_path: str = src_candidate if Path(src_candidate).exists() else src_pkg_init
        mkdocs_gen_files.set_edit_path(mod_ref_doc, edit_path)  # generated only
        # Scan public API module docstring for unlinked symbol references.
        _scan_module_docstring(mod, edit_path, mod_ref_doc)


def _write_package_index(pkg: str, children: set[str]) -> None:
    """Write per-package indices with links to immediate children."""
    # Compute the docs path for this package's index
    pkg_path: str = pkg.replace(".", "/")
    pkg_index_path: str = f"api/internals/{pkg_path}/index.md"
    current_doc = pkg_index_path

    # Keep edit links correct for packages.
    pkg_src_rel: str = pkg.replace(".", "/")
    mkdocs_gen_files.set_edit_path(pkg_index_path, f"src/{pkg_src_rel}/__init__.py")

    with mkdocs_gen_files.open(pkg_index_path, "w") as fd:
        # Render the package module docstring at the top via mkdocstrings
        fd.write(f"# {pkg} package index\n\n")

        # Breadcrumbs (from topmark down to the parent of `pkg`)
        bc = _breadcrumbs_for_package(pkg, current_doc)
        if bc:
            crumbs_rendered: list[str] = []
            for label, href in bc:
                if href is None:
                    crumbs_rendered.append(label)
                else:
                    crumbs_rendered.append(f"[{label}]({href})")
            fd.write(" / ".join(crumbs_rendered) + "\n\n")

        # IMPORTANT: avoid duplicate mkdocs-autorefs identifiers.
        # Public surfaces are documented under api/reference/*.
        if pkg in PUBLIC_API_PREFIXES:
            pub_ref_doc: str = f"api/reference/{pkg}.md"
            pub_href: str = rel_href(current_doc, pub_ref_doc)
            fd.write(
                "This package is part of the **public API** and is documented here: "
                f"[`{pkg}`]({pub_href}).\n\n"
            )
        else:
            # Render the package module docstring at the top via mkdocstrings.
            fd.write("::: " + pkg + "\n")
            fd.write("    options:\n")
            fd.write("      heading_level: 2\n")
            fd.write("      show_root_heading: false\n")
            fd.write("      members_order: source\n")
            fd.write("      filters:\n")
            fd.write('        - "!^_"\n')
            fd.write("\n")

        fd.write("## Immediate children in this package\n\n")
        for child_full in sorted(children):
            child_name: str = _child_segment(child_full)
            # If child is a subpackage, link to its index.md; otherwise to its module page
            if _exists_in_src(child_full) and _is_package(child_full):
                link = f"./{child_name}/index.md"
            else:
                link = f"./{child_name}.md"
            summary: str | None = _first_line_summary(child_full)
            if summary:
                fd.write(f"- [{child_full}]({link}) — {summary}\n")
            else:
                fd.write(f"- [{child_full}]({link})\n")
        fd.write("\n")


def main() -> None:
    """Generate MkDocs pages for TopMark and optionally enforce reference hygiene.

    This is the entry point invoked during the MkDocs build via mkdocs-gen-files.

    It:
    - Walks TopMark modules under `src/` and generates internals pages under `api/internals/`
    - Writes a grouped internals index
    - Writes public reference pages for `PUBLIC_API_PREFIXES` under `api/reference/`
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
    for name in sorted(set(_walk(topmark))):
        # Only generate a page if the module imports cleanly; otherwise skip.
        try:
            importlib.import_module(name)
        except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover - generation-time guard
            # Record import failures so we can surface them in debug summaries.
            skipped_import.append((name, f"import failed: {type(e).__name__}: {e}"))
            continue

        path: str = name.replace(".", "/") + ".md"
        current_doc: str = f"api/internals/{path}"
        _write_module_page(name, current_doc)

        written_pages += 1

        src_rel: str = name.replace(".", "/")
        src_path: str = f"src/{src_rel}/__init__.py" if _is_package(name) else f"src/{src_rel}.py"
        mkdocs_gen_files.set_edit_path(current_doc, src_path)

        # Scan module docstring for unlinked backticked TopMark symbol references.
        _scan_module_docstring(name, src_path, current_doc)

        if name != "topmark" and name.startswith("topmark."):
            top: str = name.split(".", 2)[1] if "." in name else name
            groups[top].append(name)

        # Record this module under its parent package for index generation
        parent: str | None = _parent_package(name)
        if parent is not None:
            packages[parent].add(name)

    # Write a small grouped index under api/internals/topmark/index.md
    index_path = "api/internals/topmark/index.md"
    _write_internals_index(index_path, groups)

    # Public (reference) API:
    _write_public_reference_pages()

    # Write per-package indices with links to immediate children
    for pkg, children in sorted(packages.items()):
        _write_package_index(pkg, children)

    generate_cli_reference_pages()

    # If strict ref hygiene is enabled, fail once after generation if docstring issues were found.
    if TOPMARK_DOCS_STRICT_REFS is True and _DOCSTRING_REF_FINDINGS:
        total: int = sum(len(d) for (_src, d) in _DOCSTRING_REF_FINDINGS)
        message: str = (
            f"Found {total} unlinked backticked symbol reference(s) in source docstrings "
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

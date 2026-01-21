# topmark:header:start
#
#   project      : TopMark
#   file         : gen_api_pages.py
#   file_relpath : docs/gen_api_pages.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Generate per-module API pages for internals.

Skips public surfaces (topmark.api, topmark.registry) to avoid duplicate anchors
and mkdocs-autorefs warnings. Only writes pages for modules that successfully
import, so mkdocstrings won't fail collecting them.
"""

# pyright: reportMissingModuleSource=false

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath("src"))

import importlib
import pkgutil
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import mkdocs_gen_files

import topmark

if TYPE_CHECKING:
    from collections.abc import Iterable


def _run_topmark_markdown(*args: str) -> str:
    """Run TopMark via `python -m topmark ...` and return stdout.

    We intentionally execute TopMark as a module to avoid relying on an
    installed console-script entry point when building docs.

    Args:
        *args (str): CLI arguments passed to `python -m topmark`.

    Returns:
        str: The command's stdout.

    Raises:
        RuntimeError: If the command exits non-zero.
    """
    cmd: list[str] = [sys.executable, "-m", "topmark", *args]
    proc: subprocess.CompletedProcess[str] = subprocess.run(
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
    """Generate version-accurate reference pages from TopMark CLI output."""
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
            dest (str): Docs-relative output path (e.g. `usage/generated-filetypes.md`).
            title (str): Page title to render at the top.
            body (str): Pre-rendered Markdown emitted by `topmark ... --output-format markdown`.
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
        modname (str): The module name.

    Returns:
        str | None: the parent package name for the module or None for top-level.
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
    rel: str = modname.replace(".", "/")
    return os.path.exists(os.path.join("src", f"{rel}.py")) or os.path.exists(
        os.path.join("src", rel, "__init__.py")
    )


def _is_package(modname: str) -> bool:
    """Return True if the module is a package with an ``__init__.py`` under ./src."""
    rel: str = modname.replace(".", "/")
    return os.path.isdir(os.path.join("src", rel)) and os.path.exists(
        os.path.join("src", rel, "__init__.py")
    )


def _rel(from_doc: str, to_doc: str) -> str:
    """Return a relative link from one doc file to another.

    Both paths should be repo-relative doc paths like
    `api/internals/topmark/cli/index.md` or `api/internals/topmark/cli.md`.
    """
    return os.path.relpath(to_doc, start=os.path.dirname(from_doc)).replace(os.sep, "/")


def _breadcrumbs_for_parts(parts: list[str], current_doc: str) -> list[tuple[str, str | None]]:
    """Build compact breadcrumbs for parts under `topmark` relative to current doc."""
    depth: int = len(parts)
    crumbs: list[tuple[str, str | None]] = []
    if depth == 0:
        return [("topmark", None)]
    # top-level: 'topmark' index
    top_index = "api/internals/topmark/index.md"
    crumbs.append(("topmark", _rel(current_doc, top_index)))
    # intermediate ancestors (labels are segment-only)
    for i in range(1, depth):
        ancestor: str = "api/internals/topmark/" + "/".join(parts[:i]) + "/index.md"
        href: str = _rel(current_doc, ancestor)
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
    except Exception:
        return None
    doc_obj: Any | None = getattr(mod, "__doc__", None)
    if not isinstance(doc_obj, str):
        return None
    for line in doc_obj.splitlines():
        s: str = line.strip()
        if s:
            return s
    return None


# Modules/prefixes to skip from internals (documented on the Public API page)
PUBLIC_API_PREFIXES: tuple[str, ...] = (
    "topmark.api",
    "topmark.registry",
)


def _should_skip(modname: str) -> bool:
    # Skip dunder/private and our public-facing packages
    if modname.startswith(PUBLIC_API_PREFIXES):
        return True
    if any(part.startswith("_") for part in modname.split(".")):
        return True
    return False


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

for name in sorted(set(_walk(topmark))):
    # Only generate a page if the module imports cleanly; otherwise skip.
    try:
        importlib.import_module(name)
    except Exception:  # pragma: no cover - generation-time guard
        continue

    path: str = name.replace(".", "/") + ".md"
    current_doc: str = f"api/internals/{path}"
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

    written_pages += 1

    src_rel: str = name.replace(".", "/")
    src_path: str = f"src/{src_rel}/__init__.py" if _is_package(name) else f"src/{src_rel}.py"
    mkdocs_gen_files.set_edit_path(current_doc, src_path)

    if name != "topmark" and name.startswith("topmark."):
        top: str = name.split(".", 2)[1] if "." in name else name
        groups[top].append(name)

    # Record this module under its parent package for index generation
    parent: str | None = _parent_package(name)
    if parent is not None:
        packages[parent].add(name)


# Write a small grouped index under api/internals/topmark/index.md
index_path = "api/internals/topmark/index.md"
with mkdocs_gen_files.open(index_path, "w") as fd:
    fd.write("# topmark internals index\n\n")
    fd.write(
        "This index groups internal modules by top-level package. "
        "Use the search box for symbols, or browse below.\n\n"
    )
    for group in sorted(groups):
        fd.write(f"## {group}\n\n")
        for mod in sorted(groups[group]):
            link: str = _rel(index_path, f"api/internals/{mod.replace('.', '/')}.md")
            label = mod  # full dotted path for clarity
            fd.write(f"- [{label}]({link})\n")
        fd.write("\n")


# Public (reference) API:
for mod in PUBLIC_API_PREFIXES:
    mod_ref_doc: str = f"api/reference/{mod}.md"
    mod_ref_md: str = f"""# `{mod}`

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
    mkdocs_gen_files.set_edit_path(
        mod_ref_doc,
        "src/" + mod.replace(".", "/") + ".py",
    )  # generated only


# Write per-package indices with links to immediate children
for pkg, children in sorted(packages.items()):
    # Compute the docs path for this package's index
    pkg_path: str = pkg.replace(".", "/")
    pkg_index_path: str = f"api/internals/{pkg_path}/index.md"
    current_doc = pkg_index_path
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

generate_cli_reference_pages()

# --- Summary (printed only if TOPMARK_DOCS_DEBUG is set) ---
print(
    f"summary: wrote {written_pages} pages; "
    f"{len(skipped_import)} modules skipped due to import errors"
)
for mod, reason in skipped_import[:20]:
    print(f"  - skipped: {mod} -> {reason}")
if len(skipped_import) > 20:
    print(f"  ... and {len(skipped_import) - 20} more")

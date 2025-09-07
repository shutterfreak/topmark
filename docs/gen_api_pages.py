# topmark:header:start
#
#   file         : gen_api_pages.py
#   file_relpath : docs/gen_api_pages.py
#   project      : TopMark
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
import sys

sys.path.insert(0, os.path.abspath("src"))

import importlib
import pkgutil
from collections import defaultdict
from typing import DefaultDict, Iterable

import mkdocs_gen_files  # type: ignore[import-not-found]

import topmark

# Map a package module name to the set of its immediate children (module or package names)
packages: DefaultDict[str, set[str]] = defaultdict(set)


def _parent_package(modname: str) -> str | None:
    """Return the parent package name for a module, or None for top-level.

    Examples:
        topmark.cli.commands.check -> topmark.cli.commands
        topmark.cli -> topmark
        topmark -> None
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
    rel = modname.replace(".", "/")
    return os.path.exists(os.path.join("src", f"{rel}.py")) or os.path.exists(
        os.path.join("src", rel, "__init__.py")
    )


def _is_package(modname: str) -> bool:
    """Return True if the module is a package with an ``__init__.py`` under ./src."""
    rel = modname.replace(".", "/")
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
    depth = len(parts)
    crumbs: list[tuple[str, str | None]] = []
    if depth == 0:
        return [("topmark", None)]
    # top-level: 'topmark' index
    top_index = "api/internals/topmark/index.md"
    crumbs.append(("topmark", _rel(current_doc, top_index)))
    # intermediate ancestors (labels are segment-only)
    for i in range(1, depth):
        ancestor = "api/internals/topmark/" + "/".join(parts[:i]) + "/index.md"
        href = _rel(current_doc, ancestor)
        crumbs.append((parts[i - 1], href))
    # current page label (last segment), no link
    crumbs.append((parts[-1], None))
    return crumbs


def _breadcrumbs_for_package(pkg: str, current_doc: str) -> list[tuple[str, str | None]]:
    assert pkg.startswith("topmark"), pkg
    if pkg == "topmark":
        return [("topmark", None)]
    segs = pkg.split(".")[1:]  # after 'topmark'
    return _breadcrumbs_for_parts(segs, current_doc)


def _breadcrumbs_for_module(modname: str, current_doc: str) -> list[tuple[str, str | None]]:
    assert modname.startswith("topmark"), modname
    segs = modname.split(".")[1:]  # after 'topmark'
    return _breadcrumbs_for_parts(segs, current_doc)


def _first_line_summary(modname: str) -> str | None:
    """Return the first non-empty line of the module's docstring, if available."""
    try:
        mod = importlib.import_module(modname)
    except Exception:
        return None
    doc_obj = getattr(mod, "__doc__", None)
    if not isinstance(doc_obj, str):
        return None
    for line in doc_obj.splitlines():
        s = line.strip()
        if s:
            return s
    return None


# Modules/prefixes to skip from internals (documented on the Public API page)
_SKIP_PREFIXES: tuple[str, ...] = (
    "topmark.api",
    "topmark.registry",
)


def _should_skip(modname: str) -> bool:
    # Skip dunder/private and our public-facing packages
    if modname.startswith(_SKIP_PREFIXES):
        return True
    if any(part.startswith("_") for part in modname.split(".")):
        return True
    return False


def _walk(package: object) -> Iterable[str]:
    for m in pkgutil.walk_packages(topmark.__path__, topmark.__name__ + "."):
        name = m.name
        if _should_skip(name):
            continue
        if not _exists_in_src(name):
            continue
        yield name


# Group modules by their first segment after `topmark` (e.g. cli, pipeline, filetypes)
groups: dict[str, list[str]] = defaultdict(list)


for name in sorted(set(_walk(topmark))):
    # Only generate a page if the module imports cleanly; otherwise skip.
    try:
        importlib.import_module(name)
    except Exception:  # pragma: no cover - generation-time guard
        continue

    path = name.replace(".", "/") + ".md"
    current_doc = f"api/internals/{path}"
    with mkdocs_gen_files.open(current_doc, "w") as fd:
        fd.write(f"# {name}\n\n")
        # Breadcrumbs for module pages
        bc = _breadcrumbs_for_module(name, current_doc)
        if bc:
            rendered: list[str] = []
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

    mkdocs_gen_files.set_edit_path(
        current_doc,
        "src/" + name.replace(".", "/") + ".py",
    )

    if name != "topmark" and name.startswith("topmark."):
        top = name.split(".", 2)[1] if "." in name else name
        groups[top].append(name)

    # Record this module under its parent package for index generation
    parent = _parent_package(name)
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
            link = _rel(index_path, f"api/internals/{mod.replace('.', '/')}.md")
            label = mod  # full dotted path for clarity
            fd.write(f"- [{label}]({link})\n")
        fd.write("\n")


# Write per-package indices with links to immediate children
for pkg, children in sorted(packages.items()):
    # Compute the docs path for this package's index
    pkg_path = pkg.replace(".", "/")
    pkg_index_path = f"api/internals/{pkg_path}/index.md"
    current_doc = pkg_index_path

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
            child_name = _child_segment(child_full)
            # If child is a subpackage, link to its index.md; otherwise to its module page
            if _exists_in_src(child_full) and _is_package(child_full):
                link = f"./{child_name}/index.md"
            else:
                link = f"./{child_name}.md"
            summary = _first_line_summary(child_full)
            if summary:
                fd.write(f"- [{child_full}]({link}) — {summary}\n")
            else:
                fd.write(f"- [{child_full}]({link})\n")
        fd.write("\n")

# topmark:header:start
#
#   project      : TopMark
#   file         : web.py
#   file_relpath : src/topmark/filetypes/builtins/web.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Web and frontend assets.

Includes markup, stylesheets, vector graphics, and browser/Node-oriented
languages and frameworks.

Exports:
    FILETYPES (list[FileType]): Concrete definitions for HTML, XML, XHTML,
        XSL/XSLT, SVG, JavaScript, TypeScript, CSS, Less, SCSS, Stylus, Vue,
        and Svelte.

Notes:
    - JavaScript/TypeScript allow shebangs for Node.js executables (``#!/usr/bin/env node``).
    - Stylesheet formats generally enforce a blank line after the header block.
"""

from __future__ import annotations

from topmark.filetypes.base import FileType
from topmark.filetypes.checks.xml import xml_can_insert
from topmark.filetypes.policy import FileTypeHeaderPolicy

FILETYPES: list[FileType] = [
    FileType(
        name="css",
        extensions=[".css"],
        filenames=[],
        patterns=[],
        description="Cascading Style Sheets (CSS)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="html",
        extensions=[".html"],
        filenames=[],
        patterns=[],
        description="HyperText Markup Language (HTML)",
        pre_insert_checker=xml_can_insert,
    ),
    FileType(
        name="javascript",
        extensions=[".js", ".mjs", ".cjs", ".jsx"],
        filenames=[],
        patterns=[],
        description="JavaScript sources (*.js, *.mjs, *.cjs, *.jsx)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="less",
        extensions=[".less"],
        filenames=[],
        patterns=[],
        description="Less stylesheets (*.less)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="scss",
        extensions=[".scss"],
        filenames=[],
        patterns=[],
        description="Sass SCSS syntax (*.scss)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="stylus",
        extensions=[".styl"],
        filenames=[],
        patterns=[],
        description="Stylus stylesheets (*.styl)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="svelte",
        extensions=[".svelte"],
        filenames=[],
        patterns=[],
        description="Svelte component files",
    ),
    FileType(
        name="svg",
        extensions=[".svg"],
        filenames=[],
        patterns=[],
        description="Scalable Vector Graphics (SVG)",
        pre_insert_checker=xml_can_insert,
    ),
    FileType(
        name="typescript",
        extensions=[".ts", ".tsx", ".mts", ".cts"],
        filenames=[],
        patterns=[],
        description="TypeScript sources (*.ts, *.tsx, *.mts, *.cts)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="vue",
        extensions=[".vue"],
        filenames=[],
        patterns=[],
        description="Vue Single-File Components",
    ),
    FileType(
        name="xhtml",
        extensions=[".xhtml", ".xht"],
        filenames=[],
        patterns=[],
        description="XHTML documents",
        pre_insert_checker=xml_can_insert,
    ),
    FileType(
        name="xml",
        extensions=[".xml"],
        filenames=["pom.xml"],
        patterns=[],
        description="Extensible Markup Language (XML)",
        pre_insert_checker=xml_can_insert,
    ),
    FileType(
        name="xsl",
        extensions=[".xsl"],
        filenames=[],
        patterns=[],
        description="XSL stylesheets",
        pre_insert_checker=xml_can_insert,
    ),
    FileType(
        name="xslt",
        extensions=[".xslt"],
        filenames=[],
        patterns=[],
        description="XSLT stylesheets",
        pre_insert_checker=xml_can_insert,
    ),
]

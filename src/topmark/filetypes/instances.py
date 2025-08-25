# topmark:header:start
#
#   file         : instances.py
#   file_relpath : src/topmark/filetypes/instances.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File type instances and registry for TopMark.

This module defines concrete singleton instances of FileType used throughout
TopMark for file recognition and header processing. It also builds a registry
mapping file type names to their definitions.
"""

from topmark.config.logging import get_logger
from topmark.filetypes.policy import FileTypeHeaderPolicy

from .base import FileType

logger = get_logger(__name__)

# Note: some FileTypes may set skip_processing=True to recognize-but-skip
# (e.g., JSON, LICENSE, py.typed).

# Alphabetical list of all supported file types (singleton instances).
file_types: list[FileType] = [
    FileType(
        name="c",
        extensions=[".c", ".h"],
        filenames=[],
        patterns=[],
        description="C sources and headers (*.c, *.h)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="cpp",
        extensions=[".cc", ".cxx", ".cpp", ".hh", ".hpp", ".hxx"],
        filenames=[],
        patterns=[],
        description="C++ sources and headers (*.cc, *.cxx, *.cpp, *.hh, *.hpp, *.hxx)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="cs",
        extensions=[".cs"],
        filenames=[],
        patterns=[],
        description="C# sources (*.cs)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="dockerfile",
        extensions=[],
        filenames=["Dockerfile"],
        patterns=[r"Dockerfile(\..+)?"],
        description="Dockerfiles",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="env",
        extensions=[],
        filenames=[".env"],
        patterns=[r"\.env\..*"],
        description="Environment variable definition files (.env, .env.*)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="git-meta",
        extensions=[],
        filenames=[".gitignore", ".gitattributes"],
        patterns=[],
        description="Git metadata files (.gitignore, .gitattributes)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="go",
        extensions=[".go"],
        filenames=[],
        patterns=[],
        description="Go sources (*.go)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="html",
        extensions=[".html"],
        filenames=[],
        patterns=[],
        description="HyperText Markup Language (HTML)",
    ),
    FileType(
        name="ini",
        extensions=[".ini", ".cfg"],
        filenames=[".pypirc", ".pypirc.example", "pip.conf"],
        patterns=[],
        description="INI-style configuration files (*.ini, *.cfg, .pypirc, pip.conf)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="java",
        extensions=[".java"],
        filenames=[],
        patterns=[],
        description="Java sources (*.java)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="javascript",
        extensions=[".js", ".mjs", ".cjs", ".jsx"],
        filenames=[],
        patterns=[],
        description="JavaScript sources (*.js, *.mjs, *.cjs, *.jsx)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="kotlin",
        extensions=[".kt", ".kts"],
        filenames=[],
        patterns=[],
        description="Kotlin sources (*.kt, *.kts)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="license_text",
        extensions=[],
        filenames=["LICENSE", "LICENSE.txt"],
        patterns=[],
        description="License text (keep verbatim)",
        skip_processing=True,
    ),
    FileType(
        name="makefile",
        extensions=[],
        filenames=["Makefile", "makefile"],
        patterns=[],
        description="Make build scripts (Makefile)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="json",
        extensions=[".json"],
        filenames=[],
        patterns=[],
        description="JSON (no comments; unheaderable)",
        skip_processing=True,
    ),
    FileType(
        name="julia",
        extensions=[".jl"],
        filenames=[],
        patterns=[],
        description="Julia source files (*.jl)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="markdown",
        extensions=[".md", ".markdown"],
        filenames=[],
        patterns=[],
        description="MarkDown source files (*.md)",
    ),
    FileType(
        name="perl",
        extensions=[".pl", ".pm"],
        filenames=[],
        patterns=[],
        description="Perl scripts/modules (*.pl, *.pm)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        description="Python source files (*.py)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=r"coding[:=]\s*([-\w.]+)",
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="python-requirements",
        extensions=[],
        filenames=[],
        patterns=[r"requirements.*\.(in|txt)$", r"constraints.*\.txt$"],
        description="Python dependency/constraints files (requirements*.in|txt, constraints*.txt)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="python-typed-marker",
        extensions=[],
        filenames=["py.typed"],
        patterns=[],
        description="PEP 561 marker (single-token file)",
        skip_processing=True,
    ),
    FileType(
        name="r",
        extensions=[".R", ".r"],
        filenames=[],
        patterns=[],
        description="R scripts (*.R, *.r)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="ruby",
        extensions=[".rb"],
        filenames=[],
        patterns=[],
        description="Ruby source files (*.rb)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=r"(coding|encoding)[:=]\s*([-\w.]+)",
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="rust",
        extensions=[".rs"],
        filenames=[],
        patterns=[],
        description="Rust sources (*.rs)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="shell",
        extensions=[".sh", ".bash", ".zsh"],
        filenames=[],
        patterns=[],
        description="POSIX/Bash/Zsh shell scripts",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
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
    ),
    FileType(
        name="swift",
        extensions=[".swift"],
        filenames=[],
        patterns=[],
        description="Swift sources (*.swift)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="toml",
        extensions=[".toml"],
        filenames=[],
        patterns=[],
        description="Tom's Obvious Minimal Language (*.toml)",
    ),
    FileType(
        name="typescript",
        extensions=[".ts", ".tsx", ".mts", ".cts"],
        filenames=[],
        patterns=[],
        description="TypeScript sources (*.ts, *.tsx, *.mts, *.cts)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="vscode-jsonc",
        extensions=[],
        filenames=[".vscode/settings.json", ".vscode/extensions.json"],
        patterns=[],
        description="VS Code JSON with comments (JSONC)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            encoding_line_regex=None,
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
        extensions=[".xhtml"],
        filenames=[],
        patterns=[],
        description="XHTML documents",
    ),
    FileType(
        name="xml",
        extensions=[".xml"],
        filenames=["pom.xml"],
        patterns=[],
        description="Extensible Markup Language (XML)",
    ),
    FileType(
        name="xsl",
        extensions=[".xsl"],
        filenames=[],
        patterns=[],
        description="XSL stylesheets",
    ),
    FileType(
        name="xslt",
        extensions=[".xslt"],
        filenames=[],
        patterns=[],
        description="XSLT stylesheets",
    ),
    FileType(
        name="yaml",
        extensions=[".yaml", ".yml"],
        filenames=[],
        patterns=[],
        description="YAML files (*.yaml, *.yml)",
    ),
]


def _generate_registry() -> dict[str, FileType]:
    """Generate a registry mapping file type names to their definitions.

    This function checks for duplicate or missing file type names
    and builds a dictionary keyed by `FileType.name`.

    Returns:
        dict[str, FileType]: A dictionary of file type name → FileType instance.

    Raises:
        ValueError: If any FileType has a missing or duplicate name.
    """
    registry: dict[str, FileType] = {}
    errors = 0
    for t in file_types:
        if not t.name:
            logger.error("FileType has empty name: %r", t)
            errors += 1
            continue
        if t.name in registry:
            logger.error("Duplicate FileType name: '%s'", t.name)
            errors += 1
            continue
        registry[t.name] = t
    if errors > 0:
        raise ValueError("The File Type registry contains invalid entries. Please fix them.")
    return registry


#: Registry of all file types, keyed by name.
_file_type_registry: dict[str, FileType] = _generate_registry()


def get_file_type_registry() -> dict[str, FileType]:
    """Return the file type registry.

    Returns:
        The file type registry as dict of file type names and FileType instances.
    """
    return _file_type_registry

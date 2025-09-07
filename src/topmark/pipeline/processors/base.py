# topmark:header:start
#
#   file         : base.py
#   file_relpath : src/topmark/pipeline/processors/base.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Header processor base module for TopMark's header processing pipeline.

This module defines the HeaderProcessor base class, which provides a framework for
processing file headers in different file types. It includes logic for scanning,
parsing, and rendering header fields according to comment styles and file extensions.

The module also supports associating processors with file types to enable flexible,
extensible header processing in the TopMark pipeline.
"""

import re

from topmark.config import Config
from topmark.config.logging import get_logger
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.filetypes.base import FileType
from topmark.pipeline.context import ProcessingContext
from topmark.rendering.formats import HeaderOutputFormat

logger = get_logger(__name__)


# Sentinel value when get_header_insertion_index() cannot find an insertion index:
NO_LINE_ANCHOR: int = -1


class HeaderProcessor:
    """Base class for header processors that handle specific file types.

    A *header processor* knows how to **find**, **render**, and **modify** TopMark
    headers for one concrete :class:`~topmark.filetypes.base.FileType`. The registry
    binds a processor instance to a file type at runtime (``proc.file_type = ft``),
    and TopMark uses that pairing during scanning and updates.

    Responsibilities:
        - **Scanning:** Locate existing headers via start/end markers and comment
          affixes (see :meth:`get_header_bounds`, :meth:`line_has_directive`).
        - **Parsing:** Extract key→value pairs from the header payload (see
          :meth:`parse_fields`).
        - **Rendering:** Emit preamble/fields/postamble with proper comment syntax
          (see :meth:`render_preamble_lines`, :meth:`render_header_lines`,
          :meth:`render_postamble_lines`).
        - **Placement policy:** Determine insertion points; default is
          *shebang‑aware* for languages like Python (see
          :meth:`get_header_insertion_index`).
        - **Update/strip helpers:** Prepare insertions and removals in a way that
          preserves surrounding whitespace (see
          :meth:`prepare_header_for_insertion`, :meth:`strip_header_block`).

    What this class does **not** do:
        - **Content‑based recognition.** Deciding *which* file type a path belongs
          to is the role of :class:`~topmark.filetypes.base.FileType` via
          :attr:`FileType.content_matcher`. The processor assumes it is already
          associated with the correct file type.

    Indentation semantics:
        - `header_indent`: indentation *before* the line prefix (used to preserve
          existing indentation when replacing nested/indented headers).
        - `line_indent`: indentation *after* the line prefix (applied to the
          header field lines).

    Extension points:
        Subclasses typically set comment delimiters (``line_prefix``,
        ``line_suffix``, ``block_prefix``, ``block_suffix``) and may override any of
        the hooks documented below to support format‑specific behavior (e.g., XML
        prolog placement or Markdown fences).

    Public API note:
        In the stable public surface, consider typing against a minimal protocol
        rather than this concrete base if you are authoring plugins. The registry
        binds processors to file types and exposes read‑only metadata for common
        integrations.
    """

    file_type: FileType | None = None

    block_prefix: str = ""  # Prefix for block-style headers, if applicable
    block_suffix: str = ""  # Suffix for block-style headers, if applicable
    line_prefix: str = ""  # Prefix for each line in the header block
    line_suffix: str = ""  # Suffix for each line in the header block

    # Indentation **after** the comment prefix (applies to the header field lines).
    line_indent: str = "  "

    # Indentation **before** the line prefix (used to preserve existing indentation
    # when replacing an indented header inside a document, e.g. JSONC nested blocks).
    header_indent: str = ""

    """
    The file type associated with this processor, used for matching files.
    This should be set by the processor implementation.
    """

    def __init__(
        self,
        *,
        block_prefix: str = "",
        block_suffix: str = "",
        line_prefix: str = "",
        line_suffix: str = "",
        line_indent: str = "  ",
        header_indent: str = "",
    ) -> None:
        """Initialize a HeaderProcessor instance.

        Args:
            block_prefix: The prefix string for block-style header start.
            block_suffix: The suffix string for block-style header end.
            line_prefix: The prefix string for each line within the header block.
            line_suffix: The suffix string for each line within the header block.
            line_indent: The indentation applied to *header field lines* **after**
                the comment prefix (e.g., spaces after `//`).
            header_indent: The indentation applied *before* the comment prefix; used
                to preserve existing leading indentation when replacing an indented
                header block inside a document (e.g., nested JSONC).
        """
        self.file_type = None

        self.block_prefix = block_prefix
        self.block_suffix = block_suffix
        self.line_prefix = line_prefix
        self.line_suffix = line_suffix

        self.line_indent = line_indent
        self.header_indent = header_indent

    def parse_fields(self, context: ProcessingContext) -> dict[str, str]:
        """Parse key-value pairs from the detected header block (outer slice).

        This implementation is robust to scanners providing an *outer* slice that may
        include block wrappers and always includes the TopMark START/END marker lines.
        It searches within ``context.existing_header_lines`` for the first START marker
        and the next END marker, then parses only the payload lines between them.

        Args:
            context (ProcessingContext): Pipeline context with ``existing_header_lines``
                set to the outer header slice (markers included).

        Returns:
            dict[str, str]: Mapping of parsed header fields (key → value). Returns an
                empty dict if no payload is found or markers are missing.

        Notes:
            - Comment affixes (``line_prefix`` / ``line_suffix``) are stripped per line.
            - Malformed field lines add diagnostics but do not set MALFORMED; reserve
              MALFORMED for marker issues (normally handled by the scanner).
            - Subclasses may override to support multi-line fields or alternate syntax.
        """
        lines: list[str] | None = context.existing_header_lines
        # TODO: improve
        if not context.existing_header_range or not lines:
            return {}

        logger.info("line count: %d, lines: %s", len(lines), lines)

        # 1) Locate START and END markers *within* the provided slice.
        start_rel, end_rel = self._find_inner_marker_indices(lines)
        if start_rel is None or end_rel is None or end_rel <= start_rel:
            # Keep scanner as the single authority for header MALFORMED status.
            # Here we just surface a diagnostic to aid debugging.
            context.diagnostics.append(
                f"parse_fields(): could not locate a valid START/END marker pair in {context.path}"
            )
            return {}

        # 2) Extract payload (strictly between markers).
        payload = lines[start_rel + 1 : end_rel]
        if not payload:
            return {}

        # 3) Parse lines as `key: value`, stripping comment affixes and whitespace.
        result: dict[str, str] = {}
        # Compute approximate absolute line number for diagnostics if we can.
        abs_start, _ = context.existing_header_range

        for i, raw in enumerate(payload, start=1):
            # Absolute line number in the original file (1-based)
            abs_line_no: int = abs_start + start_rel + i + 1
            logger.trace("Header line %d: [%s]", abs_line_no, raw)

            cleaned = self._strip_line_affixes(raw).strip()
            if not cleaned:
                continue

            if ":" not in cleaned:
                context.diagnostics.append(
                    f"Unrecognized header line at {context.path}:{abs_line_no}: '{raw.rstrip()}'"
                )
                continue

            key, value = cleaned.split(":", 1)
            k = key.strip().lstrip("#")  # tolerate accidental leading '#'
            v = value.strip()
            if not k:
                logger.warning(
                    "Malformed header at line %d: %s",
                    abs_line_no,
                    raw,
                )
                context.diagnostics.append(
                    f"Empty header key at {context.path}:{abs_line_no}: '{raw.rstrip()}'"
                )
                continue
            result[k] = v

        return result

    def _find_inner_marker_indices(self, lines: list[str]) -> tuple[int | None, int | None]:
        """Find START and END marker indices relative to the given slice.

        Returns:
            (start_rel, end_rel) where both are relative indices into `lines`.
            Any of them may be None if not found.
        """
        start_rel: int | None = None
        end_rel: int | None = None

        for i, line in enumerate(lines):
            if self.line_has_directive(line, TOPMARK_START_MARKER):
                start_rel = i
                break

        if start_rel is not None:
            for j in range(start_rel + 1, len(lines)):
                if self.line_has_directive(lines[j], TOPMARK_END_MARKER):
                    end_rel = j
                    break

        return start_rel, end_rel

    def _strip_line_affixes(self, line: str) -> str:
        """Remove configured line prefix/suffix from a single line, if present.

        This mirrors the matching semantics of `line_has_directive()`:
            - If a prefix is configured and present at start, remove it.
            - If a suffix is configured and present at end, remove it.
        Then strip surrounding whitespace.
        """
        cleaned = line.rstrip("\r\n")
        if self.line_prefix and cleaned.lstrip().startswith(self.line_prefix):
            # allow incidental indentation before the prefix
            leading_ws_len = len(cleaned) - len(cleaned.lstrip())
            head = cleaned[leading_ws_len:]
            if head.startswith(self.line_prefix):
                cleaned = cleaned[:leading_ws_len] + head.removeprefix(self.line_prefix)
        elif self.line_prefix and not cleaned.strip().startswith(self.line_prefix):
            # Prefix configured but not present—leave the line as-is; parser tolerates.
            pass

        if self.line_suffix and cleaned.rstrip().endswith(self.line_suffix):
            cleaned = cleaned.removesuffix(self.line_suffix)

        return cleaned.strip()

    def _wrap_line(
        self,
        content: str,
        *,
        newline_style: str,
        line_prefix: str | None = None,
        line_suffix: str | None = None,
        header_indent: str = "",
        after_prefix_indent: str | None = None,
    ) -> str:
        """Wrap a single content line using line prefix/suffix, then append a newline.

        Args:
            content (str): Inner text for the line (without prefixes/suffixes or newline).
            newline_style (str): Newline characters to append (``LF``, ``CR``, ``CRLF``).
            line_prefix (str | None): Optional override for the line prefix; defaults to
                the instance's ``line_prefix`` when ``None``.
            line_suffix (str | None): Optional override for the line suffix; defaults to
                the instance's ``line_suffix`` when ``None``.
            header_indent: The indentation applied *before* the comment prefix; used
                to preserve existing leading indentation when replacing an indented
                header block inside a document (e.g., nested JSONC).
            after_prefix_indent (str | None): Indentation to apply after the line prefix
                (overrides the instance's ``line_indent`` for this line).

        Returns:
            str: The fully wrapped line (prefix + content + suffix) including the trailing
                newline characters.
        """
        lp = self.line_prefix if line_prefix is None else line_prefix
        ls = self.line_suffix if line_suffix is None else line_suffix
        # Pre-prefix indentation is applied to the whole line before the prefix
        lead = header_indent or ""
        # Indentation after prefix defaults to instance setting unless overridden
        api = self.line_indent if after_prefix_indent is None else after_prefix_indent

        parts: list[str] = []
        if lp:
            parts.append(f"{lp}")
        if content:
            # Only add after-prefix indentation when there is content to show
            if api:
                parts.append(api + content.rstrip())
            else:
                parts.append(content.rstrip())
        if ls:
            parts.append(ls)

        return lead + " ".join(parts) + newline_style

    def render_preamble_lines(
        self,
        *,
        newline_style: str,
        block_prefix: str | None = None,
        line_prefix: str | None = None,
        line_suffix: str | None = None,
        header_indent: str = "",
    ) -> list[str]:
        """Render the TopMark preamble lines for the current processor.

        The preamble consists of:
          1) the block comment opener (when configured),
          2) the ``TOPMARK_START_MARKER`` directive line, and
          3) an intentional blank line following the start marker.

        Args:
            newline_style (str): Newline characters to append to each rendered line.
            block_prefix (str | None): Optional override for the block prefix; defaults to
                the instance's ``block_prefix`` when ``None``.
            line_prefix (str | None): Optional override for the line prefix; defaults to
                the instance's ``line_prefix`` when ``None``.
            line_suffix (str | None): Optional override for the line suffix; defaults to
                the instance's ``line_suffix`` when ``None``.
            header_indent: The indentation applied *before* the comment prefix; used
                to preserve existing leading indentation when replacing an indented
                header block inside a document (e.g., nested JSONC).

        Returns:
          list[str]: Preamble lines (each ending with ``newline_style``) that precede
          the header fields.
        """
        bp = self.block_prefix if block_prefix is None else block_prefix
        lines: list[str] = []
        if bp:
            lines.append(header_indent + bp + newline_style)
        lines.append(
            self._wrap_line(
                TOPMARK_START_MARKER,
                newline_style=newline_style,
                line_prefix=line_prefix,
                line_suffix=line_suffix,
                header_indent=header_indent,
                after_prefix_indent="",
            )
        )
        # Empty line after start marker
        lines.append(
            self._wrap_line(
                "",
                newline_style=newline_style,
                line_prefix=line_prefix,
                line_suffix=line_suffix,
                header_indent=header_indent,
                after_prefix_indent="",
            )
        )
        return lines

    def render_postamble_lines(
        self,
        *,
        newline_style: str,
        block_suffix: str | None = None,
        line_prefix: str | None = None,
        line_suffix: str | None = None,
        header_indent: str = "",
    ) -> list[str]:
        """Render the TopMark postamble lines for the current processor.

        The postamble consists of:
          1) an intentional blank line before the end marker,
          2) the ``TOPMARK_END_MARKER`` directive line, and
          3) the block comment closer (when configured).

        Args:
            newline_style (str): Newline characters to append to each rendered line.
            block_suffix (str | None): Optional override for the block suffix; defaults to
                the instance's ``block_suffix`` when ``None``.
            line_prefix (str | None): Optional override for the line prefix; defaults to
                the instance's ``line_prefix`` when ``None``.
            line_suffix (str | None): Optional override for the line suffix; defaults to
                the instance's ``line_suffix`` when ``None``.
            header_indent: The indentation applied *before* the comment prefix; used
                to preserve existing leading indentation when replacing an indented
                header block inside a document (e.g., nested JSONC).

        Returns:
          list[str]: Postamble lines (each ending with ``newline_style``) that follow
          the header fields.
        """
        bs = self.block_suffix if block_suffix is None else block_suffix
        lines: list[str] = []
        # Empty line before end marker
        lines.append(
            self._wrap_line(
                "",
                newline_style=newline_style,
                line_prefix=line_prefix,
                line_suffix=line_suffix,
                header_indent=header_indent,
                after_prefix_indent="",
            )
        )
        lines.append(
            self._wrap_line(
                TOPMARK_END_MARKER,
                newline_style=newline_style,
                line_prefix=line_prefix,
                line_suffix=line_suffix,
                header_indent=header_indent,
                after_prefix_indent="",
            )
        )
        if bs:
            lines.append(bs + newline_style)
        return lines

    def render_header_lines(
        self,
        header_values: dict[str, str],
        config: Config,
        newline_style: str,
        block_prefix_override: str | None = None,
        block_suffix_override: str | None = None,
        line_prefix_override: str | None = None,
        line_suffix_override: str | None = None,
        line_indent_override: str | None = None,
        header_indent_override: str | None = None,
    ) -> list[str]:
        """Render a header block from configuration, template, and overrides.

        This method generates a header string using the configuration's header fields and
        values, optionally overridden by provided header_list and custom_headers. It respects
        alignment and raw_header settings from the configuration to format the output.

        Args:
            header_values (dict[str, str]): Mapping of header fields to render.
            config (Config): TopMark configuration (defines header fields and options).
            newline_style (str): Newline style (``LF``, ``CR``, ``CRLF``).
            block_prefix_override (str | None): Optional block prefix override.
            block_suffix_override (str | None): Optional block suffix override.
            line_prefix_override (str | None): Optional line prefix override.
            line_suffix_override (str | None): Optional line suffix override.
            header_indent_override (str | None): Optional indentation override *before*
                the comment prefix, applied to complete header lines (used to preserve
                existing leading indentation on replace).
            line_indent_override (str | None): Optional indentation override *after*
                the comment prefix, applied to header field lines (defaults to the
                processor's `line_indent`).

        Returns:
          list[str]: Rendered header lines ending with ``newline_style``.

        Notes:
          If ``config.header_format`` is ``HeaderOutputFormat.PLAIN``, the method emits
          a raw/plain header (no prefixes/suffixes/indentation) unless overrides are given.
        """
        assert config, "Config is undefined"

        logger.info(
            "%s: rendering header fields: %s",
            self.__class__.__name__,
            ", ".join(config.header_fields),
        )

        if config.header_format is HeaderOutputFormat.PLAIN:
            # Don't use the config's block_prefix/suffix or
            # line_prefix/suffix, but rather the provided overrides or defaults.
            block_prefix = block_suffix = line_prefix = line_suffix = effective_line_indent = (
                header_indent
            ) = ""
        else:
            # Use provided overrides or defaults from the instance
            block_prefix = (
                block_prefix_override if block_prefix_override is not None else self.block_prefix
            )
            block_suffix = (
                block_suffix_override if block_suffix_override is not None else self.block_suffix
            )
            line_prefix = (
                line_prefix_override if line_prefix_override is not None else self.line_prefix
            )
            line_suffix = (
                line_suffix_override if line_suffix_override is not None else self.line_suffix
            )
            effective_line_indent = (
                line_indent_override if line_indent_override is not None else self.line_indent
            )
            header_indent = (
                header_indent_override if header_indent_override is not None else self.header_indent
            )

        # Compute header field name width:
        width = max(len(k) for k in header_values) + 1 if len(header_values) > 0 else 0

        # Build the header lines
        lines: list[str] = []

        # Compose preamble
        lines.extend(
            self.render_preamble_lines(
                newline_style=newline_style,
                block_prefix=block_prefix,
                line_prefix=line_prefix,
                line_suffix=line_suffix,
                header_indent=header_indent,
            )
        )

        # Field lines (no blanks in-between)
        for field in config.header_fields:
            value = header_values.get(field, "")
            inner = f"{field:<{width}}: {value}" if width else f"{field}: {value}"
            lines.append(
                self._wrap_line(
                    inner,
                    newline_style=newline_style,
                    line_prefix=line_prefix,
                    line_suffix=line_suffix,
                    header_indent=header_indent,
                    after_prefix_indent=effective_line_indent,
                )
            )

        # Compose postamble
        lines.extend(
            self.render_postamble_lines(
                newline_style=newline_style,
                block_suffix=block_suffix,
                line_prefix=line_prefix,
                line_suffix=line_suffix,
                header_indent=header_indent,
            )
        )

        logger.debug("Rendered %d header lines:\n%s", len(lines), "".join(lines))

        return lines

    def get_header_insertion_index(self, file_lines: list[str]) -> int:
        """Determine where to insert the header based on file type policy.

        Default behavior is *shebang-aware*:
          - If the file type policy declares ``supports_shebang=True`` and the first line
            starts with ``#!``, insert the header *after* the shebang (and optional encoding
            line when ``encoding_line_regex`` is provided).
          - Otherwise, insert at the top of file (index 0).

        If inserting after a preamble and the next line is already blank, consume exactly
        one existing blank line so that a single blank separates the preamble from the header.

        Subclasses may override this when a format imposes different placement rules.

        Args:
          file_lines (list[str]): Lines from the file being processed.

        Returns:
          int: Index at which to insert the TopMark header, or ``NO_LINE_ANCHOR`` if
          no insertion index can be found.
        """
        index = 0
        shebang_present = False

        # Shebang handling based on per-file-type policy
        policy = getattr(self.file_type, "header_policy", None)
        if policy and policy.supports_shebang and file_lines and file_lines[0].startswith("#!"):
            shebang_present = True
            index = 1

            # Optional encoding line immediately after shebang (e.g., Python)
            if policy.encoding_line_regex and len(file_lines) > index:
                if re.search(policy.encoding_line_regex, file_lines[index]):
                    index += 1

        # If a shebang block exists and the next line is already blank, consume exactly one
        if shebang_present and index < len(file_lines) and file_lines[index].strip() == "":
            index += 1

        return index

    def line_has_directive(self, line: str, directive: str) -> bool:
        """Check whether a line contains the directive with the expected affixes.

        This method is used by ``get_header_bounds()`` to locate header start/end markers.
        Subclasses may override this method for more flexible or format-specific matching.

        Args:
          line (str): The line of text to check (whitespace is trimmed internally).
          directive (str): The directive string to look for.

        Returns:
          bool: ``True`` if the line contains the directive with the configured
          prefix/suffix, otherwise ``False``.
        """
        line = line.strip()

        # Step 1: Check for the presence of the defined prefix
        if self.line_prefix and not line.startswith(self.line_prefix):
            return False

        # Step 2: Check for the presence of the defined suffix
        if self.line_suffix and not line.endswith(self.line_suffix):
            return False

        # Step 3: Remove the prefix and suffix and check the remaining content
        candidate = line
        if self.line_prefix:
            candidate = candidate.removeprefix(self.line_prefix)
        if self.line_suffix:
            candidate = candidate.removesuffix(self.line_suffix)

        # Step 4: Strip white space after stripped line prefix and before stripped line suffix
        candidate = candidate.strip()

        return candidate == directive

    def validate_header_location(
        self,
        lines: list[str],
        *,
        header_start_idx: int,
        header_end_idx: int,
        anchor_idx: int,
    ) -> bool:
        """Validate that a detected header is at an acceptable location.

        The default policy accepts a candidate header only when its *start* line is
        exactly at the computed anchor or within a small proximity window around it.
        Subclasses may override this to enforce format-specific constraints.

        Args:
            lines (list[str]): Full file content split into lines.
            header_start_idx (int): 0-based index of the candidate header's first line.
            header_end_idx (int): 0-based index of the candidate header's last line (inclusive).
            anchor_idx (int): 0-based index where a header would be inserted per policy.

        Returns:
            bool: ``True`` if the candidate lies within the configured proximity window,
                otherwise ``False``.

        Notes:
            The proximity window can be tuned per file type by defining
            ``scan_window_before`` and ``scan_window_after`` on the associated
            ``FileType``. Defaults are 0 and 2, respectively.
        """
        # Per-file-type tunables (fallback to conservative defaults)
        before = 0
        after = 2
        if self.file_type is not None:
            before = int(getattr(self.file_type, "scan_window_before", before) or 0)
            after = int(getattr(self.file_type, "scan_window_after", after) or 2)

        return (anchor_idx - before) <= header_start_idx <= (anchor_idx + after)

    def get_header_bounds(self, lines: list[str]) -> tuple[int | None, int | None]:
        """Identify the inclusive (start, end) line indices of the TopMark header.

        Supports both line-comment and block-comment styles depending on the processor's
        configuration. Uses :meth:`validate_header_location` to filter candidates near
        the computed insertion anchor.

        Args:
            lines (list[str]): Full list of lines from the file.

        Returns:
            tuple[int | None, int | None]: ``(start_index, end_index)`` (inclusive) when
                a valid header is found, or ``(None, None)`` otherwise.
        """
        anchor_idx = self.get_header_insertion_index(lines) or 0

        if self.block_prefix and self.block_suffix:
            candidates = self._collect_bounds_block_comments(lines)
        else:
            candidates = self._collect_bounds_line_comments(lines)

        for s, e in candidates:
            if self.validate_header_location(
                lines,
                header_start_idx=s,
                header_end_idx=e,
                anchor_idx=anchor_idx,
            ):
                return s, e

        # No valid header near the expected anchor → treat as absent
        return None, None

    def strip_header_block(
        self, *, lines: list[str], span: tuple[int, int] | None = None
    ) -> tuple[list[str], tuple[int, int] | None]:
        """Remove the TopMark header block and return the updated file image.

        This method supports two detection modes:

        1) **Policy-aware detection** (preferred):
           If ``span`` is not provided, the processor calls ``get_header_bounds(lines)``
           to locate a valid header near the computed insertion anchor. This respects
           file-type placement rules (shebang handling, XML prolog, Markdown fences, etc.).

        2) **Permissive fallback** (best-effort):
           If policy-aware detection fails, the method performs a lightweight scan for
           the first ``START``..``END`` marker pair *anywhere* in the file. The scan
           accepts either exact directive matches (prefix/suffix aware) **or** marker
           substrings appearing inside single-line comment wrappers (e.g.,
           ``<!-- TOPMARK_START_MARKER -->`` for XML/HTML/Markdown). This covers older
           files or content transformed by formatters.

        When a header is removed at the very top of the file (``start == 0``), the
        method trims **exactly one** leading blank line that may be left behind by the
        removal to avoid introducing an extra gap.

        Args:
            lines: Full file content split into lines (each typically ending with a newline).
            span: Optional inclusive ``(start, end)`` line index tuple, normally provided by
                the scanner via ``ctx.existing_header_range``. When set, no scanning is performed.

        Returns:
            tuple[list[str], tuple[int, int] | None]:
                ``(new_lines, removed_span)`` where ``removed_span`` is the inclusive
                span actually removed, or ``None`` if no header was found.
        """
        # 1) Resolve bounds: prefer explicit span, else policy-aware detection.
        if span is None:
            # First try the standard, policy-aware bounds detection.
            start, end = self.get_header_bounds(lines)
            span = (start, end) if start is not None and end is not None else None

            if span is None:
                # Permissive scan: accept directive substrings inside single-line
                # comment wrappers (e.g., XML/HTML `<!-- ... -->`).
                # Useful when stripping headers that were inserted by older versions
                # or were moved by formatting tools.
                n = len(lines)
                i = 0
                while i < n:
                    # Accept either exact directive match (prefix/suffix-aware)
                    # or the directive appearing inside a single-line comment wrapper.
                    start_match = self.line_has_directive(lines[i], TOPMARK_START_MARKER) or (
                        TOPMARK_START_MARKER in lines[i]
                    )
                    if start_match:
                        j = i + 1
                        while j < n:
                            end_match = self.line_has_directive(lines[j], TOPMARK_END_MARKER) or (
                                TOPMARK_END_MARKER in lines[j]
                            )
                            if end_match:
                                span = (i, j)
                                break
                            j += 1
                        if span is not None:
                            break
                    i += 1

        # 2) No header? Return original content unchanged.
        if span is None:
            return lines, None

        start, end = span
        # Defensive validation of bounds
        if start < 0 or end < start or end >= len(lines):
            # Defensive: invalid span -> no-op
            return lines, None

        # Remove the block (inclusive header span)
        new_lines = lines[:start] + lines[end + 1 :]

        # Top-of-file cleanup: trim exactly one blank line left by removal.
        if start == 0 and new_lines and new_lines[0].strip() == "":
            new_lines = new_lines[1:]

        return new_lines, (start, end)

    def _collect_bounds_line_comments(self, lines: list[str]) -> list[tuple[int, int]]:
        """Collect all (start,end) pairs for pound-style headers in the file."""
        results: list[tuple[int, int]] = []
        i = 0
        n = len(lines)
        while i < n:
            if self.line_has_directive(lines[i], TOPMARK_START_MARKER):
                start = i
                j = i + 1
                while j < n and not self.line_has_directive(lines[j], TOPMARK_END_MARKER):
                    j += 1
                if j < n and self.line_has_directive(lines[j], TOPMARK_END_MARKER):
                    results.append((start, j))
                    i = j + 1
                    continue
            i += 1
        return results

    def _collect_bounds_block_comments(self, lines: list[str]) -> list[tuple[int, int]]:
        """Collect all header spans for block-comment wrappers (e.g., HTML/XML).

        For each detected START..END pair, prefer returning the wrapper span
        (block_prefix..block_suffix) when both are immediately around the header
        without intervening non-blank content; otherwise return the markers only.
        """
        results: list[tuple[int, int]] = []
        n = len(lines)
        i = 0
        while i < n:
            # Find a START marker
            if not self.line_has_directive(lines[i], TOPMARK_START_MARKER):
                i += 1
                continue
            start_idx = i
            # Find the matching END marker after start
            j = i + 1
            while j < n and not self.line_has_directive(lines[j], TOPMARK_END_MARKER):
                j += 1
            if j >= n:
                break  # unmatched START; stop collecting further
            end_idx = j

            # Try to expand to block_prefix/block_suffix if they tightly wrap the header
            block_start = None
            k = start_idx - 1
            while k >= 0 and lines[k].strip() == "":
                k -= 1
            if k >= 0 and self.block_prefix and lines[k].strip() == self.block_prefix:
                block_start = k

            block_end = None
            k = end_idx + 1
            while k < n and lines[k].strip() == "":
                k += 1
            if k < n and self.block_suffix and lines[k].strip() == self.block_suffix:
                block_end = k

            if (
                block_start is not None
                and block_end is not None
                and block_start < start_idx < end_idx < block_end
            ):
                results.append((block_start, block_end))
            else:
                results.append((start_idx, end_idx))

            i = end_idx + 1
        return results

    def _get_bounds_line_comments(self, lines: list[str]) -> tuple[int | None, int | None]:
        """Identify bounds of a line-comment TopMark header.

        Scans for the first occurrence of ``TOPMARK_START_MARKER`` and the next
        ``TOPMARK_END_MARKER`` using the processor's configured line affixes. This
        helper does no placement validation; callers should apply policy checks.

        Args:
            lines: Full file content split into lines.

        Returns:
            A tuple ``(start_index, end_index)`` where both are 0-based line indices of
            the directive lines (inclusive), or ``(None, None)`` when no pair is found.
        """
        start_index: int | None = None
        end_index: int | None = None

        for i, line in enumerate(lines):
            if self.line_has_directive(line, TOPMARK_START_MARKER):
                start_index = i
                logger.debug("Header start marker found at line %d", i + 1)
                break

        index = 0 if start_index is None else start_index + 1
        for j in range(index, len(lines)):
            if self.line_has_directive(lines[j], TOPMARK_END_MARKER):
                end_index = j
                logger.debug("Header end marker found at line %d", j + 1)
                break

        return start_index, end_index

    def _get_bounds_block_comments(self, lines: list[str]) -> tuple[int | None, int | None]:
        """Identify the bounds of a block-comment-wrapped header (e.g. HTML, XML, Markdown).

        Returns:
            A tuple (start_index, end_index) representing the lines to include (inclusive),
            or (None, None) if not found or malformed.
        """
        block_prefix_index: int | None = None
        header_start_index: int | None = None
        header_end_index: int | None = None
        block_suffix_index: int | None = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if self.block_prefix and stripped == self.block_prefix and block_prefix_index is None:
                block_prefix_index = i
                logger.debug("Block prefix found at line %d", i + 1)
            if self.line_has_directive(line, TOPMARK_START_MARKER) and header_start_index is None:
                header_start_index = i
                logger.debug("Header start marker found at line %d", i + 1)
            if self.line_has_directive(line, TOPMARK_END_MARKER):
                header_end_index = i
                logger.debug("Header end marker found at line %d", i + 1)
            if self.block_suffix and stripped == self.block_suffix:
                block_suffix_index = i
                logger.debug("Block suffix found at line %d", i + 1)

        if header_start_index is None or header_end_index is None:
            return None, None

        # If a block comment wrapper is used, return its full span
        if block_prefix_index is not None and block_suffix_index is not None:
            return block_prefix_index, block_suffix_index

        # Fallback: return just the header markers
        return header_start_index, header_end_index

    def prepare_header_for_insertion(
        self,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
    ) -> list[str]:
        """Adjust whitespace around the header for line-based insertion.

        Default implementation returns ``rendered_header_lines`` unchanged. Subclasses
        can override to add/remove leading or trailing blank lines depending on
        surrounding context.

        Args:
            original_lines (list[str]): The original file lines.
            insert_index (int): Line index at which the header will be inserted.
            rendered_header_lines (list[str]): The header lines to insert.

        Returns:
            list[str]: Possibly modified header lines to insert at ``insert_index``.
        """
        return rendered_header_lines

    def get_header_insertion_char_offset(self, original_text: str) -> int | None:
        """Return a character offset for text-based insertion, or ``None``.

        This hook enables processors to compute non line-based insertion points
        (e.g., XML prolog-aware placement when declaration/DOCTYPE and content appear
        on the same line). Returning ``None`` signals that the pipeline should fall
        back to the standard line-based insertion path.

        Args:
            original_text (str): Full file content as a single string.

        Returns:
            int | None: 0-based character offset at which to insert, or ``None`` to
                use the line-based insertion strategy.
        """
        return None

    def prepare_header_for_insertion_text(
        self,
        original_text: str,
        insert_offset: int,
        rendered_header_text: str,
    ) -> str:
        """Adjust the rendered header *text* before text-based insertion.

        Subclasses may override this to add or trim surrounding newlines so the header
        block sits on its own lines when performing text-based insertion.

        Args:
            original_text (str): Full file content as a single string.
            insert_offset (int): 0-based character offset where the header will be inserted.
            rendered_header_text (str): The header block as a single string.

        Returns:
            str: The (possibly modified) header text to splice into ``original_text`` at
                ``insert_offset``.
        """
        return rendered_header_text

# topmark:header:start
#
#   project      : TopMark
#   file         : base.py
#   file_relpath : src/topmark/processors/base.py
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

Placement strategies
--------------------
TopMark supports two complementary placement strategies:

* **Line-based insertion** (default): processors return a line anchor from
  `get_header_insertion_index()`; pipeline steps use `compute_insertion_anchor()`
  as the façade to obtain that anchor.
* **Character-offset insertion** (for positional formats like XML/HTML): processors
  return `NO_LINE_ANCHOR` from `get_header_insertion_index()` and implement
  `get_header_insertion_char_offset()` to compute a byte/character offset.

The pipeline first attempts text-based insertion when a char offset is provided;
otherwise it falls back to the line-based strategy using the computed anchor.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import ClassVar
from typing import Final
from typing import Literal
from typing import Protocol
from typing import final

from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_NAMESPACE
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.logging import get_logger
from topmark.pipeline.policy_whitespace import is_pure_spacer
from topmark.processors.types import BoundsKind
from topmark.processors.types import HeaderBounds
from topmark.processors.types import HeaderFieldValidationIssue
from topmark.processors.types import HeaderFieldValidationResult
from topmark.processors.types import HeaderParseResult
from topmark.processors.types import StripDiagKind
from topmark.processors.types import StripDiagnostic
from topmark.processors.types import StripHeaderResult
from topmark.registry.identity import make_qualified_key
from topmark.registry.identity import owner_label
from topmark.registry.identity import require_and_validate_registry_identity
from topmark.registry.identity import validate_reserved_topmark_namespace

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence

    from topmark.core.logging import TopmarkLogger
    from topmark.diagnostic.model import MutableDiagnosticLog
    from topmark.filetypes.model import FileType
    from topmark.filetypes.policy import FileTypeHeaderPolicy
    from topmark.pipeline.views import HeaderView
    from topmark.pipeline.views import Views


class RuntimeConfigLike(Protocol):
    """Minimal structural subset of `FrozenConfig` required by `HeaderProcessor`.

    This protocol keeps [`topmark.processors.base`][topmark.processors.base]
    independent from the full runtime [`FrozenConfig`][topmark.config.model.FrozenConfig]
    model and avoids import cycles. Only the fields actually consumed by
    [`render_header_lines()`][topmark.processors.base.HeaderProcessor.render_header_lines]
    are included here.
    """

    @property
    def header_fields(self) -> tuple[str, ...]:
        """List of header fields from the [header] section."""
        ...

    @property
    def align_fields(self) -> bool | None:
        """Whether to align fields, from [formatting]."""
        ...

    @property
    def max_header_line_length(self) -> int | None:
        """Optional soft maximum physical header-line length."""
        ...

    @property
    def wrap_fields(self) -> tuple[str, ...]:
        """Ordered field names eligible for automatic folded wrapping."""
        ...


class ProcessingContextLike(Protocol):
    """Minimal structural subset of `ProcessingContext` required by `HeaderProcessor`.

    This protocol keeps `topmark.processors.base` independent from the full
    pipeline context model and avoids import cycles. Only the views bundle and
    diagnostic sink methods needed by processor helpers are included here.
    """

    @property
    def views(self) -> Views:
        """Pipeline view bundle used by processor helpers."""
        ...

    @property
    def diagnostics(self) -> MutableDiagnosticLog:
        """Mutable diagnostic sink used by processor helpers."""
        ...


logger: TopmarkLogger = get_logger(__name__)


# Sentinel value when get_header_insertion_index() cannot find an insertion index:
NO_LINE_ANCHOR: Final[int] = -1

_CONTINUATION_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*(\|=|\||>=|>)")
_FIELD_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<name>[^:]+?)(?P<padding> *):(?P<tail>.*)$")
_SPACE_RUN_RE: Final[re.Pattern[str]] = re.compile(r" +")


def normalize_semantic_newlines(
    value: str,
) -> str:
    """Normalize CRLF and CR semantic newlines to LF."""
    return value.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True, kw_only=True, slots=True)
class _ContinuationRecord:
    """One decoded continuation record."""

    mode: Literal["literal", "folded"]
    value: str
    exact: bool


def _equals_affix_ignoring_space_tab(line: str, affix: str) -> bool:
    """Return True if `line` equals `affix` when ignoring only spaces/tabs and EOLs.

    We intentionally do *not* use `str.strip()` here because it removes all
    Unicode whitespace (including control chars like form-feed). For block
    affix equality we want to allow incidental spaces/tabs around the affix,
    but preserve any other leading characters as significant.
    """
    s: str = line.rstrip("\r\n").strip(" \t")
    return s == (affix or "")


class HeaderProcessor:
    """Base class for header processors that handle specific file types.

    A *header processor* knows how to **find**, **render**, and **modify** TopMark
    headers for one concrete [`topmark.filetypes.model.FileType`][].
    The registry binds a processor instance to a file type at runtime (``proc.file_type = ft``),
    and TopMark uses that pairing during scanning and updates.

    Responsibilities:
        - **Scanning:** Locate existing headers via start/end markers and comment
          affixes (see `get_header_bounds`, `line_has_directive`).
        - **Parsing:** Extract key→value pairs from the header payload (see
          `parse_fields`).
        - **Rendering:** Emit preamble/fields/postamble with proper comment syntax
          (see `render_preamble_lines`, `render_header_lines`,
          `render_postamble_lines`).
        - **Placement policy:** Determine insertion points; default is
          *shebang-aware* for languages like Python (see
          `get_header_insertion_index`).
        - **Update/strip helpers:** Prepare insertions and removals in a way that
          preserves surrounding whitespace (see
          `prepare_header_for_insertion`, `strip_header_block`).

    What this class does **not** do:
        - **Content-based recognition.** Deciding *which* file type a path belongs
          to is the role of [`topmark.filetypes.model.FileType`][] via
          `FileType.content_matcher`. The processor assumes it is already
          associated with the correct file type.

    Indentation semantics:
        - `header_indent`: indentation *before* the line prefix (used to preserve
          existing indentation when replacing nested/indented headers).
        - `line_indent`: indentation *after* the line prefix (applied to the
          header field lines).

    Extension points:
        Subclasses typically set comment delimiters (``line_prefix``,
        ``line_suffix``, ``block_prefix``, ``block_suffix``) and may override any of
        the hooks documented below to support format-specific behavior (e.g., XML
        prolog placement or Markdown fences).

    Placement strategies:
        - **Line-based** (default): override `get_header_insertion_index()` if needed.
          Pipeline steps call `compute_insertion_anchor()` as a stable façade.
        - **Character-offset** (XML/HTML-like): return `NO_LINE_ANCHOR` from
          `get_header_insertion_index()` and implement
          `get_header_insertion_char_offset()`; the pipeline will prefer this path.

    Public API note:
        In the stable public surface, consider typing against a minimal protocol
        rather than this concrete base if you are authoring plugins. The registry
        binds processors to file types and exposes read-only metadata for common
        integrations.

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

    Attributes:
        namespace: Processor namespace class metadata.
        local_key: Unique processor identity class metadata within its namespace.
        description: Human-readable processor description class metadata.
        file_type: The `FileType` bound to this processor instance by the registry.
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

    namespace: ClassVar[str] = TOPMARK_NAMESPACE
    local_key: ClassVar[str] = "base"
    description: ClassVar[str] = (
        "Base header processor class. All header processor classes must subclass this class."
    )

    @property
    def qualified_key(self) -> str:
        """Return the qualified identity key for this processor.

        Format: ``"<namespace>:<local_key>"``.
        """
        cls: type[HeaderProcessor] = type(self)
        return make_qualified_key(cls.namespace, cls.local_key)

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Validate processor identity attributes on subclasses.

        Every concrete `HeaderProcessor` subclass must define a stable identity:

        - `namespace`: non-empty string identifying the producer. Built-in processors use the
          reserved [`TOPMARK_NAMESPACE`][topmark.core.constants.TOPMARK_NAMESPACE].
        - `local_key`: non-empty string identifying the processor within its namespace.

        Constraints (kept intentionally strict so keys are stable and easy to serialize):

        - Lowercase ASCII only.
        - Must not contain ':' (reserved separator for qualified keys).
        - Allowed characters are defined by
          [`VALID_REGISTRY_TOKEN_RE`][topmark.core.constants.VALID_REGISTRY_TOKEN_RE].

        Uniqueness of the qualified key (``"<namespace>:<local_key>"``) is validated at registry
        composition time.
        """
        super().__init_subclass__(**kwargs)

        owner: Final[str] = owner_label(cls)

        namespace: str
        local_key: str
        namespace, local_key = require_and_validate_registry_identity(
            namespace=getattr(cls, "namespace", None),
            local_key=getattr(cls, "local_key", None),
            owner=owner,
        )

        # Normalize validated identity values on the subclass.
        cls.namespace = namespace
        cls.local_key = local_key

        # Reserve the builtin namespace for TopMark itself.
        validate_reserved_topmark_namespace(
            namespace=namespace,
            owner=owner,
            owner_module=cls.__module__,
            entities="processors",
        )

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

    def __init__(
        self,
        *,
        block_prefix: str | None = None,
        block_suffix: str | None = None,
        line_prefix: str | None = None,
        line_suffix: str | None = None,
        line_indent: str | None = None,
        header_indent: str | None = None,
    ) -> None:
        self.file_type = None

        if block_prefix is not None:
            self.block_prefix = block_prefix
        if block_suffix is not None:
            self.block_suffix = block_suffix
        if line_prefix is not None:
            self.line_prefix = line_prefix
        if line_suffix is not None:
            self.line_suffix = line_suffix
        if line_indent is not None:
            self.line_indent = line_indent
        if header_indent is not None:
            self.header_indent = header_indent

        # Cache for per-policy encoding regex to avoid recompilation
        self._encoding_pattern: re.Pattern[str] | None = None
        self._encoding_pattern_src: str | None = None

    def parse_fields(self, context: ProcessingContextLike) -> HeaderParseResult:
        """Parse key-value pairs from the detected header block (*view-based*).

        This implementation expects the scanner to have populated
        `context.header` with an outer slice (markers included). It searches
        within ``context.header.lines`` for the first START marker and the next END
        marker, then parses only the payload lines between them.

        Args:
            context: Pipeline context where ``header`` has been set to a
                [`topmark.pipeline.views.HeaderView`][] (range/lines/block/mapping).

        Returns:
            Parsed mapping and per-line success/error counters.

        Raises:
            RuntimeError: If the internal continuation decoder violates its
                record-or-error invariant.

        Notes:
            - Physical newlines and comment affixes are removed before field parsing.
            - Empty field openers are promoted after two literal records or one folded record.
            - Malformed logical fields add safe diagnostics but do not mutate
              ``context.status.header`` (handled by the scanner).
        """
        # Keep track of processed header entries (lines)
        cnt_header_ok: int = 0
        cnt_header_error: int = 0

        empty_result = HeaderParseResult()

        hv: HeaderView | None = context.views.header
        if hv is None or hv.range is None or hv.lines is None:
            return HeaderParseResult(
                fields={}, success_count=cnt_header_ok, error_count=cnt_header_error
            )

        # Operate on the header lines as provided by the scanner (outer slice).
        lines: list[str] = list(hv.lines)
        if not lines:
            return empty_result

        # 1) Locate START and END markers *within* the provided slice.
        start_rel: int | None
        end_rel: int | None
        start_rel, end_rel = self._find_inner_marker_indices(lines)
        if start_rel is None or end_rel is None or end_rel <= start_rel:
            # Keep scanner as the single authority for MALFORMED; just surface a diagnostic.
            context.diagnostics.add_error(
                "parse_fields(): could not locate a valid START/END marker pair."
            )
            return empty_result

        # 2) Extract payload (strictly between markers).
        payload: list[str] = lines[start_rel + 1 : end_rel]
        if not payload:
            return empty_result

        # 3) Parse ordinary fields and explicit continuation records.
        header_mapping: dict[str, str] = {}
        # Compute approximate absolute line number for diagnostics if we can.
        abs_start: int
        _abs_end: int
        abs_start, _abs_end = hv.range

        pending_name: str | None = None
        pending_index: int | None = None
        pending_records: list[_ContinuationRecord] = []
        pending_mode: Literal["literal", "folded"] | None = None
        pending_malformed = False
        last_was_ordinary = False

        def field_label(
            field_index: int | None,
        ) -> str:
            """Return a safe one-based field position."""
            return f"field #{(field_index if field_index is not None else cnt_header_ok) + 1}"

        def diagnose(
            code: str,
            line_no: int,
            field_index: int | None = None,
        ) -> None:
            """Add one safe continuation diagnostic."""
            context.diagnostics.add_error(
                f"{code} at {field_label(field_index)}, physical line {line_no}."
            )

        def commit_field(
            name: str,
            value: str,
            *,
            field_index: int,
            line_no: int,
        ) -> bool:
            """Validate and commit one complete semantic field."""
            validation: HeaderFieldValidationResult = self.validate_header_fields(
                field_names=(name,),
                header_values={name: value},
            )
            if validation.is_valid:
                header_mapping[name] = value
                return True
            for issue in validation.issues:
                context.diagnostics.add_error(
                    f"{issue.rule} at {field_label(field_index)}, physical line {line_no}."
                )
            return False

        def close_pending(
            line_no: int,
        ) -> None:
            """Commit or reject the pending empty/scalar field exactly once."""
            nonlocal cnt_header_ok
            nonlocal cnt_header_error
            nonlocal pending_name
            nonlocal pending_index
            nonlocal pending_records
            nonlocal pending_mode
            nonlocal pending_malformed
            nonlocal last_was_ordinary

            if pending_name is None:
                return
            if pending_malformed:
                cnt_header_error += 1
                last_was_ordinary = False
            elif pending_mode is None:
                if commit_field(
                    pending_name,
                    "",
                    field_index=pending_index if pending_index is not None else cnt_header_ok,
                    line_no=line_no,
                ):
                    cnt_header_ok += 1
                    last_was_ordinary = True
                else:
                    cnt_header_error += 1
                    last_was_ordinary = False
            elif pending_mode == "literal" and len(pending_records) < 2:
                diagnose(
                    "header:scalar-too-short",
                    line_no,
                    pending_index,
                )
                cnt_header_error += 1
                last_was_ordinary = False
            else:
                if pending_mode == "literal":
                    semantic_value: str = "\n".join(record.value for record in pending_records)
                else:
                    first_record, *remaining_records = pending_records
                    folded_parts: list[str] = [first_record.value]
                    for record in remaining_records:
                        if not record.exact:
                            folded_parts.append(" ")
                        folded_parts.append(record.value)
                    semantic_value = "".join(folded_parts)
                if commit_field(
                    pending_name,
                    semantic_value,
                    field_index=pending_index if pending_index is not None else cnt_header_ok,
                    line_no=line_no,
                ):
                    cnt_header_ok += 1
                else:
                    cnt_header_error += 1
                last_was_ordinary = False

            pending_name = None
            pending_index = None
            pending_records = []
            pending_mode = None
            pending_malformed = False

        i = 0
        while i < len(payload):
            raw: str = payload[i]
            # Absolute line number in the original file (1-based)
            abs_line_no: int = abs_start + start_rel + i + 2
            logger.trace("Header line %d: [%s]", abs_line_no, raw)

            inner: str
            affix_valid: bool
            inner, affix_valid = self._remove_line_affixes(raw)
            cleaned: str = inner.lstrip(" \t")
            continuation_like: bool = _CONTINUATION_TOKEN_RE.match(cleaned) is not None

            if not cleaned.strip(" \t"):
                close_pending(abs_line_no)
                last_was_ordinary = False
                i += 1
                continue

            record: _ContinuationRecord | None = None
            record_error: str | None = None
            if continuation_like:
                if not affix_valid:
                    record_error = "header:invalid-continuation-affix"
                else:
                    record, record_error = self._parse_continuation_record(cleaned)

            if continuation_like:
                if pending_name is None:
                    code: str
                    if record_error is not None:
                        code = record_error
                    elif last_was_ordinary:
                        code = "header:continuation-after-scalar"
                    else:
                        code = "header:orphan-continuation"
                    diagnose(code, abs_line_no)
                    cnt_header_error += 1
                    last_was_ordinary = False
                    i += 1
                    continue

                if pending_malformed:
                    i += 1
                    continue

                if record_error is not None:
                    diagnose(
                        record_error,
                        abs_line_no,
                        pending_index,
                    )
                    pending_malformed = True
                    i += 1
                    continue

                if record is None:  # pragma: no cover - exhaustive internal guard
                    raise RuntimeError("Continuation parser returned no record or error")

                if pending_mode is None:
                    pending_mode = record.mode
                    pending_records.append(record)
                elif pending_mode != record.mode:
                    diagnose(
                        "header:mixed-scalar-mode",
                        abs_line_no,
                        pending_index,
                    )
                    pending_malformed = True
                else:
                    pending_records.append(record)
                i += 1
                continue

            field_match: re.Match[str] | None = _FIELD_RE.fullmatch(cleaned)
            if field_match is not None:
                close_pending(abs_line_no)
                key: str = field_match.group("name").strip()
                tail: str = field_match.group("tail")
                value: str = tail[1:] if tail.startswith(" ") else tail
                value = value.strip()
                if value == "":
                    pending_name = key
                    pending_index = cnt_header_ok + cnt_header_error
                    pending_records = []
                    pending_mode = None
                    pending_malformed = False
                    last_was_ordinary = False
                else:
                    field_index: int = cnt_header_ok + cnt_header_error
                    if commit_field(
                        key,
                        value,
                        field_index=field_index,
                        line_no=abs_line_no,
                    ):
                        cnt_header_ok += 1
                        last_was_ordinary = True
                    else:
                        cnt_header_error += 1
                        last_was_ordinary = False
                i += 1
                continue

            if pending_name is not None:
                if pending_mode is None:
                    close_pending(abs_line_no)
                else:
                    diagnose(
                        "header:missing-continuation-body",
                        abs_line_no,
                        pending_index,
                    )
                    pending_malformed = True
                    i += 1
                    continue

            if ":" not in cleaned:
                context.diagnostics.add_error(
                    f"Malformed header at physical line {abs_line_no} (no colon found)."
                )
            else:
                context.diagnostics.add_error(
                    f"Malformed header at physical line {abs_line_no} (empty text before colon)."
                )
            cnt_header_error += 1
            last_was_ordinary = False
            i += 1

        end_line_no: int = abs_start + end_rel + 1
        close_pending(end_line_no)

        return HeaderParseResult(
            fields=header_mapping,
            success_count=cnt_header_ok,
            error_count=cnt_header_error,
        )

    @final
    def validate_header_fields(
        self,
        *,
        field_names: Sequence[str],
        header_values: Mapping[str, str],
        config: RuntimeConfigLike | None = None,
        header_indent_override: str | None = None,
    ) -> HeaderFieldValidationResult:
        """Validate the exact ordered fields that would be rendered.

        Shared TopMark serialization rules are always evaluated first. Each
        field is then passed to `validate_processor_field` so subclasses can
        add grammar-specific constraints without duplicating the shared rules.

        Args:
            field_names: Ordered configured field names to serialize.
            header_values: Selected field values; missing names use the same
                empty-string fallback as rendering.
            config: Optional effective formatting configuration. When supplied,
                encoded-line hooks receive the exact canonical ordinary, literal,
                or folded payload lines selected for rendering.
            header_indent_override: Optional preserved pre-prefix indentation used
                for complete-line wrapping measurement.

        Returns:
            Immutable, deterministically ordered validation issues.
        """
        issues: list[HeaderFieldValidationIssue] = []
        width: int = (
            max((len(name) for name in header_values), default=0) + 1
            if config is not None and config.align_fields and header_values
            else 0
        )
        effective_header_indent: str = (
            header_indent_override if header_indent_override is not None else self.header_indent
        )

        def measure_payload_line(inner: str, continuation: bool) -> int:
            """Return the default complete physical line length for validation."""
            return len(
                self._wrap_line(
                    inner,
                    newline_style="",
                    line_prefix=self.line_prefix,
                    line_suffix=self.line_suffix,
                    header_indent=effective_header_indent,
                    after_prefix_indent=(
                        self.line_indent + "  " if continuation else self.line_indent
                    ),
                )
            )

        for field_index, field_name in enumerate(field_names):
            field_value: str = normalize_semantic_newlines(header_values.get(field_name, ""))

            if not field_name:
                issues.append(
                    self._field_validation_issue(
                        field_index=field_index,
                        field_name=field_name,
                        target="name",
                        rule="name:empty",
                    )
                )
            elif field_name != field_name.strip():
                issues.append(
                    self._field_validation_issue(
                        field_index=field_index,
                        field_name=field_name,
                        target="name",
                        rule="name:not-round-trippable",
                    )
                )

            if ":" in field_name:
                issues.append(
                    self._field_validation_issue(
                        field_index=field_index,
                        field_name=field_name,
                        target="name",
                        rule="name:colon",
                    )
                )

            issues.extend(
                self._validate_generic_field_content(
                    field_index=field_index,
                    field_name=field_name,
                    target="name",
                    content=field_name,
                )
            )
            issues.extend(
                self._validate_generic_field_content(
                    field_index=field_index,
                    field_name=field_name,
                    target="value",
                    content=field_value,
                )
            )
            issues.extend(
                self.validate_processor_field(
                    field_index=field_index,
                    field_name=field_name,
                    field_value=field_value,
                )
            )
            for encoded_line in self._encode_field_lines(
                field_name=field_name,
                field_value=field_value,
                width=width,
                max_line_length=(
                    config.max_header_line_length
                    if config is not None
                    and config.max_header_line_length is not None
                    and field_name in config.wrap_fields
                    and "\n" not in field_value
                    else None
                ),
                measure_line=measure_payload_line,
            ):
                issues.extend(
                    self.validate_processor_encoded_line(
                        field_index=field_index,
                        field_name=field_name,
                        field_value=field_value,
                        encoded_line=encoded_line,
                    )
                )

        return HeaderFieldValidationResult(issues=tuple(issues))

    def validate_processor_field(
        self,
        *,
        field_index: int,
        field_name: str,
        field_value: str,
    ) -> tuple[HeaderFieldValidationIssue, ...]:
        """Return processor-specific issues for one field.

        Custom processors may override this additive hook. Shared rules remain
        owned by `validate_header_fields` and must not be repeated.

        Args:
            field_index: Zero-based position in the configured field sequence.
            field_name: Field name to validate.
            field_value: Effective value that would be rendered.

        Returns:
            Processor-specific issues in deterministic rule order.
        """
        return ()

    def validate_processor_encoded_line(
        self,
        *,
        field_index: int,
        field_name: str,
        field_value: str,
        encoded_line: str,
    ) -> tuple[HeaderFieldValidationIssue, ...]:
        """Return processor-specific issues for one encoded payload line.

        This additive hook runs after shared semantic validation and before
        processor affixes are applied. Custom processors may add restrictions
        but cannot replace shared validation or continuation encoding.
        """
        return ()

    @staticmethod
    def _field_validation_issue(
        *,
        field_index: int,
        field_name: str,
        target: str,
        rule: str,
    ) -> HeaderFieldValidationIssue:
        """Build a typed validation issue for an internal validation rule."""
        if target == "name":
            normalized_target = "name"
        elif target == "value":
            normalized_target = "value"
        else:  # pragma: no cover - internal exhaustive guard
            raise ValueError(f"Unsupported header field validation target: {target}")
        return HeaderFieldValidationIssue(
            field_index=field_index,
            field_name=field_name,
            target=normalized_target,
            rule=rule,
        )

    def _validate_generic_field_content(
        self,
        *,
        field_index: int,
        field_name: str,
        target: str,
        content: str,
    ) -> tuple[HeaderFieldValidationIssue, ...]:
        """Return shared content violations for a field name or value."""
        issues: list[HeaderFieldValidationIssue] = []

        def add(rule: str) -> None:
            issues.append(
                self._field_validation_issue(
                    field_index=field_index,
                    field_name=field_name,
                    target=target,
                    rule=rule,
                )
            )

        if target == "name" and ("\r" in content or "\n" in content):
            add("content:line-break")
        if "\0" in content:
            add("content:nul")
        if any(
            unicodedata.category(char) == "Cc" and char not in {"\r", "\n", "\0"}
            for char in content
        ):
            add("content:control-character")
        if TOPMARK_START_MARKER in content:
            add("content:reserved-start-marker")
        if TOPMARK_END_MARKER in content:
            add("content:reserved-end-marker")
        if "\u2028" in content or "\u2029" in content:
            add("content:unicode-line-separator")

        return tuple(issues)

    @staticmethod
    def _parse_continuation_record(
        cleaned: str,
    ) -> tuple[_ContinuationRecord | None, str | None]:
        """Decode one affix-free continuation record."""
        mode: Literal["literal", "folded"] = "literal" if cleaned.startswith("|") else "folded"
        token: str = "|" if mode == "literal" else ">"
        exact_token: str = f"{token}="

        if cleaned == token:
            if mode == "folded":
                return None, "header:missing-continuation-body"
            return _ContinuationRecord(mode=mode, value="", exact=False), None

        if cleaned.startswith(exact_token):
            remainder: str = cleaned[len(exact_token) :]
            if not remainder or remainder == " ":
                return None, "header:missing-continuation-body"
            if not remainder.startswith(' "'):
                return None, "header:invalid-continuation-string"
            quoted: str = remainder[1:]
            if len(quoted) < 2 or not quoted.startswith('"') or not quoted.endswith('"'):
                return None, "header:invalid-continuation-string"
            body: str = quoted[1:-1]
            decoded: list[str] = []
            index = 0
            while index < len(body):
                char: str = body[index]
                if char == "\\":
                    index += 1
                    if index >= len(body) or body[index] not in {'"', "\\"}:
                        return None, "header:invalid-continuation-string"
                    decoded.append(body[index])
                elif char == '"':
                    return None, "header:invalid-continuation-string"
                else:
                    decoded.append(char)
                index += 1
            value: str = "".join(decoded)
        elif cleaned.startswith(f"{token} "):
            value = cleaned[2:]
            if not value:
                return None, "header:missing-continuation-body"
            if value != value.strip(" \t"):
                return None, "header:invalid-continuation-character"
        else:
            return None, "header:missing-continuation-body"

        if any(
            unicodedata.category(char) == "Cc" or char in {"\u2028", "\u2029"} for char in value
        ):
            return None, "header:invalid-continuation-character"
        return _ContinuationRecord(
            mode=mode,
            value=value,
            exact=cleaned.startswith(exact_token),
        ), None

    def _find_inner_marker_indices(self, lines: list[str]) -> tuple[int | None, int | None]:
        """Find START and END marker indices relative to the given slice.

        Args:
            lines: The lines in which to search for the START and END markers.

        Returns:
            Tuple `(start_rel, end_rel)` where both are relative indices into `lines`.
            Any of them may be `None` if not found.
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

    def _remove_line_affixes(
        self,
        line: str,
    ) -> tuple[str, bool]:
        """Remove physical newline and required affixes while preserving layout."""
        cleaned: str = line
        if cleaned.endswith("\r\n"):
            cleaned = cleaned[:-2]
        elif cleaned.endswith(("\r", "\n")):
            cleaned = cleaned[:-1]

        valid = True
        if self.line_prefix:
            leading_len: int = len(cleaned) - len(cleaned.lstrip(" \t"))
            head: str = cleaned[leading_len:]
            if head.startswith(self.line_prefix):
                cleaned = head.removeprefix(self.line_prefix)
            else:
                valid = False

        if self.line_suffix:
            without_layout: str = cleaned.rstrip(" \t")
            if without_layout.endswith(self.line_suffix):
                cleaned = without_layout.removesuffix(self.line_suffix)
                if cleaned.endswith(" "):
                    cleaned = cleaned[:-1]
            else:
                valid = False

        return cleaned, valid

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
            content: Inner text for the line (without prefixes/suffixes or newline).
            newline_style: Newline characters to append (``LF``, ``CR``, ``CRLF``).
            line_prefix: Optional override for the line prefix; defaults to
                the instance's ``line_prefix`` when ``None``.
            line_suffix: Optional override for the line suffix; defaults to
                the instance's ``line_suffix`` when ``None``.
            header_indent: The indentation applied *before* the comment prefix; used
                to preserve existing leading indentation when replacing an indented
                header block inside a document (e.g., nested JSONC).
            after_prefix_indent: Indentation to apply after the line prefix
                (overrides the instance's ``line_indent`` for this line).

        Returns:
            str: The fully wrapped line (prefix + content + suffix) including the trailing
                newline characters.

        Raises:
            ValueError: If `content` contains a raw CR or LF character.
        """
        if "\r" in content or "\n" in content:
            raise ValueError("A physical header line cannot contain CR or LF")

        lp: str = self.line_prefix if line_prefix is None else line_prefix
        ls: str = self.line_suffix if line_suffix is None else line_suffix
        # Pre-prefix indentation is applied to the whole line before the prefix
        lead: str = header_indent or ""
        # Indentation after prefix defaults to instance setting unless overridden
        api: str = self.line_indent if after_prefix_indent is None else after_prefix_indent

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
            newline_style: Newline characters to append to each rendered line.
            block_prefix: Optional override for the block prefix; defaults to
                the instance's ``block_prefix`` when ``None``.
            line_prefix: Optional override for the line prefix; defaults to
                the instance's ``line_prefix`` when ``None``.
            line_suffix: Optional override for the line suffix; defaults to
                the instance's ``line_suffix`` when ``None``.
            header_indent: The indentation applied *before* the comment prefix; used
                to preserve existing leading indentation when replacing an indented
                header block inside a document (e.g., nested JSONC).

        Returns:
            Preamble lines (each ending with ``newline_style``) that precede the header fields.
        """
        bp: str = self.block_prefix if block_prefix is None else block_prefix
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
            newline_style: Newline characters to append to each rendered line.
            block_suffix: Optional override for the block suffix; defaults to
                the instance's ``block_suffix`` when ``None``.
            line_prefix: Optional override for the line prefix; defaults to
                the instance's ``line_prefix`` when ``None``.
            line_suffix: Optional override for the line suffix; defaults to
                the instance's ``line_suffix`` when ``None``.
            header_indent: The indentation applied *before* the comment prefix; used
                to preserve existing leading indentation when replacing an indented
                header block inside a document (e.g., nested JSONC).

        Returns:
            Postamble lines (each ending with ``newline_style``) that follow the header fields.
        """
        bs: str = self.block_suffix if block_suffix is None else block_suffix
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
            lines.append(header_indent + bs + newline_style)
        return lines

    def render_header_lines(
        self,
        header_values: Mapping[str, str],
        config: RuntimeConfigLike,
        newline_style: str,
        block_prefix_override: str | None = None,
        block_suffix_override: str | None = None,
        line_prefix_override: str | None = None,
        line_suffix_override: str | None = None,
        line_indent_override: str | None = None,
        header_indent_override: str | None = None,
        soft_overflow_fields: set[str] | None = None,
    ) -> list[str]:
        """Render a header block from configuration, template, and overrides.

        This method serializes configured semantic values using ordinary, literal,
        or folded continuation records, then applies the processor affixes and selected
        physical newline style to every emitted line.

        Args:
            header_values: Mapping of header fields to render.
            config: TopMark configuration (defines header fields and options).
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).
            block_prefix_override: Optional block prefix override.
            block_suffix_override: Optional block suffix override.
            line_prefix_override: Optional line prefix override.
            line_suffix_override: Optional line suffix override.
            line_indent_override: Optional indentation override *after*
                the comment prefix, applied to header field lines (defaults to the
                processor's `line_indent`).
            header_indent_override: Optional indentation override *before*
                the comment prefix, applied to complete header lines (used to preserve
                existing leading indentation on replace).
            soft_overflow_fields: Optional mutable collector populated with field
                names whose canonical active-wrapping output exceeds the soft target.

        Returns:
            Rendered header lines ending with ``newline_style``.
        """
        logger.info(
            "%s: rendering header fields: %s",
            self.__class__.__name__,
            ", ".join(config.header_fields),
        )
        logger.debug("render_header_lines: align_fields=%s", config.align_fields)

        # Use provided overrides or defaults from the instance
        block_prefix = (
            block_prefix_override if block_prefix_override is not None else self.block_prefix
        )
        block_suffix = (
            block_suffix_override if block_suffix_override is not None else self.block_suffix
        )
        line_prefix = line_prefix_override if line_prefix_override is not None else self.line_prefix
        line_suffix = line_suffix_override if line_suffix_override is not None else self.line_suffix
        effective_line_indent = (
            line_indent_override if line_indent_override is not None else self.line_indent
        )
        header_indent = (
            header_indent_override if header_indent_override is not None else self.header_indent
        )

        # Compute header field name width only when alignment is enabled.
        # When align_fields is False, emit compact "field : value" without padding.
        if config.align_fields and header_values:
            width: int = max(len(k) for k in header_values) + 1
        else:
            width = 0

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
            value: str = normalize_semantic_newlines(header_values.get(field, ""))

            def measure_payload_line(
                inner: str,
                continuation: bool,
            ) -> int:
                """Return the complete physical payload-line length without its terminator."""
                return len(
                    self._wrap_line(
                        inner,
                        newline_style="",
                        line_prefix=line_prefix,
                        line_suffix=line_suffix,
                        header_indent=header_indent,
                        after_prefix_indent=(
                            effective_line_indent + "  " if continuation else effective_line_indent
                        ),
                    )
                )

            wrap_active: bool = (
                config.max_header_line_length is not None
                and field in config.wrap_fields
                and "\n" not in value
            )
            encoded_lines: list[str] = self._encode_field_lines(
                field_name=field,
                field_value=value,
                width=width,
                max_line_length=config.max_header_line_length if wrap_active else None,
                measure_line=measure_payload_line,
            )
            if (
                wrap_active
                and soft_overflow_fields is not None
                and config.max_header_line_length is not None
                and any(
                    measure_payload_line(inner, index > 0) > config.max_header_line_length
                    for index, inner in enumerate(encoded_lines)
                )
            ):
                soft_overflow_fields.add(field)
            for encoded_index, inner in enumerate(encoded_lines):
                lines.append(
                    self._wrap_line(
                        inner,
                        newline_style=newline_style,
                        line_prefix=line_prefix,
                        line_suffix=line_suffix,
                        header_indent=header_indent,
                        after_prefix_indent=(
                            effective_line_indent
                            if encoded_index == 0
                            else effective_line_indent + "  "
                        ),
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

    def _encode_field_lines(
        self,
        *,
        field_name: str,
        field_value: str,
        width: int,
        max_line_length: int | None = None,
        measure_line: Callable[[str, bool], int] | None = None,
    ) -> list[str]:
        """Encode one semantic field into canonical ordinary, literal, or folded lines."""
        if "\r" in field_value:
            raise ValueError("Semantic field values must be normalized before encoding")

        opener: str = f"{field_name:<{width}}:" if width else f"{field_name}:"
        ordinary: str = f"{opener} {field_value}"

        if "\n" not in field_value:
            if field_value and field_value != field_value.strip():
                return [opener, self._encode_exact_record(">=", field_value)]
            if (
                max_line_length is None
                or measure_line is None
                or measure_line(ordinary, False) <= max_line_length
            ):
                return [ordinary]

            folded_records: list[str] = self._wrap_folded_records(
                field_value,
                max_line_length=max_line_length,
                measure_line=measure_line,
            )
            if len(folded_records) >= 2:
                return [opener, *folded_records]
            return [ordinary]

        records: list[str] = []
        for logical_line in field_value.split("\n"):
            if logical_line == "":
                records.append("|")
            elif logical_line != logical_line.strip(" \t"):
                records.append(self._encode_exact_record("|=", logical_line))
            else:
                records.append(f"| {logical_line}")
        return [opener, *records]

    @staticmethod
    def _encode_exact_record(
        token: str,
        value: str,
    ) -> str:
        """Return one exact continuation record with canonical escaping."""
        escaped: str = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{token} "{escaped}"'

    def _wrap_folded_records(
        self,
        value: str,
        *,
        max_line_length: int,
        measure_line: Callable[[str, bool], int],
    ) -> list[str]:
        """Return deterministic lossless folded records for one overlong semantic value."""
        records: list[str] = []
        cursor = 0
        while True:
            remaining: str = value[cursor:]
            final_record: str = self._encode_folded_record(remaining)
            runs: list[re.Match[str]] = [
                match
                for match in _SPACE_RUN_RE.finditer(value, cursor)
                if match.start() > cursor and match.end() < len(value)
            ]
            if measure_line(final_record, True) <= max_line_length and (records or not runs):
                records.append(final_record)
                break
            if not runs:
                records.append(final_record)
                break

            chosen: re.Match[str] | None = None
            for match in runs:
                candidate: str = value[cursor : match.start()]
                encoded: str = self._encode_folded_record(candidate)
                if measure_line(encoded, True) <= max_line_length:
                    chosen = match
                else:
                    break
            if chosen is None:
                chosen = runs[0]

            fragment: str = value[cursor : chosen.start()]
            records.append(self._encode_folded_record(fragment))
            cursor = chosen.end() if len(chosen.group()) == 1 else chosen.start()

        if self._decode_folded_records(records) != value:
            raise RuntimeError("Folded continuation encoding did not preserve the semantic value")
        return records

    def _encode_folded_record(
        self,
        value: str,
    ) -> str:
        """Return the canonical plain or exact folded record for one fragment."""
        if value and value == value.strip(" \t"):
            return f"> {value}"
        return self._encode_exact_record(">=", value)

    @classmethod
    def _decode_folded_records(
        cls,
        records: Sequence[str],
    ) -> str:
        """Decode renderer-produced folded records for an internal round-trip check."""
        decoded: list[str] = []
        for index, encoded in enumerate(records):
            record, error = cls._parse_continuation_record(encoded)
            if error is not None or record is None or record.mode != "folded":
                raise RuntimeError("Renderer produced an invalid folded continuation record")
            if index > 0 and not record.exact:
                decoded.append(" ")
            decoded.append(record.value)
        return "".join(decoded)

    def compute_insertion_anchor(self, lines: list[str]) -> int:
        """Return a stable line-based insertion anchor for the pipeline.

        This small facade exists so pipeline steps have a single, stable
        entry point for *line-based* placement. By default, it simply
        delegates to `get_header_insertion_index`.

        Processors that insert by **character offset** (e.g., XML/HTML) should
        override `get_header_insertion_index` to return
        `NO_LINE_ANCHOR`, which this method will propagate unchanged.

        Args:
            lines: Full file content split into lines.

        Returns:
            A 0-based line index where a header would be inserted, or `NO_LINE_ANCHOR` when
            line-based anchoring is not used.
        """
        return self.get_header_insertion_index(lines)

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
            file_lines: Lines from the file being processed.

        Returns:
            Index at which to insert the TopMark header, or ``NO_LINE_ANCHOR`` if no insertion
            index can be found.
        """
        index = 0
        shebang_present = False

        # Shebang handling based on per-file-type policy
        policy: FileTypeHeaderPolicy | None = (
            self.file_type.header_policy if self.file_type else None
        )
        if policy and policy.supports_shebang and file_lines and file_lines[0].startswith("#!"):
            shebang_present = True
            index = 1

            # Optional encoding line immediately after shebang (e.g., Python)
            if policy.encoding_line_regex and len(file_lines) > index:
                src = policy.encoding_line_regex
                # Compile on first use or when the pattern string changes
                if self._encoding_pattern_src != src:
                    try:
                        self._encoding_pattern = re.compile(src)
                    except re.error:
                        self._encoding_pattern = None
                    self._encoding_pattern_src = src
                if self._encoding_pattern is not None and self._encoding_pattern.search(
                    file_lines[index]
                ):
                    index += 1

        # If a shebang block exists and the next line is a *policy-blank*, consume exactly one.
        # This keeps a single spacer between the preamble and the header without eating content
        # under STRICT (e.g., form-feed \x0c is preserved).
        if (
            shebang_present
            and index < len(file_lines)
            and is_pure_spacer(file_lines[index], policy)
        ):
            index += 1

        return index

    def line_has_directive(self, line: str, directive: str) -> bool:
        """Check whether a line contains the directive with the expected affixes.

        This method is used by ``get_header_bounds()`` to locate header start/end markers.
        Subclasses may override this method for more flexible or format-specific matching.

        Args:
            line: The line of text to check (whitespace is trimmed internally).
            directive: The directive string to look for.

        Returns:
            ``True`` if the line contains the directive with the configured prefix/suffix,
            otherwise ``False``.
        """
        # This method matches directives with configured affixes; policy-based blank
        # collapsing does not apply here. Normalize incidental whitespace for affix matching.
        line = line.strip()

        # Step 1: Check for the presence of the defined prefix
        if self.line_prefix and not line.startswith(self.line_prefix):
            return False

        # Step 2: Check for the presence of the defined suffix
        if self.line_suffix and not line.endswith(self.line_suffix):
            return False

        # Step 3: Remove the prefix and suffix and check the remaining content
        candidate: str = line
        if self.line_prefix:
            candidate = candidate.removeprefix(self.line_prefix)
        if self.line_suffix:
            candidate = candidate.removesuffix(self.line_suffix)

        # # Step 4: Strip whitespace after removing affixes to match the directive exactly.
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
            lines: Full file content split into lines.
            header_start_idx: 0-based index of the candidate header's first line.
            header_end_idx: 0-based index of the candidate header's last line (inclusive).
            anchor_idx: 0-based index where a header would be inserted per policy.

        Returns:
            ``True`` if the candidate lies within the configured proximity window,
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
            # TODO: add both properties to the FileType dataclass
            before = int(getattr(self.file_type, "scan_window_before", before) or 0)
            after = int(getattr(self.file_type, "scan_window_after", after) or 2)

        return (anchor_idx - before) <= header_start_idx <= (anchor_idx + after)

    def get_header_bounds(
        self,
        *,
        lines: Iterable[str],
        newline_style: str,
    ) -> HeaderBounds:
        """Locate the TopMark header bounds as (start_idx, end_idx), inclusive.

        This method first performs a **marker preflight** to catch malformed
        shapes (e.g., lone ``:end``, lone ``:start``, multiple or reversed markers).
        It then applies format-aware detection and proximity validation to return
        a valid span when present.

        Args:
            lines: Logical file lines (``keepends=True``). The iterable
                may be list-backed or lazy (e.g., a generator).
            newline_style: Dominant newline style (``LF``, ``CR``, ``CRLF``);
                unused by the default scanner but kept for parity with callers.

        Returns:
            A discriminated result:
                - ``BoundsKind.SPAN`` with ``start`` (inclusive) and ``end`` (exclusive)
                  when a valid header can be used.
                - ``BoundsKind.MALFORMED`` with a best-effort range and ``reason`` when
                  markers exist but the shape is invalid.
                - ``BoundsKind.NONE`` when no markers are present.

        Notes:
            Subclasses may override this method to provide format-specific detection
            and location validation but should preserve the discriminated-union
            semantics of the return value.
        """
        # Materialize once for look-ahead and validation.
        buf: list[str] = list(lines)

        if not buf:
            return HeaderBounds(kind=BoundsKind.NONE)

        # --- Preflight: marker-shape scan (format-agnostic) --------------------
        start_idxs: list[int] = []
        end_idxs: list[int] = []
        i: int
        ln: str
        for i, ln in enumerate(buf):
            # Accept either exact directive lines or markers inside a single-line comment
            # wrapper; the more exact check (line_has_directive) happens later.
            if TOPMARK_START_MARKER in ln:
                start_idxs.append(i)
            if TOPMARK_END_MARKER in ln:
                end_idxs.append(i)

        if end_idxs and not start_idxs:
            i = end_idxs[0]
            reason: str = "end marker without preceding start"
            logger.debug(reason)
            return HeaderBounds(
                kind=BoundsKind.MALFORMED,
                start=None,
                end=i + 1,
                reason="end marker without preceding start",
            )

        if start_idxs and not end_idxs:
            s: int = start_idxs[0]
            reason = "start marker without matching end"
            logger.debug(reason)
            return HeaderBounds(
                kind=BoundsKind.MALFORMED,
                start=s,
                end=None,
                reason="start marker without matching end",
            )

        if start_idxs and end_idxs:
            # We only want to find the first header occurrence
            s0: int
            e0: int
            s0, e0 = start_idxs[0], end_idxs[0]
            if e0 < s0:
                s_min: int = min(s0, e0)
                e_max: int = max(s0, e0) + 1
                reason = "end marker before start marker"
                logger.debug(reason)
                return HeaderBounds(
                    kind=BoundsKind.MALFORMED,
                    start=s_min,
                    end=e_max,
                    reason=reason,
                )
        # Validate the complete marker stream, not only its first pair. Multiple
        # non-overlapping complete headers remain deterministic, while nested or
        # dangling markers make the overall shape malformed.
        open_start: int | None = None
        for marker_idx, marker_line in enumerate(buf):
            has_start: bool = TOPMARK_START_MARKER in marker_line
            has_end: bool = TOPMARK_END_MARKER in marker_line
            if has_start and has_end:
                return HeaderBounds(
                    kind=BoundsKind.MALFORMED,
                    start=marker_idx,
                    end=marker_idx + 1,
                    reason="start and end marker on the same line",
                )
            if has_start:
                if open_start is not None:
                    return HeaderBounds(
                        kind=BoundsKind.MALFORMED,
                        start=open_start,
                        end=marker_idx + 1,
                        reason="start marker before previous header ended",
                    )
                open_start = marker_idx
            if has_end:
                if open_start is None:
                    return HeaderBounds(
                        kind=BoundsKind.MALFORMED,
                        start=None,
                        end=marker_idx + 1,
                        reason="end marker without preceding start",
                    )
                open_start = None

        if open_start is not None:
            return HeaderBounds(
                kind=BoundsKind.MALFORMED,
                start=open_start,
                end=None,
                reason="start marker without matching end",
            )

        # --- Policy-aware detection near computed anchor -----------------------
        anchor_idx: int = self.compute_insertion_anchor(buf)
        if anchor_idx == NO_LINE_ANCHOR:
            text: str = "".join(buf)
            char_off: int | None = self.get_header_insertion_char_offset(text)
            if char_off is not None:
                # Translate char offset to a line index using newline_style
                # (best-effort; the default processor doesn't rely on it further).
                nl: str = newline_style or "\n"
                anchor_idx = text[:char_off].count(nl)
            else:
                anchor_idx = 0

        if self.block_prefix and self.block_suffix:
            candidates: list[tuple[int, int]] = self._collect_bounds_block_comments(buf)
            # should return outer-inclusive spans
        else:
            candidates = self._collect_bounds_line_comments(buf)

        for s, e_inclusive in candidates:
            # Convert inclusive end → exclusive end for view/bounds consumers.
            e_exclusive: int = e_inclusive + 1
            if self.validate_header_location(
                buf,
                header_start_idx=s,
                header_end_idx=e_inclusive,
                anchor_idx=anchor_idx,
            ):
                return HeaderBounds(kind=BoundsKind.SPAN, start=s, end=e_exclusive)

        # No acceptable header near the anchor; treat as absent.
        return HeaderBounds(kind=BoundsKind.NONE)

    def strip_header_block(
        self,
        *,
        lines: list[str],
        span: tuple[int, int] | None = None,
        newline_style: str = "\n",
        ends_with_newline: bool | None = None,
    ) -> StripHeaderResult:
        """Remove the TopMark header block and return the updated file image.

        This method supports two detection modes:

        1. **Policy-aware detection** (preferred):
           If ``span`` is not provided, the processor calls
           ``get_header_bounds(lines, newline_style)``
           to locate a valid header near the computed insertion anchor. This respects
           file-type placement rules (shebang handling, XML prolog, Markdown fences, etc.).

        2. **Permissive fallback** (best-effort):
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
            span: Optional inclusive ``(start, end)`` line index tuple,
                normally provided by the scanner via ``ctx.existing_header_range``.
                When set, no scanning is performed.
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).
            ends_with_newline: If known, whether the original file ended with a newline.
                If ``None``, this information is not available.

        Returns:
            Structured strip result containing the updated file lines, the
            inclusive removed span when a header was removed, and the diagnostic
            describing the outcome.

        Raises:
            RuntimeError: If policy-aware bounds detection reports a SPAN but omits
                start/end indices.
        """
        # 1) Resolve bounds: prefer explicit span, else policy-aware detection.
        if span is None:
            # First try the standard, policy-aware bounds detection.
            start: int | None
            end: int | None
            bounds: HeaderBounds = self.get_header_bounds(lines=lines, newline_style=newline_style)
            if bounds.kind is BoundsKind.SPAN:
                # convert exclusive end to inclusive span expected by this method
                if bounds.start is None or bounds.end is None:
                    raise RuntimeError("Start and end bounds must be defined.")
                span = (bounds.start, bounds.end - 1)

            elif bounds.kind is BoundsKind.MALFORMED:
                # Do not strip malformed headers; return unchanged lines.
                return StripHeaderResult(
                    lines=lines,
                    removed_span=None,
                    diagnostic=StripDiagnostic(
                        kind=StripDiagKind.MALFORMED_REFUSED,
                        reason=bounds.reason,
                    ),
                )

            else:  # BoundsKind.NONE
                span = None
                # fall through to the permissive scan you already have

            if span is None:
                # A complete header can be structurally valid but outside the normal
                # insertion window (for example, a legacy XML header inside a DOCTYPE).
                # Preserve the collector's wrapper-aware span before falling back to
                # substring matching for older single-line comment forms.
                legacy_candidates: list[tuple[int, int]]
                if self.block_prefix and self.block_suffix:
                    legacy_candidates = self._collect_bounds_block_comments(lines)
                else:
                    legacy_candidates = self._collect_bounds_line_comments(lines)
                if legacy_candidates:
                    span = legacy_candidates[0]

            if span is None:
                # Permissive scan: accept directive substrings inside single-line
                # comment wrappers (e.g., XML/HTML `<!-- ... -->`).
                # Useful when stripping headers that were inserted by older versions
                # or were moved by formatting tools.
                n: int = len(lines)
                i = 0
                while i < n:
                    # Accept either exact directive match (prefix/suffix-aware)
                    # or the directive appearing inside a single-line comment wrapper.
                    start_match: bool = self.line_has_directive(lines[i], TOPMARK_START_MARKER) or (
                        TOPMARK_START_MARKER in lines[i]
                    )
                    if start_match:
                        j: int = i + 1
                        while j < n:
                            end_match: bool = self.line_has_directive(
                                lines[j], TOPMARK_END_MARKER
                            ) or (TOPMARK_END_MARKER in lines[j])
                            if end_match:
                                span = (i, j)
                                break
                            j += 1
                        if span is not None:
                            break
                    i += 1

        # 2) No header? Return original content unchanged.
        if span is None:
            return StripHeaderResult(
                lines=lines,
                removed_span=None,
                diagnostic=StripDiagnostic(
                    kind=StripDiagKind.NOT_FOUND,
                ),
            )

        start, end = span
        # Defensive validation of bounds
        if start < 0 or end < start or end >= len(lines):
            # Defensive: invalid span -> no-op
            return StripHeaderResult(
                lines=lines,
                removed_span=None,
                diagnostic=StripDiagnostic(
                    kind=StripDiagKind.NOT_FOUND,
                ),
            )

        # Remove the block (inclusive header span)
        new_lines: list[str] = lines[:start] + lines[end + 1 :]
        policy: FileTypeHeaderPolicy | None = getattr(
            getattr(self, "file_type", None), "header_policy", None
        )

        # Policy-aware cleanup: trim exactly one spacer left by removal.
        # Use in-place deletion (del) to preserve list identity.
        if start == 0:
            # Top-of-file: remove a single leading spacer if present
            if new_lines and is_pure_spacer(new_lines[0], policy):
                del new_lines[0]
        else:
            # General case: remove a single spacer at the removal site
            if 0 <= start < len(new_lines) and is_pure_spacer(new_lines[start], policy):
                del new_lines[start]

        return StripHeaderResult(
            lines=new_lines,
            removed_span=(start, end),
            diagnostic=StripDiagnostic(
                kind=StripDiagKind.REMOVED,
                removed_span=(start, end),
            ),
        )

    def _collect_bounds_line_comments(self, lines: list[str]) -> list[tuple[int, int]]:
        """Collect all (start,end) pairs for pound-style headers in the file."""
        results: list[tuple[int, int]] = []
        i: int = 0
        n: int = len(lines)
        while i < n:
            if self.line_has_directive(lines[i], TOPMARK_START_MARKER):
                start: int = i
                j: int = i + 1
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
        n: int = len(lines)
        i: int = 0
        while i < n:
            # Find a START marker
            if not self.line_has_directive(lines[i], TOPMARK_START_MARKER):
                i += 1
                continue
            start_idx: int = i
            # Find the matching END marker after start
            j: int = i + 1
            while j < n and not self.line_has_directive(lines[j], TOPMARK_END_MARKER):
                j += 1
            if j >= n:
                break  # unmatched START; stop collecting further
            end_idx: int = j

            # Try to expand to block_prefix/block_suffix if they tightly wrap the header
            block_start: int | None = None
            k: int = start_idx - 1
            policy: FileTypeHeaderPolicy | None = getattr(
                getattr(self, "file_type", None), "header_policy", None
            )
            # Walk left over policy-blank spacers only; do not consume control whitespace
            # under STRICT.
            while k >= 0 and is_pure_spacer(lines[k], policy):
                k -= 1
            if (
                k >= 0
                and self.block_prefix
                and _equals_affix_ignoring_space_tab(lines[k], self.block_prefix)
            ):
                block_start = k

            block_end: int | None = None
            k = end_idx + 1
            # Walk right over policy-blank spacers only.
            while k < n and is_pure_spacer(lines[k], policy):
                k += 1
            if (
                k < n
                and self.block_suffix
                and _equals_affix_ignoring_space_tab(lines[k], self.block_suffix)
            ):
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

    def prepare_header_for_insertion(
        self,
        *,
        original_lines: list[str],
        insert_index: int,
        rendered_header_lines: list[str],
        newline_style: str,
    ) -> list[str]:
        """Adjust whitespace around the header for line-based insertion.

        Default implementation returns ``rendered_header_lines`` unchanged. Subclasses
        and mixins can override to add/remove leading or trailing blank lines
        depending on surrounding context.

        Args:
            original_lines: The original file lines.
            insert_index: Line index at which the header will be inserted.
            rendered_header_lines: The header lines to insert.
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            Possibly modified header lines to insert at ``insert_index``.
        """
        return rendered_header_lines

    def get_header_insertion_char_offset(self, original_text: str) -> int | None:
        """Return a character offset for text-based insertion, or ``None``.

        This hook enables processors to compute non line-based insertion points
        (e.g., XML prolog-aware placement when declaration/DOCTYPE and content appear
        on the same line). Returning ``None`` signals that the pipeline should fall
        back to the standard line-based insertion path.

        Args:
            original_text: Full file content as a single string.

        Returns:
            0-based character offset at which to insert, or ``None`` to use the line-based
            insertion strategy.
        """
        return None

    def prepare_header_for_insertion_text(
        self,
        *,
        original_text: str,
        insert_offset: int,
        rendered_header_text: str,
        newline_style: str,
    ) -> str:
        """Adjust the rendered header *text* before text-based insertion.

        Subclasses may override this to add or trim surrounding newlines so the header
        block sits on its own lines when performing text-based insertion.

        Args:
            original_text: Full file content as a single string.
            insert_offset: 0-based character offset where the header will be inserted.
            rendered_header_text: The header block as a single string.
            newline_style: Newline style (``LF``, ``CR``, ``CRLF``).

        Returns:
            The (possibly modified) header text to splice into ``original_text`` at
            ``insert_offset``.
        """
        return rendered_header_text

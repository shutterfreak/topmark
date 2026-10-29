<!--
topmark:header:start

  project      : TopMark
  file         : configuration.md
  file_relpath : docs/usage/configuration.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# User configuration

TopMark runtime configuration may be provided through:

- `topmark.toml`
- `pyproject.toml` (`[tool.topmark]`)
- CLI overrides
- API overlays

Configuration is resolved through layered discovery, normalization, and precedence rules; a
higher-precedence layer overrides a lower-precedence layer. For the complete discovery order,
discovery-anchor behavior, and configuration-source identity contract, see
[Configuration discovery, precedence, and policy](../configuration/discovery.md).

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## CLI, configuration, and API value spelling

Configuration keys use consistent naming across the CLI, API, and TOML configuration surfaces. Some
options accept predefined multi-word values such as `add_only` or `whitespace_empty`.

TopMark uses different spelling conventions depending on the interface: finite-choice CLI values
require exact lowercase spelling and *hyphenated forms* for multiword values, while TOML
configuration, Python API values, and machine-readable output use *canonical underscore forms*.

{% include-markdown "\_snippets/option-spelling.md" %}

Unless otherwise noted, configuration and policy values shown throughout this page use the canonical
TOML/API/machine-readable underscore form.

______________________________________________________________________

## Multiline field values

> [!NOTE]
>
> Available since version 2.0.0.

The target design in [#339](https://github.com/shutterfreak/topmark/issues/339) changes multiline
field rendering. Under that design, custom `[fields]` values may use TOML multiline strings; TopMark
removes their incidental leading and trailing blank lines, then renders multiline values using
pipe-prefixed continuation records:

```toml
[fields]
notice = """
First line.
Second line.
"""

[header]
fields = ["notice"]
```

See [Multiline header field rendering](../dev/multiline-header-fields.md) for continuation,
paragraph, validation, and canonicalization details.

### Deterministic field wrapping

Under the target design, selected fields treat multiline TOML content as reflowable prose and wrap
it into canonical continuation records:

```toml
[formatting]
max_header_line_length = 100
wrap_fields = ["notice", "copyright"]
```

Wrapping is disabled unless both a positive width and an allowlisted field are present. The width
counts Unicode code points across the complete physical field line, including comment syntax and
indentation but excluding the line terminator. It is a soft target: TopMark wraps only at lossless
U+0020 SPACE boundaries and never hard-splits URLs, paths, identifiers, or other unbreakable
content.

For a selected field, nonblank TOML line breaks become spaces and blank-line runs become paragraph
separators. TopMark wraps each paragraph independently and uses a bare continuation pipe between
paragraphs. Unselected multiline fields retain their logical lines. The rendered header is derived
from the effective configuration; it is not an independent source of field values.

______________________________________________________________________

## File type identifiers

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](filtering.md#file-type-filtering) for the full identifier contract.

File type identifiers participate in stable runtime behavior such as:

- `include_file_types`
- `exclude_file_types`
- `opt_in_file_types`
- `policy_by_type`
- CLI file-type filters
- API file-type filters and policy overlays

______________________________________________________________________

## File-type filters

File-type filters allow restricting runtime processing to a selected subset of file types.

Example using local identifiers:

```toml
[files]
include_file_types = ["python", "markdown"]
```

Equivalent configuration using canonical qualified file type identifiers:

```toml
[files]
include_file_types = ["topmark:python", "topmark:markdown"]
```

Exclude filters work the same way:

```toml
[files]
exclude_file_types = ["topmark:yaml"]
```

### Opt-in activation

File-type filters do not grant processing authorization. A file type declared `opt-in` requires
explicit consent through `opt_in_file_types`:

```toml
[files]
opt_in_file_types = ["topmark:json-as-jsonc"]
```

As with filters, local identifiers are accepted only when unambiguous and TopMark normalizes them to
canonical qualified identities. File types declared `default` need no entry. File types declared
`never` cannot be made processable by configuration, and an exclusion filter remains a veto even for
an explicitly opted-in type.

> [NOTE] Internally, TopMark normalizes configured file type identifiers to canonical qualified
> identities before filtering, runtime resolution, policy evaluation, diagnostics, and registry
> lookup.

______________________________________________________________________

## Per-file-type policy

`policy_by_type` allows file-type-specific policy overrides for selected file types.

Example using a local identifier:

```toml
[policy_by_type.python]
header_mutation_mode = "update_only"
```

Equivalent configuration using canonical qualified file type identifiers:

```toml
[policy_by_type."topmark:python"]
header_mutation_mode = "update_only"
```

Both forms are accepted when the local identifier resolves unambiguously.

Internally, TopMark stores and resolves per-file-type policies using canonical qualified file type
identities.

### Example: Different policy per file type

```toml
[policy]
header_mutation_mode = "add_only"
bom_before_shebang = "reject"
mixed_line_endings = "preserve"

[policy_by_type."topmark:python"]
header_mutation_mode = "update_only"
bom_before_shebang = "remove_bom"
mixed_line_endings = "reject"

[policy_by_type.markdown]
allow_content_probe = false
```

In this example:

- the global default header mutation policy uses `add_only` and mixed line endings are preserved
  when present
- Python files override this with `update_only`
- Python files also remediate a BOM immediately before a shebang
- Python files also reject files with mixed line endings
- Markdown files disable runtime content probing

______________________________________________________________________

## Ambiguous identifiers

When more than one registered file type shares the same local identifier, TopMark requires the
canonical qualified form.

For example, if both:

- `topmark:python`
- `acme:python`

are registered, then:

```toml
include_file_types = ["python"]
```

is ambiguous.

Use:

```toml
include_file_types = ["topmark:python"]
```

instead.

Ambiguous identifiers are ignored diagnostically during configuration normalization and staged
configuration-loading validation.

______________________________________________________________________

## Unknown and malformed identifiers

Unknown identifiers are ignored diagnostically during configuration normalization and staged
configuration-loading validation.

Malformed qualified identifiers are also ignored diagnostically during configuration normalization
and staged configuration-loading validation.

Examples of malformed identifiers:

```text
:python
topmark:
topmark:python:extra
```

______________________________________________________________________

## CLI and API parity

CLI options, TOML configuration, API overlays, and runtime policy evaluation all share the same file
type identity semantics.

Examples:

```bash
topmark check --include-file-types python .
```

```bash
topmark check --include-file-types topmark:python .
```

```bash
topmark check --opt-in-file-type topmark:json-as-jsonc .
```

```python
api.check(
    paths=[repo],
    include_file_types=["topmark:python"],
)
```

______________________________________________________________________

## Runtime configuration model

{% include-markdown "\_snippets/runtime-configuration-model.md" %}

Runtime evaluation consumes the effective configuration produced after workspace-root discovery,
precedence, normalization, and configuration-source identity resolution have completed.

For configuration files loaded through symlinks, the effective configuration is associated with the
resolved configuration target rather than the symlink spelling used to reach it.

Hard-link processing policy is not represented in the runtime configuration model because it is a
processing-target eligibility rule evaluated by runtime file-processing commands rather than a
configuration-layering concern.

______________________________________________________________________

## Assign existing file types

> [!NOTE]
>
> Available since version 3.0.0.

Use ordered rules to select registered file types for otherwise unrecognized paths or to override
automatic recognition. In `topmark.toml`:

```toml
[[files.file_type_assignments]]
file_type = "topmark:git-meta"
patterns = [".project_ignore"]

[[files.file_type_assignments]]
file_type = "topmark:jsonc"
patterns = ["config/service.json", "config/local/*.json"]

[[files.file_type_assignments]]
action = "infer"
patterns = ["generated/**"]
```

> [!INFO]
>
> Rules belong to `[files]` because they control selection of processing inputs alongside path and
> type filters. They do not define registry types or processor bindings.

In `pyproject.toml`, use `[[tool.topmark.files.file_type_assignments]]`. Assignment entries require
one existing `file_type` and a nonempty pattern list. An omitted action means `"assign"`;
`action = "assign"` is equivalent. Inference controls require `action = "infer"` and patterns, and
forbid the `file_type` key entirely, including empty values. Unknown actions, malformed shapes,
unknown or ambiguous identifiers, and invalid patterns are errors. Unknown keys follow normal
warning/strict-mode conventions. Local type identifiers are accepted when unambiguous; effective
configuration uses canonical qualified identities.

The last applicable matching rule wins. Ancestor rules precede local rules; within a directory,
`pyproject.toml` precedes `topmark.toml`. Explicit configuration sources retain their existing scope
and follow discovered sources in argument order. CLI rules follow configuration rules. A winning
inference control cancels earlier assignments and runs ordinary recognition; it never resumes an
earlier assignment. Empty assignment lists retain inherited rules. TopMark 3.0 does not provide a
separate clear-all inheritance setting.

Assignments select a type directly, bypassing filename and content recognition gates. The selected
type retains its processor binding, policies, activation consent, include/exclude type filters,
insertion checks, encoding checks, and runtime safety checks. A blocked, filtered,
never-processable, or unbound assignment has no fallback. Assignments add no discovery roots and do
not override path exclusions. Registry introspection remains independent of project rules.

Type filters apply to the effective assigned identity, rather than every identity that could match
the path automatically. For example, `exclude_file_types = ["topmark:json"]` does not block a
`topmark:jsonc` assignment to `config/service.json`. Excluding `topmark:jsonc`, or including only
other types, blocks that assignment without retrying automatic JSON recognition. Activation consent
is independent: including a type does not authorize an opt-in type.

For comment-free JSON documents known to permit comments, assign `topmark:jsonc`. This enables
normal header insertion and stripping through its existing processor. `json-as-jsonc` retains both
its conservative content-based automatic recognition and its separate insertion guard. Successful
probing does not promise successful insertion.

### Pattern and scope contract

Rules use TopMark's case-sensitive gitignore-style positive patterns, with POSIX `/` separators on
all platforms. A basename pattern such as `.project_ignore` or `*.json` matches at any depth,
including dotfiles. A pattern containing a directory separator is relative to its definition base; a
leading `/` anchors it there. `*` does not cross directories; `**` can. Character classes, `?`, and
backslash escaping use the existing pathspec gitignore conventions. Unclosed brackets are literals,
while invalid ranges and dangling escapes are errors. Empty, whitespace-only, comment (`#`), negated
(`!`), and control-character patterns are rejected. Escape a literal initial `#` or `!` with a
backslash.

The raw pattern is preserved. Leading spaces are literal; unescaped trailing spaces follow gitignore
semantics and are ignored during matching. Escape trailing spaces to match them. Backslashes escape
glob characters; use `/` for directory separators. Matching uses the selected resolved processing
path, so symlink spellings collapse to the target and follow its scope. Patterns are interpreted
relative to the declaring configuration directory, independently of applicability scope. CLI
patterns use the invocation directory. Nested sources apply only to their subtree and honor
`root = true` boundaries. STDIN rules match the logical `--stdin-filename`; content probes continue
to read the staged input.

### CLI ordering and exact values

`check`, `strip`, `probe`, `config check`, and `config dump` accept both repeatable options:

```console
topmark probe . --assign-filetype 'topmark:jsonc=*.json' \
  --infer-filetype 'generated/**' \
  --assign-filetype 'topmark:jsonc=generated/special.json'
```

Both option kinds participate in one sequence, preserving their actual command-line interleaving.
Reversing matching assignment/inference occurrences reverses the winner. One assignment occurrence
contains exactly one type and one pattern, split at the first `=`. Registry identifiers cannot
contain `=`. Everything after that delimiter is preserved, including further equals signs, colons,
spaces, Unicode, commas, brackets, and backslashes. Values are never comma-split or trimmed.
Whitespace around the type identifier is invalid. Quote values to prevent shell expansion.
`--assign-filetype=TYPE=GLOB` and `--infer-filetype=GLOB` are equivalent to separate-value forms.
Leading-dash values are accepted in both forms; the equals form makes that intent clearest.

### Single-file remediation hints

For an assignment-selected file, `check` and `strip` suggest an apply command with the canonical
file type and an exact-path assignment, rather than repeating the original broad glob:

```console
topmark check --assign-filetype 'topmark:jsonc=tests/api/public_api_snapshot.json' --apply 'tests/api/public_api_snapshot.json'
```

The pattern is anchored to the invocation directory, with glob metacharacters and spaces escaped
literally and shell arguments quoted separately. STDIN hints use the logical `--stdin-filename`.
Automatic recognition and winning `infer` rules do not generate assignment overrides. Run the
suggestion from the same directory and retain any required explicit configuration files, activation
consent, and policy overrides: the minimal assignment reproduces file-type selection, rather than
all invocation settings. For paths outside the invocation directory or patterns that cannot be
represented safely, guidance asks you to rerun with the original settings instead of supplying an
incomplete command. Shell quoting follows POSIX shell conventions.

### Diagnostics and portable dumps

Ordinary overlaps are valid overrides. Probe collects actual matches lazily without static glob
intersection or additional filesystem scans. Identical outcomes are harmless. Contradictory
duplicate patterns in one source warn, and strict validation rejects those warnings. Diagnostics are
emitted once per declaration rather than once per matching file. Ancestor/local and broad/narrow
overrides do not generate overlap warning floods.

Probe always explains the winning rule; `-v` reveals superseded matches in TEXT. Markdown always
includes superseded matches and ignores verbosity and quiet controls. JSON and NDJSON include the
complete ordered `rule_matches` independently of verbosity, with `selection_method` equal to
`assignment` or `inference`. No scores or content hits are fabricated for assignment winners. See
[Machine-readable output](machine-output.md).

Configuration dumps retain rule order and absolute `base` and `scope`, plus `source`, `order`, and
`precedence` provenance. These exported entry fields can be read back. Empty exported `scope` means
global applicability. Reloading a dump preserves absolute pattern locations rather than relocating
rules to a new checkout. File-backed source scope still applies: place a dump at a common ancestor
of its original scopes, or use its mapping as an explicit API configuration seed, to retain full
applicability. Moving a TOML source outside the original tree does not expand its source scope. For
a portable project configuration, keep the authored entries with source-relative patterns and omit
exported provenance fields. Rule array order controls resolution; provenance numbers describe the
original layers.

Public API configuration accepts the same structured mapping, for example
`config={"files": {"file_type_assignments": [{"file_type": "jsonc", "patterns": ["*.json"]}]}}`.
Explicit API configuration retains its existing discovery-skipping seed behavior. Public probe
results add `selection_method` and `rule_matches`, with no changes to command signatures.

______________________________________________________________________

## Synthetic configuration provenance

Configuration inspection uses stable labels for sources without a filesystem path. These include
`<defaults>`, `<API config>`, `<API overrides>`, `<API policy overrides>`, and `<CLI overrides>`.
The built-in defaults document and bundled starter template retain their distinct labels
`<built-in topmark defaults>` and `<bundled topmark-template.toml>`.

Assignment and inference-control rules supplied on the CLI report `<CLI assignments>` within the CLI
override layer. Anonymous in-memory fragments report `<anonymous config>` for rules; only explicit
API mappings report `<API config>`. These labels are provenance metadata and are never resolved as
filesystem paths. Rule labels in exported TOML remain strings when reloaded; absolute rule bases and
scopes preserve matching behavior when the dump is relocated. JSON, NDJSON, and human output retain
the same label spellings.

______________________________________________________________________

## See also

- [Machine-readable output](machine-output.md#tomlprovenancepayload)
- [Filtering recipes and behavior](filtering.md)
- [Configuration overview](../configuration/index.md)
- [Configuration discovery, precedence, and policy](../configuration/discovery.md)

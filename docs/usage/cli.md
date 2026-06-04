<!--
topmark:header:start

  project      : TopMark
  file         : cli.md
  file_relpath : docs/usage/cli.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Command-line interface

TopMark provides a deterministic command-line interface supporting:

- checking header state
- inserting or updating headers
- stripping headers
- inspecting effective runtime configuration
- generating starter configuration files
- inspecting registry state and resolution decisions
- shell tab-completion via Click-generated completion scripts

The CLI is intentionally conservative:

- commands default to dry-run behavior
- mutations require `--apply`
- filesystem identity is normalized before runtime processing
- unsupported files are skipped diagnostically
- repeated runs converge to stable results
- command help and shell completion are available across supported platforms

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## Common workflows

| Goal                                 | Command                             | More info                                                                                              |
| ------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Check headers safely in dry-run mode | `topmark check src/`                | [`topmark check`](commands/check.md), [Shared options](shared-options.md), [Exit codes](exit-codes.md) |
| Apply header updates explicitly      | `topmark check --apply src/`        | [`topmark check`](commands/check.md), [Policies](policies.md)                                          |
| Remove TopMark headers               | `topmark strip --apply src/`        | [`topmark strip`](commands/strip.md), [Header placement](header-placement.md)                          |
| Inspect file type resolution         | `topmark probe README.md`           | [`topmark probe`](commands/probe.md), [Filtering](filtering.md)                                        |
| Inspect effective configuration      | `topmark config dump --show-layers` | [`topmark config dump`](commands/config/dump.md), [Configuration](configuration.md)                    |

Filesystem inputs are normalized to selected processing paths before runtime processing. If multiple
path spellings resolve to the same filesystem target (for example a symlink and its target), TopMark
processes the target once and reports the selected processing path in machine-readable output.

______________________________________________________________________

## Installation

Install TopMark from PyPI:

```bash
pip install topmark
```

Verify the installation:

```bash
topmark version
```

______________________________________________________________________

## Command structure

The CLI uses the following structure:

```text
topmark COMMAND [COMMAND OPTIONS] [PATHS...]
```

The root command currently exposes only help (`topmark --help`). Shared controls such as
configuration loading, output format, verbosity, filtering, and mutation flags are exposed only on
the command families where they apply.

Examples:

```bash
topmark --help
```

```bash
topmark check src/
```

```bash
topmark check --apply src/
```

```bash
topmark strip --apply src/
```

For commands that operate on filesystem inputs (`check`, `strip`, and `probe`), positional paths
participate in TopMark's discovery, filtering, filesystem-identity normalization, and
processing-path selection pipeline before runtime processing begins.

______________________________________________________________________

## Command help

Every command and command group provides built-in help output.

Examples:

```bash
topmark --help
```

```bash
topmark check --help
```

```bash
topmark config --help
```

```bash
topmark registry filetypes --help
```

The short form `-h` is also supported.

______________________________________________________________________

## Shell tab-completion

TopMark supports shell tab-completion through Click's generated completion scripts.

Shell completion helps with:

- command discovery
- subcommand navigation
- option completion
- filesystem path completion

Completion support depends on the active shell environment.

### Bash (Linux/macOS)

Temporary session setup:

```bash
eval "$(_TOPMARK_COMPLETE=bash_source topmark)"
```

Persistent setup:

```bash
echo 'eval "$(_TOPMARK_COMPLETE=bash_source topmark)"' >> ~/.bashrc
```

Reload the shell configuration:

```bash
source ~/.bashrc
```

### Zsh (macOS/Linux)

Temporary session setup:

```zsh
eval "$(_TOPMARK_COMPLETE=zsh_source topmark)"
```

Persistent setup:

```zsh
echo 'eval "$(_TOPMARK_COMPLETE=zsh_source topmark)"' >> ~/.zshrc
```

Reload the shell configuration:

```zsh
source ~/.zshrc
```

### Fish (Linux/macOS)

Install the completion script:

```fish
_TOPMARK_COMPLETE=fish_source topmark > ~/.config/fish/completions/topmark.fish
```

Fish automatically loads completion files from this directory.

### PowerShell (Windows)

Register completion for the current PowerShell profile:

```powershell
_TOPMARK_COMPLETE=powershell_source topmark | Out-String | Invoke-Expression
```

To persist the setup across sessions, add the command to the PowerShell profile referenced by:

```powershell
$PROFILE
```

### Completion environment variable

Click-based completion uses the `_TOPMARK_COMPLETE` environment variable.

Supported values include:

- `bash_source`
- `zsh_source`
- `fish_source`
- `powershell_source`

For additional Click shell-completion details, see the upstream Click documentation.

______________________________________________________________________

## Shared options

Common shared options include the following, where supported by the selected command:

| Option                                        | Description                                                      |
| --------------------------------------------- | ---------------------------------------------------------------- |
| `--config FILE`                               | Load and merge an additional configuration file                  |
| `--apply`                                     | Apply file mutations instead of dry-run, where supported         |
| `-v`, `--verbose`                             | Increase TEXT output detail, where supported                     |
| `-q`, `--quiet`                               | Suppress TEXT output, where supported                            |
| `--output-format {text,markdown,json,ndjson}` | Select output format, where machine-readable output is supported |
| `--color` / `--no-color`                      | Enable or disable colorized terminal output, where supported     |
| `--include-file-types`                        | Restrict processing to selected file types, where supported      |
| `--exclude-file-types`                        | Exclude selected file types, where supported                     |

For command applicability, output, verbosity, and formatting options, see
[Shared options](shared-options.md).

Machine-readable filesystem path fields report selected processing paths rather than preserving the
original CLI argument spelling. See [Machine-readable output](machine-output.md) for the full
contract.

{% include-markdown "\_snippets/option-spelling.md" %}

______________________________________________________________________

## File type filters

{% include-markdown "\_snippets/file-type-identifiers.md" %}

See [file-type filtering](filtering.md#file-type-filtering) for the full identifier contract.

Examples:

```bash
topmark check --include-file-types python src/
```

```bash
topmark check --include-file-types topmark:python src/
```

```bash
topmark check --exclude-file-types markdown docs/
```

File type filters behave consistently across:

- CLI options
- TOML configuration
- API overlays
- resolution and probe filtering

File type filtering operates after filesystem-identity normalization and processing-path selection.

For canonical file-type identifier semantics and layered configuration behavior, see
[Configuration](configuration.md).

______________________________________________________________________

## Command map

| Goal                                        | Command                                            |
| ------------------------------------------- | -------------------------------------------------- |
| Check headers without modifying files       | [`topmark check`](commands/check.md)               |
| Apply header insertions or updates          | [`topmark check --apply`](commands/check.md)       |
| Remove existing TopMark headers             | [`topmark strip`](commands/strip.md)               |
| Inspect resolution and processor behavior   | [`topmark probe`](commands/probe.md)               |
| Validate effective configuration            | [`topmark config check`](commands/config/check.md) |
| Inspect effective runtime configuration     | [`topmark config dump`](commands/config/dump.md)   |
| Generate starter configuration              | [`topmark config init`](commands/config/init.md)   |
| Inspect registry state                      | [`topmark registry`](commands/registry.md)         |
| Display version and environment information | [`topmark version`](commands/version.md)           |

______________________________________________________________________

## Main commands

See also:

- [Filtering](filtering.md)
- [Policies](policies.md)
- [Shared options](shared-options.md)

| Command                                                          | Purpose                                                                                                 |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [`topmark check`](commands/check.md)                             | Detect missing, malformed, or outdated headers. Dry-run by default; use `--apply` to mutate files.      |
| [`topmark strip`](commands/strip.md)                             | Remove existing TopMark headers. Dry-run by default; use `--apply` to mutate files.                     |
| [`topmark probe`](commands/probe.md)                             | Inspect file type resolution, processor binding, filtering, and probe decisions without mutating files. |
| [`topmark config`](commands/config.md)                           | Inspect, validate, render, and initialize TopMark configuration.                                        |
| [`topmark config check`](commands/config/check.md)               | Check the validity of the effective runtime configuration.                                              |
| [`topmark config dump`](commands/config/dump.md)                 | Display the effective runtime configuration.                                                            |
| [`topmark config defaults`](commands/config/defaults.md)         | Display the canonical built-in default TOML representation.                                             |
| [`topmark config init`](commands/config/init.md)                 | Render the bundled starter configuration template.                                                      |
| [`topmark registry`](commands/registry.md)                       | Inspect registered file types, processors, and registry bindings.                                       |
| [`topmark registry filetypes`](commands/registry/filetypes.md)   | Inspect file type identities and their matching rules and policies.                                     |
| [`topmark registry processors`](commands/registry/processors.md) | Inspect header processor identities and their capabilities.                                             |
| [`topmark registry bindings`](commands/registry/bindings.md)     | Inspect effective bindings between file types and processors.                                           |
| [`topmark version`](commands/version.md)                         | Display version and environment information.                                                            |

______________________________________________________________________

## Dry-run vs apply

TopMark defaults to dry-run behavior.

Without `--apply`, commands preview planned changes without mutating files.

Example:

```bash
topmark check src/
```

Apply changes explicitly:

```bash
topmark check --apply src/
```

This safety model helps prevent accidental large-scale repository mutations while preserving
preview-oriented workflows.

______________________________________________________________________

## Related pages

- [Shared options](shared-options.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)
- [Pre-commit integration](pre-commit.md)
- [Configuration discovery, precedence, and policy](../configuration/discovery.md)
  - [Configuration source identity](../configuration/discovery.md#configuration-source-identity)
- [Machine-readable output](machine-output.md)

______________________________________________________________________

## Diagnostics and exit behavior

The CLI reports:

- unsupported file types
- malformed headers
- skipped files
- planned mutations
- write failures
- configuration validation issues
- ambiguous or malformed file type identifiers

Diagnostics are designed to remain deterministic and compatible with the stable machine-readable
output contracts. This includes stable processing-path reporting for runtime filesystem inputs and
stable configuration-source identity reporting for file-backed configuration provenance.

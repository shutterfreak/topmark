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

TopMark provides a deterministic command-line interface for:

- checking headers
- inserting or updating headers
- stripping headers
- inspecting effective configuration
- generating starter configuration files
- inspecting registry state and resolution behavior

The CLI is intentionally conservative:

- commands default to dry-run behavior
- mutations require `--apply`
- unsupported files are skipped diagnostically
- repeated runs converge to stable results
- command help is available via `--help` / `-h`

## Installation

Install TopMark from PyPI:

```bash
pip install topmark
```

Verify the installation:

```bash
topmark version
```

## Command structure

The CLI uses the following structure:

```text
topmark COMMAND [COMMAND OPTIONS] [PATHS...]
```

The root command currently exposes only help (`topmark --help`). Shared controls such as config
loading, output format, verbosity, filtering, and mutation flags are exposed on the command families
where they apply.

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

## Shared command options

Common shared options include:

| Option                                        | Description                                                  |
| --------------------------------------------- | ------------------------------------------------------------ |
| `--config FILE`                               | Load and merge an additional configuration file              |
| `--apply`                                     | Apply file mutations instead of dry-run, where supported     |
| `-v`, `--verbose`                             | Increase TEXT output detail, where supported                 |
| `-q`, `--quiet`                               | Suppress TEXT output, where supported                        |
| `--output-format {text,markdown,json,ndjson}` | Select output format, where structured output is supported   |
| `--color` / `--no-color`                      | Enable or disable colorized terminal output, where supported |
| `--include-file-types`                        | Restrict processing to selected file types, where supported  |
| `--exclude-file-types`                        | Exclude selected file types, where supported                 |

For command applicability, output, verbosity, and formatting options, see
[Shared options](shared-options.md).

{% include-markdown "\_snippets/option-spelling.md" %}

## File type filters

{% include-markdown "\_snippets/file-type-identifiers.md" %}

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

File type filters are supported consistently across:

- CLI options
- TOML configuration
- API overlays
- resolver and probe filtering

For canonical file-type identifier semantics and configuration behavior, see
[Configuration](configuration.md).

## Main commands

See also:

- [Filtering](filtering.md)
- [Policies](policies.md)
- [Shared options](shared-options.md)

### [`check`](commands/check.md)

Detect missing, malformed, or outdated headers.

Dry-run by default:

```bash
topmark check src/
```

Apply changes:

```bash
topmark check --apply src/
```

### [`strip`](commands/strip.md)

Remove existing TopMark headers.

Dry-run preview:

```bash
topmark strip src/
```

Apply removals:

```bash
topmark strip --apply src/
```

### [`probe`](commands/probe.md)

Inspect file type resolution, processor binding, filtering, and probe decisions without mutating
files.

Example:

```bash
topmark probe README.md
```

### [`config` command group](commands/config.md)

#### [`config check`](commands/config/check.md)

Check the validity of the effective merged configuration.

```bash
topmark config check
```

#### [`config dump`](commands/config/dump.md)

Display the effective merged configuration.

```bash
topmark config dump
```

#### [`config defaults`](commands/config/defaults.md)

Display the built-in default configuration.

```bash
topmark config defaults
```

#### [`config init`](commands/config/init.md)

Generate a starter configuration template.

```bash
topmark config init
```

### [`registry` command group](commands/registry.md)

Inspect registered file types, processors, and registry bindings.

#### [`registry filetypes`](commands/registry/filetypes.md)

Inspect file type identities and their matching rules and policies.

```bash
topmark registry filetypes
```

#### [`registry processors`](commands/registry/processors.md)

Inspect header processor identities and their capabilities.

```bash
topmark registry processors
```

#### [`registry bindings`](commands/registry/bindings.md)

inspect effective relationships between file types and processors.

```bash
topmark registry bindings
```

### [`version`](commands/version.md)

Display version and environment information.

```bash
topmark version
```

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

This safety model helps prevent accidental repository-wide modifications.

## Diagnostics and exit behavior

The CLI reports:

- unsupported file types
- malformed headers
- skipped files
- planned mutations
- write failures
- configuration validation issues
- ambiguous or malformed file type identifiers

Diagnostics are designed to remain deterministic and machine-readable.

## Related pages

- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Shared options](shared-options.md)
- [Exit codes](exit-codes.md)
- [Pre-commit integration](pre-commit.md)
- [Configuration discovery](../configuration/discovery.md)

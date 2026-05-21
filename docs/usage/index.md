<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/usage/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Usage documentation

This section contains the user-facing documentation for running TopMark from the command line,
configuring runtime behavior, validating repositories, and integrating TopMark into development
workflows.

Start here if you want to:

- run TopMark from the CLI;
- upgrade an existing repository to TopMark 1.0;
- configure header fields, policies, filtering, or file discovery;
- integrate TopMark with pre-commit;
- understand exit codes, reports, and machine-readable output.

______________________________________________________________________

## Common starting points

- [Upgrading to TopMark 1.0](upgrading-to-1.0.md)
- [Command overview](cli.md)
- [Shared options](shared-options.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Header placement](header-placement.md)
- [Pre-commit integration](pre-commit.md)
- [Exit codes](exit-codes.md)

______________________________________________________________________

## Command reference

- [`topmark check`](commands/check.md)
- [`topmark strip`](commands/strip.md)
- [`topmark probe`](commands/probe.md)
- [`topmark config`](commands/config.md)
- [`topmark registry`](commands/registry.md)
- [`topmark version`](commands/version.md)

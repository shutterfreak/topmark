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

This section contains the user-facing documentation for installing, running, configuring, and
integrating TopMark.

The pages in this section focus on practical CLI usage, repository workflows, configuration,
validation, and automation.

Start here if you want to:

- install TopMark and complete a safe first run;
- run TopMark from the CLI;
- upgrade an existing repository to TopMark 1.0;
- configure header fields, policies, filtering, and file discovery;
- integrate TopMark with pre-commit or CI;
- understand exit codes, reports, and machine-readable output.

______________________________________________________________________

## Common starting points

- [Getting started](getting-started.md) - install TopMark and complete a safe first run.
- [Upgrading to TopMark 1.0](upgrading-to-1.0.md) - migrate repositories from earlier TopMark
  versions.
- [Command overview](cli.md) - understand the CLI structure and shared command behavior.
- [Shared options](shared-options.md) - learn about global options, dry-run behavior, verbosity, and
  output selection.
- [Configuration](configuration.md) - configure layered runtime behavior and policy settings.
- [Filtering](filtering.md) - include, exclude, and constrain file processing.
- [Policies](policies.md) - control insertion, update, validation, and stripping behavior.
- [Header placement](header-placement.md) - understand how TopMark locates and inserts headers.
- [Pre-commit integration](pre-commit.md) - integrate TopMark into local developer workflows.
- [CI integration](ci.md) - validate repositories safely in CI pipelines.
- [Exit codes](exit-codes.md) - interpret CLI exit status values in automation and scripting.

______________________________________________________________________

## Command reference

- [`topmark check`](commands/check.md) - validate, preview, and apply TopMark headers.
- [`topmark strip`](commands/strip.md) - preview and remove TopMark-managed headers.
- [`topmark probe`](commands/probe.md) - inspect file resolution, processor selection, and
  diagnostics.
- [`topmark config`](commands/config.md) - inspect, validate, and generate configuration.
- [`topmark registry`](commands/registry.md) - inspect registered file types, processors, and
  bindings.
- [`topmark version`](commands/version.md) - show version information.

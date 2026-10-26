<!--
topmark:header:start

  project      : TopMark
  file         : upgrading.md
  file_relpath : docs/usage/upgrading.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Upgrading TopMark

Use this page to choose the migration guide for every major-version boundary your repository
crosses. Upgrade one boundary at a time, validate before mutation, and update automation as part of
the same change.

______________________________________________________________________

## Choose your path

First identify the installed version:

```bash
topmark version
```

| Current version | Target version | Required migration guides                                                             |
| --------------- | -------------- | ------------------------------------------------------------------------------------- |
| 2.x             | 3.0.x          | [Upgrading to TopMark 3.0](upgrading-to-3.0.md)                                       |
| 1.x             | 3.0.x          | [Upgrading to 2.0](upgrading-to-2.0.md), then [Upgrading to 3.0](upgrading-to-3.0.md) |
| 0.11.x or older | 3.0.x          | [Upgrading to 1.0](upgrading-to-1.0.md), then 2.0, then 3.0, in order                 |

The historical 1.0 guide remains at its published URL for older repositories. Do not skip it when
moving directly from a pre-1.0 release: the 2.0 guide assumes the 1.0 configuration and command
model.

______________________________________________________________________

## Safe upgrade sequence

For each major boundary:

1. Update TopMark in an isolated environment or a dedicated dependency-update change.

1. Strictly validate configuration before processing files:

   ```bash
   topmark config check --strict
   topmark config dump --show-layers
   ```

1. Run a dry-run check and review its exit status and output:

   ```bash
   topmark check --report noncompliant .
   ```

1. Update CI, pre-commit configuration, shell scripts, API integrations, and output snapshots.

1. Apply header changes only after the dry run is understood:

   ```bash
   topmark check --apply .
   ```

See [CI integration](ci.md), [Pre-commit integration](pre-commit.md), and
[Machine-readable output](machine-output.md) when your automation consumes those contracts.

<!--
topmark:header:start

  project      : TopMark
  file         : descendant-config-discovery.md
  file_relpath : docs/_snippets/descendant-config-discovery.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

For file-processing commands, every explicit directory input contributes both its resolved ancestor
chain and supported descendant configuration sources. Each file receives only the applicable scoped
layers, so a nested configuration overrides inherited settings within its subtree without affecting
siblings. File-agnostic configuration inspection commands continue to use the current working
directory chain unless explicitly given configuration files.

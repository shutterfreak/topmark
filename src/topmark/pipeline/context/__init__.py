# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/pipeline/context/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Context layer for the TopMark pipeline.

The ``topmark.pipeline.context`` package groups the core types that describe
per-file processing state:

* [model][topmark.pipeline.context.model] provides the
  [ProcessingContext][topmark.pipeline.context.model.ProcessingContext], and
  [FlowControl][topmark.pipeline.context.model.FlowControl] data structures.
* [status][topmark.pipeline.context.status] defines the aggregate
  ``ProcessingStatus`` used as the single source of truth for all
  pipeline axes.
* [policy][topmark.pipeline.context.policy] contains helpers that interpret
  the effective policy for a given context.

Higher-level engine and runner modules depend on this package but should not
need to reach into individual implementation details beyond the documented
public attributes and methods.
"""

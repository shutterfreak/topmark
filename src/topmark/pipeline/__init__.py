# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/pipeline/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark processing pipeline package.

This package contains the components that implement TopMark's multi-step
header processing pipeline, including:

- Context handling and shared state between steps
- Step implementations (resolver, reader, comparer, patcher, etc.)
- Pipeline assembly and execution helpers
- Contracts and status enums used to coordinate step behavior

The public API is composed of the pipeline assembly helpers in
[`topmark.pipeline.pipelines`][topmark.pipeline.pipelines], the execution helper in
[`topmark.pipeline.runner`][topmark.pipeline.runner], and the shared context model in
[`topmark.pipeline.context`][topmark.pipeline.context].
"""

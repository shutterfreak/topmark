# topmark:header:start
#
#   file         : __init__.py
#   file_relpath : src/topmark/filetypes/__init__.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Registry and matching logic for all supported file types in TopMark.

This module maintains a registry of file types supported by TopMark and provides
functions to match file paths against these types, validate requested file types
from CLI arguments, and resolve the best matching file type for a given path.
"""

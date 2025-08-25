# topmark:header:start
#
#   file         : contracts.py
#   file_relpath : src/topmark/pipeline/contracts.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Module defining type contracts for pipeline steps in TopMark.

This module provides type aliases for pipeline step functions used in TopMark.
`Step` is a callable type alias representing a single pipeline step function,
which takes a ProcessingContext as input and returns a ProcessingContext.
"""

from typing import Callable

from .context import ProcessingContext

Step = Callable[[ProcessingContext], ProcessingContext]

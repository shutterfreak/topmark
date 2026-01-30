# topmark:header:start
#
#   project      : TopMark
#   file         : colored_enum.py
#   file_relpath : src/topmark/rendering/colored_enum.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Color-aware enum primitives for human-facing rendering.

This module provides a small, focused base enum that stores a textual value
while *optionally* attaching a colorizer (callable that decorates strings).
It avoids coupling the rest of the system to a specific color library.

Key types:
    - `Colorizer`: Protocol describing any callable compatible with
      `yachalk.ChalkBuilder.__call__`.
    - `ColoredStrEnum`: `str, Enum` that stores the enum's text value and a
      colorizer (e.g., a yachalk style). The enum `.value` remains a plain
      string, while the colorizer is exposed via `.color`.

Design:
    `ColoredStrEnum` keeps `_value_` as the plain `str` and stores the
    color function separately (`_color`). This preserves Enum semantics
    (hashing, equality, `repr`) and avoids crashes in pretty-printers that
    assume a scalar value. The colorizer can be any callable that matches the
    `Colorizer` protocol; in practice, it's typically a `ChalkBuilder`.

Example:
    ```python
    from yachalk import chalk

    class Cluster(ColoredStrEnum):
        OK    = ("ok", chalk.green)
        ERROR = ("error", chalk.red_bright)

    print(Cluster.OK.value)            # 'ok'
    print(Cluster.OK.color("hello"))   # green "hello"
    ```
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class Colorizer(Protocol):
    """Callable that decorates a string for display.

    Designed to be compatible with `yachalk.ChalkBuilder.__call__`, which
    accepts a variadic list of arguments and a `sep` keyword. Implementations
    may ignore extra args; TopMark typically calls colorizers with a single string.
    """

    def __call__(self, *args: object, sep: str = " ") -> str:
        """Colorize and concatenate provided arguments into a display string.

        This method takes one or more objects (typically strings), optionally joins them
        using the specified separator, and applies colorization or decoration suitable for
        display in a terminal or other output. The decoration is implementation-dependent,
        and may include color, bolding, or other markup.

        Args:
            *args (object): One or more objects to render, typically strings.
            sep (str): Separator between arguments when multiple values
                are provided. Defaults to a single space.

        Returns:
            str: The colorized and concatenated output string.
        """
        ...


class ColoredStrEnum(str, Enum):
    """Enum whose *value* is a string and that carries an associated colorizer.

    The enum member remains a `str` (so Enum internals, hashing, repr, etc.
    behave normally), and the colorizer is stored separately on the instance.
    """

    _value_: str
    _color: Colorizer

    def __new__(cls, text: str, color: Colorizer) -> ColoredStrEnum:
        """Construct a colored enum member.

        Args:
            text (str): The textual value for the enum member (stored in `_value_`).
            color (Colorizer): A callable used to colorize text for display.

        Returns:
            ColoredStrEnum: The newly constructed enum member.

        Notes:
            Stores the textual value in `_value_` and the colorizer in `_color` to preserve
            `Enum` semantics while exposing color separately.
        """
        # Ensure the enum *value* is the textual string
        obj: ColoredStrEnum = str.__new__(cls, text)
        obj._value_ = text
        obj._color = color
        return obj

    @property
    def value(self) -> str:
        """Return the textual value of the enum member.

        Returns:
            str: The string value associated with this member.
        """
        # `_value_` is assigned in __new__; Enum guarantees it exists on members.
        return self._value_

    @property
    def color(self) -> Colorizer:
        """Return the colorizer associated with this member.

        Returns:
            Colorizer: A callable that decorates strings for display.
        """
        return self._color

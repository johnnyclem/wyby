"""Unicode character width utilities for terminal cell grids.

Provides display-width calculation for individual characters and strings,
used by :class:`~wyby.grid.CellBuffer` to correctly place wide characters
(CJK ideographs, fullwidth forms) that occupy two terminal columns.

Width classification uses :func:`unicodedata.east_asian_width` from the
Python standard library, which follows Unicode Standard Annex #11
(East Asian Width).  No external dependency (e.g. ``wcwidth``) is
required.

Caveats
-------
- **Terminal disagreement.**  UAX #11 is a guideline, not a mandate.
  Individual terminal emulators may render specific characters at a
  different width than what this module reports.  Most modern terminals
  (kitty, iTerm2, WezTerm, Windows Terminal, GNOME Terminal) agree on
  common characters, but edge cases exist — especially for characters
  in the Ambiguous (``A``) category.
- **Emoji width is unreliable.**  Simple single-codepoint emoji are
  classified as Wide (``W``) by UAX #11, so :func:`char_width` returns
  2 for them.  However, actual rendering varies wildly: some terminals
  display emoji as 1 column, others as 2, and multi-codepoint emoji
  (skin tone modifiers, ZWJ sequences, keycap sequences) are not
  single characters at all.  **Do not rely on this module for emoji
  width.**  Stick to ASCII, box-drawing, block elements, and simple
  Unicode symbols for reliable results.
- **Combining characters.**  Characters like combining diacriticals
  (U+0300–U+036F) have zero display width — they modify the preceding
  character.  :func:`char_width` returns 0 for them, but
  :class:`~wyby.grid.Cell` requires a single character per cell.
  Placing a combining character in its own cell will produce
  terminal-dependent results (typically a standalone diacritical
  rendered on a dotted circle).
- **Control characters.**  C0/C1 control characters (U+0000–U+001F,
  U+007F–U+009F) return width 0.  They should not be placed in cells.
- **Ambiguous width characters.**  Characters with East Asian Width
  ``A`` (e.g. some Greek, Cyrillic, and mathematical symbols) are
  treated as width 1 here.  In CJK locale contexts, some terminals
  render these at width 2.  This module does not account for locale.
"""

from __future__ import annotations

import unicodedata

# East Asian Width values that indicate a 2-column character.
_WIDE_EAW_VALUES = frozenset({"W", "F"})  # Wide, Fullwidth

# Unicode general categories with zero display width.
_ZERO_WIDTH_CATEGORIES = frozenset({
    "Mn",  # Mark, Nonspacing (combining diacriticals, etc.)
    "Me",  # Mark, Enclosing
    "Cf",  # Format (ZWJ, ZWNJ, soft hyphen, etc.)
    "Cc",  # Control (C0/C1 control characters)
})


def char_width(ch: str) -> int:
    """Return the terminal display width of a single character.

    Returns
    -------
    int
        - ``2`` for wide characters (CJK ideographs, fullwidth forms).
        - ``0`` for combining marks, control characters, and format
          characters (ZWJ, ZWNJ, etc.).
        - ``1`` for everything else (ASCII, Latin, Cyrillic, Greek,
          box-drawing, block elements, arrows, most symbols).

    Raises
    ------
    ValueError
        If *ch* is not exactly one character long.

    Examples
    --------
    >>> char_width("A")
    1
    >>> char_width("│")       # box-drawing
    1
    >>> char_width("█")       # full block
    1
    >>> char_width("中")      # CJK ideograph
    2
    >>> char_width("Ａ")      # fullwidth A
    2
    """
    if not isinstance(ch, str) or len(ch) != 1:
        msg = f"expected a single character, got {ch!r}"
        raise ValueError(msg)

    category = unicodedata.category(ch)
    if category in _ZERO_WIDTH_CATEGORIES:
        return 0

    eaw = unicodedata.east_asian_width(ch)
    if eaw in _WIDE_EAW_VALUES:
        return 2

    return 1


def string_width(text: str) -> int:
    """Return the total terminal display width of a string.

    Sums :func:`char_width` for each character in *text*.  This gives
    the number of terminal columns the string would occupy if rendered
    without line wrapping.

    Caveats
    -------
    - Does not account for multi-codepoint sequences (emoji ZWJ,
      variation selectors, grapheme clusters).  Each Python character
      is measured independently.
    - Does not account for tab stops or newlines.

    Examples
    --------
    >>> string_width("Hello")
    5
    >>> string_width("中文")
    4
    >>> string_width("A中B")
    4
    """
    return sum(char_width(ch) for ch in text)


def is_wide_char(ch: str) -> bool:
    """Return ``True`` if *ch* occupies two terminal columns.

    Convenience wrapper around :func:`char_width`.

    Examples
    --------
    >>> is_wide_char("A")
    False
    >>> is_wide_char("中")
    True
    >>> is_wide_char("Ａ")     # fullwidth A
    True
    """
    return char_width(ch) == 2

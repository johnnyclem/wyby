"""Unicode character width utilities for terminal cell grids.

Provides display-width calculation for individual characters and strings,
used by :class:`~wyby.grid.CellBuffer` to correctly place wide characters
(CJK ideographs, fullwidth forms) that occupy two terminal columns.

Width classification uses :func:`unicodedata.east_asian_width` from the
Python standard library, which follows Unicode Standard Annex #11
(East Asian Width).  No external dependency (e.g. ``wcwidth``) is
required.

Grapheme cluster support
------------------------
The :func:`grapheme_width`, :func:`grapheme_string_width`, and
:func:`iter_grapheme_clusters` functions provide width calculation
that accounts for multi-codepoint grapheme clusters — user-perceived
characters that consist of several Unicode codepoints (e.g. base
character + combining marks, emoji ZWJ sequences, flag sequences).

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
- **Simplified grapheme segmentation.**  :func:`iter_grapheme_clusters`
  does NOT implement full UAX #29 (Unicode Text Segmentation).  It
  handles the most common cases — combining marks, ZWJ sequences,
  variation selectors, emoji modifiers, and regional indicator pairs —
  but may mis-segment complex scripts (Indic scripts with virama/halant,
  complex emoji tag sequences).  For full correctness, use the
  third-party ``grapheme`` package.
"""

from __future__ import annotations

import unicodedata
from typing import Iterator

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


# ---------------------------------------------------------------------------
# Grapheme cluster segmentation and width
# ---------------------------------------------------------------------------

# Zero-Width Joiner — joins adjacent characters into a single grapheme
# cluster (used in emoji ZWJ sequences like family/profession emoji).
_ZWJ = "\u200D"

# Variation selectors change the presentation of the preceding character.
# VS1–VS16 (U+FE00–U+FE0F).  VS16 (U+FE0F) is the emoji presentation
# selector — it requests that the preceding character be rendered as a
# colorful emoji glyph rather than a text glyph.
_VARIATION_SELECTOR_START = 0xFE00
_VARIATION_SELECTOR_END = 0xFE0F

# Regional indicator symbols (U+1F1E6–U+1F1FF) combine in pairs to form
# flag emoji (e.g. U+1F1FA U+1F1F8 = 🇺🇸).
_REGIONAL_INDICATOR_START = 0x1F1E6
_REGIONAL_INDICATOR_END = 0x1F1FF

# Emoji skin tone modifiers (U+1F3FB–U+1F3FF) — Fitzpatrick scale.
_EMOJI_MODIFIER_START = 0x1F3FB
_EMOJI_MODIFIER_END = 0x1F3FF


def _is_regional_indicator(ch: str) -> bool:
    """Return True if *ch* is a Regional Indicator Symbol."""
    cp = ord(ch)
    return _REGIONAL_INDICATOR_START <= cp <= _REGIONAL_INDICATOR_END


def _is_variation_selector(ch: str) -> bool:
    """Return True if *ch* is a variation selector (VS1–VS16)."""
    cp = ord(ch)
    return _VARIATION_SELECTOR_START <= cp <= _VARIATION_SELECTOR_END


def _is_emoji_modifier(ch: str) -> bool:
    """Return True if *ch* is an emoji skin tone modifier."""
    cp = ord(ch)
    return _EMOJI_MODIFIER_START <= cp <= _EMOJI_MODIFIER_END


def _is_combining(ch: str) -> bool:
    """Return True if *ch* is a combining mark (Mn, Me, or Mc)."""
    return unicodedata.category(ch) in {"Mn", "Me", "Mc"}


def iter_grapheme_clusters(text: str) -> Iterator[str]:
    """Yield approximate grapheme clusters from *text*.

    A grapheme cluster is a user-perceived character that may consist of
    multiple Unicode codepoints.  This function groups codepoints into
    clusters using simplified rules that cover common cases:

    - Base character + combining marks (e.g. ``e`` + combining acute)
    - ZWJ sequences (e.g. family/profession emoji)
    - Variation selectors (VS1–VS16)
    - Regional indicator pairs (flag emoji)
    - Emoji skin tone modifiers

    Caveats
    -------
    - Does **not** implement full UAX #29 grapheme cluster segmentation.
    - May mis-segment complex scripts with virama/halant joining (e.g.
      Devanagari conjuncts) or emoji tag sequences (U+E0020–U+E007F).
    - For full correctness, use the third-party ``grapheme`` package.

    Examples
    --------
    >>> list(iter_grapheme_clusters("Hello"))
    ['H', 'e', 'l', 'l', 'o']
    >>> list(iter_grapheme_clusters("e\\u0301"))  # e + combining acute
    ['e\\u0301']
    """
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        cluster = ch
        i += 1

        # Regional indicator pairs form flag emoji (always consumed in
        # pairs; a lone trailing indicator becomes its own cluster).
        if _is_regional_indicator(ch):
            if i < n and _is_regional_indicator(text[i]):
                cluster += text[i]
                i += 1
            # Absorb any trailing combining marks / variation selectors.
            while i < n and (
                _is_combining(text[i]) or _is_variation_selector(text[i])
            ):
                cluster += text[i]
                i += 1
            yield cluster
            continue

        # Absorb combining marks, variation selectors, emoji modifiers,
        # and ZWJ-joined continuations into the current cluster.
        while i < n:
            next_ch = text[i]
            if (
                _is_combining(next_ch)
                or _is_variation_selector(next_ch)
                or _is_emoji_modifier(next_ch)
            ):
                cluster += next_ch
                i += 1
            elif next_ch == _ZWJ and i + 1 < n:
                # ZWJ joins the next character into this cluster.
                cluster += next_ch + text[i + 1]
                i += 2
            else:
                break

        yield cluster


def grapheme_width(grapheme: str) -> int:
    """Return the terminal display width of a grapheme cluster.

    A grapheme cluster is a user-perceived character that may consist of
    multiple Unicode codepoints.  The display width is determined by the
    base (first) character of the cluster, with one exception: if the
    cluster contains VS16 (U+FE0F, emoji presentation selector) and has
    more than one codepoint, the width is 2 — VS16 requests emoji
    presentation, which most modern terminals render at double width.

    For single codepoints this is equivalent to :func:`char_width`
    (without the single-character validation).

    Caveats
    -------
    - Terminal emulators disagree on emoji width.  The VS16 heuristic
      works for most modern terminals but is not guaranteed.
    - ZWJ sequence width is based on the leading character.  Some
      terminals may render these wider or narrower than reported.

    Parameters
    ----------
    grapheme : str
        One or more codepoints representing a single grapheme cluster.

    Returns
    -------
    int
        The display width: 0, 1, or 2.

    Examples
    --------
    >>> grapheme_width("A")
    1
    >>> grapheme_width("中")
    2
    >>> grapheme_width("e\\u0301")  # e + combining acute
    1
    """
    if not grapheme:
        return 0

    base = grapheme[0]
    category = unicodedata.category(base)
    if category in _ZERO_WIDTH_CATEGORIES:
        return 0

    eaw = unicodedata.east_asian_width(base)
    if eaw in _WIDE_EAW_VALUES:
        return 2

    # VS16 (U+FE0F) requests emoji presentation, which typically renders
    # at width 2 on modern terminals.  Only apply this when the cluster
    # has multiple codepoints (a lone VS16 would be zero-width).
    if len(grapheme) > 1 and "\uFE0F" in grapheme:
        return 2

    return 1


def grapheme_string_width(text: str) -> int:
    """Return the total display width of *text* using grapheme clusters.

    Unlike :func:`string_width`, this function segments the text into
    grapheme clusters before calculating width.  This gives more accurate
    results for text containing multi-codepoint sequences like emoji ZWJ
    sequences, flag emoji, or characters with combining marks.

    For ASCII and simple Unicode text without combining characters or
    multi-codepoint sequences, this returns the same result as
    :func:`string_width` but is slightly slower due to the segmentation
    overhead.  Prefer :func:`string_width` for performance-critical paths
    that only handle simple text.

    Examples
    --------
    >>> grapheme_string_width("Hello")
    5
    >>> grapheme_string_width("中文")
    4
    >>> grapheme_string_width("e\\u0301")  # e + combining acute
    1
    """
    return sum(grapheme_width(cluster) for cluster in iter_grapheme_clusters(text))


# ---------------------------------------------------------------------------
# Emoji detection
# ---------------------------------------------------------------------------

# Common emoji Unicode ranges.  This is not exhaustive — Unicode defines
# emoji via properties (Emoji, Emoji_Presentation, Emoji_Component) that
# are not directly accessible from the standard library.  These ranges
# cover the vast majority of emoji encountered in practice.
_EMOJI_RANGES: list[tuple[int, int]] = [
    (0x2600, 0x27BF),    # Miscellaneous Symbols, Dingbats
    (0x2B50, 0x2B55),    # Stars, circles
    (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map Symbols
    (0x1F700, 0x1F77F),  # Alchemical Symbols
    (0x1F780, 0x1F7FF),  # Geometric Shapes Extended
    (0x1F800, 0x1F8FF),  # Supplemental Arrows-C
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA00, 0x1FA6F),  # Chess Symbols
    (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
    (0x231A, 0x231B),    # Watch, Hourglass
    (0x23E9, 0x23F3),    # Play buttons, hourglasses
    (0x23F8, 0x23FA),    # Pause, stop, record
    (0x25AA, 0x25AB),    # Small squares
    (0x25FB, 0x25FE),    # Medium squares
    (0x2934, 0x2935),    # Curved arrows
    (0x2B05, 0x2B07),    # Arrows
]


def _is_emoji_codepoint(cp: int) -> bool:
    """Return True if *cp* falls in a common emoji codepoint range."""
    for start, end in _EMOJI_RANGES:
        if start <= cp <= end:
            return True
    return False


def contains_emoji(text: str) -> bool:
    """Return ``True`` if *text* contains any emoji characters.

    Checks for:

    - Single codepoints in common emoji Unicode ranges (emoticons,
      pictographs, transport symbols, etc.)
    - Emoji presentation selector (VS16 / U+FE0F)
    - Regional indicator symbols (flag emoji)
    - Emoji skin tone modifiers (Fitzpatrick scale)
    - Zero-Width Joiner sequences (ZWJ emoji)

    This function is intentionally conservative — it may return ``True``
    for some non-emoji characters that share Unicode blocks with emoji,
    but it will not miss common emoji.

    Caveats
    -------
    - Unicode defines emoji via character properties (``Emoji``,
      ``Emoji_Presentation``) that are not accessible from Python's
      :mod:`unicodedata` module.  This function uses heuristic range
      checks that cover common emoji but are not exhaustive.
    - Some characters in the detected ranges (e.g. U+2600 BLACK SUN
      WITH RAYS) have dual text/emoji presentation and may render as
      a monochrome symbol on some terminals, not as a colourful emoji.

    Parameters
    ----------
    text : str
        The string to scan for emoji.

    Returns
    -------
    bool
        ``True`` if at least one emoji character or sequence is found.

    Examples
    --------
    >>> contains_emoji("Hello")
    False
    >>> contains_emoji("Hello 🌍")
    True
    >>> contains_emoji("Flag: \\U0001F1FA\\U0001F1F8")  # 🇺🇸
    True
    """
    for ch in text:
        cp = ord(ch)
        if _is_emoji_codepoint(cp):
            return True
        if _is_regional_indicator(ch):
            return True
        if _is_emoji_modifier(ch):
            return True
        # VS16 (emoji presentation selector) signals emoji intent.
        if cp == 0xFE0F:
            return True
    return False

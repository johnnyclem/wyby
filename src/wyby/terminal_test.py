"""Manual test-render card for verifying rendering across terminal emulators.

This module provides a :class:`TestCard` that generates a
:class:`~wyby.grid.CellBuffer` containing diagnostic test patterns:
ASCII text, box-drawing characters, block elements, colour swatches
(16-colour, 256-colour, truecolor gradient), wide characters (CJK),
bold/dim styles, and an optional emoji section.  Running the test card
in different terminal emulators reveals rendering differences that are
invisible in automated tests.

Usage::

    from wyby.terminal_test import TestCard
    card = TestCard()
    buffer = card.build()   # returns a CellBuffer
    report = card.report()  # returns a human-readable summary string

The primary entry point for quick verification is :func:`build_test_card`,
which returns a ready-to-render :class:`~wyby.grid.CellBuffer`, and
:func:`format_report`, which returns a multi-line summary of detected
capabilities and known caveats for the current terminal.

Why manual testing is necessary
-------------------------------
Automated tests run in non-TTY environments (pytest captures stdout) and
cannot exercise the terminal emulator's rendering pipeline.  The
following behaviours vary across emulators and **cannot** be verified
programmatically:

- **Box-drawing / block element rendering.**  All modern terminals render
  these correctly, but some bitmap-font configurations misalign them.
- **Colour accuracy.**  The 16 ANSI system colours depend on the user's
  terminal theme.  The 256-colour palette is standardised but rarely
  visually inspected.  Truecolor gradients reveal banding or dithering
  on terminals that silently downgrade.
- **Wide character alignment.**  CJK characters should occupy exactly two
  columns.  Misalignment corrupts the rest of the row.
- **Bold / dim rendering.**  Some terminals render bold as bright colour
  instead of heavier weight.  Dim may be unsupported or invisible.
- **Emoji width.**  Emoji rendering is notoriously inconsistent across
  terminals — width may be 1 or 2 columns, and multi-codepoint sequences
  are not representable in wyby's one-character-per-cell model.

Known terminal emulator caveats
-------------------------------
The following are empirically observed differences.  They are documented
here — not as exhaustive compatibility guarantees — but as a starting
point for manual verification:

- **iTerm2** (macOS): Full truecolor, good Unicode support.  Emoji
  render at 2 columns (consistent with UAX #11).  Box-drawing seamless
  with most fonts.  Ligature-enabled fonts may unexpectedly join
  box-drawing characters.
- **Terminal.app** (macOS built-in): Supports 256 colours.  Truecolor
  may silently downgrade to 256.  Bold often renders as bright colour
  rather than increased weight.  Some CJK glyphs misalign with the
  default font (Menlo).
- **Windows Terminal**: Full truecolor, good Unicode.  Emoji render
  at 2 columns.  Legacy ``conhost`` mode has significantly worse
  Unicode and colour support — ensure the user runs Windows Terminal,
  not ``cmd.exe`` with ``conhost``.
- **kitty**: Full truecolor, excellent Unicode support.  Uses its own
  text rendering engine (not the system one).  Emoji render at 2
  columns.  ``$TERM_PROGRAM`` is set to ``kitty``.
- **WezTerm**: Full truecolor, good Unicode.  Emoji render at 2
  columns.  Reports capabilities via ``$TERM_PROGRAM=WezTerm``.
- **GNOME Terminal / VTE-based**: Full truecolor (since VTE 0.36).
  ``$COLORTERM=truecolor`` is set.  Emoji width is generally 2 but
  may vary with older VTE versions.
- **Alacritty**: Full truecolor, GPU-accelerated.  No ligature support.
  Box-drawing is pixel-perfect.  Emoji render at 2 columns but may
  appear as tofu (missing glyphs) if the configured font lacks them.
- **tmux / screen**: The multiplexer interposes between the application
  and the outer terminal.  ``$TERM`` is overridden (typically to
  ``screen-256color`` or ``tmux-256color``).  ``$COLORTERM`` may not
  pass through unless explicitly configured.  This can cause capability
  under-reporting.  Users should set ``set -g default-terminal
  tmux-256color`` and ``set -ga terminal-overrides ",*:Tc"`` in
  ``~/.tmux.conf`` for truecolor pass-through.
- **SSH**: Terminal capabilities depend on the *remote* terminal's
  ``$TERM`` and the SSH client's terminal emulation.  Latency is
  additive: each frame's ANSI output traverses the network, so even
  small grids may feel sluggish.  ``ssh -C`` (compression) helps for
  large frames but adds CPU overhead.
- **Linux virtual console** (``/dev/ttyN``): Limited to 16 colours.
  No alternate screen buffer.  No truecolor.  Unicode support depends
  on the framebuffer console configuration.  Not a practical target
  for wyby games, but the test card degrades gracefully.
"""

from __future__ import annotations

import logging

from wyby.diagnostics import TerminalCapabilities, detect_capabilities
from wyby.grid import CellBuffer

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test-card geometry
# ---------------------------------------------------------------------------

# Width and height of the test card buffer.  Chosen to fit an 80x24
# terminal with room to spare.  Wider terminals will see blank space
# to the right; narrower terminals will clip (silent, no error).
_CARD_WIDTH = 72
_CARD_HEIGHT = 23

# Character used for horizontal and vertical separators.
_H_RULE = "─"
_V_RULE = "│"


# ---------------------------------------------------------------------------
# Known terminal caveats (structured data for programmatic access)
# ---------------------------------------------------------------------------

# Mapping from terminal program identifier (as detected by
# _detect_terminal_program) to a short description of known rendering
# caveats.  These are intentionally terse — the module docstring has
# the full discussion.
#
# Caveat: terminal identification is best-effort.  Inside tmux/screen,
# the reported program may be the multiplexer, not the outer terminal.
# An unrecognised terminal (None key) does not mean the terminal is
# incapable — only unidentified.
TERMINAL_CAVEATS: dict[str | None, str] = {
    "iTerm2": (
        "Good truecolor & Unicode.  Ligature fonts may join "
        "box-drawing chars."
    ),
    "iTerm.app": (
        "Good truecolor & Unicode.  Ligature fonts may join "
        "box-drawing chars."
    ),
    "Apple_Terminal": (
        "256 colours only (truecolor silently downgrades).  Bold may "
        "render as bright colour.  CJK may misalign with default font."
    ),
    "kitty": (
        "Excellent truecolor & Unicode.  Custom rendering engine."
    ),
    "WezTerm": (
        "Good truecolor & Unicode.  GPU-accelerated."
    ),
    "Windows Terminal": (
        "Good truecolor & Unicode.  Legacy conhost has worse support."
    ),
    "Alacritty": (
        "Good truecolor, GPU-accelerated.  No ligatures.  Emoji may "
        "show as tofu if font lacks glyphs."
    ),
    "tmux": (
        "Multiplexer — capabilities depend on outer terminal.  "
        "Truecolor requires terminal-overrides config."
    ),
    "screen": (
        "Multiplexer — capabilities depend on outer terminal.  "
        "Limited colour pass-through by default."
    ),
    None: (
        "Terminal not identified.  Capabilities may be under-reported."
    ),
}


# ---------------------------------------------------------------------------
# Test-card builder
# ---------------------------------------------------------------------------


class TestCard:
    """Generates a diagnostic test-card :class:`~wyby.grid.CellBuffer`.

    The test card includes sections for:

    1. **Header** — detected terminal program and size.
    2. **ASCII** — printable ASCII characters (safe baseline).
    3. **Box-drawing** — ``─│┌┐└┘├┤┬┴┼`` and related characters.
    4. **Block elements** — ``█▓▒░▀▄▌▐`` for density rendering.
    5. **16-colour swatches** — ANSI system colours as background fills.
    6. **256-colour sample** — a selection of the 6x6x6 colour cube.
    7. **Truecolor gradient** — a red-to-blue gradient using hex colours.
    8. **Bold / dim** — style attribute rendering.
    9. **Wide characters** — CJK ideographs to test 2-column alignment.
    10. **Emoji** (optional) — known-unreliable, included for comparison.

    Args:
        caps: Pre-detected :class:`~wyby.diagnostics.TerminalCapabilities`.
            If ``None``, :func:`~wyby.diagnostics.detect_capabilities` is
            called to probe the current environment.
        include_emoji: Whether to include the emoji test row.  Defaults
            to ``True``.  Set to ``False`` to skip the row entirely
            (useful for environments where emoji cause alignment issues).
        width: Override the test card width.  Defaults to 72.
        height: Override the test card height.  Defaults to 23.

    Caveats:
        - The test card is designed for **manual visual inspection**, not
          automated validation.  There is no programmatic way to verify
          that the terminal rendered it correctly — you must look at it.
        - The card assumes a monospace font.  Proportional fonts will
          misalign every row.
        - Colours in the 16-colour swatch depend on the user's terminal
          theme.  The labels (``"red"``, ``"cyan"``, etc.) refer to the
          ANSI colour *index*, not the actual rendered hue.
        - The truecolor gradient uses hex colour strings.  On terminals
          that do not support truecolor, Rich will silently downgrade to
          the nearest 256-colour or 16-colour equivalent, producing
          visible banding.  This is expected behaviour and is itself a
          useful diagnostic signal.
        - Wide characters (CJK) occupy 2 columns.  If the terminal's
          font lacks CJK glyphs, they may render as replacement
          characters (``□``) at an unpredictable width.
        - The emoji row is inherently unreliable.  Its purpose is to
          demonstrate *how* the current terminal handles emoji, not to
          assert that it handles them correctly.
    """

    def __init__(
        self,
        caps: TerminalCapabilities | None = None,
        *,
        include_emoji: bool = True,
        width: int = _CARD_WIDTH,
        height: int = _CARD_HEIGHT,
    ) -> None:
        self._caps = caps if caps is not None else detect_capabilities()
        self._include_emoji = include_emoji
        self._width = max(1, width)
        self._height = max(1, height)

    @property
    def capabilities(self) -> TerminalCapabilities:
        """The terminal capabilities snapshot used by this test card."""
        return self._caps

    @property
    def width(self) -> int:
        """Width (columns) of the test card buffer."""
        return self._width

    @property
    def height(self) -> int:
        """Height (rows) of the test card buffer."""
        return self._height

    def build(self) -> CellBuffer:
        """Build the test-card :class:`~wyby.grid.CellBuffer`.

        Returns:
            A :class:`~wyby.grid.CellBuffer` of size
            ``(self.width, self.height)`` populated with test patterns.
            Pass this to :meth:`~wyby.renderer.Renderer.present` or
            directly to ``Console.print()`` for display.
        """
        buf = CellBuffer(self._width, self._height)
        row = 0

        # -- Header --
        row = self._draw_header(buf, row)

        # -- Separator --
        row = self._draw_separator(buf, row)

        # -- ASCII --
        row = self._draw_ascii(buf, row)

        # -- Box-drawing --
        row = self._draw_box_drawing(buf, row)

        # -- Block elements --
        row = self._draw_block_elements(buf, row)

        # -- Separator --
        row = self._draw_separator(buf, row)

        # -- 16-colour swatches --
        row = self._draw_ansi16(buf, row)

        # -- 256-colour sample --
        row = self._draw_ansi256_sample(buf, row)

        # -- Truecolor gradient --
        row = self._draw_truecolor_gradient(buf, row)

        # -- Separator --
        row = self._draw_separator(buf, row)

        # -- Bold / dim --
        row = self._draw_styles(buf, row)

        # -- Wide characters (CJK) --
        row = self._draw_wide_chars(buf, row)

        # -- Emoji (optional) --
        if self._include_emoji:
            row = self._draw_emoji(buf, row)

        return buf

    def report(self) -> str:
        """Return a multi-line text report of detected capabilities and caveats.

        The report includes the detected terminal program, colour
        support, UTF-8 status, terminal size, and any known caveats
        for the detected terminal emulator.

        Returns:
            A human-readable multi-line string.  Suitable for printing
            to stderr or a log file alongside the visual test card.
        """
        caps = self._caps
        lines: list[str] = []
        lines.append("wyby terminal test report")
        lines.append("=" * 40)
        lines.append(f"Terminal program : {caps.terminal_program or '(unknown)'}")
        lines.append(f"Colour support   : {caps.color_support.name}")
        lines.append(f"UTF-8            : {caps.utf8_supported}")
        lines.append(f"TTY              : {caps.is_tty}")
        lines.append(f"Size             : {caps.columns}x{caps.rows}")
        lines.append(f"$COLORTERM       : {caps.colorterm_env or '(unset)'}")
        lines.append(f"$TERM            : {caps.term_env or '(unset)'}")
        lines.append("")

        # Look up caveat for the detected terminal program.
        caveat = TERMINAL_CAVEATS.get(caps.terminal_program)
        if caveat is None:
            # Try None key for completely unidentified terminals.
            caveat = TERMINAL_CAVEATS.get(None, "")
        lines.append(f"Known caveats: {caveat}")
        lines.append("")
        lines.append(
            "Note: This report reflects detected capabilities at a "
            "point in time.  Inside tmux/screen, the reported terminal "
            "may be the multiplexer, not the outer terminal."
        )
        return "\n".join(lines)

    # -- Internal drawing helpers -------------------------------------------

    def _draw_header(self, buf: CellBuffer, row: int) -> int:
        """Draw the header section (terminal info)."""
        if row >= self._height:
            return row
        caps = self._caps
        prog = caps.terminal_program or "unknown"
        header = f"wyby test card | {prog} | {caps.columns}x{caps.rows}"
        # Truncate to fit width.
        header = header[:self._width]
        buf.put_text(0, row, header, fg="bright_white", bold=True)
        return row + 1

    def _draw_separator(self, buf: CellBuffer, row: int) -> int:
        """Draw a horizontal separator line."""
        if row >= self._height:
            return row
        line = _H_RULE * self._width
        buf.put_text(0, row, line, fg="bright_black")
        return row + 1

    def _draw_ascii(self, buf: CellBuffer, row: int) -> int:
        """Draw printable ASCII characters (0x20–0x7E)."""
        if row >= self._height:
            return row
        label = "ASCII: "
        # Printable ASCII: space (0x20) through tilde (0x7E).
        chars = "".join(chr(c) for c in range(0x20, 0x7F))
        text = label + chars
        text = text[:self._width]
        buf.put_text(0, row, label, fg="cyan")
        buf.put_text(len(label), row, chars[:self._width - len(label)])
        return row + 1

    def _draw_box_drawing(self, buf: CellBuffer, row: int) -> int:
        """Draw box-drawing characters to test seamless line rendering."""
        if row >= self._height:
            return row
        label = "Box:   "
        # A selection of box-drawing characters.
        box_chars = "┌─┬─┐│ │ │├─┼─┤└─┴─┘╔═╦═╗║ ║ ║╠═╬═╣╚═╩═╝"
        text = box_chars[:self._width - len(label)]
        buf.put_text(0, row, label, fg="cyan")
        buf.put_text(len(label), row, text)
        return row + 1

    def _draw_block_elements(self, buf: CellBuffer, row: int) -> int:
        """Draw block element characters for density testing."""
        if row >= self._height:
            return row
        label = "Block: "
        # Block elements: full, dark shade, medium shade, light shade,
        # upper half, lower half, left half, right half.
        blocks = "█▓▒░▀▄▌▐ █▓▒░▀▄▌▐ █▓▒░▀▄▌▐"
        text = blocks[:self._width - len(label)]
        buf.put_text(0, row, label, fg="cyan")
        buf.put_text(len(label), row, text)
        return row + 1

    def _draw_ansi16(self, buf: CellBuffer, row: int) -> int:
        """Draw 16-colour ANSI background swatches.

        Caveat: the actual colours displayed depend on the user's
        terminal theme.  The labels refer to ANSI colour *indices*,
        not absolute hues.
        """
        if row >= self._height:
            return row

        # Standard 8 colours (row 1).
        label = "16clr: "
        buf.put_text(0, row, label, fg="cyan")
        col = len(label)
        std_names = [
            "black", "red", "green", "yellow",
            "blue", "magenta", "cyan", "white",
        ]
        for name in std_names:
            if col + 3 > self._width:
                break
            # Use contrasting fg for readability.
            fg = "white" if name in ("black", "red", "blue", "magenta") else "black"
            buf.put_text(col, row, f" {name[0].upper()} ", fg=fg, bg=name)
            col += 3
        row += 1
        if row >= self._height:
            return row

        # Bright 8 colours (row 2).
        buf.put_text(0, row, "       ", fg="cyan")
        col = len(label)
        bright_names = [
            "bright_black", "bright_red", "bright_green", "bright_yellow",
            "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
        ]
        for name in bright_names:
            if col + 3 > self._width:
                break
            fg = "black" if "white" in name or "yellow" in name or "green" in name or "cyan" in name else "white"
            buf.put_text(col, row, f" {name.split('_')[1][0].upper()} ", fg=fg, bg=name)
            col += 3
        return row + 1

    def _draw_ansi256_sample(self, buf: CellBuffer, row: int) -> int:
        """Draw a sample row from the 256-colour palette.

        Shows indices 16–51 (first 36 entries of the 6x6x6 colour
        cube) as background-coloured cells.  This is enough to verify
        that 256-colour mode is working without consuming many rows.

        Caveat: indices 0–15 are system colours and depend on the
        terminal theme.  Indices 16+ are standardised by xterm and
        should look the same on all terminals that support 256 colours.
        """
        if row >= self._height:
            return row
        label = "256c:  "
        buf.put_text(0, row, label, fg="cyan")
        col = len(label)
        # Show a slice of the 6x6x6 cube (indices 16–51).
        for idx in range(16, 52):
            if col + 2 > self._width:
                break
            bg = f"color({idx})"
            buf.put_text(col, row, "  ", bg=bg)
            col += 2
        return row + 1

    def _draw_truecolor_gradient(self, buf: CellBuffer, row: int) -> int:
        """Draw a red-to-blue truecolor gradient.

        Uses hex colour strings (e.g., ``"#ff0000"``) for each cell.
        On terminals that support truecolor, this should appear as a
        smooth gradient.  On terminals that silently downgrade, visible
        banding indicates the actual colour depth.

        Caveat: the gradient is a visual diagnostic, not a pass/fail
        test.  Banding on a 256-colour terminal is *expected* and
        correct behaviour (Rich is downgrading faithfully).
        """
        if row >= self._height:
            return row
        label = "24bit: "
        buf.put_text(0, row, label, fg="cyan")
        col = len(label)
        # Gradient: red -> blue across available columns.
        gradient_width = self._width - col
        for i in range(gradient_width):
            if col >= self._width:
                break
            # Interpolate: red channel decreases, blue channel increases.
            t = i / max(gradient_width - 1, 1)
            r = int(255 * (1 - t))
            b = int(255 * t)
            g = 0
            bg = f"#{r:02x}{g:02x}{b:02x}"
            buf.put_text(col, row, " ", bg=bg)
            col += 1
        return row + 1

    def _draw_styles(self, buf: CellBuffer, row: int) -> int:
        """Draw bold and dim style samples.

        Caveat: some terminals render bold as bright colour instead of
        heavier font weight.  Dim may be unsupported or barely visible.
        """
        if row >= self._height:
            return row
        label = "Style: "
        buf.put_text(0, row, label, fg="cyan")
        col = len(label)

        buf.put_text(col, row, "Normal", fg="white")
        col += 7
        buf.put_text(col, row, "Bold", fg="white", bold=True)
        col += 5
        buf.put_text(col, row, "Dim", fg="white", dim=True)
        col += 4
        buf.put_text(col, row, "BoldRed", fg="red", bold=True)
        col += 8
        buf.put_text(col, row, "DimGreen", fg="green", dim=True)
        return row + 1

    def _draw_wide_chars(self, buf: CellBuffer, row: int) -> int:
        """Draw CJK wide characters to test 2-column alignment.

        Each CJK ideograph should occupy exactly 2 terminal columns.
        If the terminal or font renders them at a different width, the
        pipe character at the end of the row will be misaligned.

        Caveat: if the terminal's font lacks CJK glyphs, replacement
        characters may appear at an unpredictable width, corrupting
        row alignment.
        """
        if row >= self._height:
            return row
        label = "Wide:  "
        buf.put_text(0, row, label, fg="cyan")
        col = len(label)
        # CJK ideographs — each is 2 columns wide.
        cjk = "漢字テスト中文"
        buf.put_text(col, row, cjk)
        col += len(cjk) * 2  # Each char is 2 cols wide.
        # Place a pipe at the expected alignment boundary.
        if col < self._width:
            buf.put_text(col, row, _V_RULE, fg="bright_black")
            col += 1
        if col < self._width:
            buf.put_text(col, row, "<- aligned?", fg="bright_black", dim=True)
        return row + 1

    def _draw_emoji(self, buf: CellBuffer, row: int) -> int:
        """Draw emoji characters (known unreliable).

        This row is intentionally included to show *how* the current
        terminal handles emoji, not to assert correct rendering.

        Caveat: emoji width is terminal-dependent.  Misalignment of
        the trailing text is expected on many terminals and demonstrates
        why wyby recommends avoiding emoji in game tiles.
        """
        if row >= self._height:
            return row
        label = "Emoji: "
        buf.put_text(0, row, label, fg="cyan")
        col = len(label)
        # Simple single-codepoint emoji.
        # Caveat: these are treated as width 2 by char_width(), but
        # terminals may render them at width 1 or 2, or as tofu.
        emoji_chars = "★♠♣♥♦"
        buf.put_text(col, row, emoji_chars, fg="bright_yellow")
        col += len(emoji_chars)  # Width 1 each (these are symbols, not emoji)
        if col < self._width:
            buf.put_text(col, row, _V_RULE, fg="bright_black")
            col += 1
        if col < self._width:
            buf.put_text(col, row, "<- aligned?", fg="bright_black", dim=True)
        return row + 1


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def build_test_card(
    *,
    include_emoji: bool = True,
    width: int = _CARD_WIDTH,
    height: int = _CARD_HEIGHT,
) -> CellBuffer:
    """Build a test-card :class:`~wyby.grid.CellBuffer` for visual inspection.

    Convenience wrapper that creates a :class:`TestCard` with auto-detected
    capabilities and returns the built buffer.

    Args:
        include_emoji: Whether to include the emoji test row.
        width: Test card width in columns.
        height: Test card height in rows.

    Returns:
        A populated :class:`~wyby.grid.CellBuffer`.

    Caveats:
        - Calls :func:`~wyby.diagnostics.detect_capabilities` to probe
          the current terminal.  This reads environment variables and
          queries terminal size — do not call per-frame.
        - The returned buffer is intended for manual visual inspection
          in different terminal emulators.  There is no automated
          pass/fail — you must visually verify the output.
    """
    card = TestCard(include_emoji=include_emoji, width=width, height=height)
    return card.build()


def format_report(
    caps: TerminalCapabilities | None = None,
) -> str:
    """Return a multi-line text report of terminal capabilities and caveats.

    Args:
        caps: Pre-detected capabilities.  If ``None``,
            :func:`~wyby.diagnostics.detect_capabilities` is called.

    Returns:
        A human-readable multi-line string.
    """
    card = TestCard(caps=caps)
    return card.report()

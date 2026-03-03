"""Mouse hover and drag consistency warnings.

Mouse hover (motion tracking) and drag event reporting varies significantly
across terminal emulators.  This module provides diagnostic functions that
warn developers when their mouse configuration may produce inconsistent
behaviour across user environments.

Hover (motion tracking, mode 1003)
----------------------------------
When ``mouse_motion=True`` is passed to :class:`~wyby.input.InputManager`,
wyby enables xterm mode 1003 (any-event tracking), which asks the terminal
to report mouse movement even when no button is held.  Terminal support for
this mode is less consistent than basic click reporting (mode 1000):

- **Well-supported:** xterm, kitty, Alacritty, WezTerm, Windows Terminal,
  GNOME Terminal, iTerm2.  These terminals report motion events reliably
  and at high frequency.
- **Partial/degraded:** macOS Terminal.app reports some motion events but
  may drop them under load or when the mouse moves fast.  Event coordinates
  may lag behind the actual cursor position.
- **Unsupported:** rxvt (without extensions), the Linux virtual console
  (``/dev/tty``), and very old PuTTY versions ignore mode 1003 entirely.
  No motion events are generated — the game receives clicks only.
- **Multiplexer issues:** tmux and screen intercept mouse events at the
  multiplexer layer.  Motion tracking requires ``set -g mouse on`` in
  tmux.  Even with that setting, tmux may throttle motion events to reduce
  bandwidth, causing gaps in hover tracking.  GNU screen has no equivalent
  mouse passthrough — motion events are not forwarded.

Drag consistency
----------------
Drag events are reported as ``action="move"`` with a non-``"none"`` button.
The terminal must report both the motion and the held button state in the
same escape sequence.  Inconsistencies include:

- **Button state during drag:** Most modern terminals correctly encode the
  held button in motion events (e.g., button code 32 = left + motion).
  However, some terminals (notably older macOS Terminal.app builds) may
  report ``button="none"`` during drags, making it impossible to
  distinguish drags from hover.
- **Drag across window boundaries:** When the mouse leaves the terminal
  window during a drag, some terminals stop reporting events; others
  continue reporting with clamped coordinates.  There is no standard
  behaviour for out-of-bounds drags.
- **Release after drag:** Some terminals fail to report the button release
  if the drag ends outside the terminal window.  The game may see a press
  and motion events but never a corresponding release — a "stuck button"
  scenario.  Games should implement timeout-based release detection as a
  workaround.
- **Multi-button drags:** Pressing a second button while dragging with
  another is poorly defined across terminals.  Some report both buttons;
  others report only the original or only the latest.  Games should avoid
  relying on multi-button drag behaviour.

Caveats
-------
- These warnings are **heuristic** — they flag known problem areas but
  cannot detect the user's actual terminal at import time.  Use
  :func:`~wyby.diagnostics.detect_capabilities` to identify the terminal
  emulator and combine with these warnings for more targeted advice.
- A clean return (no warning) does **not** guarantee consistent behaviour.
  Even well-supported terminals may exhibit edge cases under unusual
  configurations (custom terminfo entries, patched builds, Wayland vs X11
  compositors, etc.).
- Warning text is intended for developer diagnostics (logs, startup
  banners), not for end-user display.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


# Terminals known to have limited or absent motion tracking support.
# Values are human-readable descriptions of the limitation.
_LIMITED_HOVER_TERMINALS: dict[str, str] = {
    "Apple_Terminal": (
        "macOS Terminal.app has limited motion tracking. Hover events may "
        "be dropped under load or when the mouse moves quickly, and "
        "coordinates may lag behind the actual cursor position."
    ),
    "linux": (
        "The Linux virtual console does not support mouse motion tracking. "
        "No hover events will be generated."
    ),
}

# Terminals known to have limited or inconsistent drag reporting.
_LIMITED_DRAG_TERMINALS: dict[str, str] = {
    "Apple_Terminal": (
        "macOS Terminal.app may not reliably report button state during "
        "drags. Drag events may appear as hover (button='none') instead "
        "of reporting the held button. Release events after drags that "
        "end outside the window may also be missing."
    ),
    "linux": (
        "The Linux virtual console does not support mouse drag events. "
        "Only basic click reporting (if any) is available."
    ),
}


# General hover warning for when the terminal is unknown or when
# motion tracking is enabled regardless of terminal.
_HOVER_GENERAL_WARNING = (
    "Mouse motion tracking (mode 1003) has inconsistent support across "
    "terminal emulators. Known issues: (1) macOS Terminal.app may drop "
    "motion events or report stale coordinates; (2) the Linux virtual "
    "console ignores motion tracking entirely; (3) tmux/screen may "
    "throttle or block motion events even with 'set -g mouse on'; "
    "(4) SSH sessions add latency that can cause missed or reordered "
    "motion events. For reliable hover behaviour, test on your target "
    "terminals and implement fallback logic for missing events."
)

# General drag warning.
_DRAG_GENERAL_WARNING = (
    "Mouse drag reporting varies across terminal emulators. Known issues: "
    "(1) some terminals report button='none' during drags instead of the "
    "held button, making drags indistinguishable from hover; (2) dragging "
    "outside the terminal window may silently stop events or clamp "
    "coordinates; (3) button release may not be reported if the drag ends "
    "outside the window — implement timeout-based release detection as a "
    "fallback; (4) multi-button drags are poorly standardised and should "
    "not be relied upon."
)


def check_mouse_hover_warning(
    terminal_program: str | None = None,
) -> str | None:
    """Return a warning if mouse hover may be unreliable, else ``None``.

    Checks whether the identified terminal emulator is known to have
    limited motion tracking support.  If *terminal_program* is ``None``
    (terminal not identified), returns the general hover warning since
    capability cannot be confirmed.

    Args:
        terminal_program: The identified terminal emulator name, as
            returned by
            :attr:`~wyby.diagnostics.TerminalCapabilities.terminal_program`.
            Pass ``None`` if the terminal is unidentified.

    Returns:
        A human-readable warning string describing hover inconsistencies,
        or ``None`` if the terminal is known to support motion tracking
        well.

    Caveats:
        - A ``None`` return means the terminal is *not on the known-bad
          list*, not that hover tracking is guaranteed to work perfectly.
        - Terminal identification is best-effort (see
          :func:`~wyby.diagnostics.detect_capabilities`).  Inside tmux
          or screen, the reported program may be the multiplexer, not
          the outer terminal.
    """
    if terminal_program is None:
        return _HOVER_GENERAL_WARNING

    if terminal_program in _LIMITED_HOVER_TERMINALS:
        return _LIMITED_HOVER_TERMINALS[terminal_program]

    return None


def check_mouse_drag_warning(
    terminal_program: str | None = None,
) -> str | None:
    """Return a warning if mouse drag may be unreliable, else ``None``.

    Checks whether the identified terminal emulator is known to have
    inconsistent drag event reporting.  If *terminal_program* is ``None``
    (terminal not identified), returns the general drag warning since
    capability cannot be confirmed.

    Args:
        terminal_program: The identified terminal emulator name, as
            returned by
            :attr:`~wyby.diagnostics.TerminalCapabilities.terminal_program`.
            Pass ``None`` if the terminal is unidentified.

    Returns:
        A human-readable warning string describing drag inconsistencies,
        or ``None`` if the terminal is known to handle drags reliably.

    Caveats:
        - A ``None`` return means the terminal is *not on the known-bad
          list*, not that drag reporting is guaranteed to be consistent.
        - Drag-outside-window and release-after-drag issues affect even
          well-supported terminals to some degree.  Games should always
          implement timeout-based release detection as a safety net.
    """
    if terminal_program is None:
        return _DRAG_GENERAL_WARNING

    if terminal_program in _LIMITED_DRAG_TERMINALS:
        return _LIMITED_DRAG_TERMINALS[terminal_program]

    return None


def log_mouse_warnings(
    terminal_program: str | None = None,
    *,
    motion_enabled: bool = False,
) -> bool:
    """Log warnings about mouse hover/drag consistency for the current terminal.

    Convenience wrapper that calls :func:`check_mouse_drag_warning` (always,
    since drag issues affect basic mouse mode) and
    :func:`check_mouse_hover_warning` (only when *motion_enabled* is
    ``True``).  Warnings are logged at ``WARNING`` level; clean results
    are logged at ``DEBUG`` level.

    Args:
        terminal_program: The identified terminal emulator name.  Pass
            ``None`` if the terminal is unidentified.
        motion_enabled: Whether mouse motion tracking (mode 1003) is
            enabled.  When ``False``, hover warnings are skipped since
            motion events are not expected.

    Returns:
        ``True`` if any warning was logged, ``False`` otherwise.
    """
    warned = False

    drag_warning = check_mouse_drag_warning(terminal_program)
    if drag_warning:
        _logger.warning("Mouse drag caveat: %s", drag_warning)
        warned = True
    else:
        _logger.debug(
            "Terminal %r has no known mouse drag issues.",
            terminal_program,
        )

    if motion_enabled:
        hover_warning = check_mouse_hover_warning(terminal_program)
        if hover_warning:
            _logger.warning("Mouse hover caveat: %s", hover_warning)
            warned = True
        else:
            _logger.debug(
                "Terminal %r has no known mouse hover issues.",
                terminal_program,
            )

    return warned

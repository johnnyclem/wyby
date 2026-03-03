"""Input permission requirements and security rationale for wyby.

This module documents why wyby's input system does **not** require elevated
permissions (sudo/root) on any platform, contrasts the chosen approach with
the ``keyboard`` library's root requirement on Linux, and catalogs
platform-specific permission considerations.

The primary entry points are:

- :data:`INPUT_PERMISSION_ENTRIES` — the complete catalog of
  :class:`InputPermissionEntry` items covering each permission aspect.
- :data:`PERMISSION_CATEGORIES` — the set of all category names.
- :func:`get_entries_by_category` — filter entries by category.
- :func:`format_input_permissions_doc` — render the full catalog as Markdown.
- :func:`format_input_permissions_for_category` — render a single category.

Caveats:
    - This catalog is maintained manually alongside :mod:`wyby.input` and
      :mod:`wyby._platform`.  If the input backends change (e.g., a new
      platform is added), this catalog may need updating.
    - The ``keyboard`` library analysis reflects its behaviour as of 2024.
      If ``keyboard`` changes its permission model in the future, the
      contrast documented here may become outdated.
    - Permission requirements described here apply to the input subsystem
      only.  Other parts of a game (e.g., file I/O for saves) may have
      their own permission needs.
    - The entries describe the *typical* permission landscape.  Exotic
      system configurations (e.g., custom udev rules, SELinux policies,
      AppArmor profiles) may alter behaviour.
"""

from __future__ import annotations

import dataclasses


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class InputPermissionEntry:
    """A documented aspect of wyby's input permission requirements.

    Attributes:
        category: Broad topic area (e.g., ``"no_elevation"``,
            ``"keyboard_library"``, ``"platform"``, ``"environment"``).
        topic: Short human-readable label (e.g.,
            ``"No root/sudo required"``).
        description: Full explanation of the permission aspect, including
            why it matters and what the practical impact is.
        caveat: Optional caveat or edge-case note, or ``None``.

    Caveats:
        - ``category`` values are lowercase strings, not an enum.
        - ``caveat`` describes edge cases, not the main behaviour.
    """

    category: str
    topic: str
    description: str
    caveat: str | None = None


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

# Caveat: this catalog is maintained manually alongside input.py and
# _platform.py.  It reflects wyby v0.1.0dev0.  Changes to the input
# backends may require updates to this list.

INPUT_PERMISSION_ENTRIES: tuple[InputPermissionEntry, ...] = (
    # -- No elevation required ------------------------------------------------
    InputPermissionEntry(
        category="no_elevation",
        topic="No root/sudo required",
        description=(
            "wyby reads input exclusively from the process's own stdin "
            "using platform primitives (termios + select on Unix, msvcrt "
            "on Windows).  These are standard library facilities that "
            "operate on the process's own file descriptors.  No elevated "
            "privileges (root, sudo, Administrator) are required on any "
            "platform."
        ),
    ),
    InputPermissionEntry(
        category="no_elevation",
        topic="No device file access",
        description=(
            "wyby never opens /dev/input/event* or any other device file.  "
            "On Linux, raw input device files are owned by root:input with "
            "mode 0660 and require either root access or input group "
            "membership to read.  wyby avoids this entirely by reading "
            "from stdin, which is already connected to the terminal "
            "emulator."
        ),
    ),
    InputPermissionEntry(
        category="no_elevation",
        topic="No system-wide input hooks",
        description=(
            "wyby does not install OS-level keyboard hooks or register "
            "global hotkeys.  It reads only keystrokes directed to the "
            "terminal running the game.  Input from other applications, "
            "windows, or virtual desktops is never intercepted."
        ),
    ),
    # -- keyboard library contrast -------------------------------------------
    InputPermissionEntry(
        category="keyboard_library",
        topic="keyboard library excluded — root requirement on Linux",
        description=(
            "The third-party keyboard library (pypi.org/project/keyboard) "
            "is explicitly excluded from wyby.  On Linux, keyboard reads "
            "raw evdev events from /dev/input/event* device files.  These "
            "files are owned by root:input with mode 0660.  Without "
            "elevated access, keyboard raises PermissionError.  Users "
            "must either run with sudo (full root privileges) or add "
            "themselves to the input group (sudo usermod -aG input $USER), "
            "which grants access to ALL input devices system-wide."
        ),
        caveat=(
            "The keyboard library's permission model is a design choice, "
            "not a bug.  It hooks into the kernel input subsystem via "
            "/dev/input, which is inherently a privileged operation."
        ),
    ),
    InputPermissionEntry(
        category="keyboard_library",
        topic="keyboard library excluded — system-wide capture",
        description=(
            "keyboard installs OS-level input hooks that capture "
            "keystrokes from ALL applications, not just the terminal "
            "running the game.  This means a game using keyboard can see "
            "passwords typed in browsers, sensitive data in editors, and "
            "input from any other window.  This is inappropriate for a "
            "game framework."
        ),
    ),
    InputPermissionEntry(
        category="keyboard_library",
        topic="keyboard library excluded — keylogger semantics",
        description=(
            "Even when used benignly, the keyboard library's "
            "/dev/input mechanism is architecturally identical to how "
            "keyloggers work.  Bundling a library that requires root to "
            "read all keystrokes raises trust concerns for end users "
            "and may trigger security audits or antivirus alerts."
        ),
    ),
    InputPermissionEntry(
        category="keyboard_library",
        topic="keyboard library excluded — poor terminal integration",
        description=(
            "keyboard bypasses the terminal emulator entirely.  It cannot "
            "distinguish between multiple open terminals, does not respect "
            "terminal multiplexers (tmux, screen), and fails in "
            "environments without /dev/input (Docker containers, SSH "
            "sessions, CI pipelines)."
        ),
    ),
    # -- Platform-specific permission notes ----------------------------------
    InputPermissionEntry(
        category="platform",
        topic="Unix: termios raw mode — no special permissions",
        description=(
            "On Unix (Linux, macOS, BSDs), wyby uses termios to switch "
            "stdin to raw mode and select.select for non-blocking reads.  "
            "termios operates on the process's own stdin file descriptor, "
            "which is always accessible.  No special permissions, group "
            "memberships, or capabilities are required."
        ),
        caveat=(
            "termios requires stdin to be a TTY.  If stdin is piped or "
            "redirected (e.g., in CI), raw mode cannot be entered.  Use "
            "allow_fallback=True or InputMode.BASIC for non-TTY "
            "environments."
        ),
    ),
    InputPermissionEntry(
        category="platform",
        topic="Windows: msvcrt — no special permissions",
        description=(
            "On Windows, wyby uses msvcrt.kbhit() and msvcrt.getwch() "
            "for non-blocking input.  These are standard C runtime "
            "functions that read from the console input buffer.  No "
            "Administrator privileges, UAC elevation, or special "
            "permissions are required."
        ),
        caveat=(
            "msvcrt only works with the Windows console (conhost.exe or "
            "Windows Terminal).  It does not work with pipes or "
            "redirected stdin."
        ),
    ),
    InputPermissionEntry(
        category="platform",
        topic="macOS: no Accessibility permission needed",
        description=(
            "On macOS, some input libraries require Accessibility "
            "permission (System Settings > Privacy & Security > "
            "Accessibility) to capture global keyboard events.  wyby "
            "does NOT require this permission because it reads only "
            "from stdin via termios, not from the macOS event system."
        ),
    ),
    # -- Environment-specific notes ------------------------------------------
    InputPermissionEntry(
        category="environment",
        topic="Docker containers — no special flags",
        description=(
            "wyby works in Docker containers without --privileged or "
            "special device mappings.  Since wyby reads from stdin (not "
            "/dev/input), it only needs the container to be run with an "
            "interactive TTY (docker run -it).  The keyboard library, "
            "by contrast, fails in containers because /dev/input is not "
            "exposed."
        ),
        caveat=(
            "The -it flag (interactive + TTY) is required for raw-mode "
            "input.  Without it, stdin is not a TTY and raw mode cannot "
            "be entered.  Use InputMode.BASIC or allow_fallback=True "
            "for non-interactive containers."
        ),
    ),
    InputPermissionEntry(
        category="environment",
        topic="SSH sessions — works transparently",
        description=(
            "wyby works over SSH without additional configuration.  The "
            "SSH server provides a pseudo-TTY that supports termios raw "
            "mode.  The keyboard library fails over SSH because the "
            "remote machine typically does not expose /dev/input to "
            "non-root users."
        ),
        caveat=(
            "SSH adds network latency to input delivery.  High-latency "
            "connections may cause ANSI escape sequences to be split "
            "across reads, though this is rare in practice."
        ),
    ),
    InputPermissionEntry(
        category="environment",
        topic="CI/CD pipelines — graceful fallback",
        description=(
            "In CI environments (GitHub Actions, Jenkins, etc.), stdin "
            "is typically not a TTY.  wyby detects this and raises "
            "RuntimeError unless allow_fallback=True or InputMode.BASIC "
            "is used, in which case it falls back to line-buffered "
            "input() with no terminal modification."
        ),
    ),
    InputPermissionEntry(
        category="environment",
        topic="Terminal multiplexers — no extra permissions",
        description=(
            "wyby works inside tmux and screen without extra permissions.  "
            "The multiplexer provides a pseudo-TTY that supports termios "
            "raw mode.  Mouse events require the multiplexer to pass "
            "them through (e.g., 'set -g mouse on' in tmux)."
        ),
    ),
)


PERMISSION_CATEGORIES: frozenset[str] = frozenset(
    entry.category for entry in INPUT_PERMISSION_ENTRIES
)
"""All distinct category names in :data:`INPUT_PERMISSION_ENTRIES`."""


# Human-readable category labels, in display order.
_CATEGORY_ORDER: tuple[str, ...] = (
    "no_elevation",
    "keyboard_library",
    "platform",
    "environment",
)

_CATEGORY_LABELS: dict[str, str] = {
    "no_elevation": "No Elevated Permissions Required",
    "keyboard_library": "Why the keyboard Library Is Excluded",
    "platform": "Platform-Specific Permission Notes",
    "environment": "Environment-Specific Notes",
}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def get_entries_by_category(
    category: str,
) -> tuple[InputPermissionEntry, ...]:
    """Return all entries in the given category.

    Args:
        category: One of the category names in
            :data:`PERMISSION_CATEGORIES`.

    Returns:
        A tuple of :class:`InputPermissionEntry` instances.

    Raises:
        ValueError: If *category* is not a recognised category name.

    Caveats:
        - Categories are derived from the built-in catalog.  Custom
          entries added at runtime are not supported.
    """
    if category not in PERMISSION_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(PERMISSION_CATEGORIES)}"
        )
    return tuple(
        entry for entry in INPUT_PERMISSION_ENTRIES
        if entry.category == category
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_input_permissions_for_category(category: str) -> str:
    """Format all entries in a single category as Markdown.

    Args:
        category: One of the category names in
            :data:`PERMISSION_CATEGORIES`.

    Returns:
        A multi-line Markdown string.

    Raises:
        ValueError: If *category* is not recognised.

    Caveats:
        - The output is plain Markdown, not a Rich renderable.
    """
    entries = get_entries_by_category(category)
    label = _CATEGORY_LABELS.get(
        category, category.replace("_", " ").title(),
    )

    lines: list[str] = []
    lines.append(f"## {label}")
    lines.append("")

    for entry in entries:
        lines.append(f"### {entry.topic}")
        lines.append("")
        lines.append(entry.description)
        lines.append("")
        if entry.caveat:
            lines.append(f"**Caveat:** {entry.caveat}")
            lines.append("")

    return "\n".join(lines)


def format_input_permissions_doc() -> str:
    """Format the complete input permissions catalog as a Markdown document.

    Produces a document with all entries grouped by category, each
    with a description and optional caveat.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is a standalone reference document.
        - Categories are listed in a fixed display order.  Categories
          present in the catalog but not in the display order are
          appended at the end.
    """
    lines: list[str] = []
    lines.append("# Input Permissions")
    lines.append("")
    lines.append(
        "This document explains why wyby's input system requires no "
        "elevated permissions (root, sudo, Administrator) on any platform, "
        "contrasts the chosen approach with the keyboard library's "
        "root requirement on Linux, and catalogs platform-specific and "
        "environment-specific permission considerations."
    )
    lines.append("")
    lines.append(
        f"**{len(INPUT_PERMISSION_ENTRIES)} entries documented** across "
        f"{len(PERMISSION_CATEGORIES)} categories."
    )
    lines.append("")

    # Categories in display order.
    seen: set[str] = set()
    ordered_cats: list[str] = []
    for cat in _CATEGORY_ORDER:
        if cat in PERMISSION_CATEGORIES:
            ordered_cats.append(cat)
            seen.add(cat)
    # Append any categories not in the fixed order.
    for cat in sorted(PERMISSION_CATEGORIES):
        if cat not in seen:
            ordered_cats.append(cat)

    for cat in ordered_cats:
        lines.append(format_input_permissions_for_category(cat))

    return "\n".join(lines)

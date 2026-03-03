# wyby Terminal Compatibility Matrix

This document shows which terminal features wyby depends on and how well each terminal emulator supports them.  Use this to choose a terminal for development and to set expectations for end users.

**14 terminals evaluated** across **7 features**.

## Important Caveats

- **This matrix is manually maintained** and reflects known behaviour as of wyby v0.1.0dev0.  Terminal emulators update frequently.
- **"Partial" means it works with caveats** — see the per-terminal notes below for details.
- **Multiplexers (tmux, screen) reduce capabilities** even if the outer terminal is fully capable.
- **SSH sessions inherit the local terminal's capabilities** but add network latency to every frame.
- **Emoji rendering is excluded** from this matrix because width handling is too inconsistent across terminals to categorise reliably.

## Support Matrix

| Terminal | Truecolor (24-bit) | Alt Screen | Box Drawing / Blocks | Mouse Click | Mouse Hover | Mouse Drag | Key Sequences |
|----------|--------------------|------------|----------------------|-------------|-------------|------------|---------------|
| kitty | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| WezTerm | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| iTerm2 | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Windows Terminal | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Alacritty | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| GNOME Terminal | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Konsole | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| macOS Terminal.app | Partial | Yes | Yes | Partial | Partial | Partial | Yes |
| xterm | Partial | Yes | Yes | Yes | Yes | Yes | Yes |
| tmux | Partial | Yes | Yes | Partial | Partial | Partial | Yes |
| GNU Screen | No | Yes | Partial | Partial | No | No | Yes |
| Windows conhost.exe (legacy) | No | No | Partial | No | No | No | Partial |
| Linux virtual console (TTY) | No | Yes | Partial | No | No | No | Yes |
| SSH session | Partial | Yes | Yes | Partial | Partial | Partial | Yes |

## Terminal Details

### kitty

**Platform:** cross-platform

Excellent wyby compatibility.  GPU-accelerated rendering provides the best frame rate for large grids.

### WezTerm

**Platform:** cross-platform

Excellent wyby compatibility.  GPU-accelerated, cross-platform, and highly configurable.

### iTerm2

**Platform:** macos

Excellent wyby compatibility on macOS.

### Windows Terminal

**Platform:** windows

Recommended terminal for wyby on Windows.  Requires Windows 10 1903+ for full ConPTY support.

**Feature notes:**

- **Key Sequences:** Uses ConPTY.  Arrow and function keys produce standard ANSI sequences, but some extended key combos may differ from Unix terminals.

### Alacritty

**Platform:** cross-platform

GPU-accelerated and minimal.  Excellent wyby compatibility across all platforms.

### GNOME Terminal

**Platform:** linux

Default terminal on many Linux desktops.  Full wyby compatibility.

### Konsole

**Platform:** linux

Default KDE terminal.  Full wyby compatibility.

### macOS Terminal.app

**Platform:** macos

Ships with macOS but has limited capabilities compared to iTerm2.  wyby works but with reduced colour fidelity and unreliable mouse support.  iTerm2 is recommended instead.

**Feature notes:**

- **Truecolor (24-bit):** Terminal.app supports 256 colours but truecolor (24-bit) support is unreliable.  Rich falls back to 256-colour mode.  Colours will differ from truecolor terminals.
- **Mouse Click:** Basic click reporting works but may require enabling 'Allow Mouse Reporting' in the terminal profile.
- **Mouse Hover:** Motion tracking is inconsistent.  Events may be dropped or delayed.
- **Mouse Drag:** Drag reporting is unreliable.  Button state may not be preserved during motion.

### xterm

**Platform:** linux

The original X11 terminal emulator.  Capable but requires modern builds for truecolor.

**Feature notes:**

- **Truecolor (24-bit):** Truecolor requires xterm compiled with --enable-direct-color (xterm 331+).  Older builds fall back to 256 colours.  Set COLORTERM=truecolor if the terminal supports it but the env var is missing.

### tmux

**Platform:** cross-platform

Terminal multiplexer — adds an extra rendering layer that roughly doubles rendering latency.  For best wyby performance, run outside tmux.  If tmux is needed, configure truecolor and mouse passthrough.

**Feature notes:**

- **Truecolor (24-bit):** Requires 'set -g default-terminal tmux-256color' and 'set -ga terminal-overrides ",*256col*:Tc"' in tmux.conf.  Without this, tmux strips truecolor sequences.
- **Mouse Click:** Requires 'set -g mouse on' in tmux.conf.  tmux intercepts mouse events for its own scrollback; passthrough works but adds latency.
- **Mouse Hover:** Motion events are passed through when mouse mode is enabled, but tmux may throttle high-frequency motion events.
- **Mouse Drag:** Drag events are passed through but button state tracking may be lost if tmux intercepts a click for pane selection.

### GNU Screen

**Platform:** cross-platform

Legacy multiplexer with limited capability passthrough.  tmux is recommended over screen for wyby usage.

**Feature notes:**

- **Truecolor (24-bit):** GNU Screen does not support truecolor passthrough.  Colours are quantised to 256.  Use tmux instead if truecolor is needed.
- **Box Drawing / Blocks:** Depends on the outer terminal and locale.  Screen itself passes through UTF-8, but misconfigured locale can cause garbled output.
- **Mouse Click:** Basic mouse click passthrough works with 'mousetrack on' in .screenrc, but support is less reliable than tmux.

### Windows conhost.exe (legacy)

**Platform:** windows

Legacy Windows console host.  Not recommended for wyby.  Use Windows Terminal instead.  Most features are non-functional.

**Feature notes:**

- **Truecolor (24-bit):** Legacy conhost silently ignores ANSI colour sequences.  No colour output is possible without Windows Terminal or ConPTY.
- **Alt Screen:** Alt screen escape sequences are silently ignored.  Game output mixes with the shell history.
- **Box Drawing / Blocks:** Depends on the console font.  Consolas and Cascadia Code support box-drawing characters; Lucida Console and raster fonts do not.
- **Key Sequences:** Special keys produce scan-code sequences via msvcrt, not ANSI escapes.  The wyby input parser handles this, but modifier detection is limited.

### Linux virtual console (TTY)

**Platform:** linux

The raw Linux TTY (Ctrl+Alt+F1).  Keyboard input works but colours and mouse are severely limited.  Use a graphical terminal emulator for wyby.

**Feature notes:**

- **Truecolor (24-bit):** The Linux framebuffer console supports 16 colours only.  Rich falls back to basic colour mode.
- **Box Drawing / Blocks:** Depends on the console font (setfont).  The default font may lack box-drawing glyphs.  Install a Unicode console font like Terminus.
- **Mouse Click:** No mouse support in the Linux virtual console.  gpm can provide basic mouse reporting but is not widely deployed.

### SSH session

**Platform:** cross-platform

SSH forwards terminal I/O over the network.  All capabilities depend on the local terminal emulator.  Network latency affects every frame — use ssh -C for compression and keep grids small.

**Feature notes:**

- **Truecolor (24-bit):** Truecolor support depends on both the local terminal and the remote TERM/COLORTERM environment.  SSH does not forward COLORTERM by default — add 'SendEnv COLORTERM' to ssh_config and 'AcceptEnv COLORTERM' to sshd_config.
- **Mouse Click:** Mouse events are forwarded through the SSH channel but add round-trip latency.  On high-latency connections, clicks may feel sluggish.
- **Mouse Hover:** High-frequency motion events over SSH add significant bandwidth.  Hover-based gameplay is impractical over slow connections.
- **Mouse Drag:** Drag events work but latency makes real-time drag interactions (e.g., drawing) unusable on connections above ~50 ms RTT.

## Recommendations

### Best terminals for wyby development

These terminals have full support for all wyby features:

- **kitty** (cross-platform)
- **WezTerm** (cross-platform)
- **iTerm2** (macos)
- **Windows Terminal** (windows)
- **Alacritty** (cross-platform)
- **GNOME Terminal** (linux)
- **Konsole** (linux)

### Terminals to avoid

These terminals have significant limitations that affect core wyby functionality:

- **GNU Screen** — 3 unsupported features
- **Windows conhost.exe (legacy)** — 5 unsupported features
- **Linux virtual console (TTY)** — 4 unsupported features

### Tips for cross-platform games

- Always provide keyboard-only controls as a fallback for terminals without mouse support.
- Design colour palettes that degrade gracefully to 256 colours for terminals without truecolor.
- Use ASCII and box-drawing characters (U+2500-U+257F) rather than emoji for game tiles.
- Test in at least one terminal per target platform (e.g., iTerm2 on macOS, Windows Terminal on Windows, GNOME Terminal on Linux).
- Avoid relying on mouse hover or drag for core gameplay — these are the least consistently supported features.

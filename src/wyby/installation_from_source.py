"""Installation from source guide for wyby.

This module provides a structured catalog of methods for installing wyby
from source, including prerequisites, editable installs, optional extras,
virtual-environment best practices, verification steps, and known caveats.

The primary entry points are:

- :data:`INSTALLATION_ENTRIES` — the complete catalog of
  :class:`InstallationEntry` items covering each installation aspect.
- :data:`INSTALLATION_CATEGORIES` — the set of all category names.
- :func:`get_entries_by_category` — filter entries by category.
- :func:`format_installation_guide` — render the full guide as Markdown.
- :func:`format_installation_for_category` — render a single category.

Caveats:
    - wyby is pre-release (v0.1.0dev0) and is not published on PyPI.
      Installation from source (``git clone`` + ``pip install``) is the
      *only* supported installation method at this time.
    - The optional ``[svg]`` extra requires a system-level Cairo library
      that cannot be installed by pip.  Users must install Cairo via their
      OS package manager before ``pip install -e ".[svg]"`` will succeed.
    - Python >= 3.10 is required.  Older interpreters will fail at install
      time because the codebase uses ``X | Y`` union syntax and other
      3.10+ features.
    - This catalog is maintained manually.  Changes to ``pyproject.toml``
      (e.g., new extras or dependency bumps) may require updates here.

See also:
    - :mod:`wyby.limitations_caveats` for a comprehensive catalog of
      wyby's known limitations.
    - :mod:`wyby.api_reference` for the API module catalog.
"""

from __future__ import annotations

import dataclasses


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class InstallationEntry:
    """A documented aspect of installing wyby from source.

    Attributes:
        category: Broad topic area (e.g., ``"prerequisites"``,
            ``"basic_install"``, ``"optional_extras"``,
            ``"virtual_environment"``, ``"verification"``,
            ``"caveats"``).
        topic: Short human-readable label (e.g.,
            ``"Python >= 3.10 required"``).
        description: Full explanation including commands and rationale.
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

# Caveat: this catalog is maintained manually alongside pyproject.toml.
# It reflects wyby v0.1.0dev0.  Changes to the build configuration,
# dependency versions, or optional extras may require updates here.

INSTALLATION_ENTRIES: tuple[InstallationEntry, ...] = (
    # -- Prerequisites --------------------------------------------------------
    InstallationEntry(
        category="prerequisites",
        topic="Python >= 3.10 required",
        description=(
            "wyby requires Python 3.10 or later.  The codebase uses "
            "PEP 604 union syntax (X | Y), structural pattern matching, "
            "and other language features introduced in 3.10.  Attempting "
            "to install with an older interpreter will produce syntax "
            "errors during byte-compilation.  Check your version with: "
            "python3 --version"
        ),
        caveat=(
            "Some Linux distributions ship Python 3.8 or 3.9 as the "
            "system Python.  You may need to install a newer version via "
            "your package manager (e.g., sudo apt install python3.12) or "
            "use pyenv to manage multiple Python versions."
        ),
    ),
    InstallationEntry(
        category="prerequisites",
        topic="Git required for cloning",
        description=(
            "The source repository is hosted on GitHub and must be cloned "
            "with Git.  Install Git via your OS package manager if it is "
            "not already available: brew install git (macOS), "
            "sudo apt install git (Debian/Ubuntu), or download from "
            "git-scm.com (Windows)."
        ),
    ),
    InstallationEntry(
        category="prerequisites",
        topic="pip and setuptools",
        description=(
            "wyby uses setuptools as its build backend (configured in "
            "pyproject.toml).  A recent pip (>= 21.3) that supports "
            "PEP 660 editable installs is required.  Upgrade pip before "
            "installing: python3 -m pip install --upgrade pip"
        ),
        caveat=(
            "Very old pip versions (< 21.3) do not support PEP 660 "
            "editable installs with pyproject.toml.  If you see errors "
            "about 'editable installs', upgrade pip first."
        ),
    ),
    # -- Basic installation ---------------------------------------------------
    InstallationEntry(
        category="basic_install",
        topic="Clone and install in editable mode",
        description=(
            "Clone the repository and install in editable (development) "
            "mode so that changes to the source are immediately reflected "
            "without reinstalling:\n\n"
            "    git clone https://github.com/your-org/wyby.git\n"
            "    cd wyby\n"
            "    pip install -e .\n\n"
            "This installs wyby and its sole runtime dependency (rich "
            ">= 13.0) into the active Python environment."
        ),
        caveat=(
            "The -e (editable) flag creates a link to the source tree "
            "instead of copying files into site-packages.  Moving or "
            "deleting the cloned directory will break the installation."
        ),
    ),
    InstallationEntry(
        category="basic_install",
        topic="Install with dev dependencies",
        description=(
            "To install wyby with all development tools (pytest, ruff, "
            "coverage, Pillow, cairosvg):\n\n"
            "    pip install -e \".[dev]\"\n\n"
            "This is the recommended setup for contributors.  It includes "
            "the test runner, linter, and all optional dependencies needed "
            "to run the full test suite."
        ),
    ),
    InstallationEntry(
        category="basic_install",
        topic="Non-editable install from local source",
        description=(
            "If you do not need to modify the source, you can install "
            "without the -e flag:\n\n"
            "    pip install .\n\n"
            "This copies the package into site-packages.  You will need "
            "to re-run this command after every source change."
        ),
        caveat=(
            "Non-editable installs are less convenient during development "
            "because source changes require a reinstall.  Use editable "
            "mode (pip install -e .) unless you have a specific reason "
            "not to."
        ),
    ),
    # -- Optional extras ------------------------------------------------------
    InstallationEntry(
        category="optional_extras",
        topic="Image loading extra — [image]",
        description=(
            "Install Pillow for image-to-cell-grid conversion "
            "(from_image(), from_image_with_fallback()):\n\n"
            "    pip install -e \".[image]\"\n\n"
            "This adds Pillow >= 9.0 as a dependency.  Without it, "
            "image loading functions will raise ImportError."
        ),
    ),
    InstallationEntry(
        category="optional_extras",
        topic="SVG rasterization extra — [svg]",
        description=(
            "Install cairosvg and Pillow for SVG-to-cell-grid conversion "
            "(load_svg()):\n\n"
            "    pip install -e \".[svg]\"\n\n"
            "This adds cairosvg >= 2.5 and Pillow >= 9.0."
        ),
        caveat=(
            "cairosvg requires a system-level Cairo library that pip "
            "cannot install.  Install Cairo first via your OS package "
            "manager: brew install cairo (macOS), sudo apt install "
            "libcairo2-dev (Debian/Ubuntu), or see the cairographics.org "
            "documentation for Windows.  Without Cairo, pip install will "
            "succeed but cairosvg will fail at import time with an OSError."
        ),
    ),
    InstallationEntry(
        category="optional_extras",
        topic="Combining extras",
        description=(
            "Multiple extras can be combined in a single install command "
            "using comma separation:\n\n"
            "    pip install -e \".[dev,image,svg]\"\n\n"
            "The [dev] extra already includes Pillow and cairosvg, so "
            "this is equivalent to pip install -e \".[dev]\" in practice."
        ),
    ),
    # -- Virtual environment --------------------------------------------------
    InstallationEntry(
        category="virtual_environment",
        topic="Use a virtual environment",
        description=(
            "Always install wyby inside a virtual environment to avoid "
            "polluting the system Python:\n\n"
            "    python3 -m venv .venv\n"
            "    source .venv/bin/activate   # macOS/Linux\n"
            "    .venv\\Scripts\\activate       # Windows\n"
            "    pip install -e \".[dev]\"\n\n"
            "The repository already includes a .venv directory in "
            ".gitignore."
        ),
        caveat=(
            "On Windows, the activation command differs: use "
            ".venv\\Scripts\\activate instead of source .venv/bin/activate.  "
            "PowerShell may also require execution policy changes: "
            "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
        ),
    ),
    InstallationEntry(
        category="virtual_environment",
        topic="pyenv for managing Python versions",
        description=(
            "If your system Python is too old, pyenv lets you install "
            "and switch between multiple Python versions without affecting "
            "the system installation:\n\n"
            "    pyenv install 3.12.0\n"
            "    pyenv local 3.12.0\n"
            "    python -m venv .venv\n\n"
            "See https://github.com/pyenv/pyenv for installation "
            "instructions."
        ),
        caveat=(
            "pyenv builds Python from source and requires build "
            "dependencies (e.g., libssl-dev, libffi-dev on Linux).  "
            "pyenv is not available on Windows; use the Python.org "
            "installer or the Microsoft Store instead."
        ),
    ),
    # -- Verification ---------------------------------------------------------
    InstallationEntry(
        category="verification",
        topic="Verify the installation",
        description=(
            "After installing, verify that wyby is importable and the "
            "correct version is installed:\n\n"
            "    python -c \"import wyby; print('wyby imported OK')\"\n\n"
            "A successful import confirms that wyby and its runtime "
            "dependency (rich) are available."
        ),
    ),
    InstallationEntry(
        category="verification",
        topic="Run the test suite",
        description=(
            "Run the full test suite with pytest to confirm everything "
            "works:\n\n"
            "    pytest\n\n"
            "This requires the [dev] extra to be installed.  pytest is "
            "configured in pyproject.toml with coverage reporting enabled."
        ),
        caveat=(
            "Some tests exercise optional features (image loading, SVG "
            "conversion) and will be skipped if the corresponding "
            "optional dependencies are not installed.  Install with "
            "[dev] to run the complete suite."
        ),
    ),
    InstallationEntry(
        category="verification",
        topic="Run the linter",
        description=(
            "Check code quality with ruff:\n\n"
            "    ruff check src/ tests/\n\n"
            "ruff is included in the [dev] extra.  The linter "
            "configuration is defined in pyproject.toml."
        ),
    ),
    # -- Caveats & known issues -----------------------------------------------
    InstallationEntry(
        category="caveats",
        topic="Not on PyPI",
        description=(
            "wyby is pre-release (v0.1.0dev0) and is not published on "
            "PyPI.  'pip install wyby' will fail.  The only supported "
            "installation method is cloning the source repository and "
            "installing from the local checkout."
        ),
    ),
    InstallationEntry(
        category="caveats",
        topic="Rich >= 13.0 is the sole runtime dependency",
        description=(
            "wyby depends on rich >= 13.0 for terminal rendering.  pip "
            "will install Rich automatically.  If you have an older Rich "
            "version pinned elsewhere, it may cause a conflict.  Rich 13 "
            "introduced breaking changes to Live and Console that wyby "
            "relies on."
        ),
    ),
    InstallationEntry(
        category="caveats",
        topic="Cairo system dependency for SVG support",
        description=(
            "The [svg] extra depends on cairosvg, which wraps the Cairo "
            "C library via cffi.  Cairo must be installed at the system "
            "level before pip install.  Without it, the Python package "
            "installs but fails at runtime with an OSError when attempting "
            "to load the shared library."
        ),
        caveat=(
            "Cairo installation varies by platform: brew install cairo "
            "(macOS), sudo apt install libcairo2-dev (Debian/Ubuntu), "
            "choco install cairo (Windows with Chocolatey).  There is no "
            "pure-Python fallback."
        ),
    ),
    InstallationEntry(
        category="caveats",
        topic="Editable installs require pip >= 21.3",
        description=(
            "PEP 660 editable installs with pyproject.toml (no setup.py) "
            "require pip >= 21.3 and setuptools >= 64.  If you encounter "
            "errors like 'A setup.py or setup.cfg is required for "
            "editable installs', upgrade pip: "
            "python3 -m pip install --upgrade pip setuptools"
        ),
    ),
    InstallationEntry(
        category="caveats",
        topic="Pre-release API instability",
        description=(
            "wyby is v0.1.0dev0.  API names, module paths, and behaviour "
            "may change without notice before 1.0.  Do not depend on "
            "the current API being stable.  Pin to a specific commit hash "
            "if you need reproducibility."
        ),
    ),
)


INSTALLATION_CATEGORIES: frozenset[str] = frozenset(
    entry.category for entry in INSTALLATION_ENTRIES
)
"""All distinct category names in :data:`INSTALLATION_ENTRIES`."""


# Human-readable category labels, in display order.
_CATEGORY_ORDER: tuple[str, ...] = (
    "prerequisites",
    "basic_install",
    "optional_extras",
    "virtual_environment",
    "verification",
    "caveats",
)

_CATEGORY_LABELS: dict[str, str] = {
    "prerequisites": "Prerequisites",
    "basic_install": "Basic Installation",
    "optional_extras": "Optional Extras",
    "virtual_environment": "Virtual Environment",
    "verification": "Verification",
    "caveats": "Caveats & Known Issues",
}


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def get_entries_by_category(
    category: str,
) -> tuple[InstallationEntry, ...]:
    """Return all installation entries in the given category.

    Args:
        category: One of the category names in
            :data:`INSTALLATION_CATEGORIES`.

    Returns:
        A tuple of :class:`InstallationEntry` instances.

    Raises:
        ValueError: If *category* is not a recognised category name.

    Caveats:
        - Categories are derived from the built-in catalog.  Custom
          entries added at runtime are not supported.
    """
    if category not in INSTALLATION_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}.  "
            f"Known categories: {sorted(INSTALLATION_CATEGORIES)}"
        )
    return tuple(
        entry for entry in INSTALLATION_ENTRIES
        if entry.category == category
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_installation_for_category(category: str) -> str:
    """Format all installation entries in a single category as Markdown.

    Args:
        category: One of the category names in
            :data:`INSTALLATION_CATEGORIES`.

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


def format_installation_guide() -> str:
    """Format the complete installation-from-source guide as Markdown.

    Produces a document with all entries grouped by category, each
    with a description and optional caveat.

    Returns:
        A multi-line Markdown string.

    Caveats:
        - The output is a standalone reference document.
        - Categories are listed in a fixed display order.  Categories
          present in the catalog but not in the display order are
          appended at the end.
        - This guide reflects wyby v0.1.0dev0.  Installation steps may
          change once the package is published to PyPI.
    """
    lines: list[str] = []
    lines.append("# Installing wyby from Source")
    lines.append("")
    lines.append(
        "wyby is pre-release (v0.1.0dev0) and is not available on PyPI.  "
        "The only supported installation method is cloning the source "
        "repository and installing with pip.  This guide covers "
        "prerequisites, installation commands, optional extras, "
        "virtual-environment setup, and verification."
    )
    lines.append("")
    lines.append(
        f"**{len(INSTALLATION_ENTRIES)} entries documented** across "
        f"{len(INSTALLATION_CATEGORIES)} categories."
    )
    lines.append("")

    # Categories in display order.
    seen: set[str] = set()
    ordered_cats: list[str] = []
    for cat in _CATEGORY_ORDER:
        if cat in INSTALLATION_CATEGORIES:
            ordered_cats.append(cat)
            seen.add(cat)
    # Append any categories not in the fixed order.
    for cat in sorted(INSTALLATION_CATEGORIES):
        if cat not in seen:
            ordered_cats.append(cat)

    for cat in ordered_cats:
        lines.append(format_installation_for_category(cat))

    return "\n".join(lines)

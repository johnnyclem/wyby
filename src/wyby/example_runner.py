"""Validate that bundled examples can be imported and their scenes exercised.

This module provides utilities to verify that wyby example scripts are
importable and that their scene classes can be constructed and run through
a basic lifecycle (construct, render, update, handle_events) without a
real terminal or Engine instance.  This is useful for CI environments,
documentation generation, and smoke-testing after framework changes.

The primary entry points are:

- :func:`check_example` — validate a single example file.
- :func:`check_all_examples` — discover and validate all ``*.py`` files
  in the examples directory.
- :func:`format_check_results` — format validation results as a
  human-readable table.

Caveats:
    - **No real terminal required.**  Validation exercises scene logic
      (construction, ``render()``, ``update()``, ``handle_events([])``)
      without a TTY.  This proves the scene classes are importable and
      their core methods don't raise, but it does **not** verify
      interactive behaviour (keyboard input, Rich Live display, frame
      timing).  A scene that passes validation may still fail at runtime
      if the terminal lacks capabilities (e.g., Unicode support, colour
      depth).
    - **No Engine instance.**  Scenes are instantiated directly, not via
      ``Engine.push_scene()``.  This means the game loop, input manager,
      and renderer are not involved.  Engine-level bugs (tick timing,
      input polling, display refresh) are not caught by this module.
    - **Import side effects.**  Importing an example module may execute
      top-level code outside of ``if __name__ == "__main__":`` guards.
      Well-structured examples should have no side effects at import
      time, but if an example violates this convention, validation may
      produce unexpected output or state changes.
    - **Scene discovery is heuristic.**  The module inspects each example
      file for subclasses of :class:`~wyby.scene.Scene` using
      ``inspect.getmembers``.  If an example defines a Scene subclass
      under a non-standard name or imports it from another module, it
      will still be detected — but helper classes that inherit Scene
      for testing purposes may also be picked up.
    - **Seeded RNG where possible.**  For examples that accept an
      ``rng`` keyword argument (e.g., SnakeGameScene, PongScene),
      validation passes a seeded ``random.Random(42)`` for
      deterministic results.  Examples without ``rng`` parameters
      use their own random state, so results may vary between runs.
    - **The default examples directory is resolved relative to this
      module's file path** (``../../examples/`` from ``src/wyby/``).
      If wyby is installed as a wheel or zip, the examples directory
      may not exist.  :func:`check_all_examples` returns an empty list
      in that case rather than raising.
    - **Validation is not exhaustive.**  A passing result means the
      scene can be constructed and its three lifecycle methods
      (``handle_events``, ``update``, ``render``) don't raise with
      trivial inputs.  It does not test game logic, collision
      detection, scoring, or state transitions.  Use the dedicated
      test suite (``tests/test_*.py``) for thorough coverage.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import random
import sys
from pathlib import Path

from wyby.scene import Scene

_logger = logging.getLogger(__name__)


class ExampleCheckResult:
    """Result of validating a single example file.

    Attributes:
        path: Absolute path to the example file.
        importable: Whether the module could be imported without error.
        scene_classes: Names of Scene subclasses found in the module.
        scenes_constructed: Number of scene classes successfully
            instantiated.
        lifecycle_ok: Whether all constructed scenes passed the
            lifecycle check (``handle_events``, ``update``, ``render``).
        error: Error message if any step failed, or ``None``.
        caveats: List of caveat strings relevant to this example.

    Caveats:
        - ``importable`` being ``True`` does not guarantee the example
          works interactively — it only means ``importlib`` could load
          the module without raising.
        - ``lifecycle_ok`` being ``True`` means ``handle_events([])``,
          ``update(1/30)``, and ``render()`` all returned without
          exception.  It does not validate the correctness of output.
    """

    __slots__ = (
        "path",
        "importable",
        "scene_classes",
        "scenes_constructed",
        "lifecycle_ok",
        "error",
        "caveats",
    )

    def __init__(
        self,
        *,
        path: str,
        importable: bool = False,
        scene_classes: list[str] | None = None,
        scenes_constructed: int = 0,
        lifecycle_ok: bool = False,
        error: str | None = None,
        caveats: list[str] | None = None,
    ) -> None:
        self.path = path
        self.importable = importable
        self.scene_classes = scene_classes or []
        self.scenes_constructed = scenes_constructed
        self.lifecycle_ok = lifecycle_ok
        self.error = error
        self.caveats = caveats or []

    @property
    def filename(self) -> str:
        """Base filename without directory components."""
        return Path(self.path).name

    @property
    def ok(self) -> bool:
        """Whether the example passed all validation steps."""
        return self.importable and self.lifecycle_ok and self.error is None

    def __repr__(self) -> str:
        status = "OK" if self.ok else "FAIL"
        return (
            f"ExampleCheckResult(filename={self.filename!r}, "
            f"status={status}, scenes={self.scene_classes})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExampleCheckResult):
            return NotImplemented
        return (
            self.path == other.path
            and self.importable == other.importable
            and self.scene_classes == other.scene_classes
            and self.scenes_constructed == other.scenes_constructed
            and self.lifecycle_ok == other.lifecycle_ok
            and self.error == other.error
        )


def _default_examples_dir() -> Path:
    """Resolve the default examples directory relative to this module.

    Returns the ``examples/`` directory at the repository root, located
    by traversing up from ``src/wyby/`` to the repo root.

    Caveats:
        - This relies on the source tree layout (``src/wyby/`` ->
          ``../../examples/``).  If wyby is installed from a wheel
          or running from a zip archive, this path will not exist.
    """
    return Path(__file__).resolve().parent.parent.parent / "examples"


# Scene classes that accept an ``rng`` keyword argument.
# Caveat: This set is maintained manually.  If a new example adds
# ``rng`` support, add its class name here for deterministic validation.
_RNG_SCENE_CLASSES = frozenset({
    "SnakeGameScene",
    "PongScene",
    "FlappyBirdScene",
})


def _try_construct_scene(
    cls: type,
    class_name: str,
) -> Scene | None:
    """Attempt to instantiate a Scene subclass with default arguments.

    Passes a seeded RNG for classes known to accept one, ensuring
    deterministic validation.

    Caveats:
        - Only default constructor arguments are used.  If a scene
          requires non-default arguments to construct (e.g., mandatory
          callbacks), construction will fail and return ``None``.
        - The seeded RNG (``random.Random(42)``) is only passed to
          classes listed in ``_RNG_SCENE_CLASSES``.  Other classes
          use their own random state.

    Returns:
        The constructed Scene, or ``None`` if construction raised.
    """
    try:
        if class_name in _RNG_SCENE_CLASSES:
            return cls(rng=random.Random(42))
        return cls()
    except Exception:
        return None


def _run_lifecycle(scene: Scene) -> None:
    """Exercise one tick of a scene's lifecycle.

    Calls ``handle_events([])``, ``update(1/30)``, and ``render()``
    in sequence — the same order the Engine uses per tick.

    Caveats:
        - An empty event list is passed to ``handle_events``.  This
          does not test input handling — only that the method accepts
          an empty list without raising.
        - ``dt=1/30`` simulates a 30 TPS tick.  Scenes with time-based
          logic (e.g., move timers) will advance their state.
        - ``render()`` writes to the scene's internal CellBuffer.  The
          buffer contents are not inspected — only the absence of
          exceptions is checked.

    Raises:
        Any exception raised by the scene's lifecycle methods.
    """
    scene.handle_events([])
    scene.update(1 / 30)
    scene.render()


def _common_caveats() -> list[str]:
    """Return caveats common to all examples.

    These apply to every example in the wyby project and are included
    in every :class:`ExampleCheckResult`.
    """
    return [
        "Requires a real TTY for interactive use; validated without one.",
        "Terminal cells are ~1:2 aspect ratio (taller than wide).",
        "No dirty-region tracking; full buffer redraw each frame.",
        "AltScreen not used in examples for simplicity.",
    ]


def check_example(path: str | Path) -> ExampleCheckResult:
    """Validate a single example file.

    Attempts to:

    1. Import the module.
    2. Discover Scene subclasses.
    3. Construct each scene with default arguments.
    4. Run one lifecycle tick (events, update, render).

    Args:
        path: Path to the example ``.py`` file.

    Returns:
        An :class:`ExampleCheckResult` with the validation outcome.

    Caveats:
        - The module is loaded via ``importlib.util`` with a synthetic
          module name (``_wyby_example_<stem>``).  If the module has
          already been loaded under a different name, it will be loaded
          again as a separate module object.  This is intentional —
          validation should not depend on prior import state.
        - If the module raises during import (e.g., missing dependency,
          syntax error), the result will have ``importable=False`` and
          the error message in ``error``.
        - If no Scene subclasses are found, the result has
          ``lifecycle_ok=False`` with an appropriate error message.
          This can happen if the example defines its scene classes
          conditionally or in a nested scope.
        - The ``caveats`` list in the result includes both common
          caveats (TTY requirement, aspect ratio, etc.) and any
          example-specific notes discovered during validation.
    """
    resolved = str(Path(path).resolve())
    result = ExampleCheckResult(path=resolved, caveats=_common_caveats())

    # Step 1: Import.
    stem = Path(path).stem
    module_name = f"_wyby_example_{stem}"

    # Ensure the examples directory is on sys.path so relative imports
    # within examples (if any) can resolve.
    examples_dir = str(Path(resolved).parent)
    path_added = False
    if examples_dir not in sys.path:
        sys.path.insert(0, examples_dir)
        path_added = True

    try:
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            result.error = f"Cannot create module spec for {resolved}"
            return result

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        result.importable = True
        _logger.debug("Imported example: %s", resolved)
    except Exception as exc:
        result.error = f"Import failed: {exc}"
        _logger.warning("Failed to import %s: %s", resolved, exc)
        return result
    finally:
        # Clean up the synthetic module to avoid polluting sys.modules.
        sys.modules.pop(module_name, None)
        if path_added:
            try:
                sys.path.remove(examples_dir)
            except ValueError:
                pass

    # Step 2: Discover Scene subclasses.
    scene_classes: list[tuple[str, type]] = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, Scene) and obj is not Scene:
            scene_classes.append((name, obj))

    result.scene_classes = [name for name, _ in scene_classes]

    if not scene_classes:
        result.error = "No Scene subclasses found"
        _logger.debug("No Scene subclasses in %s", resolved)
        return result

    # Step 3 & 4: Construct and exercise lifecycle.
    constructed = 0
    lifecycle_errors: list[str] = []

    for class_name, cls in scene_classes:
        scene = _try_construct_scene(cls, class_name)
        if scene is None:
            lifecycle_errors.append(
                f"{class_name}: construction failed"
            )
            continue
        constructed += 1

        try:
            _run_lifecycle(scene)
        except Exception as exc:
            lifecycle_errors.append(
                f"{class_name}: lifecycle error: {exc}"
            )

    result.scenes_constructed = constructed

    if lifecycle_errors:
        result.error = "; ".join(lifecycle_errors)
        _logger.warning("Lifecycle issues in %s: %s", resolved, result.error)
    else:
        result.lifecycle_ok = True
        _logger.debug("All checks passed for %s", resolved)

    return result


def check_all_examples(
    directory: str | Path | None = None,
) -> list[ExampleCheckResult]:
    """Discover and validate all ``*.py`` files in a directory.

    Args:
        directory: Path to the directory to scan.  Defaults to the
            bundled ``examples/`` directory resolved relative to this
            module's source file.

    Returns:
        A list of :class:`ExampleCheckResult` instances, sorted by
        filename.  Returns an empty list if the directory does not
        exist or contains no ``*.py`` files.

    Caveats:
        - Only ``*.py`` files in the top level of the directory are
          included.  Subdirectories are **not** recursed into.  This
          avoids accidentally validating ``__pycache__`` artefacts or
          nested packages.
        - Files that fail to import are included in the results with
          ``importable=False``.  This allows callers to distinguish
          "file doesn't import" from "file not found".
        - The default examples directory is resolved from the source
          tree layout.  If wyby is installed from a wheel, the
          ``examples/`` directory is typically not included and this
          function returns an empty list.
        - Each example is validated independently.  A failure in one
          example does not affect validation of others.
    """
    if directory is None:
        directory = _default_examples_dir()

    dir_path = Path(directory)
    if not dir_path.is_dir():
        _logger.debug(
            "Examples directory does not exist: %s", dir_path,
        )
        return []

    results: list[ExampleCheckResult] = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_file() or entry.suffix != ".py":
            continue
        result = check_example(entry)
        results.append(result)

    _logger.debug(
        "Validated %d example file(s) from %s",
        len(results),
        dir_path,
    )
    return results


def format_check_results(results: list[ExampleCheckResult]) -> str:
    """Format validation results as a human-readable table.

    Args:
        results: List of :class:`ExampleCheckResult` instances.

    Returns:
        A multi-line string with a header row and one row per example,
        plus a summary line.  Returns ``"No examples found."`` if
        *results* is empty.

    Caveats:
        - Column widths are computed from the data.  Very long filenames
          may produce wide output that wraps in narrow terminals.
        - The table is plain text, not a Rich renderable.  For
          integration with Rich-based UIs, consume the
          :class:`ExampleCheckResult` objects directly.
    """
    if not results:
        return "No examples found."

    name_width = max(len(r.filename) for r in results)
    name_width = max(name_width, len("Example"))

    header = (
        f"{'Example':<{name_width}}  "
        f"{'Import':>6}  {'Scenes':>6}  {'Lifecycle':>9}  {'Status':>6}"
    )
    separator = "-" * len(header)

    lines = [header, separator]
    for r in results:
        import_status = "OK" if r.importable else "FAIL"
        scene_count = str(len(r.scene_classes))
        lifecycle_status = "OK" if r.lifecycle_ok else "FAIL"
        overall = "OK" if r.ok else "FAIL"

        lines.append(
            f"{r.filename:<{name_width}}  "
            f"{import_status:>6}  {scene_count:>6}  "
            f"{lifecycle_status:>9}  {overall:>6}"
        )

    # Summary.
    passed = sum(1 for r in results if r.ok)
    total = len(results)
    lines.append(separator)
    lines.append(f"{passed}/{total} examples passed validation.")

    # Common caveats footer.
    lines.append("")
    lines.append("Caveats:")
    for caveat in _common_caveats():
        lines.append(f"  - {caveat}")

    return "\n".join(lines)

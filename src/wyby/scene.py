"""Scene base class and scene stack management.

This module will provide the ``Scene`` abstract base class and a
``SceneStack`` that allows pushing, popping, and replacing scenes
(e.g., pushing a pause menu over gameplay).

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - Only the top scene on the stack receives input. Scenes below it
      may or may not render depending on configuration (e.g., a
      transparent pause overlay vs. an opaque menu).
    - Scenes own their entities and state. There is no implicit global
      state shared between scenes. Cross-scene communication must be
      done explicitly (e.g., via a shared context object).
    - Scene transitions (push, pop, replace) are explicit. There is no
      automatic transition animation system in v0.1.
"""

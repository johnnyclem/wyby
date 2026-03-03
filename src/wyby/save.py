"""Schema-based save/load helpers.

This module will provide utilities for serialising game state to JSON
(or optionally MessagePack) and reading it back. Games must implement
explicit ``to_save_data()`` / ``from_save_data()`` methods that produce
and consume plain data — wyby does not serialise object graphs
automatically.

Caveats:
    - **Not yet implemented.** This module is a placeholder establishing
      the package structure. See SCOPE.md for the intended design.
    - ``pickle`` is **explicitly excluded**. Pickle deserialisation is
      arbitrary code execution, making it unsafe for save files that
      could be shared, modified, or downloaded. wyby requires explicit
      schema-based serialisation.
    - Games define their own save schema (a dictionary or dataclass
      describing the state to persist). This is the game's
      responsibility, not the framework's.
    - wyby does not serialise scene objects, entity instances, or
      runtime state automatically. Implicit serialisation of object
      graphs leads to versioning nightmares and opaque bugs.
    - MessagePack support (``msgpack``) is an optional dependency.
      JSON is the default and always available.
"""

"""Component base class for entity composition.

This module provides the :class:`Component` base class.  Components are
data-and-behaviour bundles that attach to an :class:`~wyby.entity.Entity`
to give it capabilities (rendering, velocity, health, AI, etc.).

The component model follows simple composition — entities hold components
keyed by type, and game logic queries or updates them.  This is **not**
a full Entity Component System (ECS): there is no archetype storage, no
bitset component masks, and no automatic system scheduling.

Usage::

    class Health(Component):
        def __init__(self, hp: int = 100) -> None:
            super().__init__()
            self.hp = hp
            self.max_hp = hp

        def update(self, dt: float) -> None:
            # Regenerate 1 hp per second while alive.
            if self.hp > 0:
                self.hp = min(self.hp + dt, self.max_hp)

Caveats:
    - **Not a full ECS.**  There is no archetype storage, no system
      scheduling, no bitset queries.  Components are stored in a plain
      dict keyed by their class.  If your game outgrows this model,
      you can bring in ``esper`` or another ECS library and use wyby
      only for rendering.
    - **One component per type per entity.**  An entity can hold at
      most one instance of each component class.  If you need multiple
      instances (e.g. multiple status effects), use a single component
      that holds a list internally.
    - **Single-entity ownership.**  A component instance can be
      attached to at most one entity at a time.  Attaching a component
      that is already attached elsewhere raises :class:`RuntimeError`.
      Detach it first.
    - **No systems.**  wyby has no ``System`` base class and no
      automatic update scheduling.  The ``update(dt)`` hook exists for
      convenience, but nothing calls it automatically — there is no
      framework-managed system loop.  Your scene or game loop must
      iterate over entities and call ``update`` each tick explicitly.
      See ``docs/entity_model.md`` for the rationale and migration path.
    - **Lifecycle hooks are synchronous.**  ``on_attach`` and
      ``on_detach`` run immediately during attach/detach.  Avoid
      heavy work in these hooks — defer it to ``update``.
    - **Thread safety.**  Component attachment and mutation are not
      thread-safe.  The game loop is expected to be single-threaded.
    - **Subclass identity.**  Components are keyed by their exact
      class, not by base classes.  If ``AdvancedHealth`` inherits
      from ``Health``, they are separate component types.  Querying
      for ``Health`` will not find ``AdvancedHealth``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wyby.entity import Entity

_logger = logging.getLogger(__name__)


class Component:
    """Base class for all entity components.

    Subclass this to create components that attach to entities.
    Override :meth:`update` for per-tick logic and :meth:`on_attach` /
    :meth:`on_detach` for lifecycle management.

    The :attr:`entity` property provides a reference back to the owning
    entity, or ``None`` if the component is not currently attached.

    Caveats:
        - A component instance can be attached to at most one entity.
          Attempting to attach a component that is already attached
          elsewhere raises :class:`RuntimeError`.
        - The ``entity`` attribute is managed by the attachment
          mechanism (e.g. ``Entity.add_component``).  Do not set
          ``_entity`` directly from game code — use the attach/detach
          API instead.
        - ``update(dt)`` is not called automatically.  Your game
          loop must call it explicitly.
    """

    __slots__ = ("_entity",)

    def __init__(self) -> None:
        self._entity: Entity | None = None

    @property
    def entity(self) -> Entity | None:
        """The entity this component is attached to, or ``None``.

        Read-only from game code.  Set internally by the attachment
        mechanism.
        """
        return self._entity

    def on_attach(self, entity: Entity) -> None:
        """Called immediately after this component is attached to *entity*.

        Override in subclasses to perform setup that requires a
        reference to the owning entity (e.g. reading the entity's
        position or tags).

        The default implementation does nothing.

        Args:
            entity: The entity this component was just attached to.

        Caveats:
            - ``self.entity`` is already set when this method is called.
            - Keep this method lightweight.  Defer heavy initialisation
              to the first ``update`` call if possible.
        """

    def on_detach(self, entity: Entity) -> None:
        """Called immediately before this component is detached from *entity*.

        Override in subclasses to perform teardown (e.g. releasing
        resources tied to the entity).

        The default implementation does nothing.

        Args:
            entity: The entity this component is about to be detached
                from.

        Caveats:
            - ``self.entity`` is still set to *entity* when this method
              is called.  It will be cleared to ``None`` after this
              method returns.
        """

    def update(self, dt: float) -> None:
        """Per-tick update hook.

        Override in subclasses to implement per-tick logic
        (movement, cooldowns, animation, etc.).

        The default implementation does nothing.

        Args:
            dt: Time elapsed since the last tick, in seconds.

        Caveats:
            - This method is **not** called automatically.  Your
              scene or game loop must iterate over components and
              call ``update`` each tick.
            - ``dt`` is typically a fixed timestep (e.g. 1/30) from
              the engine's accumulator pattern, not wall-clock time.
            - The component may not be attached to an entity when
              this is called if your code calls it manually on a
              detached component.  Check ``self.entity`` if needed.
        """

    def __repr__(self) -> str:
        entity_info = (
            f"entity_id={self._entity.id}" if self._entity is not None
            else "detached"
        )
        return f"{type(self).__name__}({entity_info})"

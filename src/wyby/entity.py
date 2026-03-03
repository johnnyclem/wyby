"""Entity container and spatial queries.

This module provides a simple entity model — not a full Entity Component
System (ECS).  Entities are Python objects with an id, position, and
optional tags for querying.

The :class:`Entity` class is a lightweight container.  Games create
entities, place them in scenes, and query them by position or tag.
The entity model's job is to answer: "what is at position (x, y)?"
and "give me all entities tagged 'enemy'."

Caveats:
    - **Not a full ECS.**  There is no archetype storage, no bitset
      component masks, and no systems layer.  wyby has no ``System``
      base class and no automatic component-update scheduling — your
      game loop or scene must call ``entity.update(dt)`` explicitly.
      If your game outgrows this model, you can bring in ``esper`` or
      another ECS library and use wyby only for rendering.  See
      ``docs/entity_model.md`` for the full rationale.
    - **IDs are auto-assigned.**  Each entity receives a unique integer
      id from a module-level counter.  IDs are not recycled — once an
      entity is created, its id is permanently consumed.  For typical
      games (thousands of entities over a session) this is fine.  For
      extremely long-running programs that create and discard millions
      of entities, the counter grows without bound but never overflows
      (Python ints have arbitrary precision).
    - **Position is mutable.**  ``x`` and ``y`` are plain int
      attributes.  There is no observer/notification system — if your
      scene maintains a spatial index, it must be updated manually
      when an entity moves.
    - **No built-in spatial index.**  Spatial query performance is
      O(n) over all entities.  For games with hundreds of entities
      this is fine; for thousands, a spatial index (grid hash, quadtree)
      would be needed but is not provided in v0.1.
    - **No collision detection or physics.**  The entity model stores
      positions but does not enforce any spatial constraints.  Two
      entities can occupy the same position.  Collision logic is the
      game's responsibility.
    - **Tags are unordered sets.**  Tag ordering is not preserved.
      Tag values must be non-empty strings.
    - **Thread safety.**  Entity creation and mutation are not
      thread-safe.  The id counter uses :func:`itertools.count` which
      is thread-safe for ``next()`` calls in CPython (GIL), but
      attribute mutations on entities are not synchronized.  The
      game loop is expected to be single-threaded.
"""

from __future__ import annotations

import itertools
import logging
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from wyby.component import Component

_logger = logging.getLogger(__name__)

# Module-level auto-incrementing id counter.  Each call to next(_id_counter)
# produces a unique int.  IDs start at 1 (0 is reserved as a sentinel /
# "no entity" value in some patterns).
#
# Caveat: this counter is global and never resets.  If you need
# deterministic ids (e.g. for replay or save/load), assign ids
# explicitly via Entity(entity_id=...) rather than relying on
# auto-assignment.
_id_counter = itertools.count(1)


class Entity:
    """A simple game entity with an id and a grid position.

    Entities are the basic unit of "things that exist in the game world."
    Each entity has a unique integer :attr:`id` and a position
    (:attr:`x`, :attr:`y`) on the grid.  Entities may also carry a set
    of string :attr:`tags` for grouping and querying (e.g. ``"enemy"``,
    ``"item"``, ``"wall"``).

    Args:
        x: Horizontal grid position (column).  Defaults to 0.
        y: Vertical grid position (row).  Defaults to 0.
        tags: Optional iterable of string tags for grouping.
            Duplicates are silently collapsed (tags are stored as a set).
        entity_id: Explicit id override.  If ``None`` (the default),
            an id is auto-assigned from the module-level counter.
            Use explicit ids when you need deterministic assignment
            (e.g. save/load, replays, tests).

    Raises:
        TypeError: If *x* or *y* is not an int, or if *entity_id*
            is provided and is not an int.
        TypeError: If any tag is not a string.
        ValueError: If any tag is an empty string.
        ValueError: If *entity_id* is negative.

    Caveats:
        - Position coordinates are plain ints with no enforced bounds.
          Negative positions are allowed (useful for off-screen
          entities or scrolling viewports).  It is the game's
          responsibility to clamp positions to valid grid bounds
          when needed.
        - Terminal grids typically use (0, 0) as the top-left corner,
          with x increasing rightward and y increasing downward.
          This is the opposite of mathematical convention where y
          increases upward.  wyby follows the terminal convention.
        - Entity ids are unique within a process but are **not**
          stable across save/load cycles unless you assign them
          explicitly.  The auto-counter resets when the process
          restarts.
        - Entities are not automatically registered with any scene or
          container.  Creating an entity does not make it appear in
          the game — you must add it to your scene's entity collection.
    """

    __slots__ = ("_id", "_x", "_y", "_tags", "_components", "_alive")

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        *,
        tags: Iterable[str] | None = None,
        entity_id: int | None = None,
    ) -> None:
        # Validate position types.
        if not isinstance(x, int) or isinstance(x, bool):
            raise TypeError(
                f"x must be an int, got {type(x).__name__}"
            )
        if not isinstance(y, int) or isinstance(y, bool):
            raise TypeError(
                f"y must be an int, got {type(y).__name__}"
            )

        # Assign or validate id.
        if entity_id is None:
            self._id = next(_id_counter)
        else:
            if not isinstance(entity_id, int) or isinstance(entity_id, bool):
                raise TypeError(
                    f"entity_id must be an int, got {type(entity_id).__name__}"
                )
            if entity_id < 0:
                raise ValueError(
                    f"entity_id must be non-negative, got {entity_id}"
                )
            self._id = entity_id

        self._x = x
        self._y = y
        self._alive = True
        self._components: dict[type[Component], Component] = {}

        # Validate and store tags.
        if tags is not None:
            validated: set[str] = set()
            for tag in tags:
                if not isinstance(tag, str):
                    raise TypeError(
                        f"tags must be strings, got {type(tag).__name__}"
                    )
                if not tag:
                    raise ValueError("tags must be non-empty strings")
                validated.add(tag)
            self._tags = validated
        else:
            self._tags: set[str] = set()

        _logger.debug(
            "Entity created: id=%d pos=(%d, %d) tags=%r",
            self._id, self._x, self._y, self._tags,
        )

    @property
    def id(self) -> int:
        """The unique identifier for this entity.

        Read-only.  Assigned at creation and never changes.
        """
        return self._id

    @property
    def x(self) -> int:
        """Horizontal grid position (column)."""
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(
                f"x must be an int, got {type(value).__name__}"
            )
        self._x = value

    @property
    def y(self) -> int:
        """Vertical grid position (row)."""
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(
                f"y must be an int, got {type(value).__name__}"
            )
        self._y = value

    @property
    def position(self) -> tuple[int, int]:
        """The ``(x, y)`` position as a tuple.

        This is a convenience property.  Setting it updates both
        :attr:`x` and :attr:`y` atomically (from the caller's
        perspective — there is no actual locking).

        Caveats:
            - Returns a new tuple each call.  Do not rely on
              identity (``is``) comparisons between position tuples.
        """
        return (self._x, self._y)

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        if not isinstance(value, tuple) or len(value) != 2:
            raise TypeError(
                "position must be a (x, y) tuple of two ints"
            )
        x, y = value
        if not isinstance(x, int) or isinstance(x, bool):
            raise TypeError(
                f"position x must be an int, got {type(x).__name__}"
            )
        if not isinstance(y, int) or isinstance(y, bool):
            raise TypeError(
                f"position y must be an int, got {type(y).__name__}"
            )
        self._x = x
        self._y = y

    @property
    def tags(self) -> frozenset[str]:
        """The entity's tags as an immutable frozenset.

        Returns a frozenset to prevent accidental mutation of the
        internal tag set.  Use :meth:`add_tag` and :meth:`remove_tag`
        to modify tags.
        """
        return frozenset(self._tags)

    def has_tag(self, tag: str) -> bool:
        """Check whether this entity has the given tag.

        Args:
            tag: The tag to check.

        Returns:
            ``True`` if the entity has the tag, ``False`` otherwise.
        """
        return tag in self._tags

    def add_tag(self, tag: str) -> None:
        """Add a tag to this entity.

        Args:
            tag: A non-empty string tag.

        Raises:
            TypeError: If *tag* is not a string.
            ValueError: If *tag* is empty.

        Caveats:
            - Adding a tag that the entity already has is a no-op.
        """
        if not isinstance(tag, str):
            raise TypeError(
                f"tag must be a string, got {type(tag).__name__}"
            )
        if not tag:
            raise ValueError("tag must be a non-empty string")
        self._tags.add(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from this entity.

        Args:
            tag: The tag to remove.

        Raises:
            KeyError: If the entity does not have the tag.
        """
        self._tags.remove(tag)  # raises KeyError if not found

    def add_component(self, component: Component) -> None:
        """Attach a component to this entity.

        The component is stored keyed by its exact class
        (``type(component)``).  After attachment, ``component.entity``
        points back to this entity and :meth:`~wyby.component.Component.on_attach`
        is called.

        Args:
            component: The component instance to attach.

        Raises:
            TypeError: If *component* is not a :class:`~wyby.component.Component`
                instance.
            RuntimeError: If *component* is already attached to another entity.
                Detach it first.
            ValueError: If this entity already has a component of the same type.

        Caveats:
            - **One component per type.**  An entity can hold at most one
              instance of each component class.  If you need multiples
              (e.g. multiple status effects), use a single component that
              holds a list internally.
            - **Keyed by exact class.**  If ``AdvancedHealth`` inherits from
              ``Health``, they are separate component types.  Adding both is
              allowed; querying for ``Health`` will not find ``AdvancedHealth``.
            - **Single-entity ownership.**  A component instance can only be
              attached to one entity at a time.  Attaching the same instance
              to a second entity without detaching first raises
              :class:`RuntimeError`.
            - **on_attach runs synchronously** during this call.  Avoid
              heavy work in that hook — defer it to ``update``.
        """
        from wyby.component import Component as _Component

        if not isinstance(component, _Component):
            raise TypeError(
                f"component must be a Component instance, "
                f"got {type(component).__name__}"
            )
        if component._entity is not None:
            raise RuntimeError(
                f"{type(component).__name__} is already attached to "
                f"Entity(id={component._entity.id}); detach it first"
            )
        comp_type = type(component)
        if comp_type in self._components:
            raise ValueError(
                f"Entity(id={self._id}) already has a "
                f"{comp_type.__name__} component"
            )
        self._components[comp_type] = component
        component._entity = self
        component.on_attach(self)
        _logger.debug(
            "Component %s attached to Entity id=%d",
            comp_type.__name__, self._id,
        )

    def remove_component(self, component_type: type[Component]) -> Component:
        """Detach and return the component of the given type.

        Calls :meth:`~wyby.component.Component.on_detach` before removing
        the component, then clears the component's entity back-reference.

        Args:
            component_type: The exact class of the component to remove
                (e.g. ``Health``, not an instance).

        Returns:
            The detached component instance.

        Raises:
            TypeError: If *component_type* is not a type, or is not a
                subclass of :class:`~wyby.component.Component`.
            KeyError: If this entity does not have a component of the
                given type.

        Caveats:
            - **Exact class match only.**  Passing a base class will not
              remove subclass components.  ``remove_component(Health)``
              will not remove an ``AdvancedHealth`` component.
            - **on_detach runs synchronously** during this call with
              ``component.entity`` still set.  The back-reference is
              cleared to ``None`` after ``on_detach`` returns.
            - **The returned component can be re-attached** to another
              entity (or the same one) via :meth:`add_component`.
        """
        from wyby.component import Component as _Component

        if not isinstance(component_type, type) or not issubclass(
            component_type, _Component
        ):
            raise TypeError(
                f"component_type must be a Component subclass, "
                f"got {component_type!r}"
            )
        if component_type not in self._components:
            raise KeyError(
                f"Entity(id={self._id}) has no "
                f"{component_type.__name__} component"
            )
        component = self._components.pop(component_type)
        component.on_detach(self)
        component._entity = None
        _logger.debug(
            "Component %s detached from Entity id=%d",
            component_type.__name__, self._id,
        )
        return component

    def get_component(self, component_type: type[Component]) -> Component | None:
        """Return the component of the given type, or ``None``.

        This is the primary way to query an entity's components.  It
        avoids the need to access internal storage directly.

        Args:
            component_type: The exact class of the component to look up
                (e.g. ``Position``, not an instance).

        Returns:
            The component instance, or ``None`` if the entity does not
            have a component of that type.

        Raises:
            TypeError: If *component_type* is not a type or is not a
                subclass of :class:`~wyby.component.Component`.

        Caveats:
            - **Exact class match only.**  Passing a base class will not
              find subclass components.  ``get_component(Health)`` will
              not return an ``AdvancedHealth`` component.
            - **This is simple composition, not a full ECS.**  There are
              no bitset queries, no archetype tables, and no way to query
              across all entities for a component type.  If you need those
              patterns, consider a dedicated ECS library like ``esper`` and
              use wyby only for rendering.  See ``docs/entity_model.md``
              for migration guidance.
        """
        from wyby.component import Component as _Component

        if not isinstance(component_type, type) or not issubclass(
            component_type, _Component
        ):
            raise TypeError(
                f"component_type must be a Component subclass, "
                f"got {component_type!r}"
            )
        return self._components.get(component_type)

    def has_component(self, component_type: type[Component]) -> bool:
        """Check whether this entity has a component of the given type.

        Args:
            component_type: The exact class of the component to check.

        Returns:
            ``True`` if the entity has the component, ``False`` otherwise.

        Raises:
            TypeError: If *component_type* is not a type or is not a
                subclass of :class:`~wyby.component.Component`.

        Caveats:
            - **Exact class match only**, same as :meth:`get_component`.
        """
        from wyby.component import Component as _Component

        if not isinstance(component_type, type) or not issubclass(
            component_type, _Component
        ):
            raise TypeError(
                f"component_type must be a Component subclass, "
                f"got {component_type!r}"
            )
        return component_type in self._components

    def update(self, dt: float) -> None:
        """Update all attached components for one tick.

        Iterates over every component attached to this entity and calls
        its :meth:`~wyby.component.Component.update` method with *dt*.

        This is a convenience method — games can also call individual
        component ``update`` methods directly for more control over
        ordering and selective updates.

        Args:
            dt: Time elapsed since the last tick, in seconds.  Typically
                a fixed timestep (e.g. 1/30) from the engine's
                accumulator pattern, not wall-clock time.

        Caveats:
            - **Iteration order** follows component attachment order
              (dict insertion order, guaranteed in Python 3.7+).  If
              your game depends on a specific update order (e.g.
              Velocity before Health), attach components in that order.
              For fine-grained control, call component ``update``
              methods individually instead.
            - **Snapshot iteration.**  This method iterates over a
              snapshot of the component list, so adding or removing
              components during an ``update`` callback will not cause
              ``RuntimeError`` from dict mutation.  However, newly
              added components will NOT be updated in the current tick,
              and removed components that haven't been reached yet will
              still be updated.
            - **Exceptions propagate.**  If a component's ``update``
              raises an exception, it will propagate immediately and
              remaining components will not be updated for that tick.
              The framework does not catch or log component errors —
              handle them in your component or game loop.
            - **No-op when empty.**  If the entity has no components,
              this method returns immediately.
        """
        # Snapshot via list() so mutations during iteration are safe.
        for component in list(self._components.values()):
            component.update(dt)

    @property
    def alive(self) -> bool:
        """Whether this entity is still alive (not destroyed).

        Returns ``False`` after :meth:`destroy` has been called.
        """
        return self._alive

    def destroy(self) -> None:
        """Mark this entity as destroyed and detach all components.

        Calls :meth:`~wyby.component.Component.on_detach` on every
        attached component (in attachment order), clears the component
        dict, clears tags, and sets :attr:`alive` to ``False``.

        Calling ``destroy()`` on an already-destroyed entity is a
        no-op — it will not raise or re-trigger detach hooks.

        Caveats:
            - **Does not remove the entity from any scene.**  The game
              must call ``scene.remove_entity(entity)`` separately.
              ``destroy()`` is purely about cleaning up the entity's
              own state (components and tags).  Scenes have no
              automatic "dead entity sweep" — you must remove destroyed
              entities in your game loop or scene update.
            - **Components are detached in attachment order** (dict
              insertion order, guaranteed in Python 3.7+).  Each
              component's ``on_detach`` is called with ``self`` still
              set as the entity, then the back-reference is cleared,
              same as :meth:`remove_component`.
            - **Idempotent.**  Calling ``destroy()`` more than once is
              safe and does nothing after the first call.
            - **The entity id is not recycled.**  A destroyed entity
              still holds its id.  The auto-incrementing counter never
              rewinds.
            - **The entity remains a valid Python object** after
              destruction.  Its ``id``, ``x``, ``y``, and ``position``
              are still readable.  Code that holds a reference to the
              entity should check :attr:`alive` before using it.
        """
        if not self._alive:
            return

        # Detach all components, calling on_detach for each.
        # Snapshot via list() since we mutate the dict during iteration.
        for comp_type, component in list(self._components.items()):
            component.on_detach(self)
            component._entity = None
            _logger.debug(
                "Component %s detached during destroy of Entity id=%d",
                comp_type.__name__, self._id,
            )
        self._components.clear()

        self._tags.clear()
        self._alive = False

        _logger.debug("Entity destroyed: id=%d", self._id)

    def move(self, dx: int, dy: int) -> None:
        """Move the entity by a relative offset.

        Args:
            dx: Horizontal offset (positive = rightward).
            dy: Vertical offset (positive = downward).

        Raises:
            TypeError: If *dx* or *dy* is not an int.

        Caveats:
            - No bounds checking is performed.  The entity can move
              to negative coordinates or beyond the grid dimensions.
              Clamp to valid bounds in your game logic if needed.
        """
        if not isinstance(dx, int) or isinstance(dx, bool):
            raise TypeError(
                f"dx must be an int, got {type(dx).__name__}"
            )
        if not isinstance(dy, int) or isinstance(dy, bool):
            raise TypeError(
                f"dy must be an int, got {type(dy).__name__}"
            )
        self._x += dx
        self._y += dy

    def __eq__(self, other: object) -> bool:
        """Entities are equal if they have the same id.

        Caveats:
            - Equality is based on :attr:`id` alone, not position or
              tags.  Two entities at the same position with the same
              tags are **not** equal unless they share an id.
        """
        if not isinstance(other, Entity):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        tag_str = f", tags={self._tags!r}" if self._tags else ""
        return f"Entity(id={self._id}, x={self._x}, y={self._y}{tag_str})"

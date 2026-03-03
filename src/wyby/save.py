"""Schema-based save/load helpers.

This module provides utilities for serialising game state to JSON
(or optionally MessagePack) and reading it back. Games must implement
explicit ``to_save_data()`` / ``from_save_data()`` methods that produce
and consume plain data — wyby does not serialise object graphs
automatically.

Usage::

    from wyby.save import SaveManager

    class GameState:
        def __init__(self):
            self.score = 0
            self.level = 1
            self.player_name = "Player"
        
        def to_save_data(self) -> dict:
            return {
                "score": self.score,
                "level": self.level,
                "player_name": self.player_name,
            }
        
        @classmethod
        def from_save_data(cls, data: dict) -> "GameState":
            state = cls()
            state.score = data.get("score", 0)
            state.level = data.get("level", 1)
            state.player_name = data.get("player_name", "Player")
            return state

    manager = SaveManager("mygame")
    state = GameState()
    state.score = 1000
    manager.save(state)
    loaded = manager.load(GameState)

Caveats:
    - ``pickle`` is **explicitly excluded**. Pickle deserialisation is
      arbitrary code execution, making it unsafe for save files.
    - MessagePack support (``msgpack``) is optional.
    - Save files are not encrypted.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    pass

T = TypeVar("T")

_logger = logging.getLogger(__name__)


class SaveError(Exception):
    """Base exception for save/load operations."""
    pass


class SaveFormatError(SaveError):
    """Raised when an unsupported save format is requested."""
    pass


class LoadError(SaveError):
    """Raised when loading fails (corrupt file, wrong schema)."""
    pass


class SchemaError(SaveError):
    """Raised when save data doesn't match expected schema."""
    pass


class Saveable(ABC):
    """Abstract base class for saveable game objects."""

    @abstractmethod
    def to_save_data(self) -> dict[str, Any]:
        """Convert this object to a plain dict for serialisation."""

    @classmethod
    @abstractmethod
    def from_save_data(cls, data: dict[str, Any]) -> Saveable:
        """Reconstruct this object from saved data."""
        raise NotImplementedError


class Serializer(ABC):
    """Abstract base class for serialisation formats."""

    @property
    @abstractmethod
    def extension(self) -> str:
        """File extension for this format."""

    @abstractmethod
    def dumps(self, data: dict[str, Any]) -> bytes:
        """Serialize data to bytes."""

    @abstractmethod
    def loads(self, data: bytes) -> dict[str, Any]:
        """Deserialize data from bytes."""


class JSONSerializer(Serializer):
    """JSON serialisation format."""

    def __init__(self, *, indent: int | None = 2, ensure_ascii: bool = False):
        self._indent = indent
        self._ensure_ascii = ensure_ascii

    @property
    def extension(self) -> str:
        return ".json"

    def dumps(self, data: dict[str, Any]) -> bytes:
        json_str = json.dumps(data, indent=self._indent, ensure_ascii=self._ensure_ascii)
        return json_str.encode("utf-8")

    def loads(self, data: bytes) -> dict[str, Any]:
        try:
            return json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise LoadError(f"Invalid JSON: {e}") from e


class MessagePackSerializer(Serializer):
    """MessagePack serialisation format. Requires ``msgpack`` package."""

    def __init__(self) -> None:
        try:
            import msgpack
            self._msgpack = msgpack
        except ImportError:
            raise SaveFormatError(
                "MessagePack requires 'msgpack' package. Install with: pip install msgpack"
            )

    @property
    def extension(self) -> str:
        return ".msgpack"

    def dumps(self, data: dict[str, Any]) -> bytes:
        return self._msgpack.packb(data, use_bin_type=True)

    def loads(self, data: bytes) -> dict[str, Any]:
        try:
            unpacked = self._msgpack.unpackb(data, raw=False)
            if not isinstance(unpacked, dict):
                raise LoadError(f"MessagePack must be a dict, got {type(unpacked).__name__}")
            return unpacked
        except self._msgpack.MsgpackError as e:
            raise LoadError(f"Invalid MessagePack: {e}") from e


def get_serializer(format: str) -> Serializer:
    """Get a serializer for the specified format."""
    if format == "json":
        return JSONSerializer()
    elif format == "msgpack":
        return MessagePackSerializer()
    else:
        raise SaveFormatError(f"Unknown format: {format!r}. Use 'json' or 'msgpack'.")


def validate_schema(
    data: dict[str, Any],
    schema: dict[str, type],
    *,
    path: str = "",
) -> None:
    """Validate that saved data matches expected schema."""
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: expected dict, got {type(data).__name__}")

    for field, expected_type in schema.items():
        if field not in data:
            raise SchemaError(f"{path}.{field}: missing required field")
        value = data[field]
        if not isinstance(value, expected_type):
            raise SchemaError(
                f"{path}.{field}: expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )


def coerce_types(
    data: dict[str, Any],
    schema: dict[str, type],
) -> dict[str, Any]:
    """Coerce saved data types to match schema where possible."""
    result = dict(data)

    for field, expected_type in schema.items():
        if field not in result:
            continue
        value = result[field]
        if isinstance(value, bool) and expected_type is int:
            result[field] = int(value)
        elif expected_type is int and isinstance(value, str):
            try:
                result[field] = int(value)
            except ValueError:
                pass
        elif expected_type is float and isinstance(value, str):
            try:
                result[field] = float(value)
            except ValueError:
                pass

    return result


class SaveManager:
    """Manages saving and loading game state.

    Args:
        game_name: Identifier for the game.
        save_dir: Directory for save files. Defaults to platform-specific location.
        create_dir: If True, create save_dir if it doesn't exist.
    """

    def __init__(
        self,
        game_name: str,
        save_dir: Path | str | None = None,
        create_dir: bool = True,
    ) -> None:
        if not game_name:
            raise ValueError("game_name must be non-empty")

        self._game_name = game_name

        if save_dir is None:
            save_dir = self._get_default_save_dir()
        self._save_dir = Path(save_dir)

        if create_dir and not self._save_dir.exists():
            self._save_dir.mkdir(parents=True, exist_ok=True)
            _logger.debug("Created save directory: %s", self._save_dir)

    @staticmethod
    def _get_default_save_dir() -> Path:
        import platform
        system = platform.system()

        if system == "Windows":
            base = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
            return Path(base) / "wyby" / "saves"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "wyby" / "saves"
        else:
            xdg_data = os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
            return Path(xdg_data) / "wyby" / "saves"

    def _get_save_path(self, format: str) -> Path:
        serializer = get_serializer(format)
        filename = f"{self._game_name}_save{serializer.extension}"
        return self._save_dir / filename

    def save(
        self,
        state: Saveable,
        *,
        format: str = "json",
    ) -> Path:
        """Save game state to a file."""
        serializer = get_serializer(format)
        save_path = self._get_save_path(format)

        try:
            data = state.to_save_data()
        except Exception as e:
            raise SaveError(f"Failed to serialise state: {e}") from e

        try:
            serialized = serializer.dumps(data)
        except Exception as e:
            raise SaveError(f"Failed to encode data: {e}") from e

        try:
            save_path.write_bytes(serialized)
        except Exception as e:
            raise SaveError(f"Failed to write save file: {e}") from e

        _logger.info("Saved game to %s", save_path)
        return save_path

    def load(
        self,
        state_class: type[T],
        *,
        format: str = "json",
    ) -> T:
        """Load game state from a file."""
        serializer = get_serializer(format)
        save_path = self._get_save_path(format)

        if not save_path.exists():
            raise FileNotFoundError(f"Save file not found: {save_path}")

        try:
            data = save_path.read_bytes()
        except Exception as e:
            raise LoadError(f"Failed to read save file: {e}") from e

        try:
            deserialized = serializer.loads(data)
        except LoadError:
            raise
        except Exception as e:
            raise LoadError(f"Failed to decode data: {e}") from e

        try:
            state = state_class.from_save_data(deserialized)  # type: ignore[attr-defined]
        except Exception as e:
            raise LoadError(f"Failed to reconstruct state: {e}") from e

        _logger.info("Loaded game from %s", save_path)
        return state

    def exists(self, format: str = "json") -> bool:
        """Check if a save file exists."""
        return self._get_save_path(format).exists()

    def delete(self, format: str = "json") -> bool:
        """Delete the save file."""
        save_path = self._get_save_path(format)
        if save_path.exists():
            save_path.unlink()
            _logger.info("Deleted save file: %s", save_path)
            return True
        return False

    def list_saves(self) -> list[str]:
        """List all available save formats for this game."""
        formats = []
        for fmt in ("json", "msgpack"):
            try:
                if self._get_save_path(fmt).exists():
                    formats.append(fmt)
            except SaveFormatError:
                pass  # Format not available (e.g., msgpack not installed)
        return formats

    @property
    def save_dir(self) -> Path:
        return self._save_dir

    @property
    def game_name(self) -> str:
        return self._game_name


class SaveSlot:
    """Represents a single save slot for games with multiple slots."""

    def __init__(self, slot_id: int | str, manager: SaveManager) -> None:
        self._slot_id = slot_id
        self._manager = manager

    def _get_slot_path(self, format: str) -> Path:
        serializer = get_serializer(format)
        filename = f"{self._manager.game_name}_slot{self._slot_id}{serializer.extension}"
        return self._manager.save_dir / filename

    def save(self, state: Saveable, *, format: str = "json") -> Path:
        serializer = get_serializer(format)
        save_path = self._get_slot_path(format)

        try:
            data = state.to_save_data()
            serialized = serializer.dumps(data)
            save_path.write_bytes(serialized)
            _logger.info("Saved to slot %s: %s", self._slot_id, save_path)
            return save_path
        except Exception as e:
            raise SaveError(f"Failed to save to slot {self._slot_id}: {e}") from e

    def load(self, state_class: type[T], *, format: str = "json") -> T:
        serializer = get_serializer(format)
        save_path = self._get_slot_path(format)

        if not save_path.exists():
            raise FileNotFoundError(f"Slot {self._slot_id} is empty")

        data = save_path.read_bytes()
        deserialized = serializer.loads(data)
        return state_class.from_save_data(deserialized)  # type: ignore[attr-defined]

    def exists(self, format: str = "json") -> bool:
        return self._get_slot_path(format).exists()

    def delete(self, format: str = "json") -> bool:
        save_path = self._get_slot_path(format)
        if save_path.exists():
            save_path.unlink()
            return True
        return False

    @property
    def slot_id(self) -> int | str:
        return self._slot_id


class SlotManager(SaveManager):
    """Extended SaveManager with support for multiple save slots."""

    def __getitem__(self, slot_id: int | str) -> SaveSlot:
        return SaveSlot(slot_id, self)

    def get_occupied_slots(self, max_slots: int = 10) -> list[int]:
        occupied = []
        for i in range(1, max_slots + 1):
            if self[i].exists():
                occupied.append(i)
        return occupied

    def delete_all(self) -> None:
        for i in range(1, 100):
            if not self[i].delete():
                break

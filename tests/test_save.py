"""Tests for wyby.save module."""

import tempfile
from pathlib import Path

import pytest

from wyby.save import (
    SaveManager,
    SlotManager,
    Saveable,
    SaveError,
    SaveFormatError,
    LoadError,
    SchemaError,
    JSONSerializer,
    MessagePackSerializer,
    get_serializer,
    validate_schema,
    coerce_types,
    SaveSlot,
)


class SimpleGameState(Saveable):
    """A simple saveable game state for testing."""

    def __init__(self):
        self.score = 0
        self.level = 1
        self.player_name = "Player"
        self.items: list[str] = []

    def to_save_data(self) -> dict:
        return {
            "score": self.score,
            "level": self.level,
            "player_name": self.player_name,
            "items": self.items,
        }

    @classmethod
    def from_save_data(cls, data: dict) -> "SimpleGameState":
        state = cls()
        state.score = data.get("score", 0)
        state.level = data.get("level", 1)
        state.player_name = data.get("player_name", "Player")
        state.items = data.get("items", [])
        return state


class TestJSONSerializer:
    """Tests for JSONSerializer."""

    def test_dumps_loads_roundtrip(self):
        serializer = JSONSerializer()
        data = {"score": 100, "name": "test"}
        encoded = serializer.dumps(data)
        decoded = serializer.loads(encoded)
        assert decoded == data

    def test_dumps_returns_bytes(self):
        serializer = JSONSerializer()
        data = {"key": "value"}
        result = serializer.dumps(data)
        assert isinstance(result, bytes)

    def test_extension(self):
        serializer = JSONSerializer()
        assert serializer.extension == ".json"

    def test_loads_invalid_json_raises(self):
        serializer = JSONSerializer()
        with pytest.raises(LoadError):
            serializer.loads(b"not valid json")


class TestMessagePackSerializer:
    """Tests for MessagePackSerializer."""

    def test_dumps_loads_roundtrip(self):
        try:
            serializer = MessagePackSerializer()
        except SaveFormatError:
            pytest.skip("msgpack not installed")

        data = {"score": 100, "name": "test"}
        encoded = serializer.dumps(data)
        decoded = serializer.loads(encoded)
        assert decoded == data

    def test_extension(self):
        try:
            serializer = MessagePackSerializer()
        except SaveFormatError:
            pytest.skip("msgpack not installed")
        assert serializer.extension == ".msgpack"


class TestGetSerializer:
    """Tests for get_serializer function."""

    def test_json_serializer(self):
        serializer = get_serializer("json")
        assert isinstance(serializer, JSONSerializer)

    def test_msgpack_serializer(self):
        try:
            serializer = get_serializer("msgpack")
            assert isinstance(serializer, MessagePackSerializer)
        except SaveFormatError:
            pytest.skip("msgpack not installed")

    def test_unknown_format_raises(self):
        with pytest.raises(SaveFormatError):
            get_serializer("invalid")


class TestValidateSchema:
    """Tests for validate_schema function."""

    def test_valid_schema(self):
        data = {"name": "test", "score": 100}
        schema = {"name": str, "score": int}
        validate_schema(data, schema)  # Should not raise

    def test_missing_field_raises(self):
        data = {"name": "test"}
        schema = {"name": str, "score": int}
        with pytest.raises(SchemaError):
            validate_schema(data, schema)

    def test_wrong_type_raises(self):
        data = {"name": 123}
        schema = {"name": str}
        with pytest.raises(SchemaError):
            validate_schema(data, schema)

    def test_nested_path_in_error(self):
        data = {}
        schema = {"name": str}
        with pytest.raises(SchemaError) as exc_info:
            validate_schema(data, schema, path="player")
        assert "player.name" in str(exc_info.value)


class TestCoerceTypes:
    """Tests for coerce_types function."""

    def test_bool_to_int(self):
        data = {"value": True}
        schema = {"value": int}
        result = coerce_types(data, schema)
        assert result["value"] == 1

    def test_str_to_int(self):
        data = {"value": "123"}
        schema = {"value": int}
        result = coerce_types(data, schema)
        assert result["value"] == 123

    def test_str_to_float(self):
        data = {"value": "1.5"}
        schema = {"value": float}
        result = coerce_types(data, schema)
        assert result["value"] == 1.5

    def test_preserves_original_types(self):
        data = {"value": 42}
        schema = {"value": int}
        result = coerce_types(data, schema)
        assert result["value"] == 42


class TestSaveManager:
    """Tests for SaveManager class."""

    def test_init_with_temp_dir(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td, create_dir=False)
            assert mgr.game_name == "testgame"
            assert mgr.save_dir == Path(td)

    def test_init_with_string_dir(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            assert mgr.save_dir == Path(td)

    def test_init_empty_game_name_raises(self):
        with pytest.raises(ValueError):
            SaveManager("")

    def test_save_and_load_json(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)

            state = SimpleGameState()
            state.score = 1000
            state.level = 5
            state.items = ["sword", "shield"]

            path = mgr.save(state)
            assert path.exists()

            loaded = mgr.load(SimpleGameState)
            assert loaded.score == 1000
            assert loaded.level == 5
            assert loaded.items == ["sword", "shield"]

    def test_save_and_load_msgpack(self):
        try:
            get_serializer("msgpack")
        except SaveFormatError:
            pytest.skip("msgpack not installed")

        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)

            state = SimpleGameState()
            state.score = 500

            mgr.save(state, format="msgpack")
            loaded = mgr.load(SimpleGameState, format="msgpack")
            assert loaded.score == 500

    def test_load_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            with pytest.raises(FileNotFoundError):
                mgr.load(SimpleGameState)

    def test_exists_false_for_new_save(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            assert not mgr.exists()

    def test_exists_true_after_save(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            state = SimpleGameState()
            mgr.save(state)
            assert mgr.exists()

    def test_delete_removes_file(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            state = SimpleGameState()
            mgr.save(state)
            assert mgr.exists()
            mgr.delete()
            assert not mgr.exists()

    def test_delete_nonexistent_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            assert mgr.delete() is False

    def test_list_saves_json_only(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            state = SimpleGameState()
            mgr.save(state)
            saves = mgr.list_saves()
            assert "json" in saves

    def test_save_invalid_state_raises(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)

            class BadState:
                pass

            with pytest.raises(SaveError):
                mgr.save(BadState())

    def test_load_corrupt_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            path = mgr._get_save_path("json")
            path.write_bytes(b"not valid json")

            with pytest.raises(LoadError):
                mgr.load(SimpleGameState)


class TestSaveSlot:
    """Tests for SaveSlot class."""

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            slot = SaveSlot(1, mgr)

            state = SimpleGameState()
            state.score = 2500

            slot.save(state)
            assert slot.exists()

            loaded = slot.load(SimpleGameState)
            assert loaded.score == 2500

    def test_exists_false_for_empty_slot(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            slot = SaveSlot(1, mgr)
            assert not slot.exists()

    def test_delete_slot(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            slot = SaveSlot(1, mgr)

            state = SimpleGameState()
            slot.save(state)
            assert slot.exists()

            slot.delete()
            assert not slot.exists()

    def test_string_slot_id(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SaveManager("testgame", save_dir=td)
            slot = SaveSlot("quicksave", mgr)

            state = SimpleGameState()
            state.score = 999
            slot.save(state)

            loaded = slot.load(SimpleGameState)
            assert loaded.score == 999


class TestSlotManager:
    """Tests for SlotManager class."""

    def test_getitem_returns_save_slot(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SlotManager("testgame", save_dir=td)
            slot = mgr[1]
            assert isinstance(slot, SaveSlot)
            assert slot.slot_id == 1

    def test_get_occupied_slots(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SlotManager("testgame", save_dir=td)

            state = SimpleGameState()
            mgr[1].save(state)
            mgr[3].save(state)

            occupied = mgr.get_occupied_slots(max_slots=5)
            assert sorted(occupied) == [1, 3]

    def test_delete_all(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SlotManager("testgame", save_dir=td)

            state = SimpleGameState()
            mgr[1].save(state)
            mgr[2].save(state)

            mgr.delete_all()

            occupied = mgr.get_occupied_slots()
            assert occupied == []


class TestSaveable:
    """Tests for Saveable abstract base class."""

    def test_subclass_must_implement_methods(self):
        class Incomplete(Saveable):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_complete_subclass(self):
        class Complete(Saveable):
            def to_save_data(self):
                return {"x": 1}

            @classmethod
            def from_save_data(cls, data):
                return cls()

        obj = Complete()
        data = obj.to_save_data()
        assert data == {"x": 1}

        loaded = Complete.from_save_data(data)
        assert isinstance(loaded, Complete)


class TestErrorClasses:
    """Tests for exception classes."""

    def test_save_error(self):
        with pytest.raises(SaveError):
            raise SaveError("test")

    def test_save_format_error(self):
        with pytest.raises(SaveFormatError):
            raise SaveFormatError("test")

    def test_load_error(self):
        with pytest.raises(LoadError):
            raise LoadError("test")

    def test_schema_error(self):
        with pytest.raises(SchemaError):
            raise SchemaError("test")

    def test_save_error_is_base(self):
        assert issubclass(SaveFormatError, SaveError)
        assert issubclass(LoadError, SaveError)
        assert issubclass(SchemaError, SaveError)

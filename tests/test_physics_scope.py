"""Tests for physics scope documentation — verifying PHYSICS_SCOPE constant."""

from __future__ import annotations

import os

from wyby.physics import PHYSICS_SCOPE


class TestPhysicsScopeConstant:
    """PHYSICS_SCOPE documents what wyby provides and does not provide."""

    def test_is_a_string(self) -> None:
        assert isinstance(PHYSICS_SCOPE, str)

    def test_not_empty(self) -> None:
        assert len(PHYSICS_SCOPE.strip()) > 0

    def test_states_not_a_physics_engine(self) -> None:
        """The constant must explicitly say wyby is not a physics engine."""
        assert "NOT" in PHYSICS_SCOPE
        assert "physics engine" in PHYSICS_SCOPE.lower()

    def test_documents_what_is_provided(self) -> None:
        """Key provided features are mentioned."""
        text = PHYSICS_SCOPE.lower()
        assert "position" in text
        assert "velocity" in text
        assert "collision" in text

    def test_documents_what_is_not_provided(self) -> None:
        """Key absent features are mentioned."""
        text = PHYSICS_SCOPE.lower()
        assert "rigid-body" in text or "rigid body" in text
        assert "continuous collision" in text
        assert "spatial indexing" in text

    def test_mentions_euler_integration(self) -> None:
        """Euler integration caveat is documented."""
        assert "euler" in PHYSICS_SCOPE.lower()

    def test_importable_from_package_root(self) -> None:
        from wyby import PHYSICS_SCOPE as root_scope
        assert root_scope is PHYSICS_SCOPE

    def test_in_package_all(self) -> None:
        import wyby
        assert "PHYSICS_SCOPE" in wyby.__all__


class TestPhysicsDesignDoc:
    """The docs/physics_design.md file exists and covers key topics."""

    def _read_doc(self) -> str:
        doc_path = os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            "docs",
            "physics_design.md",
        )
        with open(doc_path) as f:
            return f.read()

    def test_doc_file_exists(self) -> None:
        """docs/physics_design.md exists."""
        doc_path = os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            "docs",
            "physics_design.md",
        )
        assert os.path.isfile(doc_path)

    def test_doc_title(self) -> None:
        content = self._read_doc()
        assert "No Full Physics Engine" in content

    def test_doc_covers_what_is_provided(self) -> None:
        content = self._read_doc()
        assert "What wyby Provides" in content

    def test_doc_covers_why_no_physics(self) -> None:
        content = self._read_doc()
        assert "Why No Physics Engine" in content

    def test_doc_covers_collision_response(self) -> None:
        content = self._read_doc()
        assert "Collision Detection Has No Response" in content

    def test_doc_covers_migration(self) -> None:
        """Doc mentions what to do if you need real physics."""
        content = self._read_doc().lower()
        assert "pymunk" in content or "pybox2d" in content

    def test_doc_covers_euler_limitation(self) -> None:
        content = self._read_doc().lower()
        assert "euler" in content

    def test_doc_covers_gravity_friction_caveats(self) -> None:
        content = self._read_doc()
        assert "Gravity and Friction Are Approximations" in content

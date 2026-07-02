"""Unit tests for RuntimeContext."""

import pytest

from agentshield.core.context import RuntimeContext, RuntimePhase


class TestRuntimeContext:
    """Test RuntimeContext functionality."""

    def test_initialization(self) -> None:
        """Test context initialization."""
        ctx = RuntimeContext(tenant_id="tenant-1", session_id="session-1")

        assert ctx.tenant_id == "tenant-1"
        assert ctx.session_id == "session-1"
        assert ctx.correlation_id is not None
        assert ctx.current_phase == RuntimePhase.IDENTITY

    def test_auto_generated_ids(self) -> None:
        """Test auto-generated session and correlation IDs."""
        ctx = RuntimeContext(tenant_id="tenant-1")

        assert ctx.session_id is not None
        assert ctx.correlation_id is not None
        assert len(ctx.session_id) > 0
        assert len(ctx.correlation_id) > 0

    def test_phase_advancement(self) -> None:
        """Test phase advancement with state history."""
        ctx = RuntimeContext(tenant_id="tenant-1")
        ctx.set_data("key1", "value1")

        # Advance to next phase
        ctx.advance_phase(RuntimePhase.INPUT)

        assert ctx.current_phase == RuntimePhase.INPUT
        assert len(ctx.get_state_history()) == 1

        # Previous state should be captured
        history = ctx.get_state_history()
        assert history[0].phase == RuntimePhase.IDENTITY
        assert history[0].data["key1"] == "value1"

    def test_data_management(self) -> None:
        """Test data get/set operations."""
        ctx = RuntimeContext(tenant_id="tenant-1")

        ctx.set_data("key1", "value1")
        ctx.set_data("key2", {"nested": "data"})

        assert ctx.get_data("key1") == "value1"
        assert ctx.get_data("key2") == {"nested": "data"}
        assert ctx.get_data("nonexistent", "default") == "default"

    def test_metadata_management(self) -> None:
        """Test metadata get/set operations."""
        ctx = RuntimeContext(tenant_id="tenant-1")

        ctx.set_metadata("user_id", "user-123")
        ctx.set_metadata("source", "api")

        assert ctx.get_metadata("user_id") == "user-123"
        assert ctx.get_metadata("source") == "api"
        assert ctx.get_metadata("nonexistent") is None

    def test_state_history_immutability(self) -> None:
        """Test that state history is immutable."""
        ctx = RuntimeContext(tenant_id="tenant-1")
        ctx.set_data("key1", "value1")
        ctx.advance_phase(RuntimePhase.INPUT)

        # Get history
        history1 = ctx.get_state_history()
        initial_len = len(history1)

        # Advance again
        ctx.advance_phase(RuntimePhase.CONTEXT)

        # Previous history reference should not change
        assert len(history1) == initial_len

        # New history should have more entries
        history2 = ctx.get_state_history()
        assert len(history2) == initial_len + 1

    def test_current_state_snapshot(self) -> None:
        """Test current state snapshot."""
        ctx = RuntimeContext(tenant_id="tenant-1")
        ctx.set_data("key1", "value1")
        ctx.set_metadata("meta1", "metavalue1")

        state = ctx.get_current_state()

        assert state.phase == RuntimePhase.IDENTITY
        assert state.data["key1"] == "value1"
        assert state.metadata["meta1"] == "metavalue1"

    def test_to_dict_serialization(self) -> None:
        """Test serialization to dictionary."""
        ctx = RuntimeContext(
            tenant_id="tenant-1",
            session_id="session-1",
            correlation_id="corr-1",
        )
        ctx.set_data("key1", "value1")
        ctx.advance_phase(RuntimePhase.INPUT)

        data = ctx.to_dict()

        assert data["tenant_id"] == "tenant-1"
        assert data["session_id"] == "session-1"
        assert data["correlation_id"] == "corr-1"
        assert data["current_phase"] == "input"
        assert data["data"]["key1"] == "value1"
        assert len(data["state_history"]) == 1

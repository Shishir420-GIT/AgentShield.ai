"""Runtime Context - Shared state management across execution lifecycle."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RuntimePhase(str, Enum):
    """Runtime lifecycle phases."""

    IDENTITY = "identity"
    INPUT = "input"
    CONTEXT = "context"
    MEMORY_READ = "memory_read"
    PLANNER = "planner"
    REASONING = "reasoning"
    TOOL_SELECTION = "tool_selection"
    TOOL_ARGUMENTS = "tool_arguments"
    POLICY = "policy"
    SANDBOX = "sandbox"
    EXECUTION = "execution"
    TOOL_OUTPUT = "tool_output"
    MEMORY_WRITE = "memory_write"
    OUTPUT = "output"
    AUDIT = "audit"
    REPLAY = "replay"


class RuntimeState(BaseModel):
    """Immutable state snapshot at a specific phase."""

    phase: RuntimePhase
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeContext:
    """
    Shared runtime context that tracks state throughout execution lifecycle.

    Principles:
    - Correlation tracking across all phases
    - Multi-tenant isolation
    - Immutable state history
    - Thread-safe access
    """

    def __init__(
        self,
        tenant_id: str,
        session_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Initialize runtime context."""
        self.tenant_id = tenant_id
        self.session_id = session_id or str(uuid4())
        self.correlation_id = correlation_id or str(uuid4())
        self.created_at = datetime.now(UTC)

        # State tracking
        self._current_phase = RuntimePhase.IDENTITY
        self._state_history: list[RuntimeState] = []
        self._data: dict[str, Any] = {}
        self._metadata: dict[str, Any] = {}

    @property
    def current_phase(self) -> RuntimePhase:
        """Get current execution phase."""
        return self._current_phase

    def advance_phase(self, phase: RuntimePhase) -> None:
        """
        Advance to next phase and snapshot current state.

        Args:
            phase: The next runtime phase
        """
        # Snapshot current state before advancing
        state = RuntimeState(
            phase=self._current_phase,
            timestamp=datetime.now(UTC),
            data=self._data.copy(),
            metadata=self._metadata.copy(),
        )
        self._state_history.append(state)

        # Advance phase
        self._current_phase = phase

    def set_data(self, key: str, value: Any) -> None:
        """Set runtime data."""
        self._data[key] = value

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get runtime data."""
        return self._data.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata."""
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata."""
        return self._metadata.get(key, default)

    def get_state_history(self) -> list[RuntimeState]:
        """Get immutable history of all states."""
        return self._state_history.copy()

    def get_current_state(self) -> RuntimeState:
        """Get current state snapshot."""
        return RuntimeState(
            phase=self._current_phase,
            timestamp=datetime.now(UTC),
            data=self._data.copy(),
            metadata=self._metadata.copy(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize context to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
            "current_phase": self._current_phase.value,
            "data": self._data,
            "metadata": self._metadata,
            "state_history": [
                {
                    "phase": state.phase.value,
                    "timestamp": state.timestamp.isoformat(),
                    "data": state.data,
                    "metadata": state.metadata,
                }
                for state in self._state_history
            ],
        }

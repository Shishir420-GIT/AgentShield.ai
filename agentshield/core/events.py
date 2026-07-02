"""Event Bus - Event-driven communication with correlation tracking."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Core event types across runtime lifecycle."""

    PROMPT_RECEIVED = "prompt_received"
    CONTEXT_VALIDATED = "context_validated"
    PLANNER_VALIDATED = "planner_validated"
    TOOL_AUTHORIZED = "tool_authorized"
    TOOL_EXECUTED = "tool_executed"
    OUTPUT_VALIDATED = "output_validated"
    MEMORY_UPDATED = "memory_updated"
    INCIDENT_CREATED = "incident_created"
    SESSION_CLOSED = "session_closed"

    # Additional runtime events
    POLICY_EVALUATED = "policy_evaluated"
    POLICY_BLOCKED = "policy_blocked"
    ORCHESTRATOR_STARTED = "orchestrator_started"
    ORCHESTRATOR_COMPLETED = "orchestrator_completed"
    AUDIT_LOGGED = "audit_logged"


class Event(BaseModel):
    """
    Immutable event with correlation tracking.

    Every event includes:
    - correlation_id: Tracks related events across execution
    - tenant_id: Multi-tenant isolation
    - session_id: Groups events within a session
    - timestamp: Event time
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    correlation_id: str
    tenant_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]


class EventBus:
    """
    Async event bus for pub/sub communication.

    Features:
    - Topic-based subscription
    - Async handler execution
    - Error isolation (handler failures don't affect other handlers)
    - Event ordering within tenant/session
    """

    def __init__(self) -> None:
        """Initialize event bus."""
        self._handlers: dict[EventType, list[AsyncEventHandler]] = {}
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._processing_task: asyncio.Task[None] | None = None
        self._running = False

    def subscribe(self, event_type: EventType, handler: AsyncEventHandler) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: The event type to listen for
            handler: Async callback function
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: AsyncEventHandler) -> None:
        """
        Unsubscribe from events.

        Args:
            event_type: The event type
            handler: Handler to remove
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def publish(self, event: Event) -> None:
        """
        Publish event to all subscribers.

        Args:
            event: The event to publish
        """
        await self._event_queue.put(event)

    async def start(self) -> None:
        """Start event processing loop."""
        if self._running:
            return

        self._running = True
        self._processing_task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        """Stop event processing loop."""
        self._running = False
        if self._processing_task:
            await self._event_queue.join()
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

    async def _process_events(self) -> None:
        """Internal event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._dispatch_event(event)
                self._event_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing event: {e}")

    async def _dispatch_event(self, event: Event) -> None:
        """
        Dispatch event to all handlers.

        Args:
            event: The event to dispatch
        """
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return

        # Execute all handlers concurrently
        tasks = []
        for handler in handlers:
            try:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                # Handler creation failed - log but continue
                print(f"Error creating handler task: {e}")

        # Wait for all handlers to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any handler errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"Handler {i} failed: {result}")

    def get_subscriber_count(self, event_type: EventType) -> int:
        """Get number of subscribers for an event type."""
        return len(self._handlers.get(event_type, []))

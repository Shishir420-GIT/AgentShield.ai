"""Unit tests for EventBus."""

import asyncio

import pytest

from agentshield.core.events import Event, EventBus, EventType


class TestEvent:
    """Test Event model."""

    def test_event_creation(self) -> None:
        """Test event creation with required fields."""
        event = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )

        assert event.event_id is not None
        assert event.event_type == EventType.PROMPT_RECEIVED
        assert event.correlation_id == "corr-1"
        assert event.tenant_id == "tenant-1"
        assert event.timestamp is not None

    def test_event_with_payload(self) -> None:
        """Test event with payload data."""
        payload = {"prompt": "test prompt", "user_id": "user-123"}

        event = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
            payload=payload,
        )

        assert event.payload["prompt"] == "test prompt"
        assert event.payload["user_id"] == "user-123"

    def test_event_immutability(self) -> None:
        """Test that events are immutable."""
        event = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )

        with pytest.raises(Exception):  # Pydantic will raise ValidationError
            event.correlation_id = "new-corr"  # type: ignore


class TestEventBus:
    """Test EventBus functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self) -> None:
        """Test basic subscribe and publish."""
        bus = EventBus()
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        bus.subscribe(EventType.PROMPT_RECEIVED, handler)
        await bus.start()

        # Publish event
        event = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )
        await bus.publish(event)

        # Wait for processing
        await asyncio.sleep(0.1)
        await bus.stop()

        assert len(received_events) == 1
        assert received_events[0].event_id == event.event_id

    @pytest.mark.asyncio
    async def test_multiple_handlers(self) -> None:
        """Test multiple handlers for same event type."""
        bus = EventBus()
        handler1_called = False
        handler2_called = False

        async def handler1(event: Event) -> None:
            nonlocal handler1_called
            handler1_called = True

        async def handler2(event: Event) -> None:
            nonlocal handler2_called
            handler2_called = True

        bus.subscribe(EventType.PROMPT_RECEIVED, handler1)
        bus.subscribe(EventType.PROMPT_RECEIVED, handler2)
        await bus.start()

        event = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )
        await bus.publish(event)

        await asyncio.sleep(0.1)
        await bus.stop()

        assert handler1_called
        assert handler2_called

    @pytest.mark.asyncio
    async def test_handler_error_isolation(self) -> None:
        """Test that handler errors don't affect other handlers."""
        bus = EventBus()
        successful_handler_called = False

        async def failing_handler(event: Event) -> None:
            raise ValueError("Handler error")

        async def successful_handler(event: Event) -> None:
            nonlocal successful_handler_called
            successful_handler_called = True

        bus.subscribe(EventType.PROMPT_RECEIVED, failing_handler)
        bus.subscribe(EventType.PROMPT_RECEIVED, successful_handler)
        await bus.start()

        event = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )
        await bus.publish(event)

        await asyncio.sleep(0.1)
        await bus.stop()

        # Successful handler should still be called despite other handler failing
        assert successful_handler_called

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        """Test unsubscribing from events."""
        bus = EventBus()
        handler_call_count = 0

        async def handler(event: Event) -> None:
            nonlocal handler_call_count
            handler_call_count += 1

        bus.subscribe(EventType.PROMPT_RECEIVED, handler)
        await bus.start()

        # Publish first event
        event1 = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )
        await bus.publish(event1)
        await asyncio.sleep(0.1)

        # Unsubscribe
        bus.unsubscribe(EventType.PROMPT_RECEIVED, handler)

        # Publish second event
        event2 = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-2",
            tenant_id="tenant-1",
            session_id="session-1",
        )
        await bus.publish(event2)
        await asyncio.sleep(0.1)

        await bus.stop()

        # Handler should only be called once
        assert handler_call_count == 1

    @pytest.mark.asyncio
    async def test_event_type_filtering(self) -> None:
        """Test that handlers only receive subscribed event types."""
        bus = EventBus()
        prompt_received = False
        context_validated = False

        async def prompt_handler(event: Event) -> None:
            nonlocal prompt_received
            prompt_received = True

        async def context_handler(event: Event) -> None:
            nonlocal context_validated
            context_validated = True

        bus.subscribe(EventType.PROMPT_RECEIVED, prompt_handler)
        bus.subscribe(EventType.CONTEXT_VALIDATED, context_handler)
        await bus.start()

        # Publish only PROMPT_RECEIVED
        event = Event(
            event_type=EventType.PROMPT_RECEIVED,
            correlation_id="corr-1",
            tenant_id="tenant-1",
            session_id="session-1",
        )
        await bus.publish(event)

        await asyncio.sleep(0.1)
        await bus.stop()

        assert prompt_received
        assert not context_validated

    @pytest.mark.asyncio
    async def test_subscriber_count(self) -> None:
        """Test getting subscriber count."""
        bus = EventBus()

        async def handler1(event: Event) -> None:
            pass

        async def handler2(event: Event) -> None:
            pass

        assert bus.get_subscriber_count(EventType.PROMPT_RECEIVED) == 0

        bus.subscribe(EventType.PROMPT_RECEIVED, handler1)
        assert bus.get_subscriber_count(EventType.PROMPT_RECEIVED) == 1

        bus.subscribe(EventType.PROMPT_RECEIVED, handler2)
        assert bus.get_subscriber_count(EventType.PROMPT_RECEIVED) == 2

        bus.unsubscribe(EventType.PROMPT_RECEIVED, handler1)
        assert bus.get_subscriber_count(EventType.PROMPT_RECEIVED) == 1

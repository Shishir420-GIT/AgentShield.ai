"""Shared test fixtures."""

import asyncio

import pytest
from prometheus_client import CollectorRegistry

from agentshield.core.events import EventBus
from agentshield.core.tool_sdk import ToolRegistry


class MockMetricsCollector:
    """Mock metrics collector for tests to avoid Prometheus registry conflicts."""

    def record_request(self, tenant_id: str, phase: str) -> None:
        pass

    def record_request_duration(
        self, tenant_id: str, phase: str, duration: float
    ) -> None:
        pass

    def record_policy_decision(self, tenant_id: str, decision: str) -> None:
        pass

    def record_tool_execution(
        self, tenant_id: str, tool_id: str, category: str
    ) -> None:
        pass

    def record_tool_duration(
        self, tenant_id: str, tool_id: str, duration: float
    ) -> None:
        pass

    def record_incident(self, tenant_id: str, severity: str) -> None:
        pass

    def record_blocked_action(self, tenant_id: str, reason: str) -> None:
        pass

    def set_active_sessions(self, tenant_id: str, count: int) -> None:
        pass


@pytest.fixture
async def event_bus() -> EventBus:
    """Create and manage event bus for tests."""
    bus = EventBus()
    await bus.start()
    yield bus
    # Ensure proper cleanup
    await asyncio.sleep(0.01)  # Let pending events process
    await bus.stop()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """Create tool registry for tests."""
    return ToolRegistry()


@pytest.fixture
def metrics() -> MockMetricsCollector:
    """Create mock metrics collector for tests."""
    return MockMetricsCollector()

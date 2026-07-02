"""Unit tests for RuntimeOrchestrator."""

import asyncio

import pytest

from agentshield.core.context import RuntimeContext, RuntimePhase
from agentshield.core.events import EventBus
from agentshield.core.metrics import MetricsCollector
from agentshield.core.tool_sdk import (
    Recommendation,
    RuntimeTool,
    Severity,
    ToolCategory,
    ToolEvidence,
    ToolMetadata,
    ToolPriority,
    ToolRegistry,
    ToolResult,
)
from agentshield.orchestrator import RuntimeOrchestrator


class MockInputValidationTool(RuntimeTool):
    """Mock input validation tool."""

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """Execute mock validation."""
        evidence = ToolEvidence(
            source=self.metadata.id,
            findings={"validated": True},
        )

        return ToolResult(
            tool_id=self.metadata.id,
            evidence=evidence,
            confidence=0.95,
            severity=Severity.INFO,
            recommendation=Recommendation.ALLOW,
        )


class MockMaliciousTool(RuntimeTool):
    """Mock tool that detects malicious content."""

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """Execute mock detection."""
        evidence = ToolEvidence(
            source=self.metadata.id,
            findings={"threat_detected": True, "threat_type": "injection"},
            indicators=["eval()", "exec()"],
        )

        return ToolResult(
            tool_id=self.metadata.id,
            evidence=evidence,
            confidence=0.9,
            severity=Severity.HIGH,
            recommendation=Recommendation.BLOCK,
        )


class TestRuntimeOrchestrator:
    """Test RuntimeOrchestrator functionality."""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self) -> None:
        """Test orchestrator initialization."""
        registry = ToolRegistry()
        bus = EventBus()
        metrics = MetricsCollector()

        orchestrator = RuntimeOrchestrator(registry, bus, metrics)

        assert orchestrator.tool_registry == registry
        assert orchestrator.event_bus == bus
        assert orchestrator.metrics == metrics

    @pytest.mark.asyncio
    async def test_analyze_with_no_tools(
        self, event_bus: EventBus, tool_registry: ToolRegistry, metrics: MetricsCollector
    ) -> None:
        """Test analysis with no tools registered."""
        orchestrator = RuntimeOrchestrator(tool_registry, event_bus, metrics)

        context = RuntimeContext(tenant_id="tenant-1")
        context.advance_phase(RuntimePhase.INPUT)

        result = await orchestrator.analyze(context)
        await asyncio.sleep(0.01)  # Let events process

        assert result.final_recommendation == Recommendation.ALLOW
        assert result.final_severity == Severity.INFO
        assert len(result.tool_results) == 0

    @pytest.mark.asyncio
    async def test_analyze_with_passing_tool(
        self, event_bus: EventBus, tool_registry: ToolRegistry, metrics: MetricsCollector
    ) -> None:
        """Test analysis with tool that passes."""
        # Register passing tool
        tool_meta = ToolMetadata(
            id="input-validator",
            version="1.0.0",
            name="Input Validator",
            description="Validates input",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.HIGH,
        )
        tool = MockInputValidationTool(tool_meta)
        tool_registry.register(tool)

        orchestrator = RuntimeOrchestrator(tool_registry, event_bus, metrics)

        context = RuntimeContext(tenant_id="tenant-1")
        context.advance_phase(RuntimePhase.INPUT)

        result = await orchestrator.analyze(context)
        await asyncio.sleep(0.01)

        assert result.final_recommendation == Recommendation.ALLOW
        assert len(result.tool_results) == 1
        assert result.tool_results[0].tool_id == "input-validator"

    @pytest.mark.asyncio
    async def test_analyze_with_blocking_tool(
        self, event_bus: EventBus, tool_registry: ToolRegistry, metrics: MetricsCollector
    ) -> None:
        """Test analysis with tool that blocks."""
        # Register blocking tool
        tool_meta = ToolMetadata(
            id="malicious-detector",
            version="1.0.0",
            name="Malicious Content Detector",
            description="Detects malicious content",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.CRITICAL,
        )
        tool = MockMaliciousTool(tool_meta)
        tool_registry.register(tool)

        orchestrator = RuntimeOrchestrator(tool_registry, event_bus, metrics)

        context = RuntimeContext(tenant_id="tenant-1")
        context.advance_phase(RuntimePhase.INPUT)

        result = await orchestrator.analyze(context)
        await asyncio.sleep(0.01)

        assert result.final_recommendation == Recommendation.BLOCK
        assert result.final_severity == Severity.HIGH
        assert len(result.tool_results) == 1

    @pytest.mark.asyncio
    async def test_analyze_with_multiple_tools(
        self, event_bus: EventBus, tool_registry: ToolRegistry, metrics: MetricsCollector
    ) -> None:
        """Test analysis with multiple tools."""
        # Register multiple tools
        tool1_meta = ToolMetadata(
            id="validator-1",
            version="1.0.0",
            name="Validator 1",
            description="First validator",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.HIGH,
        )
        tool1 = MockInputValidationTool(tool1_meta)
        tool_registry.register(tool1)

        tool2_meta = ToolMetadata(
            id="detector-1",
            version="1.0.0",
            name="Detector 1",
            description="Malicious detector",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.CRITICAL,
        )
        tool2 = MockMaliciousTool(tool2_meta)
        tool_registry.register(tool2)

        orchestrator = RuntimeOrchestrator(tool_registry, event_bus, metrics)

        context = RuntimeContext(tenant_id="tenant-1")
        context.advance_phase(RuntimePhase.INPUT)

        result = await orchestrator.analyze(context)
        await asyncio.sleep(0.01)

        # Should block because one tool recommends blocking
        assert result.final_recommendation == Recommendation.BLOCK
        assert len(result.tool_results) == 2

    @pytest.mark.asyncio
    async def test_tool_priority_ordering(
        self, event_bus: EventBus, tool_registry: ToolRegistry, metrics: MetricsCollector
    ) -> None:
        """Test that tools execute in priority order."""
        # Register tools with different priorities
        tool1_meta = ToolMetadata(
            id="low-priority",
            version="1.0.0",
            name="Low Priority Tool",
            description="Low priority",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.LOW,
        )
        tool1 = MockInputValidationTool(tool1_meta)
        tool_registry.register(tool1)

        tool2_meta = ToolMetadata(
            id="high-priority",
            version="1.0.0",
            name="High Priority Tool",
            description="High priority",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.CRITICAL,
        )
        tool2 = MockInputValidationTool(tool2_meta)
        tool_registry.register(tool2)

        orchestrator = RuntimeOrchestrator(tool_registry, event_bus, metrics)

        context = RuntimeContext(tenant_id="tenant-1")
        context.advance_phase(RuntimePhase.INPUT)

        result = await orchestrator.analyze(context)
        await asyncio.sleep(0.01)

        # High priority tool should execute first
        assert result.tool_results[0].tool_id == "high-priority"
        assert result.tool_results[1].tool_id == "low-priority"

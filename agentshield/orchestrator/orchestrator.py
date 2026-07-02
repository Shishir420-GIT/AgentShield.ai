"""
Runtime Prevention Orchestrator.

The orchestrator is a base agent that:
- Analyzes requests dynamically
- Selects appropriate security tools
- Builds investigation plans
- Executes tools and correlates evidence
- Produces recommendations for the policy engine
- NEVER directly enforces security decisions
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from agentshield.core.context import RuntimeContext, RuntimePhase
from agentshield.core.events import Event, EventBus, EventType
from agentshield.core.metrics import MetricsCollector
from agentshield.core.tool_sdk import (
    Recommendation,
    RuntimeTool,
    Severity,
    ToolCategory,
    ToolRegistry,
    ToolResult,
)


class InvestigationPlan:
    """Plan for investigating a security request."""

    def __init__(self, context: RuntimeContext) -> None:
        """Initialize investigation plan."""
        self.context = context
        self.selected_tools: list[RuntimeTool] = []
        self.execution_order: list[str] = []
        self.created_at = datetime.now(UTC)

    def add_tool(self, tool: RuntimeTool, priority: int = 0) -> None:
        """Add tool to investigation plan."""
        self.selected_tools.append(tool)
        self.execution_order.append(tool.metadata.id)

    def get_tools(self) -> list[RuntimeTool]:
        """Get tools in execution order."""
        # Sort by priority (lower number = higher priority)
        return sorted(self.selected_tools, key=lambda t: t.metadata.priority.value)


class OrchestratorRecommendation:
    """Final recommendation from orchestrator based on correlated evidence."""

    def __init__(
        self,
        context: RuntimeContext,
        tool_results: list[ToolResult],
        final_recommendation: Recommendation,
        final_severity: Severity,
        confidence: float,
        reasoning: str,
    ) -> None:
        """Initialize orchestrator recommendation."""
        self.context = context
        self.tool_results = tool_results
        self.final_recommendation = final_recommendation
        self.final_severity = final_severity
        self.confidence = confidence
        self.reasoning = reasoning
        self.timestamp = datetime.now(UTC)


class RuntimeOrchestrator:
    """
    Agentic Runtime Prevention Orchestrator.

    Responsibilities:
    1. Analyze incoming requests
    2. Dynamically select appropriate security tools
    3. Build investigation plans
    4. Execute tools in optimal order
    5. Correlate evidence across tools
    6. Produce unified recommendation

    Critical: Never directly enforces - only recommends.
    The deterministic policy engine makes final decisions.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        event_bus: EventBus,
        metrics: MetricsCollector,
    ) -> None:
        """Initialize runtime orchestrator."""
        self.tool_registry = tool_registry
        self.event_bus = event_bus
        self.metrics = metrics

    async def analyze(self, context: RuntimeContext) -> OrchestratorRecommendation:
        """
        Analyze request and produce recommendation.

        Args:
            context: Runtime context with request data

        Returns:
            Unified recommendation based on correlated evidence
        """
        start_time = datetime.now(UTC)

        # Emit orchestrator started event
        await self.event_bus.publish(
            Event(
                event_type=EventType.ORCHESTRATOR_STARTED,
                correlation_id=context.correlation_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                payload={"phase": context.current_phase.value},
            )
        )

        # Step 1: Build investigation plan
        plan = await self._build_investigation_plan(context)

        # Step 2: Execute tools
        tool_results = await self._execute_tools(plan, context)

        # Step 3: Correlate evidence
        recommendation = await self._correlate_evidence(context, tool_results)

        # Emit completion event
        duration = (datetime.now(UTC) - start_time).total_seconds()
        await self.event_bus.publish(
            Event(
                event_type=EventType.ORCHESTRATOR_COMPLETED,
                correlation_id=context.correlation_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                payload={
                    "duration_seconds": duration,
                    "tools_executed": len(tool_results),
                    "recommendation": recommendation.final_recommendation.value,
                    "severity": recommendation.final_severity.value,
                },
            )
        )

        # Record metrics
        self.metrics.record_request_duration(
            context.tenant_id, context.current_phase.value, duration
        )

        return recommendation

    async def _build_investigation_plan(
        self, context: RuntimeContext
    ) -> InvestigationPlan:
        """
        Dynamically build investigation plan based on context.

        Args:
            context: Runtime context

        Returns:
            Investigation plan with selected tools
        """
        plan = InvestigationPlan(context)

        # Select tools based on current phase
        phase = context.current_phase
        category_map = {
            RuntimePhase.IDENTITY: ToolCategory.IDENTITY,
            RuntimePhase.INPUT: ToolCategory.INPUT_VALIDATION,
            RuntimePhase.CONTEXT: ToolCategory.CONTEXT_SECURITY,
            RuntimePhase.MEMORY_READ: ToolCategory.MEMORY_SECURITY,
            RuntimePhase.PLANNER: ToolCategory.PLANNER_SECURITY,
            RuntimePhase.REASONING: ToolCategory.REASONING_SECURITY,
            RuntimePhase.TOOL_SELECTION: ToolCategory.TOOL_SECURITY,
            RuntimePhase.TOOL_ARGUMENTS: ToolCategory.TOOL_SECURITY,
            RuntimePhase.EXECUTION: ToolCategory.EXECUTION_SECURITY,
            RuntimePhase.OUTPUT: ToolCategory.OUTPUT_SECURITY,
            RuntimePhase.AUDIT: ToolCategory.AUDIT,
        }

        category = category_map.get(phase)
        if category:
            # Get all enabled tools for this category
            tools = self.tool_registry.get_tools_by_category(category)
            for tool in tools:
                if tool.metadata.enabled and await tool.validate(context):
                    plan.add_tool(tool, tool.metadata.priority.value)

        # Add governance and observability tools (always run)
        governance_tools = self.tool_registry.get_tools_by_category(
            ToolCategory.GOVERNANCE
        )
        for tool in governance_tools:
            if tool.metadata.enabled:
                plan.add_tool(tool, tool.metadata.priority.value)

        return plan

    async def _execute_tools(
        self, plan: InvestigationPlan, context: RuntimeContext
    ) -> list[ToolResult]:
        """
        Execute tools in investigation plan.

        Args:
            plan: Investigation plan
            context: Runtime context

        Returns:
            List of tool results
        """
        results: list[ToolResult] = []
        tools = plan.get_tools()

        # Execute tools sequentially (could be parallelized for independent tools)
        for tool in tools:
            try:
                start_time = datetime.now(UTC)

                # Execute tool
                result = await tool.execute(context)
                results.append(result)

                # Record metrics
                duration = (datetime.now(UTC) - start_time).total_seconds()
                self.metrics.record_tool_execution(
                    context.tenant_id,
                    tool.metadata.id,
                    tool.metadata.category.value,
                )
                self.metrics.record_tool_duration(
                    context.tenant_id, tool.metadata.id, duration
                )

                # Emit tool executed event
                await self.event_bus.publish(
                    Event(
                        event_type=EventType.TOOL_EXECUTED,
                        correlation_id=context.correlation_id,
                        tenant_id=context.tenant_id,
                        session_id=context.session_id,
                        payload={
                            "tool_id": tool.metadata.id,
                            "tool_category": tool.metadata.category.value,
                            "recommendation": result.recommendation.value,
                            "severity": result.severity.value,
                            "confidence": result.confidence,
                            "duration_seconds": duration,
                        },
                    )
                )

            except Exception as e:
                # Log error but continue with other tools
                print(f"Error executing tool {tool.metadata.id}: {e}")
                continue

        return results

    async def _correlate_evidence(
        self, context: RuntimeContext, tool_results: list[ToolResult]
    ) -> OrchestratorRecommendation:
        """
        Correlate evidence from multiple tools to produce unified recommendation.

        Args:
            context: Runtime context
            tool_results: Results from all executed tools

        Returns:
            Unified recommendation
        """
        if not tool_results:
            # No tools executed - default to allow
            return OrchestratorRecommendation(
                context=context,
                tool_results=[],
                final_recommendation=Recommendation.ALLOW,
                final_severity=Severity.INFO,
                confidence=1.0,
                reasoning="No security tools executed - default allow",
            )

        # Aggregate recommendations
        block_count = sum(
            1 for r in tool_results if r.recommendation == Recommendation.BLOCK
        )
        warn_count = sum(
            1 for r in tool_results if r.recommendation == Recommendation.WARN
        )

        # Find highest severity
        severity_order = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
            Severity.INFO,
        ]
        highest_severity = Severity.INFO
        for severity in severity_order:
            if any(r.severity == severity for r in tool_results):
                highest_severity = severity
                break

        # Calculate aggregate confidence
        if tool_results:
            avg_confidence = sum(r.confidence for r in tool_results) / len(tool_results)
        else:
            avg_confidence = 0.0

        # Determine final recommendation
        if block_count > 0:
            final_rec = Recommendation.BLOCK
            reasoning = f"{block_count} tool(s) recommended blocking"
        elif warn_count > 0:
            final_rec = Recommendation.WARN
            reasoning = f"{warn_count} tool(s) raised warnings"
        else:
            final_rec = Recommendation.ALLOW
            reasoning = "All tools passed security checks"

        return OrchestratorRecommendation(
            context=context,
            tool_results=tool_results,
            final_recommendation=final_rec,
            final_severity=highest_severity,
            confidence=avg_confidence,
            reasoning=reasoning,
        )

"""Metrics and observability for the runtime platform."""

from datetime import datetime
from typing import Any

from prometheus_client import Counter, Histogram, Gauge


class MetricsCollector:
    """
    Centralized metrics collection for observability.

    Tracks:
    - Request counts and latencies
    - Policy decisions
    - Tool executions
    - Security incidents
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        # Request metrics
        self.requests_total = Counter(
            "agentshield_requests_total",
            "Total requests processed",
            ["tenant_id", "phase"],
        )

        self.request_duration_seconds = Histogram(
            "agentshield_request_duration_seconds",
            "Request duration in seconds",
            ["tenant_id", "phase"],
        )

        # Policy metrics
        self.policy_decisions_total = Counter(
            "agentshield_policy_decisions_total",
            "Total policy decisions",
            ["tenant_id", "decision"],
        )

        # Tool metrics
        self.tool_executions_total = Counter(
            "agentshield_tool_executions_total",
            "Total tool executions",
            ["tenant_id", "tool_id", "category"],
        )

        self.tool_duration_seconds = Histogram(
            "agentshield_tool_duration_seconds",
            "Tool execution duration",
            ["tenant_id", "tool_id"],
        )

        # Security metrics
        self.incidents_total = Counter(
            "agentshield_incidents_total",
            "Total security incidents",
            ["tenant_id", "severity"],
        )

        self.blocked_actions_total = Counter(
            "agentshield_blocked_actions_total",
            "Total blocked actions",
            ["tenant_id", "reason"],
        )

        # System metrics
        self.active_sessions = Gauge(
            "agentshield_active_sessions",
            "Number of active sessions",
            ["tenant_id"],
        )

    def record_request(self, tenant_id: str, phase: str) -> None:
        """Record request processed."""
        self.requests_total.labels(tenant_id=tenant_id, phase=phase).inc()

    def record_request_duration(
        self, tenant_id: str, phase: str, duration: float
    ) -> None:
        """Record request duration."""
        self.request_duration_seconds.labels(tenant_id=tenant_id, phase=phase).observe(
            duration
        )

    def record_policy_decision(self, tenant_id: str, decision: str) -> None:
        """Record policy decision."""
        self.policy_decisions_total.labels(tenant_id=tenant_id, decision=decision).inc()

    def record_tool_execution(
        self, tenant_id: str, tool_id: str, category: str
    ) -> None:
        """Record tool execution."""
        self.tool_executions_total.labels(
            tenant_id=tenant_id, tool_id=tool_id, category=category
        ).inc()

    def record_tool_duration(
        self, tenant_id: str, tool_id: str, duration: float
    ) -> None:
        """Record tool execution duration."""
        self.tool_duration_seconds.labels(tenant_id=tenant_id, tool_id=tool_id).observe(
            duration
        )

    def record_incident(self, tenant_id: str, severity: str) -> None:
        """Record security incident."""
        self.incidents_total.labels(tenant_id=tenant_id, severity=severity).inc()

    def record_blocked_action(self, tenant_id: str, reason: str) -> None:
        """Record blocked action."""
        self.blocked_actions_total.labels(tenant_id=tenant_id, reason=reason).inc()

    def set_active_sessions(self, tenant_id: str, count: int) -> None:
        """Set active session count."""
        self.active_sessions.labels(tenant_id=tenant_id).set(count)

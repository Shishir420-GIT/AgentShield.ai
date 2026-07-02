"""
Deterministic Policy Engine.

The policy engine:
- Receives recommendations from the orchestrator
- Applies deterministic policy rules
- Makes final enforcement decisions (ALLOW/BLOCK)
- Never uses AI/ML - purely rule-based
- Ensures consistent, auditable decisions
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from agentshield.core.context import RuntimeContext
from agentshield.core.events import Event, EventBus, EventType
from agentshield.core.metrics import MetricsCollector
from agentshield.core.tool_sdk import Recommendation, Severity
from agentshield.orchestrator.orchestrator import OrchestratorRecommendation


class PolicyAction(str, Enum):
    """Final enforcement actions."""

    ALLOW = "allow"
    BLOCK = "block"
    AUDIT = "audit"  # Allow but log for review


class PolicyRule(BaseModel):
    """Deterministic policy rule."""

    rule_id: str
    name: str
    description: str
    enabled: bool = True

    # Conditions
    min_severity: Severity | None = None
    max_severity: Severity | None = None
    min_confidence: float | None = None
    recommendations: list[Recommendation] | None = None
    tenant_ids: list[str] | None = None  # Tenant-specific rules

    # Action
    action: PolicyAction

    def matches(
        self,
        context: RuntimeContext,
        recommendation: OrchestratorRecommendation,
    ) -> bool:
        """
        Check if rule matches current context and recommendation.

        Args:
            context: Runtime context
            recommendation: Orchestrator recommendation

        Returns:
            True if rule matches
        """
        if not self.enabled:
            return False

        # Check tenant
        if self.tenant_ids and context.tenant_id not in self.tenant_ids:
            return False

        # Check severity
        severity_order = {
            Severity.CRITICAL: 5,
            Severity.HIGH: 4,
            Severity.MEDIUM: 3,
            Severity.LOW: 2,
            Severity.INFO: 1,
        }

        current_severity = severity_order.get(recommendation.final_severity, 0)

        if self.min_severity:
            min_sev = severity_order.get(self.min_severity, 0)
            if current_severity < min_sev:
                return False

        if self.max_severity:
            max_sev = severity_order.get(self.max_severity, 0)
            if current_severity > max_sev:
                return False

        # Check confidence
        if (
            self.min_confidence is not None
            and recommendation.confidence < self.min_confidence
        ):
            return False

        # Check recommendation
        if (
            self.recommendations
            and recommendation.final_recommendation not in self.recommendations
        ):
            return False

        return True


class PolicyDecision(BaseModel):
    """Final policy decision with rationale."""

    action: PolicyAction
    matched_rules: list[str]  # IDs of matched rules
    reasoning: str
    timestamp: datetime
    orchestrator_recommendation: Recommendation
    orchestrator_severity: Severity
    orchestrator_confidence: float


class PolicyEngine:
    """
    Deterministic Policy Engine.

    Makes final enforcement decisions based on:
    - Orchestrator recommendations
    - Configured policy rules
    - Tenant-specific policies

    Purely rule-based - no AI/ML for deterministic behavior.
    """

    def __init__(
        self,
        event_bus: EventBus,
        metrics: MetricsCollector,
    ) -> None:
        """Initialize policy engine."""
        self.event_bus = event_bus
        self.metrics = metrics
        self._rules: list[PolicyRule] = []

        # Install default rules
        self._install_default_rules()

    def add_rule(self, rule: PolicyRule) -> None:
        """
        Add policy rule.

        Args:
            rule: Policy rule to add
        """
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> None:
        """Remove policy rule."""
        self._rules = [r for r in self._rules if r.rule_id != rule_id]

    def get_rules(self) -> list[PolicyRule]:
        """Get all policy rules."""
        return self._rules.copy()

    async def evaluate(
        self,
        context: RuntimeContext,
        recommendation: OrchestratorRecommendation,
    ) -> PolicyDecision:
        """
        Evaluate orchestrator recommendation and make final decision.

        Args:
            context: Runtime context
            recommendation: Orchestrator recommendation

        Returns:
            Final policy decision
        """
        # Find matching rules (in order)
        matched_rules: list[PolicyRule] = []
        for rule in self._rules:
            if rule.matches(context, recommendation):
                matched_rules.append(rule)

        # Apply first matching rule (priority order)
        if matched_rules:
            first_rule = matched_rules[0]
            action = first_rule.action
            reasoning = f"Matched rule: {first_rule.name}"
            matched_rule_ids = [r.rule_id for r in matched_rules]
        else:
            # No rules matched - default to orchestrator recommendation
            if recommendation.final_recommendation == Recommendation.BLOCK:
                action = PolicyAction.BLOCK
                reasoning = "Default: Block based on orchestrator recommendation"
            else:
                action = PolicyAction.ALLOW
                reasoning = "Default: Allow - no blocking rules matched"
            matched_rule_ids = []

        decision = PolicyDecision(
            action=action,
            matched_rules=matched_rule_ids,
            reasoning=reasoning,
            timestamp=datetime.now(UTC),
            orchestrator_recommendation=recommendation.final_recommendation,
            orchestrator_severity=recommendation.final_severity,
            orchestrator_confidence=recommendation.confidence,
        )

        # Emit policy evaluated event
        await self.event_bus.publish(
            Event(
                event_type=EventType.POLICY_EVALUATED,
                correlation_id=context.correlation_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                payload={
                    "action": decision.action.value,
                    "matched_rules": decision.matched_rules,
                    "reasoning": decision.reasoning,
                    "orchestrator_recommendation": decision.orchestrator_recommendation.value,
                    "orchestrator_severity": decision.orchestrator_severity.value,
                },
            )
        )

        # Emit block event if blocked
        if action == PolicyAction.BLOCK:
            await self.event_bus.publish(
                Event(
                    event_type=EventType.POLICY_BLOCKED,
                    correlation_id=context.correlation_id,
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    payload={
                        "reasoning": decision.reasoning,
                        "severity": decision.orchestrator_severity.value,
                    },
                )
            )

            # Record incident
            self.metrics.record_incident(
                context.tenant_id, decision.orchestrator_severity.value
            )
            self.metrics.record_blocked_action(context.tenant_id, decision.reasoning)

        # Record policy decision
        self.metrics.record_policy_decision(context.tenant_id, decision.action.value)

        return decision

    def _install_default_rules(self) -> None:
        """Install default policy rules."""
        # Rule 1: Block all CRITICAL severity
        self.add_rule(
            PolicyRule(
                rule_id="default-block-critical",
                name="Block Critical Severity",
                description="Always block critical severity findings",
                min_severity=Severity.CRITICAL,
                action=PolicyAction.BLOCK,
            )
        )

        # Rule 2: Block HIGH severity with high confidence
        self.add_rule(
            PolicyRule(
                rule_id="default-block-high-confident",
                name="Block High Severity (High Confidence)",
                description="Block high severity with confidence > 0.8",
                min_severity=Severity.HIGH,
                max_severity=Severity.HIGH,
                min_confidence=0.8,
                action=PolicyAction.BLOCK,
            )
        )

        # Rule 3: Audit HIGH severity with lower confidence
        self.add_rule(
            PolicyRule(
                rule_id="default-audit-high-uncertain",
                name="Audit High Severity (Low Confidence)",
                description="Audit high severity with confidence <= 0.8",
                min_severity=Severity.HIGH,
                max_severity=Severity.HIGH,
                action=PolicyAction.AUDIT,
            )
        )

        # Rule 4: Block on orchestrator BLOCK recommendation
        self.add_rule(
            PolicyRule(
                rule_id="default-block-on-recommendation",
                name="Block on Orchestrator Recommendation",
                description="Block when orchestrator recommends blocking",
                recommendations=[Recommendation.BLOCK],
                action=PolicyAction.BLOCK,
            )
        )

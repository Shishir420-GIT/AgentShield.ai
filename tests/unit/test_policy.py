"""Unit tests for Policy Engine."""

import pytest

from agentshield.core.context import RuntimeContext
from agentshield.core.events import EventBus
from agentshield.core.metrics import MetricsCollector
from agentshield.core.tool_sdk import Recommendation, Severity
from agentshield.orchestrator.orchestrator import OrchestratorRecommendation
from agentshield.policy import PolicyAction, PolicyEngine, PolicyRule


class TestPolicyRule:
    """Test PolicyRule model."""

    def test_rule_creation(self) -> None:
        """Test creating a policy rule."""
        rule = PolicyRule(
            rule_id="test-rule-1",
            name="Test Rule",
            description="A test rule",
            min_severity=Severity.HIGH,
            min_confidence=0.8,
            action=PolicyAction.BLOCK,
        )

        assert rule.rule_id == "test-rule-1"
        assert rule.min_severity == Severity.HIGH
        assert rule.min_confidence == 0.8
        assert rule.action == PolicyAction.BLOCK
        assert rule.enabled is True

    def test_rule_matches_severity(self) -> None:
        """Test rule matching by severity."""
        rule = PolicyRule(
            rule_id="test-rule-1",
            name="Block High Severity",
            description="Block high severity",
            min_severity=Severity.HIGH,
            action=PolicyAction.BLOCK,
        )

        context = RuntimeContext(tenant_id="tenant-1")

        # Should match HIGH severity
        rec_high = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.HIGH,
            confidence=0.9,
            reasoning="Test",
        )
        assert rule.matches(context, rec_high) is True

        # Should not match LOW severity
        rec_low = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.LOW,
            confidence=0.9,
            reasoning="Test",
        )
        assert rule.matches(context, rec_low) is False

    def test_rule_matches_confidence(self) -> None:
        """Test rule matching by confidence."""
        rule = PolicyRule(
            rule_id="test-rule-1",
            name="High Confidence Rule",
            description="Requires high confidence",
            min_confidence=0.8,
            action=PolicyAction.BLOCK,
        )

        context = RuntimeContext(tenant_id="tenant-1")

        # Should match confidence >= 0.8
        rec_high = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.MEDIUM,
            confidence=0.9,
            reasoning="Test",
        )
        assert rule.matches(context, rec_high) is True

        # Should not match confidence < 0.8
        rec_low = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.MEDIUM,
            confidence=0.5,
            reasoning="Test",
        )
        assert rule.matches(context, rec_low) is False

    def test_rule_matches_recommendation(self) -> None:
        """Test rule matching by recommendation."""
        rule = PolicyRule(
            rule_id="test-rule-1",
            name="Block on Block Recommendation",
            description="Block when recommended",
            recommendations=[Recommendation.BLOCK],
            action=PolicyAction.BLOCK,
        )

        context = RuntimeContext(tenant_id="tenant-1")

        # Should match BLOCK recommendation
        rec_block = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.BLOCK,
            final_severity=Severity.MEDIUM,
            confidence=0.9,
            reasoning="Test",
        )
        assert rule.matches(context, rec_block) is True

        # Should not match ALLOW recommendation
        rec_allow = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.ALLOW,
            final_severity=Severity.MEDIUM,
            confidence=0.9,
            reasoning="Test",
        )
        assert rule.matches(context, rec_allow) is False

    def test_rule_matches_tenant(self) -> None:
        """Test rule matching by tenant."""
        rule = PolicyRule(
            rule_id="test-rule-1",
            name="Tenant-Specific Rule",
            description="Only for specific tenants",
            tenant_ids=["tenant-1", "tenant-2"],
            action=PolicyAction.BLOCK,
        )

        # Should match tenant-1
        context1 = RuntimeContext(tenant_id="tenant-1")
        rec = OrchestratorRecommendation(
            context=context1,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.MEDIUM,
            confidence=0.9,
            reasoning="Test",
        )
        assert rule.matches(context1, rec) is True

        # Should not match tenant-3
        context2 = RuntimeContext(tenant_id="tenant-3")
        rec2 = OrchestratorRecommendation(
            context=context2,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.MEDIUM,
            confidence=0.9,
            reasoning="Test",
        )
        assert rule.matches(context2, rec2) is False

    def test_disabled_rule_does_not_match(self) -> None:
        """Test that disabled rules don't match."""
        rule = PolicyRule(
            rule_id="test-rule-1",
            name="Disabled Rule",
            description="This rule is disabled",
            enabled=False,
            action=PolicyAction.BLOCK,
        )

        context = RuntimeContext(tenant_id="tenant-1")
        rec = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.BLOCK,
            final_severity=Severity.HIGH,
            confidence=0.9,
            reasoning="Test",
        )

        assert rule.matches(context, rec) is False


class TestPolicyEngine:
    """Test PolicyEngine functionality."""

    @pytest.mark.asyncio
    async def test_engine_initialization(self) -> None:
        """Test policy engine initialization."""
        bus = EventBus()
        metrics = MetricsCollector()
        engine = PolicyEngine(bus, metrics)

        # Should have default rules installed
        rules = engine.get_rules()
        assert len(rules) > 0

    @pytest.mark.asyncio
    async def test_add_remove_rules(self) -> None:
        """Test adding and removing rules."""
        bus = EventBus()
        metrics = MetricsCollector()
        engine = PolicyEngine(bus, metrics)

        initial_count = len(engine.get_rules())

        # Add rule
        rule = PolicyRule(
            rule_id="custom-rule-1",
            name="Custom Rule",
            description="Custom rule",
            action=PolicyAction.BLOCK,
        )
        engine.add_rule(rule)

        assert len(engine.get_rules()) == initial_count + 1

        # Remove rule
        engine.remove_rule("custom-rule-1")
        assert len(engine.get_rules()) == initial_count

    @pytest.mark.asyncio
    async def test_evaluate_critical_severity_blocks(self) -> None:
        """Test that critical severity is always blocked."""
        bus = EventBus()
        metrics = MetricsCollector()
        engine = PolicyEngine(bus, metrics)

        await bus.start()

        context = RuntimeContext(tenant_id="tenant-1")
        rec = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.CRITICAL,
            confidence=0.9,
            reasoning="Critical threat detected",
        )

        decision = await engine.evaluate(context, rec)

        await bus.stop()

        assert decision.action == PolicyAction.BLOCK
        assert "default-block-critical" in decision.matched_rules

    @pytest.mark.asyncio
    async def test_evaluate_high_severity_high_confidence_blocks(self) -> None:
        """Test that high severity with high confidence blocks."""
        bus = EventBus()
        metrics = MetricsCollector()
        engine = PolicyEngine(bus, metrics)

        await bus.start()

        context = RuntimeContext(tenant_id="tenant-1")
        rec = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.HIGH,
            confidence=0.95,
            reasoning="High confidence threat",
        )

        decision = await engine.evaluate(context, rec)

        await bus.stop()

        assert decision.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_evaluate_block_recommendation_blocks(self) -> None:
        """Test that BLOCK recommendation results in blocking."""
        bus = EventBus()
        metrics = MetricsCollector()
        engine = PolicyEngine(bus, metrics)

        await bus.start()

        context = RuntimeContext(tenant_id="tenant-1")
        rec = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.BLOCK,
            final_severity=Severity.MEDIUM,
            confidence=0.8,
            reasoning="Should block",
        )

        decision = await engine.evaluate(context, rec)

        await bus.stop()

        assert decision.action == PolicyAction.BLOCK

    @pytest.mark.asyncio
    async def test_evaluate_allow_recommendation_allows(self) -> None:
        """Test that ALLOW recommendation with low severity allows."""
        bus = EventBus()
        metrics = MetricsCollector()
        engine = PolicyEngine(bus, metrics)

        await bus.start()

        context = RuntimeContext(tenant_id="tenant-1")
        rec = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.ALLOW,
            final_severity=Severity.INFO,
            confidence=0.99,
            reasoning="All checks passed",
        )

        decision = await engine.evaluate(context, rec)

        await bus.stop()

        assert decision.action == PolicyAction.ALLOW

    @pytest.mark.asyncio
    async def test_custom_rule_priority(self) -> None:
        """Test that first matching rule is applied."""
        bus = EventBus()
        metrics = MetricsCollector()
        engine = PolicyEngine(bus, metrics)

        # Clear default rules
        for rule in engine.get_rules():
            engine.remove_rule(rule.rule_id)

        # Add rules in specific order
        rule1 = PolicyRule(
            rule_id="rule-1",
            name="Allow Rule",
            description="Allow everything",
            action=PolicyAction.ALLOW,
        )
        engine.add_rule(rule1)

        rule2 = PolicyRule(
            rule_id="rule-2",
            name="Block Rule",
            description="Block everything",
            action=PolicyAction.BLOCK,
        )
        engine.add_rule(rule2)

        await bus.start()

        context = RuntimeContext(tenant_id="tenant-1")
        rec = OrchestratorRecommendation(
            context=context,
            tool_results=[],
            final_recommendation=Recommendation.WARN,
            final_severity=Severity.MEDIUM,
            confidence=0.8,
            reasoning="Test",
        )

        decision = await engine.evaluate(context, rec)

        await bus.stop()

        # First rule (ALLOW) should match
        assert decision.action == PolicyAction.ALLOW
        assert decision.matched_rules[0] == "rule-1"

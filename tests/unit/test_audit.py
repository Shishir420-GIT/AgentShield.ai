"""Unit tests for Audit Logger."""

import tempfile
from pathlib import Path

import pytest

from agentshield.audit import AuditLogger
from agentshield.core.context import RuntimeContext, RuntimePhase
from agentshield.core.events import EventBus
from agentshield.core.tool_sdk import Recommendation, Severity
from agentshield.orchestrator.orchestrator import OrchestratorRecommendation
from agentshield.policy.engine import PolicyAction, PolicyDecision


class TestAuditLogger:
    """Test AuditLogger functionality."""

    @pytest.mark.asyncio
    async def test_logger_initialization(self) -> None:
        """Test audit logger initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus()
            logger = AuditLogger(bus, tmpdir)

            assert logger.audit_dir == Path(tmpdir)
            assert logger.audit_dir.exists()

    @pytest.mark.asyncio
    async def test_log_execution(self) -> None:
        """Test logging execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus()
            logger = AuditLogger(bus, tmpdir)

            await bus.start()

            # Create test data
            context = RuntimeContext(
                tenant_id="tenant-1",
                session_id="session-1",
                correlation_id="corr-1",
            )
            context.advance_phase(RuntimePhase.INPUT)
            context.set_data("prompt", "test prompt")

            recommendation = OrchestratorRecommendation(
                context=context,
                tool_results=[],
                final_recommendation=Recommendation.ALLOW,
                final_severity=Severity.INFO,
                confidence=0.95,
                reasoning="All checks passed",
            )

            decision = PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rules=["default-allow"],
                reasoning="Default allow",
                timestamp=context.created_at,
                orchestrator_recommendation=Recommendation.ALLOW,
                orchestrator_severity=Severity.INFO,
                orchestrator_confidence=0.95,
            )

            # Log execution
            record = await logger.log_execution(context, recommendation, decision)

            await bus.stop()

            # Verify record
            assert record.tenant_id == "tenant-1"
            assert record.session_id == "session-1"
            assert record.correlation_id == "corr-1"
            assert record.policy_action == "allow"
            assert record.orchestrator_recommendation == "allow"

    @pytest.mark.asyncio
    async def test_retrieve_audit_record(self) -> None:
        """Test retrieving audit record by ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus()
            logger = AuditLogger(bus, tmpdir)

            await bus.start()

            # Create and log execution
            context = RuntimeContext(
                tenant_id="tenant-1",
                session_id="session-1",
                correlation_id="corr-1",
            )
            context.advance_phase(RuntimePhase.INPUT)

            recommendation = OrchestratorRecommendation(
                context=context,
                tool_results=[],
                final_recommendation=Recommendation.ALLOW,
                final_severity=Severity.INFO,
                confidence=0.95,
                reasoning="Test",
            )

            decision = PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rules=[],
                reasoning="Test",
                timestamp=context.created_at,
                orchestrator_recommendation=Recommendation.ALLOW,
                orchestrator_severity=Severity.INFO,
                orchestrator_confidence=0.95,
            )

            record = await logger.log_execution(context, recommendation, decision)

            # Retrieve record
            retrieved = await logger.get_audit_record(record.audit_id, "tenant-1")

            await bus.stop()

            assert retrieved is not None
            assert retrieved.audit_id == record.audit_id
            assert retrieved.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_record(self) -> None:
        """Test retrieving nonexistent record returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus()
            logger = AuditLogger(bus, tmpdir)

            retrieved = await logger.get_audit_record("nonexistent", "tenant-1")

            assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_records_by_session(self) -> None:
        """Test retrieving all records for a session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus()
            logger = AuditLogger(bus, tmpdir)

            await bus.start()

            # Create multiple records for same session
            session_id = "session-1"

            for i in range(3):
                context = RuntimeContext(
                    tenant_id="tenant-1",
                    session_id=session_id,
                    correlation_id=f"corr-{i}",
                )
                context.advance_phase(RuntimePhase.INPUT)

                recommendation = OrchestratorRecommendation(
                    context=context,
                    tool_results=[],
                    final_recommendation=Recommendation.ALLOW,
                    final_severity=Severity.INFO,
                    confidence=0.95,
                    reasoning="Test",
                )

                decision = PolicyDecision(
                    action=PolicyAction.ALLOW,
                    matched_rules=[],
                    reasoning="Test",
                    timestamp=context.created_at,
                    orchestrator_recommendation=Recommendation.ALLOW,
                    orchestrator_severity=Severity.INFO,
                    orchestrator_confidence=0.95,
                )

                await logger.log_execution(context, recommendation, decision)

            # Retrieve all records for session
            records = await logger.get_records_by_session(session_id, "tenant-1")

            await bus.stop()

            assert len(records) == 3
            assert all(r.session_id == session_id for r in records)

    @pytest.mark.asyncio
    async def test_get_records_by_correlation(self) -> None:
        """Test retrieving all records for a correlation ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus()
            logger = AuditLogger(bus, tmpdir)

            await bus.start()

            correlation_id = "corr-1"

            # Create records with same correlation ID
            for i in range(2):
                context = RuntimeContext(
                    tenant_id="tenant-1",
                    session_id=f"session-{i}",
                    correlation_id=correlation_id,
                )
                context.advance_phase(RuntimePhase.INPUT)

                recommendation = OrchestratorRecommendation(
                    context=context,
                    tool_results=[],
                    final_recommendation=Recommendation.ALLOW,
                    final_severity=Severity.INFO,
                    confidence=0.95,
                    reasoning="Test",
                )

                decision = PolicyDecision(
                    action=PolicyAction.ALLOW,
                    matched_rules=[],
                    reasoning="Test",
                    timestamp=context.created_at,
                    orchestrator_recommendation=Recommendation.ALLOW,
                    orchestrator_severity=Severity.INFO,
                    orchestrator_confidence=0.95,
                )

                await logger.log_execution(context, recommendation, decision)

            # Retrieve all records for correlation
            records = await logger.get_records_by_correlation(
                correlation_id, "tenant-1"
            )

            await bus.stop()

            assert len(records) == 2
            assert all(r.correlation_id == correlation_id for r in records)

    @pytest.mark.asyncio
    async def test_tenant_isolation(self) -> None:
        """Test that tenants cannot access each other's records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus()
            logger = AuditLogger(bus, tmpdir)

            await bus.start()

            # Create record for tenant-1
            context = RuntimeContext(
                tenant_id="tenant-1",
                session_id="session-1",
                correlation_id="corr-1",
            )
            context.advance_phase(RuntimePhase.INPUT)

            recommendation = OrchestratorRecommendation(
                context=context,
                tool_results=[],
                final_recommendation=Recommendation.ALLOW,
                final_severity=Severity.INFO,
                confidence=0.95,
                reasoning="Test",
            )

            decision = PolicyDecision(
                action=PolicyAction.ALLOW,
                matched_rules=[],
                reasoning="Test",
                timestamp=context.created_at,
                orchestrator_recommendation=Recommendation.ALLOW,
                orchestrator_severity=Severity.INFO,
                orchestrator_confidence=0.95,
            )

            record = await logger.log_execution(context, recommendation, decision)

            # Try to retrieve with different tenant
            retrieved = await logger.get_audit_record(record.audit_id, "tenant-2")

            await bus.stop()

            assert retrieved is None

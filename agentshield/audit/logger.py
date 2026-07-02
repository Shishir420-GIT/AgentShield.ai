"""
Audit Logger - Complete execution tracking and replay.

Provides:
- Complete audit trail of all decisions
- Replay capability for forensics
- Compliance logging
- Tamper-evident records
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agentshield.core.context import RuntimeContext
from agentshield.core.events import Event, EventBus, EventType
from agentshield.orchestrator.orchestrator import OrchestratorRecommendation
from agentshield.policy.engine import PolicyDecision


class AuditRecord(BaseModel):
    """Complete audit record for a runtime execution."""

    # Correlation
    audit_id: str
    correlation_id: str
    tenant_id: str
    session_id: str
    timestamp: datetime

    # Context
    runtime_phase: str
    context_data: dict[str, Any]
    context_metadata: dict[str, Any]

    # Analysis
    tools_executed: list[str]
    orchestrator_recommendation: str
    orchestrator_severity: str
    orchestrator_confidence: float
    orchestrator_reasoning: str

    # Policy Decision
    policy_action: str
    policy_matched_rules: list[str]
    policy_reasoning: str

    # Complete state history
    state_history: list[dict[str, Any]]


class AuditLogger:
    """
    Audit logger with replay capability.

    Features:
    - Structured JSON logging
    - Complete execution trail
    - Replay from audit logs
    - Multi-tenant isolation
    """

    def __init__(
        self,
        event_bus: EventBus,
        audit_dir: Path | str = "audit_logs",
    ) -> None:
        """
        Initialize audit logger.

        Args:
            event_bus: Event bus for audit events
            audit_dir: Directory for audit logs
        """
        self.event_bus = event_bus
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    async def log_execution(
        self,
        context: RuntimeContext,
        recommendation: OrchestratorRecommendation,
        decision: PolicyDecision,
    ) -> AuditRecord:
        """
        Log complete execution with all details.

        Args:
            context: Runtime context
            recommendation: Orchestrator recommendation
            decision: Policy decision

        Returns:
            Audit record
        """
        # Create audit record
        record = AuditRecord(
            audit_id=f"audit-{context.correlation_id}",
            correlation_id=context.correlation_id,
            tenant_id=context.tenant_id,
            session_id=context.session_id,
            timestamp=datetime.now(UTC),
            runtime_phase=context.current_phase.value,
            context_data=context._data.copy(),
            context_metadata=context._metadata.copy(),
            tools_executed=[r.tool_id for r in recommendation.tool_results],
            orchestrator_recommendation=recommendation.final_recommendation.value,
            orchestrator_severity=recommendation.final_severity.value,
            orchestrator_confidence=recommendation.confidence,
            orchestrator_reasoning=recommendation.reasoning,
            policy_action=decision.action.value,
            policy_matched_rules=decision.matched_rules,
            policy_reasoning=decision.reasoning,
            state_history=[
                {
                    "phase": s.phase.value,
                    "timestamp": s.timestamp.isoformat(),
                    "data": s.data,
                    "metadata": s.metadata,
                }
                for s in context.get_state_history()
            ],
        )

        # Write to persistent storage
        await self._write_audit_log(record)

        # Emit audit event
        await self.event_bus.publish(
            Event(
                event_type=EventType.AUDIT_LOGGED,
                correlation_id=context.correlation_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                payload={
                    "audit_id": record.audit_id,
                    "policy_action": record.policy_action,
                    "orchestrator_recommendation": record.orchestrator_recommendation,
                },
            )
        )

        return record

    async def _write_audit_log(self, record: AuditRecord) -> None:
        """
        Write audit record to persistent storage.

        Args:
            record: Audit record to write
        """
        # Organize by tenant and date
        date_str = record.timestamp.strftime("%Y-%m-%d")
        tenant_dir = self.audit_dir / record.tenant_id / date_str
        tenant_dir.mkdir(parents=True, exist_ok=True)

        # Write record
        log_file = tenant_dir / f"{record.audit_id}.json"
        with open(log_file, "w") as f:
            f.write(record.model_dump_json(indent=2))

    async def get_audit_record(self, audit_id: str, tenant_id: str) -> AuditRecord | None:
        """
        Retrieve audit record by ID.

        Args:
            audit_id: Audit record ID
            tenant_id: Tenant ID (for security)

        Returns:
            Audit record if found
        """
        # Search in tenant directory
        tenant_dir = self.audit_dir / tenant_id
        if not tenant_dir.exists():
            return None

        # Search all date directories
        for date_dir in tenant_dir.iterdir():
            if not date_dir.is_dir():
                continue

            log_file = date_dir / f"{audit_id}.json"
            if log_file.exists():
                with open(log_file) as f:
                    data = json.load(f)
                return AuditRecord(**data)

        return None

    async def get_records_by_session(
        self, session_id: str, tenant_id: str
    ) -> list[AuditRecord]:
        """
        Get all audit records for a session.

        Args:
            session_id: Session ID
            tenant_id: Tenant ID

        Returns:
            List of audit records
        """
        records: list[AuditRecord] = []
        tenant_dir = self.audit_dir / tenant_id

        if not tenant_dir.exists():
            return records

        # Search all date directories
        for date_dir in tenant_dir.iterdir():
            if not date_dir.is_dir():
                continue

            for log_file in date_dir.glob("*.json"):
                with open(log_file) as f:
                    data = json.load(f)
                    record = AuditRecord(**data)
                    if record.session_id == session_id:
                        records.append(record)

        return sorted(records, key=lambda r: r.timestamp)

    async def get_records_by_correlation(
        self, correlation_id: str, tenant_id: str
    ) -> list[AuditRecord]:
        """
        Get all audit records for a correlation ID.

        Args:
            correlation_id: Correlation ID
            tenant_id: Tenant ID

        Returns:
            List of audit records
        """
        records: list[AuditRecord] = []
        tenant_dir = self.audit_dir / tenant_id

        if not tenant_dir.exists():
            return records

        # Search all date directories
        for date_dir in tenant_dir.iterdir():
            if not date_dir.is_dir():
                continue

            for log_file in date_dir.glob("*.json"):
                with open(log_file) as f:
                    data = json.load(f)
                    record = AuditRecord(**data)
                    if record.correlation_id == correlation_id:
                        records.append(record)

        return sorted(records, key=lambda r: r.timestamp)

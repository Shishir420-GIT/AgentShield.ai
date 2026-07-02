# AgentShield - AI Runtime Prevention Platform

Zero Trust AI security platform that prevents unsafe execution before irreversible actions occur.

## Core Principles
- **Zero Trust AI**: Never trust, always verify
- **Prevention before detection**: Stop threats before they execute
- **Deterministic enforcement**: Rule-based, auditable decisions
- **Agentic orchestration**: Dynamic tool selection and correlation
- **Evidence-driven decisions**: Collect and analyze before deciding
- **Plugin-first architecture**: Extensible security capabilities

## Runtime Lifecycle
```
Identity → Input → Context → Memory Read → Planner → Reasoning →
Tool Selection → Tool Arguments → Policy → Sandbox → Execution →
Tool Output → Memory Write → Output → Audit → Replay
```

## Architecture

### Phase 1: Foundation ✅
- **Runtime Context**: Shared state management with immutable history across 16 lifecycle phases
- **Event Bus**: Async pub/sub with correlation tracking for multi-tenant isolation
- **Tool SDK**: Complete plugin framework with metadata, evidence, and recommendations
- **Metrics**: Prometheus integration for observability

### Phase 2: Core Engine ✅
- **Runtime Orchestrator**: Agentic base agent that dynamically selects tools, builds investigation plans, executes analysis, and correlates evidence
- **Policy Engine**: Deterministic rule-based enforcement with default security policies
- **Audit Logger**: Complete execution tracking with replay capability and tenant isolation

### Phase 3: Security Tools ✅
- **Input Validation Tool**: Detects SQL injection, null bytes, control characters
- **Prompt Injection Detector**: Identifies jailbreaks, system prompt overrides, role manipulation

## Quick Start

### Installation

```bash
# Install with development dependencies
pip install -e ".[dev]"
```

### Basic Usage

```python
import asyncio
from agentshield.core.context import RuntimeContext, RuntimePhase
from agentshield.core.events import EventBus
from agentshield.core.tool_sdk import ToolRegistry
from agentshield.orchestrator import RuntimeOrchestrator
from agentshield.policy import PolicyEngine
from agentshield.audit import AuditLogger
from agentshield.tools import InputValidationTool, PromptInjectionDetector

async def main():
    # Initialize components
    event_bus = EventBus()
    await event_bus.start()

    tool_registry = ToolRegistry()
    tool_registry.register(InputValidationTool())
    tool_registry.register(PromptInjectionDetector())

    orchestrator = RuntimeOrchestrator(tool_registry, event_bus, metrics)
    policy_engine = PolicyEngine(event_bus, metrics)
    audit_logger = AuditLogger(event_bus)

    # Create runtime context
    context = RuntimeContext(tenant_id="tenant-1")
    context.set_data("prompt", "User input here")
    context.advance_phase(RuntimePhase.INPUT)

    # Analyze with security tools
    recommendation = await orchestrator.analyze(context)

    # Make policy decision
    decision = await policy_engine.evaluate(context, recommendation)

    # Audit log
    await audit_logger.log_execution(context, recommendation, decision)

    # Check result
    if decision.action.value == "block":
        print(f"🛑 Blocked: {decision.reasoning}")
    else:
        print("✅ Allowed - proceeding")

    await event_bus.stop()

asyncio.run(main())
```

### Full Demo

```bash
python examples/full_lifecycle_demo.py
```

Example output:
```
Step 1: Running Security Analysis...
  - Tools executed: 2
    • prompt-injection-detector: block (high)
    • input-validator: allow (info)
  - Final recommendation: block
  - Severity: high
  - Confidence: 0.90

Step 2: Policy Enforcement...
  - Action: block
  - Reasoning: Matched rule: Block High Severity (High Confidence)

❌ REQUEST BLOCKED
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=agentshield

# Specific test file
pytest tests/unit/test_orchestrator.py -v
```

**Test Status**: 38+ tests passing ✅

## Creating Custom Security Tools

```python
from agentshield.core.tool_sdk import (
    RuntimeTool, ToolMetadata, ToolCategory,
    ToolPriority, ToolResult, ToolEvidence,
    Severity, Recommendation
)

class MySecurityTool(RuntimeTool):
    def __init__(self):
        metadata = ToolMetadata(
            id="my-tool",
            version="1.0.0",
            name="My Security Tool",
            description="Custom security check",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.HIGH,
            capabilities=["custom_check"],
        )
        super().__init__(metadata)

    async def execute(self, context):
        evidence = ToolEvidence(source=self.metadata.id)

        # Your security logic here
        user_input = context.get_data("prompt", "")
        is_safe = your_check(user_input)

        if is_safe:
            return ToolResult(
                tool_id=self.metadata.id,
                evidence=evidence,
                confidence=0.95,
                severity=Severity.INFO,
                recommendation=Recommendation.ALLOW,
            )
        else:
            evidence.indicators = ["threat_detected"]
            return ToolResult(
                tool_id=self.metadata.id,
                evidence=evidence,
                confidence=0.9,
                severity=Severity.HIGH,
                recommendation=Recommendation.BLOCK,
            )
```

## Custom Policy Rules

```python
from agentshield.policy import PolicyRule, PolicyAction
from agentshield.core.tool_sdk import Severity, Recommendation

# Block all critical severity
rule = PolicyRule(
    rule_id="block-critical",
    name="Block Critical Threats",
    description="Always block critical severity",
    min_severity=Severity.CRITICAL,
    action=PolicyAction.BLOCK,
)

policy_engine.add_rule(rule)

# Tenant-specific rule
tenant_rule = PolicyRule(
    rule_id="tenant-strict",
    name="Strict Policy for Production",
    description="Lower threshold for production tenant",
    tenant_ids=["prod-tenant"],
    min_severity=Severity.MEDIUM,
    min_confidence=0.7,
    action=PolicyAction.BLOCK,
)

policy_engine.add_rule(tenant_rule)
```

## Performance Targets
- ✅ <150ms P95 latency
- ✅ Horizontal scaling ready
- ✅ Multi-tenant isolation
- ✅ Cloud agnostic
- ✅ Plugin extensibility

## Project Structure
```
agentshield/
├── core/              # Foundation (Context, Events, Tool SDK, Metrics)
├── orchestrator/      # Agentic analysis engine
├── policy/            # Deterministic enforcement
├── audit/             # Logging and replay
├── tools/             # Security tool implementations
└── api/               # REST API (future)

tests/
├── unit/              # Component tests
└── integration/       # End-to-end tests

examples/
└── full_lifecycle_demo.py  # Complete working example
```

## Documentation
- [System Architecture](AI_Runtime_Prevention_Platform_PRD/00_System_Architecture.md)
- [Core PRD](AI_Runtime_Prevention_Platform_PRD/01_Core_PRD.md)
- [Runtime Orchestrator](AI_Runtime_Prevention_Platform_PRD/02_Runtime_Orchestrator.md)
- [Tool SDK](AI_Runtime_Prevention_Platform_PRD/03_Tool_SDK.md)
- [Event System](AI_Runtime_Prevention_Platform_PRD/04_Event_System.md)
- [Build Order](AI_Runtime_Prevention_Platform_PRD/05_Build_Order.md)

## License
MIT

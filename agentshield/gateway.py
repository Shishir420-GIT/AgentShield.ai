"""
AgentShield Gateway - Core security gateway implementation.

This is the main orchestration layer that coordinates security checks,
backend communication, and policy enforcement for every AI request.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, AsyncGenerator

from agentshield.api.models import (
    BackendType,
    ChatCompletionRequest,
    ChatCompletionResponse,
    SecurityAnalysis,
)
from agentshield.audit import AuditLogger
from agentshield.backends import Backend, OpenAIBackend
from agentshield.core.context import RuntimeContext, RuntimePhase
from agentshield.core.events import EventBus
from agentshield.core.metrics import MetricsCollector
from agentshield.core.tool_sdk import ToolRegistry
from agentshield.orchestrator import RuntimeOrchestrator
from agentshield.policy import PolicyEngine


class AgentShieldGateway:
    """
    Main AgentShield security gateway.

    This class coordinates the entire security lifecycle:
    1. Receive request from frontend
    2. Run security analysis
    3. Enforce policy decisions
    4. Proxy to backend LLM (if allowed)
    5. Filter/validate output
    6. Audit everything
    7. Return response

    Acts as middleware between user and LLM.
    """

    def __init__(
        self,
        backend: Backend | None = None,
        backend_type: BackendType = BackendType.OPENAI,
        backend_api_key: str | None = None,
        backend_base_url: str | None = None,
        tool_registry: ToolRegistry | None = None,
        enable_security: bool = True,
        enable_audit: bool = True,
        audit_dir: str = "audit_logs",
    ) -> None:
        """
        Initialize AgentShield gateway.

        Args:
            backend: Pre-configured backend adapter (optional)
            backend_type: Type of backend to use (if backend not provided)
            backend_api_key: API key for backend LLM provider
            backend_base_url: Custom base URL for backend
            tool_registry: Pre-configured tool registry (optional)
            enable_security: Enable security checks
            enable_audit: Enable audit logging
            audit_dir: Directory for audit logs
        """
        # Initialize event bus
        self.event_bus = EventBus()
        self._event_bus_started = False

        # Initialize metrics
        self.metrics = MetricsCollector()

        # Initialize backend
        if backend:
            self.backend = backend
        else:
            self.backend = self._create_backend(
                backend_type,
                backend_api_key,
                backend_base_url,
            )

        # Initialize tool registry
        if tool_registry:
            self.tool_registry = tool_registry
        else:
            self.tool_registry = ToolRegistry()
            self._register_default_tools()

        # Initialize orchestrator
        self.orchestrator = RuntimeOrchestrator(
            self.tool_registry,
            self.event_bus,
            self.metrics,
        )

        # Initialize policy engine
        self.policy_engine = PolicyEngine(self.event_bus, self.metrics)

        # Initialize audit logger
        self.audit_logger = AuditLogger(
            self.event_bus,
            audit_dir=audit_dir,
        )

        # Configuration
        self.enable_security = enable_security
        self.enable_audit = enable_audit

    async def start(self) -> None:
        """Start the gateway (async initialization)."""
        if not self._event_bus_started:
            await self.event_bus.start()
            self._event_bus_started = True

    async def stop(self) -> None:
        """Stop the gateway and cleanup resources."""
        if self._event_bus_started:
            await self.event_bus.stop()
            self._event_bus_started = False

        # Close backend if it has cleanup
        if hasattr(self.backend, "close"):
            await self.backend.close()

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
        tenant_id: str | None = None,
        session_id: str | None = None,
    ) -> ChatCompletionResponse:
        """
        Process chat completion request through security gateway.

        Args:
            request: Chat completion request
            tenant_id: Tenant identifier (for multi-tenancy)
            session_id: Session identifier (for tracking)

        Returns:
            Chat completion response with security analysis

        Raises:
            SecurityException: If request is blocked by policy
            BackendError: If backend communication fails
        """
        start_time = datetime.now(UTC)

        # Ensure event bus is started
        if not self._event_bus_started:
            await self.start()

        # Use tenant/session from request if not explicitly provided
        tenant_id = tenant_id or request.tenant_id or "default"
        session_id = session_id or request.session_id or str(uuid.uuid4())

        # Create runtime context
        context = RuntimeContext(
            tenant_id=tenant_id,
            session_id=session_id,
        )

        # Extract user prompt from messages
        user_messages = [msg.content for msg in request.messages if msg.role == "user" and msg.content]
        if user_messages:
            context.set_data("prompt", user_messages[-1])  # Most recent user message

        # Store full request
        context.set_data("request", request.model_dump(exclude_none=True))
        context.set_data("model", request.model)
        context.advance_phase(RuntimePhase.INPUT)

        # Security analysis (if enabled)
        security_analysis: SecurityAnalysis | None = None

        if self.enable_security and not request.bypass_security:
            # Run orchestrator analysis
            recommendation = await self.orchestrator.analyze(context)

            # Policy decision
            context.advance_phase(RuntimePhase.POLICY)
            decision = await self.policy_engine.evaluate(context, recommendation)

            # Build security analysis
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            security_analysis = SecurityAnalysis(
                blocked=(decision.action.value == "block"),
                action=decision.action.value,  # type: ignore
                severity=recommendation.final_severity.value,  # type: ignore
                confidence=recommendation.confidence,
                reasoning=decision.reasoning,
                tools_executed=[r.tool_id for r in recommendation.tool_results],
                indicators=[
                    ind
                    for r in recommendation.tool_results
                    for ind in r.evidence.indicators
                ],
                matched_policies=decision.matched_rules,
                correlation_id=context.correlation_id,
                latency_ms=latency_ms,
            )

            # Audit logging (if enabled)
            if self.enable_audit:
                context.advance_phase(RuntimePhase.AUDIT)
                await self.audit_logger.log_execution(context, recommendation, decision)

            # Block if policy says so
            if decision.action.value == "block":
                raise SecurityException(
                    message=f"Request blocked: {decision.reasoning}",
                    security_analysis=security_analysis,
                )

        # Execute backend request
        context.advance_phase(RuntimePhase.EXECUTION)
        backend_response = await self.backend.chat_completion(request)

        # Build response
        response = ChatCompletionResponse(
            id=backend_response.provider_id,
            object="chat.completion",
            created=int(datetime.now(UTC).timestamp()),
            model=backend_response.model,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": backend_response.content,
                    },
                    "finish_reason": backend_response.finish_reason,
                }
            ],
            usage=backend_response.usage,
            security=security_analysis,
        )

        return response

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        tenant_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[ChatCompletionResponse, None]:
        """
        Process streaming chat completion request.

        Args:
            request: Chat completion request (with stream=True)
            tenant_id: Tenant identifier
            session_id: Session identifier

        Yields:
            Streaming chat completion responses

        Raises:
            SecurityException: If request is blocked
            BackendError: If backend communication fails
        """
        start_time = datetime.now(UTC)

        # Ensure event bus is started
        if not self._event_bus_started:
            await self.start()

        # Use tenant/session from request if not provided
        tenant_id = tenant_id or request.tenant_id or "default"
        session_id = session_id or request.session_id or str(uuid.uuid4())

        # Create runtime context
        context = RuntimeContext(
            tenant_id=tenant_id,
            session_id=session_id,
        )

        # Security pre-check (before streaming starts)
        if self.enable_security and not request.bypass_security:
            user_messages = [msg.content for msg in request.messages if msg.role == "user" and msg.content]
            if user_messages:
                context.set_data("prompt", user_messages[-1])

            context.set_data("request", request.model_dump(exclude_none=True))
            context.advance_phase(RuntimePhase.INPUT)

            # Run security analysis
            recommendation = await self.orchestrator.analyze(context)
            context.advance_phase(RuntimePhase.POLICY)
            decision = await self.policy_engine.evaluate(context, recommendation)

            # Block if necessary
            if decision.action.value == "block":
                latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
                security_analysis = SecurityAnalysis(
                    blocked=True,
                    action="block",
                    severity=recommendation.final_severity.value,  # type: ignore
                    confidence=recommendation.confidence,
                    reasoning=decision.reasoning,
                    tools_executed=[r.tool_id for r in recommendation.tool_results],
                    indicators=[],
                    matched_policies=decision.matched_rules,
                    correlation_id=context.correlation_id,
                    latency_ms=latency_ms,
                )

                if self.enable_audit:
                    await self.audit_logger.log_execution(context, recommendation, decision)

                raise SecurityException(
                    message=f"Stream blocked: {decision.reasoning}",
                    security_analysis=security_analysis,
                )

        # Stream from backend
        async for chunk in self.backend.chat_completion_stream(request):
            # TODO: Add real-time output filtering here
            response = ChatCompletionResponse(
                id=chunk.provider_id,
                object="chat.completion.chunk",
                created=int(datetime.now(UTC).timestamp()),
                model=chunk.model,
                choices=[
                    {
                        "index": 0,
                        "delta": {
                            "role": "assistant",
                            "content": chunk.content,
                        },
                        "finish_reason": chunk.finish_reason,
                    }
                ],
            )
            yield response

    def _create_backend(
        self,
        backend_type: BackendType,
        api_key: str | None,
        base_url: str | None,
    ) -> Backend:
        """Create backend adapter based on type."""
        if backend_type == BackendType.OPENAI:
            return OpenAIBackend(api_key=api_key, base_url=base_url)
        elif backend_type == BackendType.ANTHROPIC:
            raise NotImplementedError("Anthropic backend not yet implemented")
        elif backend_type == BackendType.BEDROCK:
            raise NotImplementedError("Bedrock backend not yet implemented")
        else:
            raise ValueError(f"Unsupported backend type: {backend_type}")

    def _register_default_tools(self) -> None:
        """Register default security tools."""
        from agentshield.tools import InputValidationTool, PromptInjectionDetector

        self.tool_registry.register(InputValidationTool())
        self.tool_registry.register(PromptInjectionDetector())


class SecurityException(Exception):
    """Exception raised when a request is blocked by security policy."""

    def __init__(
        self,
        message: str,
        security_analysis: SecurityAnalysis,
    ) -> None:
        """
        Initialize security exception.

        Args:
            message: Error message
            security_analysis: Full security analysis
        """
        super().__init__(message)
        self.message = message
        self.security_analysis = security_analysis

"""
FastAPI application for AgentShield Gateway.

This module provides a REST API interface that mimics OpenAI's API format,
making AgentShield a drop-in replacement for OpenAI/Anthropic clients.
"""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import generate_latest

from agentshield import __version__
from agentshield.api.models import (
    BackendType,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ErrorDetail,
    ErrorResponse,
    GatewayConfig,
    GatewayHealth,
)
from agentshield.gateway import AgentShieldGateway, SecurityException


# Global gateway instance
gateway: AgentShieldGateway | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for FastAPI app.

    Handles startup and shutdown of the AgentShield gateway.
    """
    global gateway

    # Startup
    print("🛡️  Starting AgentShield Gateway...")

    # Load configuration from environment
    config = _load_config_from_env()

    # Initialize gateway
    gateway = AgentShieldGateway(
        backend_type=config.backend,
        backend_api_key=config.backend_api_key,
        backend_base_url=config.backend_base_url,
        enable_security=config.enable_security,
        enable_audit=config.enable_audit,
        audit_dir=config.audit_dir,
    )
    await gateway.start()

    print(f"✅ AgentShield Gateway v{__version__} started successfully")
    print(f"📊 Backend: {config.backend.value}")
    print(f"🔒 Security: {'enabled' if config.enable_security else 'disabled'}")
    print(f"📝 Audit: {'enabled' if config.enable_audit else 'disabled'}")

    yield

    # Shutdown
    print("🛡️  Shutting down AgentShield Gateway...")
    if gateway:
        await gateway.stop()
    print("✅ AgentShield Gateway stopped")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="AgentShield Gateway",
        description="Zero Trust AI Security Gateway - Drop-in replacement for OpenAI API",
        version=__version__,
        lifespan=lifespan,
    )

    # Exception handlers
    @app.exception_handler(SecurityException)
    async def security_exception_handler(
        request: Request,
        exc: SecurityException,
    ) -> JSONResponse:
        """Handle security exceptions (blocked requests)."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=exc.message,
                    type="security_error",
                    code="request_blocked",
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle general exceptions."""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    message=str(exc),
                    type="internal_error",
                )
            ).model_dump(),
        )

    # Health check endpoints
    @app.get("/health", response_model=GatewayHealth)
    async def health_check() -> GatewayHealth:
        """Health check endpoint."""
        return GatewayHealth(
            status="healthy",
            version=__version__,
            components={
                "event_bus": "up",
                "orchestrator": "up",
                "policy_engine": "up",
                "audit_logger": "up",
            },
        )

    @app.get("/ready", response_model=GatewayHealth)
    async def readiness_check() -> GatewayHealth:
        """Readiness check endpoint."""
        if not gateway or not gateway._event_bus_started:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gateway not ready",
            )

        return GatewayHealth(
            status="healthy",
            version=__version__,
            components={
                "event_bus": "up",
                "backend": "up",
            },
        )

    @app.get("/metrics")
    async def metrics() -> str:
        """Prometheus metrics endpoint."""
        return generate_latest().decode("utf-8")

    # OpenAI-compatible chat completion endpoint
    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
    async def chat_completions(
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse | StreamingResponse:
        """
        OpenAI-compatible chat completion endpoint.

        This endpoint mimics OpenAI's /v1/chat/completions API, making
        AgentShield a drop-in replacement that adds security checks.

        Args:
            request: Chat completion request

        Returns:
            Chat completion response with security analysis

        Raises:
            HTTPException: On validation or security errors
        """
        if not gateway:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gateway not initialized",
            )

        try:
            # Handle streaming
            if request.stream:
                async def stream_generator() -> AsyncGenerator[str, None]:
                    """Generate SSE stream."""
                    async for chunk in gateway.chat_completion_stream(request):
                        # Format as Server-Sent Event
                        data = chunk.model_dump_json(exclude_none=True)
                        yield f"data: {data}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    stream_generator(),
                    media_type="text/event-stream",
                )

            # Non-streaming response
            response = await gateway.chat_completion(request)
            return response

        except SecurityException:
            # Re-raise to be handled by exception handler
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal error: {str(e)}",
            ) from e

    # Admin endpoints (for policy management)
    @app.get("/admin/policies", response_model=None)
    async def list_policies():
        """List all active policy rules."""
        if not gateway:
            raise HTTPException(status_code=503, detail="Gateway not initialized")

        rules = gateway.policy_engine.get_rules()
        return {
            "count": len(rules),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "description": r.description,
                    "enabled": r.enabled,
                    "action": r.action.value,
                }
                for r in rules
            ],
        }

    @app.get("/admin/tools", response_model=None)
    async def list_tools():
        """List all registered security tools."""
        if not gateway:
            raise HTTPException(status_code=503, detail="Gateway not initialized")

        tools = gateway.tool_registry.get_all_tools()
        return {
            "count": len(tools),
            "tools": [
                {
                    "id": t.metadata.id,
                    "name": t.metadata.name,
                    "category": t.metadata.category.value,
                    "priority": t.metadata.priority.value,
                    "enabled": t.metadata.enabled,
                }
                for t in tools
            ],
        }

    return app


def _load_config_from_env() -> GatewayConfig:
    """
    Load configuration from environment variables.

    Returns:
        Gateway configuration
    """
    return GatewayConfig(
        backend=BackendType(os.getenv("AGENTSHIELD_BACKEND", "openai")),
        backend_api_key=os.getenv("AGENTSHIELD_BACKEND_API_KEY"),
        backend_base_url=os.getenv("AGENTSHIELD_BACKEND_BASE_URL"),
        enable_security=os.getenv("AGENTSHIELD_ENABLE_SECURITY", "true").lower() == "true",
        enable_audit=os.getenv("AGENTSHIELD_ENABLE_AUDIT", "true").lower() == "true",
        audit_dir=os.getenv("AGENTSHIELD_AUDIT_DIR", "audit_logs"),
        enable_rate_limiting=os.getenv("AGENTSHIELD_ENABLE_RATE_LIMITING", "true").lower() == "true",
        rate_limit_per_minute=int(os.getenv("AGENTSHIELD_RATE_LIMIT_PER_MINUTE", "60")),
    )

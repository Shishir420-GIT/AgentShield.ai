"""
OpenAI-compatible API models for AgentShield Gateway.

These models ensure compatibility with OpenAI's API format while adding
security-specific fields for AgentShield functionality.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================================
# Request Models (OpenAI Compatible)
# ============================================================================


class ChatMessage(BaseModel):
    """A single chat message in the conversation."""

    role: Literal["system", "user", "assistant", "function", "tool"]
    content: str | None = None
    name: str | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None


class FunctionDefinition(BaseModel):
    """Function definition for function calling."""

    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ToolDefinition(BaseModel):
    """Tool definition for tool calling."""

    type: Literal["function"] = "function"
    function: FunctionDefinition


class ChatCompletionRequest(BaseModel):
    """
    OpenAI-compatible chat completion request.

    Extended with AgentShield-specific security fields.
    """

    # OpenAI Standard Fields
    model: str
    messages: list[ChatMessage]
    temperature: float | None = Field(default=1.0, ge=0.0, le=2.0)
    top_p: float | None = Field(default=1.0, ge=0.0, le=1.0)
    n: int | None = Field(default=1, ge=1, le=10)
    stream: bool = False
    stop: str | list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)
    logit_bias: dict[str, float] | None = None
    user: str | None = None  # End-user ID for abuse monitoring

    # Function/Tool Calling
    functions: list[FunctionDefinition] | None = None
    function_call: str | dict[str, str] | None = None
    tools: list[ToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None

    # Response Format
    response_format: dict[str, str] | None = None
    seed: int | None = None

    # AgentShield-Specific Fields (Optional)
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier for multi-tenant deployments"
    )
    session_id: str | None = Field(
        default=None,
        description="Session identifier for conversation tracking"
    )
    bypass_security: bool = Field(
        default=False,
        description="Bypass security checks (requires admin privileges)"
    )
    security_level: Literal["low", "medium", "high", "paranoid"] | None = Field(
        default="high",
        description="Security level for this request"
    )


# ============================================================================
# Response Models (OpenAI Compatible)
# ============================================================================


class ChatCompletionChoiceDelta(BaseModel):
    """Delta for streaming responses."""

    role: str | None = None
    content: str | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int
    message: ChatMessage | None = None
    delta: ChatCompletionChoiceDelta | None = None  # For streaming
    finish_reason: str | None = None
    logprobs: dict[str, Any] | None = None


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class SecurityAnalysis(BaseModel):
    """
    AgentShield security analysis results.

    Included in responses to provide transparency about security decisions.
    """

    blocked: bool = Field(description="Whether request was blocked")
    action: Literal["allow", "block", "audit"]
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Human-readable reason for decision")

    tools_executed: list[str] = Field(
        default_factory=list,
        description="Security tools that analyzed this request"
    )
    indicators: list[str] = Field(
        default_factory=list,
        description="Security indicators detected"
    )
    matched_policies: list[str] = Field(
        default_factory=list,
        description="Policy rules that matched"
    )

    correlation_id: str = Field(description="Correlation ID for audit trail")
    latency_ms: float = Field(description="Security analysis latency in milliseconds")


class ChatCompletionResponse(BaseModel):
    """
    OpenAI-compatible chat completion response.

    Extended with AgentShield security analysis.
    """

    id: str = Field(description="Unique completion ID")
    object: Literal["chat.completion", "chat.completion.chunk"] = "chat.completion"
    created: int = Field(description="Unix timestamp of creation")
    model: str = Field(description="Model used for completion")
    choices: list[ChatCompletionChoice]
    usage: UsageInfo | None = None

    # OpenAI fields
    system_fingerprint: str | None = None

    # AgentShield-Specific Fields
    security: SecurityAnalysis | None = Field(
        default=None,
        description="Security analysis results (only if security checks were performed)"
    )


class ErrorDetail(BaseModel):
    """Error detail information."""

    message: str
    type: str
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI-compatible error response."""

    error: ErrorDetail


# ============================================================================
# AgentShield Gateway Models
# ============================================================================


class GatewayHealth(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    components: dict[str, Literal["up", "down"]] = Field(default_factory=dict)
    details: dict[str, Any] | None = None


class GatewayMetrics(BaseModel):
    """Gateway metrics response."""

    total_requests: int
    blocked_requests: int
    allowed_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    active_sessions: int
    tools_executed: dict[str, int]
    top_threats: list[dict[str, Any]]


class BackendType(str, Enum):
    """Supported backend types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    AZURE_OPENAI = "azure-openai"
    CUSTOM = "custom"


class GatewayConfig(BaseModel):
    """Gateway configuration."""

    backend: BackendType = BackendType.OPENAI
    backend_api_key: str | None = Field(
        default=None,
        description="API key for the backend LLM provider"
    )
    backend_base_url: str | None = Field(
        default=None,
        description="Custom base URL for the backend"
    )

    # Security settings
    enable_security: bool = True
    default_security_level: Literal["low", "medium", "high", "paranoid"] = "high"
    max_request_size: int = 1_000_000  # 1MB
    request_timeout: int = 60  # seconds

    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_tenant: dict[str, int] = Field(default_factory=dict)

    # Audit
    enable_audit: bool = True
    audit_dir: str = "audit_logs"

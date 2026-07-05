"""
AgentShield Python SDK Client.

Simple drop-in replacement for OpenAI client with built-in security.
"""

from typing import Any, AsyncIterator, Iterator
import httpx


class AgentShieldError(Exception):
    """Base exception for AgentShield SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response: dict[str, Any] | None = None,
    ):
        """
        Initialize AgentShield error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            response: Full error response if available
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response or {}


class AgentShieldClient:
    """
    AgentShield Python SDK client.

    Drop-in replacement for OpenAI client with built-in security scanning.

    Example:
        ```python
        from agentshield.sdk import AgentShieldClient

        # Create client
        client = AgentShieldClient(
            api_key="your-backend-api-key",
            gateway_url="http://localhost:8000"
        )

        # Use like OpenAI client
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello!"}]
        )

        # Check security analysis
        if response.agentshield:
            print(f"Security action: {response.agentshield.action}")
            print(f"Confidence: {response.agentshield.confidence}")
        ```
    """

    def __init__(
        self,
        api_key: str,
        gateway_url: str = "http://localhost:8000",
        tenant_id: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize AgentShield client.

        Args:
            api_key: Your backend API key (e.g., OpenAI key)
            gateway_url: AgentShield gateway URL
            tenant_id: Optional tenant ID for multi-tenancy
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.gateway_url = gateway_url.rstrip("/")
        self.tenant_id = tenant_id
        self.timeout = timeout

        # Create HTTP client
        self._client = httpx.Client(timeout=timeout)
        self._async_client = httpx.AsyncClient(timeout=timeout)

        # Namespace for OpenAI-compatible API
        self.chat = ChatCompletions(self)

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id
        return headers

    def close(self) -> None:
        """Close HTTP clients."""
        self._client.close()

    async def aclose(self) -> None:
        """Close async HTTP client."""
        await self._async_client.aclose()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()


class ChatCompletions:
    """Chat completions namespace (OpenAI-compatible)."""

    def __init__(self, client: AgentShieldClient):
        """Initialize chat completions."""
        self.client = client
        self.completions = self

    def create(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> "ChatCompletionResponse":
        """
        Create a chat completion.

        Args:
            model: Model to use (e.g., "gpt-4")
            messages: List of message dicts with role and content
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            ChatCompletionResponse object

        Raises:
            AgentShieldError: If request fails or is blocked
        """
        request_data = {
            "model": model,
            "messages": messages,
            **kwargs,
        }

        if temperature is not None:
            request_data["temperature"] = temperature
        if max_tokens is not None:
            request_data["max_tokens"] = max_tokens
        if stream:
            request_data["stream"] = stream

        try:
            if stream:
                return self._stream_completion(request_data)
            else:
                response = self.client._client.post(
                    f"{self.client.gateway_url}/v1/chat/completions",
                    json=request_data,
                    headers=self.client._get_headers(),
                )
                response.raise_for_status()
                return ChatCompletionResponse(**response.json())

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                # Security violation
                error_data = e.response.json()
                raise AgentShieldError(
                    f"Security violation: {error_data.get('error', {}).get('message', 'Request blocked')}",
                    status_code=403,
                    response=error_data,
                )
            elif e.response.status_code == 502:
                # Backend error
                error_data = e.response.json()
                raise AgentShieldError(
                    f"Backend error: {error_data.get('error', {}).get('message', 'Backend unavailable')}",
                    status_code=502,
                    response=error_data,
                )
            else:
                raise AgentShieldError(
                    f"HTTP error: {e.response.status_code}",
                    status_code=e.response.status_code,
                )
        except httpx.RequestError as e:
            raise AgentShieldError(f"Request failed: {str(e)}")

    async def acreate(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> "ChatCompletionResponse":
        """
        Async create a chat completion.

        Args:
            model: Model to use
            messages: List of messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            stream: Whether to stream
            **kwargs: Additional parameters

        Returns:
            ChatCompletionResponse object

        Raises:
            AgentShieldError: If request fails
        """
        request_data = {
            "model": model,
            "messages": messages,
            **kwargs,
        }

        if temperature is not None:
            request_data["temperature"] = temperature
        if max_tokens is not None:
            request_data["max_tokens"] = max_tokens
        if stream:
            request_data["stream"] = stream

        try:
            if stream:
                return self._astream_completion(request_data)
            else:
                response = await self.client._async_client.post(
                    f"{self.client.gateway_url}/v1/chat/completions",
                    json=request_data,
                    headers=self.client._get_headers(),
                )
                response.raise_for_status()
                return ChatCompletionResponse(**response.json())

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                error_data = e.response.json()
                raise AgentShieldError(
                    f"Security violation: {error_data.get('error', {}).get('message', 'Request blocked')}",
                    status_code=403,
                    response=error_data,
                )
            else:
                raise AgentShieldError(
                    f"HTTP error: {e.response.status_code}",
                    status_code=e.response.status_code,
                )
        except httpx.RequestError as e:
            raise AgentShieldError(f"Request failed: {str(e)}")

    def _stream_completion(self, request_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """
        Stream completion chunks.

        Args:
            request_data: Request payload

        Yields:
            Completion chunks
        """
        with self.client._client.stream(
            "POST",
            f"{self.client.gateway_url}/v1/chat/completions",
            json=request_data,
            headers=self.client._get_headers(),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json
                    yield json.loads(data)

    async def _astream_completion(
        self, request_data: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Async stream completion chunks.

        Args:
            request_data: Request payload

        Yields:
            Completion chunks
        """
        async with self.client._async_client.stream(
            "POST",
            f"{self.client.gateway_url}/v1/chat/completions",
            json=request_data,
            headers=self.client._get_headers(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json
                    yield json.loads(data)


class ChatCompletionResponse:
    """
    Chat completion response.

    Compatible with OpenAI response format with additional security metadata.
    """

    def __init__(self, **data: Any):
        """Initialize from response data."""
        self.id = data.get("id", "")
        self.object = data.get("object", "chat.completion")
        self.created = data.get("created", 0)
        self.model = data.get("model", "")
        self.choices = [Choice(**choice) for choice in data.get("choices", [])]
        self.usage = Usage(**data.get("usage", {}))

        # AgentShield security analysis (if present)
        agentshield_data = data.get("agentshield")
        self.agentshield = (
            SecurityAnalysis(**agentshield_data) if agentshield_data else None
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"ChatCompletionResponse(id={self.id}, model={self.model})"


class Choice:
    """Completion choice."""

    def __init__(self, **data: Any):
        """Initialize choice."""
        self.index = data.get("index", 0)
        self.message = Message(**data.get("message", {}))
        self.finish_reason = data.get("finish_reason")


class Message:
    """Message object."""

    def __init__(self, **data: Any):
        """Initialize message."""
        self.role = data.get("role", "")
        self.content = data.get("content", "")


class Usage:
    """Token usage."""

    def __init__(self, **data: Any):
        """Initialize usage."""
        self.prompt_tokens = data.get("prompt_tokens", 0)
        self.completion_tokens = data.get("completion_tokens", 0)
        self.total_tokens = data.get("total_tokens", 0)


class SecurityAnalysis:
    """AgentShield security analysis."""

    def __init__(self, **data: Any):
        """Initialize security analysis."""
        self.blocked = data.get("blocked", False)
        self.action = data.get("action", "allow")
        self.severity = data.get("severity", "info")
        self.confidence = data.get("confidence", 0.0)
        self.reasoning = data.get("reasoning", "")
        self.tools_executed = data.get("tools_executed", [])
        self.indicators = data.get("indicators", [])
        self.matched_policies = data.get("matched_policies", [])
        self.correlation_id = data.get("correlation_id", "")
        self.latency_ms = data.get("latency_ms", 0.0)

    def __repr__(self) -> str:
        """String representation."""
        return f"SecurityAnalysis(action={self.action}, severity={self.severity}, confidence={self.confidence})"

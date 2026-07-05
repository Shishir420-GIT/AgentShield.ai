"""
Base backend interface for LLM providers.

All backend adapters must implement this interface to work with AgentShield.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from agentshield.api.models import ChatCompletionRequest


class BackendResponse(BaseModel):
    """Standardized response from any backend."""

    content: str | None = None
    model: str
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    raw_response: dict[str, Any]  # Original response from provider
    provider_id: str  # e.g., "chatcmpl-123" from OpenAI


class Backend(ABC):
    """
    Abstract base class for LLM backend adapters.

    Implementations provide a uniform interface to different LLM providers
    (OpenAI, Anthropic, Bedrock, etc.) for AgentShield to proxy requests.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize backend adapter.

        Args:
            api_key: API key for the provider
            base_url: Custom base URL (optional)
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.base_url = base_url
        self.config = kwargs

    @abstractmethod
    async def chat_completion(
        self,
        request: "ChatCompletionRequest",
    ) -> BackendResponse:
        """
        Execute chat completion request.

        Args:
            request: Standardized chat completion request

        Returns:
            Standardized backend response

        Raises:
            BackendError: If the backend request fails
        """
        pass

    @abstractmethod
    async def chat_completion_stream(
        self,
        request: "ChatCompletionRequest",
    ) -> AsyncGenerator[BackendResponse, None]:
        """
        Execute streaming chat completion request.

        Args:
            request: Standardized chat completion request

        Yields:
            Streaming backend responses (deltas)

        Raises:
            BackendError: If the backend request fails
        """
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """
        Validate that credentials are valid.

        Returns:
            True if credentials are valid

        Raises:
            BackendError: If validation fails
        """
        pass


class BackendError(Exception):
    """Exception raised when backend operations fail."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        provider_error: Any | None = None,
    ) -> None:
        """
        Initialize backend error.

        Args:
            message: Error message
            status_code: HTTP status code (if applicable)
            provider_error: Original error from provider
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.provider_error = provider_error

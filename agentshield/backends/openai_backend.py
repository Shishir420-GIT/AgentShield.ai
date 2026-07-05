"""OpenAI backend adapter for AgentShield."""

import asyncio
import json
from typing import Any, AsyncGenerator

import httpx

from agentshield.api.models import ChatCompletionRequest
from agentshield.backends.base import Backend, BackendError, BackendResponse


class OpenAIBackend(Backend):
    """
    OpenAI API backend adapter.

    Provides standardized interface to OpenAI's chat completion API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize OpenAI backend.

        Args:
            api_key: OpenAI API key
            base_url: Custom base URL (defaults to OpenAI's API)
            organization: OpenAI organization ID
            **kwargs: Additional configuration
        """
        super().__init__(api_key, base_url, **kwargs)
        self.organization = organization
        self.base_url = base_url or "https://api.openai.com/v1"

        # Create HTTP client
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=60.0,
        )

    async def chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> BackendResponse:
        """
        Execute chat completion request to OpenAI.

        Args:
            request: Chat completion request

        Returns:
            Standardized backend response

        Raises:
            BackendError: If the request fails
        """
        try:
            # Convert to OpenAI format
            payload = self._build_payload(request)

            # Make request
            response = await self.client.post(
                "/chat/completions",
                json=payload,
            )

            # Handle errors
            if response.status_code != 200:
                error_data = response.json()
                raise BackendError(
                    message=error_data.get("error", {}).get("message", "Unknown error"),
                    status_code=response.status_code,
                    provider_error=error_data,
                )

            # Parse response
            data = response.json()
            return self._parse_response(data)

        except httpx.HTTPError as e:
            raise BackendError(
                message=f"HTTP error: {e}",
                provider_error=e,
            ) from e
        except Exception as e:
            raise BackendError(
                message=f"Unexpected error: {e}",
                provider_error=e,
            ) from e

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncGenerator[BackendResponse, None]:
        """
        Execute streaming chat completion request.

        Args:
            request: Chat completion request

        Yields:
            Streaming backend responses

        Raises:
            BackendError: If the request fails
        """
        try:
            # Convert to OpenAI format with streaming
            payload = self._build_payload(request)
            payload["stream"] = True

            # Make streaming request
            async with self.client.stream(
                "POST",
                "/chat/completions",
                json=payload,
            ) as response:
                # Handle errors
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise BackendError(
                        message=f"Stream error: {error_text.decode()}",
                        status_code=response.status_code,
                    )

                # Stream chunks
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                            yield self._parse_stream_chunk(chunk)
                        except json.JSONDecodeError:
                            continue  # Skip malformed chunks

        except httpx.HTTPError as e:
            raise BackendError(
                message=f"HTTP streaming error: {e}",
                provider_error=e,
            ) from e
        except Exception as e:
            raise BackendError(
                message=f"Unexpected streaming error: {e}",
                provider_error=e,
            ) from e

    async def validate_credentials(self) -> bool:
        """
        Validate OpenAI API credentials.

        Returns:
            True if credentials are valid

        Raises:
            BackendError: If validation fails
        """
        try:
            # Try to list models as a lightweight check
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception as e:
            raise BackendError(
                message=f"Credential validation failed: {e}",
                provider_error=e,
            ) from e

    def _build_payload(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """
        Build OpenAI API payload from standardized request.

        Args:
            request: Standardized chat completion request

        Returns:
            OpenAI API payload
        """
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
        }

        # Add optional parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.n is not None:
            payload["n"] = request.n
        if request.stream is not None:
            payload["stream"] = request.stream
        if request.stop is not None:
            payload["stop"] = request.stop
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.presence_penalty is not None:
            payload["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            payload["frequency_penalty"] = request.frequency_penalty
        if request.logit_bias is not None:
            payload["logit_bias"] = request.logit_bias
        if request.user is not None:
            payload["user"] = request.user

        # Function/tool calling
        if request.functions is not None:
            payload["functions"] = [f.model_dump(exclude_none=True) for f in request.functions]
        if request.function_call is not None:
            payload["function_call"] = request.function_call
        if request.tools is not None:
            payload["tools"] = [t.model_dump(exclude_none=True) for t in request.tools]
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice

        # Response format
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.seed is not None:
            payload["seed"] = request.seed

        return payload

    def _parse_response(self, data: dict[str, Any]) -> BackendResponse:
        """
        Parse OpenAI response into standardized format.

        Args:
            data: Raw OpenAI response

        Returns:
            Standardized backend response
        """
        choice = data["choices"][0]  # Get first choice
        message = choice.get("message", {})

        return BackendResponse(
            content=message.get("content"),
            model=data["model"],
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage"),
            raw_response=data,
            provider_id=data["id"],
        )

    def _parse_stream_chunk(self, data: dict[str, Any]) -> BackendResponse:
        """
        Parse OpenAI stream chunk into standardized format.

        Args:
            data: Raw OpenAI stream chunk

        Returns:
            Standardized backend response
        """
        choice = data["choices"][0]
        delta = choice.get("delta", {})

        return BackendResponse(
            content=delta.get("content"),
            model=data["model"],
            finish_reason=choice.get("finish_reason"),
            usage=None,  # Usage not available in streaming
            raw_response=data,
            provider_id=data["id"],
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

"""Backend adapters for different LLM providers."""

from agentshield.backends.base import Backend, BackendResponse
from agentshield.backends.openai_backend import OpenAIBackend

__all__ = ["Backend", "BackendResponse", "OpenAIBackend"]

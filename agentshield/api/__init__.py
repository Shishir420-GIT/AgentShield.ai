"""AgentShield API Gateway - REST interface for security gateway."""

__all__ = ["create_app"]


def create_app():
    """Lazy import to avoid circular dependencies."""
    from agentshield.api.gateway import create_app as _create_app
    return _create_app()

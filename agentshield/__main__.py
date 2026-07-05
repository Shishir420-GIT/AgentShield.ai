"""CLI entry point for AgentShield Gateway."""

import sys


def main() -> None:
    """Main entry point for AgentShield CLI."""
    import uvicorn

    from agentshield.api.gateway import create_app

    # Create app
    app = create_app()

    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()

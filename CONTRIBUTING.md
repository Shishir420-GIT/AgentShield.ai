# Contributing to AgentShield

We welcome contributions! This guide will help you get started.

## Prerequisites

- **Python 3.11+** - Required for type hints and modern features
- **uv** - Fast Python package manager ([Installation guide](https://github.com/astral-sh/uv))

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# Verify installation
uv --version
```

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/agentshield
cd agentshield
```

### 2. Create Virtual Environment

```bash
# uv automatically creates .venv directory
uv venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install package in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

This will install:
- **Core dependencies**: FastAPI, Pydantic, httpx, etc.
- **Dev dependencies**: pytest, mypy, ruff, coverage tools

### 4. Verify Installation

```bash
# Run tests
pytest

# Check imports work
python -c "from agentshield.api.gateway import create_app; print('✅ All imports working')"
```

## Development Workflow

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_orchestrator.py -v

# With coverage
pytest --cov=agentshield --cov-report=html

# Watch mode (requires pytest-watch)
uv pip install pytest-watch
ptw
```

### Code Quality

```bash
# Format code
ruff format agentshield/

# Check linting
ruff check agentshield/

# Type checking
mypy agentshield/

# Run all quality checks
ruff check agentshield/ && ruff format agentshield/ --check && mypy agentshield/
```

### Running the Gateway

```bash
# Set your OpenAI API key
export AGENTSHIELD_BACKEND_API_KEY="sk-your-key"

# Start the gateway
python -m agentshield

# Or with uvicorn for development (auto-reload)
uvicorn agentshield.api.gateway:create_app --reload --port 8000
```

### Testing Manually

```bash
# Terminal 1: Start gateway
python -m agentshield

# Terminal 2: Run examples
python examples/full_lifecycle_demo.py
python examples/api_gateway_example.py
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

- Write code following existing patterns
- Add tests for new functionality
- Update documentation if needed

### 3. Test Your Changes

```bash
# Run tests
pytest

# Check code quality
ruff check agentshield/
mypy agentshield/

# Format code
ruff format agentshield/
```

### 4. Commit and Push

```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

### 5. Create Pull Request

Open a PR on GitHub with:
- Clear description of changes
- Link to related issues
- Screenshots/examples if applicable

## Project Structure

```
agentshield/
├── core/              # Foundation (Context, Events, Tool SDK, Metrics)
├── orchestrator/      # Security orchestration
├── policy/            # Policy engine
├── audit/             # Audit logging
├── tools/             # Security tool implementations
├── api/               # REST API gateway
├── backends/          # LLM provider adapters
└── gateway.py         # Main gateway class

tests/
├── unit/              # Unit tests
└── integration/       # Integration tests

examples/
├── full_lifecycle_demo.py      # Core functionality demo
└── api_gateway_example.py      # API gateway demo

docs/
├── 00_System_Architecture.md
├── 01_Core_PRD.md
├── ACTION_PLAN.md
└── PROGRESS_REPORT.md
```

## Adding New Security Tools

See [docs/03_Tool_SDK.md](docs/03_Tool_SDK.md) for details.

### Example Tool

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
        # Your security logic here
        evidence = ToolEvidence(source=self.metadata.id)

        # Return result
        return ToolResult(
            tool_id=self.metadata.id,
            evidence=evidence,
            confidence=0.9,
            severity=Severity.INFO,
            recommendation=Recommendation.ALLOW,
        )
```

### Register Your Tool

```python
# In agentshield/tools/__init__.py
from agentshield.tools.my_tool import MySecurityTool

__all__ = [..., "MySecurityTool"]
```

## Code Style

- **Type hints everywhere** - All functions should have type annotations
- **Async/await** - Use async throughout for consistency
- **Docstrings** - Google style docstrings for all public APIs
- **Line length** - 100 characters max
- **Imports** - Organized by stdlib, third-party, local

### Example

```python
"""Module docstring explaining purpose."""

import asyncio
from typing import Any

from pydantic import BaseModel

from agentshield.core.context import RuntimeContext


async def process_request(
    context: RuntimeContext,
    config: dict[str, Any],
) -> bool:
    """
    Process security request.

    Args:
        context: Runtime context with request data
        config: Configuration dictionary

    Returns:
        True if request is safe, False otherwise

    Raises:
        SecurityException: If critical security issue detected
    """
    # Implementation
    return True
```

## Testing Guidelines

- **Test coverage**: Aim for >80% coverage
- **Test naming**: `test_<function>_<scenario>_<expected_result>`
- **Fixtures**: Use pytest fixtures for common setup
- **Async tests**: Use `@pytest.mark.asyncio` for async tests

### Example Test

```python
import pytest
from agentshield.core.context import RuntimeContext, RuntimePhase


@pytest.mark.asyncio
async def test_orchestrator_blocks_malicious_input():
    """Test that orchestrator blocks prompt injection."""
    # Arrange
    context = RuntimeContext(tenant_id="test")
    context.set_data("prompt", "Ignore previous instructions")
    context.advance_phase(RuntimePhase.INPUT)

    # Act
    recommendation = await orchestrator.analyze(context)

    # Assert
    assert recommendation.final_recommendation == Recommendation.BLOCK
    assert recommendation.final_severity == Severity.HIGH
```

## Documentation

- Update README.md for user-facing changes
- Update docs/ for architectural changes
- Add examples/ for new features
- Include docstrings in code

## Performance Considerations

- Keep P95 latency <150ms
- Use async/await for I/O operations
- Profile before optimizing
- Consider multi-tenancy impact

## Security Considerations

- Never log sensitive data (API keys, PII)
- Validate all user inputs
- Use constant-time comparisons for secrets
- Follow OWASP guidelines

## Questions?

- Check [docs/](docs/) for technical documentation
- See [examples/](examples/) for code examples
- Ask in GitHub Discussions
- Email: dev@agentshield.dev

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

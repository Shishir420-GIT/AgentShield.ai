"""Tool SDK - Plugin framework for extensible security capabilities."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agentshield.core.context import RuntimeContext


class ToolCategory(str, Enum):
    """Tool categories aligned with runtime lifecycle."""

    IDENTITY = "identity"
    INPUT_VALIDATION = "input_validation"
    CONTEXT_SECURITY = "context_security"
    MEMORY_SECURITY = "memory_security"
    PLANNER_SECURITY = "planner_security"
    REASONING_SECURITY = "reasoning_security"
    TOOL_SECURITY = "tool_security"
    EXECUTION_SECURITY = "execution_security"
    OUTPUT_SECURITY = "output_security"
    GOVERNANCE = "governance"
    AUDIT = "audit"
    OBSERVABILITY = "observability"


class ToolPriority(int, Enum):
    """Tool execution priority."""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


class Severity(str, Enum):
    """Security severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Recommendation(str, Enum):
    """Tool recommendations for policy engine."""

    BLOCK = "block"
    ALLOW = "allow"
    WARN = "warn"
    MONITOR = "monitor"
    REVIEW = "review"


class ToolMetadata(BaseModel):
    """
    Metadata describing a runtime tool.

    Every tool must declare:
    - id: Unique identifier
    - version: Semantic version
    - category: Functional domain
    - priority: Execution priority
    - dependencies: Required tools/capabilities
    - capabilities: What the tool can detect/prevent
    """

    id: str
    version: str
    name: str
    description: str
    category: ToolCategory
    priority: ToolPriority = ToolPriority.MEDIUM
    dependencies: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True


class ToolEvidence(BaseModel):
    """Evidence collected by a tool."""

    source: str  # Tool ID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    findings: dict[str, Any] = Field(default_factory=dict)
    indicators: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """
    Result returned by a runtime tool.

    Every result includes:
    - evidence: What was found
    - confidence: How certain (0.0-1.0)
    - severity: Risk level
    - recommendation: Suggested action
    """

    tool_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence: ToolEvidence
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    recommendation: Recommendation
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeTool(ABC):
    """
    Base class for all runtime security tools.

    Every capability is a Runtime Tool that:
    - Analyzes a specific aspect of the runtime lifecycle
    - Collects evidence
    - Provides recommendations
    - Never directly enforces (policy engine does enforcement)
    """

    def __init__(self, metadata: ToolMetadata) -> None:
        """Initialize runtime tool."""
        self.metadata = metadata

    @abstractmethod
    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute tool analysis on runtime context.

        Args:
            context: Current runtime context with state

        Returns:
            ToolResult with evidence and recommendation
        """
        pass

    async def validate(self, context: RuntimeContext) -> bool:
        """
        Validate if tool can execute in current context.

        Args:
            context: Runtime context

        Returns:
            True if tool can execute
        """
        return self.metadata.enabled

    def get_dependencies(self) -> list[str]:
        """Get tool dependencies."""
        return self.metadata.dependencies

    def get_capabilities(self) -> list[str]:
        """Get tool capabilities."""
        return self.metadata.capabilities


class ToolRegistry:
    """Registry for managing available runtime tools."""

    def __init__(self) -> None:
        """Initialize tool registry."""
        self._tools: dict[str, RuntimeTool] = {}
        self._tools_by_category: dict[ToolCategory, list[RuntimeTool]] = {}

    def register(self, tool: RuntimeTool) -> None:
        """
        Register a runtime tool.

        Args:
            tool: The tool to register
        """
        tool_id = tool.metadata.id
        if tool_id in self._tools:
            raise ValueError(f"Tool {tool_id} already registered")

        self._tools[tool_id] = tool

        # Index by category
        category = tool.metadata.category
        if category not in self._tools_by_category:
            self._tools_by_category[category] = []
        self._tools_by_category[category].append(tool)

    def get_tool(self, tool_id: str) -> RuntimeTool | None:
        """Get tool by ID."""
        return self._tools.get(tool_id)

    def get_tools_by_category(self, category: ToolCategory) -> list[RuntimeTool]:
        """Get all tools in a category."""
        return self._tools_by_category.get(category, [])

    def get_all_tools(self) -> list[RuntimeTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_enabled_tools(self) -> list[RuntimeTool]:
        """Get all enabled tools."""
        return [tool for tool in self._tools.values() if tool.metadata.enabled]

    def disable_tool(self, tool_id: str) -> None:
        """Disable a tool."""
        tool = self._tools.get(tool_id)
        if tool:
            tool.metadata.enabled = False

    def enable_tool(self, tool_id: str) -> None:
        """Enable a tool."""
        tool = self._tools.get(tool_id)
        if tool:
            tool.metadata.enabled = True

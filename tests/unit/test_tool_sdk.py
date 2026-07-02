"""Unit tests for Tool SDK."""

import pytest

from agentshield.core.context import RuntimeContext
from agentshield.core.tool_sdk import (
    Recommendation,
    RuntimeTool,
    Severity,
    ToolCategory,
    ToolEvidence,
    ToolMetadata,
    ToolPriority,
    ToolRegistry,
    ToolResult,
)


class MockSecurityTool(RuntimeTool):
    """Mock security tool for testing."""

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """Execute mock analysis."""
        evidence = ToolEvidence(
            source=self.metadata.id,
            findings={"test": "finding"},
            indicators=["indicator1"],
        )

        return ToolResult(
            tool_id=self.metadata.id,
            evidence=evidence,
            confidence=0.9,
            severity=Severity.MEDIUM,
            recommendation=Recommendation.WARN,
        )


class TestToolMetadata:
    """Test ToolMetadata model."""

    def test_metadata_creation(self) -> None:
        """Test creating tool metadata."""
        metadata = ToolMetadata(
            id="test-tool-1",
            version="1.0.0",
            name="Test Tool",
            description="A test security tool",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.HIGH,
            capabilities=["validate_input", "detect_injection"],
        )

        assert metadata.id == "test-tool-1"
        assert metadata.version == "1.0.0"
        assert metadata.category == ToolCategory.INPUT_VALIDATION
        assert metadata.priority == ToolPriority.HIGH
        assert len(metadata.capabilities) == 2
        assert metadata.enabled is True

    def test_metadata_defaults(self) -> None:
        """Test metadata defaults."""
        metadata = ToolMetadata(
            id="test-tool-1",
            version="1.0.0",
            name="Test Tool",
            description="A test tool",
            category=ToolCategory.INPUT_VALIDATION,
        )

        assert metadata.priority == ToolPriority.MEDIUM
        assert metadata.dependencies == []
        assert metadata.capabilities == []
        assert metadata.enabled is True


class TestToolEvidence:
    """Test ToolEvidence model."""

    def test_evidence_creation(self) -> None:
        """Test creating evidence."""
        evidence = ToolEvidence(
            source="test-tool-1",
            findings={"malicious_pattern": "eval()"},
            indicators=["code_injection", "suspicious_function"],
            raw_data={"input": "user_input"},
        )

        assert evidence.source == "test-tool-1"
        assert evidence.findings["malicious_pattern"] == "eval()"
        assert len(evidence.indicators) == 2
        assert evidence.timestamp is not None


class TestToolResult:
    """Test ToolResult model."""

    def test_result_creation(self) -> None:
        """Test creating tool result."""
        evidence = ToolEvidence(
            source="test-tool-1",
            findings={"threat": "detected"},
        )

        result = ToolResult(
            tool_id="test-tool-1",
            evidence=evidence,
            confidence=0.95,
            severity=Severity.HIGH,
            recommendation=Recommendation.BLOCK,
        )

        assert result.tool_id == "test-tool-1"
        assert result.confidence == 0.95
        assert result.severity == Severity.HIGH
        assert result.recommendation == Recommendation.BLOCK
        assert result.timestamp is not None

    def test_confidence_validation(self) -> None:
        """Test confidence must be between 0 and 1."""
        evidence = ToolEvidence(source="test-tool-1")

        with pytest.raises(Exception):  # Pydantic validation error
            ToolResult(
                tool_id="test-tool-1",
                evidence=evidence,
                confidence=1.5,  # Invalid
                severity=Severity.HIGH,
                recommendation=Recommendation.BLOCK,
            )


class TestRuntimeTool:
    """Test RuntimeTool base class."""

    @pytest.mark.asyncio
    async def test_tool_execution(self) -> None:
        """Test tool execution."""
        metadata = ToolMetadata(
            id="mock-tool-1",
            version="1.0.0",
            name="Mock Tool",
            description="Mock security tool",
            category=ToolCategory.INPUT_VALIDATION,
        )

        tool = MockSecurityTool(metadata)
        context = RuntimeContext(tenant_id="tenant-1")

        result = await tool.execute(context)

        assert result.tool_id == "mock-tool-1"
        assert result.confidence == 0.9
        assert result.severity == Severity.MEDIUM
        assert result.recommendation == Recommendation.WARN

    @pytest.mark.asyncio
    async def test_tool_validation(self) -> None:
        """Test tool validation."""
        metadata = ToolMetadata(
            id="mock-tool-1",
            version="1.0.0",
            name="Mock Tool",
            description="Mock tool",
            category=ToolCategory.INPUT_VALIDATION,
            enabled=True,
        )

        tool = MockSecurityTool(metadata)
        context = RuntimeContext(tenant_id="tenant-1")

        assert await tool.validate(context) is True

        # Disable tool
        tool.metadata.enabled = False
        assert await tool.validate(context) is False

    def test_tool_dependencies(self) -> None:
        """Test getting tool dependencies."""
        metadata = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Test tool",
            category=ToolCategory.INPUT_VALIDATION,
            dependencies=["dep-1", "dep-2"],
        )

        tool = MockSecurityTool(metadata)
        deps = tool.get_dependencies()

        assert len(deps) == 2
        assert "dep-1" in deps
        assert "dep-2" in deps

    def test_tool_capabilities(self) -> None:
        """Test getting tool capabilities."""
        metadata = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Test tool",
            category=ToolCategory.INPUT_VALIDATION,
            capabilities=["validate", "sanitize"],
        )

        tool = MockSecurityTool(metadata)
        caps = tool.get_capabilities()

        assert len(caps) == 2
        assert "validate" in caps
        assert "sanitize" in caps


class TestToolRegistry:
    """Test ToolRegistry."""

    def test_register_tool(self) -> None:
        """Test registering a tool."""
        registry = ToolRegistry()
        metadata = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Test tool",
            category=ToolCategory.INPUT_VALIDATION,
        )
        tool = MockSecurityTool(metadata)

        registry.register(tool)

        assert registry.get_tool("tool-1") is not None
        assert registry.get_tool("tool-1") == tool

    def test_register_duplicate_tool(self) -> None:
        """Test registering duplicate tool raises error."""
        registry = ToolRegistry()
        metadata = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Test tool",
            category=ToolCategory.INPUT_VALIDATION,
        )
        tool1 = MockSecurityTool(metadata)
        tool2 = MockSecurityTool(metadata)

        registry.register(tool1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(tool2)

    def test_get_tools_by_category(self) -> None:
        """Test getting tools by category."""
        registry = ToolRegistry()

        # Create tools in different categories
        tool1_meta = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Input validation tool",
            category=ToolCategory.INPUT_VALIDATION,
        )
        tool1 = MockSecurityTool(tool1_meta)

        tool2_meta = ToolMetadata(
            id="tool-2",
            version="1.0.0",
            name="Tool 2",
            description="Output security tool",
            category=ToolCategory.OUTPUT_SECURITY,
        )
        tool2 = MockSecurityTool(tool2_meta)

        tool3_meta = ToolMetadata(
            id="tool-3",
            version="1.0.0",
            name="Tool 3",
            description="Another input validation tool",
            category=ToolCategory.INPUT_VALIDATION,
        )
        tool3 = MockSecurityTool(tool3_meta)

        registry.register(tool1)
        registry.register(tool2)
        registry.register(tool3)

        # Get by category
        input_tools = registry.get_tools_by_category(ToolCategory.INPUT_VALIDATION)
        output_tools = registry.get_tools_by_category(ToolCategory.OUTPUT_SECURITY)

        assert len(input_tools) == 2
        assert len(output_tools) == 1

    def test_get_all_tools(self) -> None:
        """Test getting all tools."""
        registry = ToolRegistry()

        tool1_meta = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Tool 1",
            category=ToolCategory.INPUT_VALIDATION,
        )
        tool1 = MockSecurityTool(tool1_meta)

        tool2_meta = ToolMetadata(
            id="tool-2",
            version="1.0.0",
            name="Tool 2",
            description="Tool 2",
            category=ToolCategory.OUTPUT_SECURITY,
        )
        tool2 = MockSecurityTool(tool2_meta)

        registry.register(tool1)
        registry.register(tool2)

        all_tools = registry.get_all_tools()
        assert len(all_tools) == 2

    def test_enable_disable_tool(self) -> None:
        """Test enabling and disabling tools."""
        registry = ToolRegistry()
        metadata = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Test tool",
            category=ToolCategory.INPUT_VALIDATION,
        )
        tool = MockSecurityTool(metadata)

        registry.register(tool)
        assert tool.metadata.enabled is True

        # Disable
        registry.disable_tool("tool-1")
        assert tool.metadata.enabled is False

        # Enable
        registry.enable_tool("tool-1")
        assert tool.metadata.enabled is True

    def test_get_enabled_tools(self) -> None:
        """Test getting only enabled tools."""
        registry = ToolRegistry()

        tool1_meta = ToolMetadata(
            id="tool-1",
            version="1.0.0",
            name="Tool 1",
            description="Tool 1",
            category=ToolCategory.INPUT_VALIDATION,
            enabled=True,
        )
        tool1 = MockSecurityTool(tool1_meta)

        tool2_meta = ToolMetadata(
            id="tool-2",
            version="1.0.0",
            name="Tool 2",
            description="Tool 2",
            category=ToolCategory.OUTPUT_SECURITY,
            enabled=False,
        )
        tool2 = MockSecurityTool(tool2_meta)

        registry.register(tool1)
        registry.register(tool2)

        enabled_tools = registry.get_enabled_tools()
        assert len(enabled_tools) == 1
        assert enabled_tools[0].metadata.id == "tool-1"

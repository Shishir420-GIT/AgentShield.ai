"""Tool Selector Validator - Validates AI tool selection and usage."""

from typing import Any

from agentshield.core.context import RuntimeContext
from agentshield.core.tool_sdk import (
    Recommendation,
    RuntimeTool,
    Severity,
    ToolCategory,
    ToolEvidence,
    ToolMetadata,
    ToolPriority,
    ToolResult,
)


class ToolSelectorValidator(RuntimeTool):
    """
    Validates AI agent tool selection and usage patterns.

    Checks for:
    - Unauthorized tool access
    - Dangerous tool combinations
    - Tool abuse patterns
    - Excessive tool calls
    - Privilege escalation via tools
    """

    def __init__(self) -> None:
        """Initialize tool selector validator."""
        metadata = ToolMetadata(
            id="tool-selector-validator",
            version="1.0.0",
            name="Tool Selector Validator",
            description="Validates AI agent tool selection and usage",
            category=ToolCategory.TOOL_VALIDATION,
            priority=ToolPriority.HIGH,
            capabilities=[
                "tool_authorization",
                "tool_combination_check",
                "tool_abuse_detection",
                "tool_call_rate_limit",
            ],
        )
        super().__init__(metadata)

        # Dangerous tools that require special authorization
        self.restricted_tools = {
            "execute_code",
            "run_shell",
            "file_delete",
            "database_write",
            "send_email",
            "make_payment",
            "delete_user",
            "modify_permissions",
        }

        # Dangerous tool combinations
        self.dangerous_combinations = [
            {"file_read", "execute_code"},
            {"database_query", "execute_code"},
            {"user_data", "send_email"},
        ]

        # Tool call limits
        self.max_tools_per_request = 10
        self.max_same_tool_calls = 3

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute tool selector validation.

        Args:
            context: Runtime context containing tool selection data

        Returns:
            ToolResult with validation findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings: dict[str, Any] = {}
        indicators = []

        # Get tool selection from context
        selected_tools = context.get_data("selected_tools", [])
        tool_calls = context.get_data("tool_calls", [])
        authorized_tools = context.get_data("authorized_tools", set())

        # Check 1: Unauthorized tool access
        unauthorized = set(selected_tools) & self.restricted_tools
        if unauthorized and not authorized_tools:
            findings["unauthorized_tools"] = list(unauthorized)
            indicators.append("unauthorized_tool_access")

        # Check 2: Tool authorization bypass
        if authorized_tools:
            bypass_attempt = set(selected_tools) - authorized_tools
            if bypass_attempt & self.restricted_tools:
                findings["authorization_bypass"] = list(bypass_attempt)
                indicators.append("authorization_bypass_attempt")

        # Check 3: Dangerous tool combinations
        selected_set = set(selected_tools)
        for combo in self.dangerous_combinations:
            if combo.issubset(selected_set):
                findings["dangerous_combination"] = list(combo)
                indicators.append("dangerous_tool_combination")
                break

        # Check 4: Excessive tool calls
        if len(selected_tools) > self.max_tools_per_request:
            findings["too_many_tools"] = {
                "count": len(selected_tools),
                "max": self.max_tools_per_request,
            }
            indicators.append("excessive_tool_calls")

        # Check 5: Same tool called repeatedly (potential abuse)
        tool_counts: dict[str, int] = {}
        for tool in selected_tools:
            tool_counts[tool] = tool_counts.get(tool, 0) + 1

        for tool, count in tool_counts.items():
            if count > self.max_same_tool_calls:
                findings["tool_abuse"] = {"tool": tool, "count": count}
                indicators.append("tool_abuse_detected")
                break

        # Check 6: Tool call patterns
        suspicious_patterns = self._check_tool_patterns(selected_tools)
        if suspicious_patterns:
            findings["suspicious_patterns"] = suspicious_patterns
            indicators.append("suspicious_tool_pattern")

        # Determine severity and recommendation
        if indicators:
            # Critical for unauthorized access or bypass
            if (
                "unauthorized_tool_access" in indicators
                or "authorization_bypass_attempt" in indicators
            ):
                severity = Severity.CRITICAL
                recommendation = Recommendation.BLOCK
                confidence = 0.95
            # High for dangerous combinations or abuse
            elif (
                "dangerous_tool_combination" in indicators
                or "tool_abuse_detected" in indicators
            ):
                severity = Severity.HIGH
                recommendation = Recommendation.WARN
                confidence = 0.9
            # Medium for excessive calls
            else:
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.8
        else:
            findings["tool_selection_valid"] = True
            severity = Severity.INFO
            recommendation = Recommendation.ALLOW
            confidence = 0.9

        evidence.findings = findings
        evidence.indicators = indicators

        return ToolResult(
            tool_id=self.metadata.id,
            evidence=evidence,
            confidence=confidence,
            severity=severity,
            recommendation=recommendation,
        )

    def _check_tool_patterns(self, tools: list[str]) -> dict[str, Any] | None:
        """
        Check for suspicious tool usage patterns.

        Args:
            tools: List of selected tools

        Returns:
            Dictionary of suspicious patterns or None
        """
        patterns = {}

        # Pattern 1: Data exfiltration (read + external communication)
        read_tools = {"file_read", "database_query", "get_secrets"}
        external_tools = {"send_email", "http_request", "webhook"}

        if any(t in tools for t in read_tools) and any(t in tools for t in external_tools):
            patterns["potential_exfiltration"] = {
                "read_tools": [t for t in tools if t in read_tools],
                "external_tools": [t for t in tools if t in external_tools],
            }

        # Pattern 2: Privilege escalation (permission tools + action tools)
        permission_tools = {"get_permissions", "check_auth"}
        action_tools = {"execute_code", "modify_user"}

        if any(t in tools for t in permission_tools) and any(t in tools for t in action_tools):
            patterns["privilege_escalation_risk"] = True

        return patterns if patterns else None

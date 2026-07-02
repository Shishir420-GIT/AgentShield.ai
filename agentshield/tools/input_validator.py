"""Input Validation Tool - Validates user input for security threats."""

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


class InputValidationTool(RuntimeTool):
    """
    Validates user input for basic security threats.

    Checks:
    - Input length limits
    - Null byte injection
    - Control characters
    - Basic SQL injection patterns
    """

    def __init__(self) -> None:
        """Initialize input validation tool."""
        metadata = ToolMetadata(
            id="input-validator",
            version="1.0.0",
            name="Input Validation Tool",
            description="Validates user input for basic security threats",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.HIGH,
            capabilities=[
                "length_validation",
                "null_byte_detection",
                "control_char_detection",
                "sql_injection_detection",
            ],
        )
        super().__init__(metadata)

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute input validation.

        Args:
            context: Runtime context containing input data

        Returns:
            ToolResult with validation findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings = {}
        indicators = []

        # Get input from context
        user_input = context.get_data("prompt", "")

        # Check 1: Length validation
        max_length = 10000
        if len(user_input) > max_length:
            findings["length_exceeded"] = True
            findings["input_length"] = len(user_input)
            findings["max_length"] = max_length
            indicators.append("input_too_long")

        # Check 2: Null byte injection
        if "\x00" in user_input:
            findings["null_byte_detected"] = True
            indicators.append("null_byte_injection")

        # Check 3: Control characters (except common ones)
        control_chars = [chr(i) for i in range(32) if i not in [9, 10, 13]]  # Exclude tab, LF, CR
        found_control = [c for c in control_chars if c in user_input]
        if found_control:
            findings["control_chars_detected"] = True
            findings["control_char_count"] = len(found_control)
            indicators.append("control_characters")

        # Check 4: Basic SQL injection patterns
        sql_patterns = [
            "' OR '1'='1",
            "'; DROP TABLE",
            "UNION SELECT",
            "1' OR '1' = '1",
            "admin'--",
        ]
        found_sql = [p for p in sql_patterns if p.lower() in user_input.lower()]
        if found_sql:
            findings["sql_injection_patterns"] = found_sql
            indicators.append("sql_injection_attempt")

        # Determine severity and recommendation
        if indicators:
            if any(ind in ["null_byte_injection", "sql_injection_attempt"] for ind in indicators):
                severity = Severity.HIGH
                recommendation = Recommendation.BLOCK
                confidence = 0.9
            else:
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.7
        else:
            findings["validated"] = True
            severity = Severity.INFO
            recommendation = Recommendation.ALLOW
            confidence = 0.95

        evidence.findings = findings
        evidence.indicators = indicators

        return ToolResult(
            tool_id=self.metadata.id,
            evidence=evidence,
            confidence=confidence,
            severity=severity,
            recommendation=recommendation,
        )

"""SQL Injection Detector - Detects SQL injection attempts."""

import re
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


class SQLInjectionDetector(RuntimeTool):
    """
    Detects SQL injection attempts in input.

    Checks for:
    - SQL keywords (DROP, DELETE, INSERT, UPDATE, etc.)
    - SQL comment patterns (-- , /* */, #)
    - UNION-based injection
    - Boolean-based injection
    - Time-based injection
    - Stacked queries
    """

    def __init__(self) -> None:
        """Initialize SQL injection detector."""
        metadata = ToolMetadata(
            id="sql-injection-detector",
            version="1.0.0",
            name="SQL Injection Detector",
            description="Detects SQL injection attack patterns",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.CRITICAL,
            capabilities=[
                "sql_keyword_detection",
                "sql_comment_detection",
                "union_injection_detection",
                "boolean_injection_detection",
                "time_injection_detection",
            ],
        )
        super().__init__(metadata)

        # SQL keywords that are dangerous in user input
        self.dangerous_keywords = [
            "drop table",
            "drop database",
            "delete from",
            "truncate table",
            "insert into",
            "update set",
            "exec(",
            "execute(",
            "xp_cmdshell",
            "sp_executesql",
        ]

        # SQL comment patterns
        self.comment_patterns = [
            r"--",  # SQL line comment
            r"/\*.*?\*/",  # SQL block comment
            r"#",  # MySQL comment
        ]

        # Injection patterns
        self.union_pattern = re.compile(r"\bunion\b.*\bselect\b", re.IGNORECASE)
        self.boolean_pattern = re.compile(
            r"(\bor\b|\band\b)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?", re.IGNORECASE
        )
        self.time_pattern = re.compile(
            r"\b(sleep|waitfor delay|benchmark)\s*\(", re.IGNORECASE
        )
        self.stacked_query_pattern = re.compile(r";\s*\w+", re.IGNORECASE)

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute SQL injection detection.

        Args:
            context: Runtime context containing input data

        Returns:
            ToolResult with detection findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings: dict[str, Any] = {}
        indicators = []

        # Get input from context
        user_input = context.get_data("prompt", "")
        tool_args = context.get_data("tool_arguments", "")
        content = f"{user_input} {tool_args}"
        lower_content = content.lower()

        # Check 1: Dangerous SQL keywords
        found_keywords = [kw for kw in self.dangerous_keywords if kw in lower_content]
        if found_keywords:
            findings["dangerous_keywords"] = found_keywords
            indicators.append("sql_keywords_detected")

        # Check 2: SQL comments
        found_comments = []
        for pattern in self.comment_patterns:
            if re.search(pattern, content):
                found_comments.append(pattern)
        if found_comments:
            findings["sql_comments"] = found_comments
            indicators.append("sql_comments_detected")

        # Check 3: UNION-based injection
        if self.union_pattern.search(content):
            findings["union_injection"] = True
            indicators.append("union_injection_detected")

        # Check 4: Boolean-based injection
        if self.boolean_pattern.search(content):
            findings["boolean_injection"] = True
            indicators.append("boolean_injection_detected")

        # Check 5: Time-based injection
        if self.time_pattern.search(content):
            findings["time_injection"] = True
            indicators.append("time_injection_detected")

        # Check 6: Stacked queries
        if ";" in content and self.stacked_query_pattern.search(content):
            findings["stacked_queries"] = True
            indicators.append("stacked_queries_detected")

        # Check 7: SQL string escape attempts
        if self._check_escape_attempts(content):
            findings["escape_attempts"] = True
            indicators.append("escape_attempts_detected")

        # Determine severity and recommendation
        if indicators:
            # Critical for destructive operations or multiple attack vectors
            if (
                "sql_keywords_detected" in indicators
                or len(indicators) >= 3
            ):
                severity = Severity.CRITICAL
                recommendation = Recommendation.BLOCK
                confidence = 0.95
            # High for clear injection patterns
            elif (
                "union_injection_detected" in indicators
                or "time_injection_detected" in indicators
                or "stacked_queries_detected" in indicators
            ):
                severity = Severity.HIGH
                recommendation = Recommendation.BLOCK
                confidence = 0.9
            # Medium for suspicious patterns
            else:
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.8
        else:
            findings["no_sql_injection_detected"] = True
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

    def _check_escape_attempts(self, content: str) -> bool:
        """
        Check for SQL string escape attempts.

        Args:
            content: Content to check

        Returns:
            True if escape attempts detected
        """
        escape_patterns = [
            "''",  # Escaped single quote
            '""',  # Escaped double quote
            "\\'",  # Backslash escaped quote
            '\\"',  # Backslash escaped double quote
            "'; ",  # Quote semicolon space
            '"; ',  # Double quote semicolon space
        ]

        return any(pattern in content for pattern in escape_patterns)

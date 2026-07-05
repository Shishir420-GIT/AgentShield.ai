"""Context Validator - Validates context windows and data flow."""

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


class ContextValidator(RuntimeTool):
    """
    Validates context window size, data flow, and conversation history.

    Checks for:
    - Context window overflow
    - Suspicious context manipulation
    - Historical data poisoning
    - Context injection attacks
    - Token limit violations
    """

    def __init__(self) -> None:
        """Initialize context validator."""
        metadata = ToolMetadata(
            id="context-validator",
            version="1.0.0",
            name="Context Validator",
            description="Validates context windows and conversation history",
            category=ToolCategory.CONTEXT_ANALYSIS,
            priority=ToolPriority.HIGH,
            capabilities=[
                "context_size_validation",
                "context_manipulation_detection",
                "history_validation",
                "token_limit_check",
            ],
        )
        super().__init__(metadata)

        # Configuration
        self.max_context_tokens = 128000  # GPT-4 limit
        self.max_messages = 1000
        self.max_message_length = 100000  # chars

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute context validation.

        Args:
            context: Runtime context to validate

        Returns:
            ToolResult with validation findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings: dict[str, Any] = {}
        indicators = []

        # Get messages from context
        messages = context.get_data("messages", [])
        context_data = context.get_data("context", {})

        # Check 1: Message count
        if len(messages) > self.max_messages:
            findings["message_count_exceeded"] = {
                "count": len(messages),
                "max": self.max_messages,
            }
            indicators.append("too_many_messages")

        # Check 2: Message length
        for idx, msg in enumerate(messages):
            content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            if len(content) > self.max_message_length:
                findings["message_too_long"] = {
                    "index": idx,
                    "length": len(content),
                    "max": self.max_message_length,
                }
                indicators.append("message_length_exceeded")
                break

        # Check 3: Token estimation (rough estimate: 1 token ~= 4 chars)
        total_chars = sum(
            len(msg.get("content", "")) if isinstance(msg, dict) else len(str(msg))
            for msg in messages
        )
        estimated_tokens = total_chars // 4
        findings["estimated_tokens"] = estimated_tokens

        if estimated_tokens > self.max_context_tokens:
            findings["token_limit_exceeded"] = {
                "estimated": estimated_tokens,
                "max": self.max_context_tokens,
            }
            indicators.append("token_limit_exceeded")

        # Check 4: Context manipulation patterns
        manipulation_detected = self._check_context_manipulation(messages)
        if manipulation_detected:
            findings["context_manipulation"] = manipulation_detected
            indicators.append("context_manipulation_detected")

        # Check 5: Conversation history anomalies
        anomalies = self._check_history_anomalies(messages)
        if anomalies:
            findings["history_anomalies"] = anomalies
            indicators.append("history_anomalies_detected")

        # Determine severity and recommendation
        if indicators:
            # High for manipulation or severe limits
            if (
                "context_manipulation_detected" in indicators
                or "token_limit_exceeded" in indicators
            ):
                severity = Severity.HIGH
                recommendation = Recommendation.WARN
                confidence = 0.85
            # Medium for count/length issues
            elif (
                "too_many_messages" in indicators
                or "message_length_exceeded" in indicators
            ):
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.8
            else:
                severity = Severity.LOW
                recommendation = Recommendation.ALLOW
                confidence = 0.75
        else:
            findings["context_valid"] = True
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

    def _check_context_manipulation(self, messages: list[Any]) -> dict[str, Any] | None:
        """
        Check for context manipulation patterns.

        Args:
            messages: List of messages

        Returns:
            Dictionary of manipulation findings or None
        """
        manipulation = {}

        for idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue

            content = msg.get("content", "").lower()

            # Check for system role override attempts
            if msg.get("role") == "system" and idx > 0:
                manipulation["system_role_injection"] = {
                    "index": idx,
                    "suspicious": True,
                }

            # Check for context poisoning keywords
            poison_keywords = [
                "previous conversation",
                "earlier you said",
                "you mentioned before",
                "in our last chat",
            ]
            if any(kw in content for kw in poison_keywords) and idx < 3:
                manipulation["history_fabrication"] = {
                    "index": idx,
                    "suspicious": True,
                }

        return manipulation if manipulation else None

    def _check_history_anomalies(self, messages: list[Any]) -> dict[str, Any] | None:
        """
        Check for conversation history anomalies.

        Args:
            messages: List of messages

        Returns:
            Dictionary of anomalies or None
        """
        anomalies = {}

        if not messages:
            return None

        # Check for role alternation (should alternate user/assistant)
        roles = [
            msg.get("role", "")
            for msg in messages
            if isinstance(msg, dict)
        ]

        # Count consecutive same roles
        max_consecutive = 1
        current_consecutive = 1
        for i in range(1, len(roles)):
            if roles[i] == roles[i - 1] and roles[i] in ["user", "assistant"]:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1

        if max_consecutive >= 3:
            anomalies["role_alternation_violation"] = {
                "max_consecutive": max_consecutive,
                "suspicious": True,
            }

        return anomalies if anomalies else None

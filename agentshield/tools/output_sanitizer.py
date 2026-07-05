"""Output Sanitizer - Sanitizes and validates AI model outputs."""

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


class OutputSanitizer(RuntimeTool):
    """
    Sanitizes and validates AI model outputs before returning to user.

    Checks for:
    - Information leakage (system prompts, internals)
    - PII in responses
    - Harmful content
    - Malicious code/scripts
    - Hallucination indicators
    - Biased/toxic content
    """

    def __init__(self) -> None:
        """Initialize output sanitizer."""
        metadata = ToolMetadata(
            id="output-sanitizer",
            version="1.0.0",
            name="Output Sanitizer",
            description="Sanitizes and validates AI model outputs",
            category=ToolCategory.OUTPUT_VALIDATION,
            priority=ToolPriority.HIGH,
            capabilities=[
                "information_leakage_detection",
                "harmful_content_detection",
                "code_injection_detection",
                "hallucination_detection",
                "toxicity_detection",
            ],
        )
        super().__init__(metadata)

        # Patterns for information leakage
        self.leakage_patterns = [
            r"system prompt:",
            r"you are a",
            r"you have been trained",
            r"your instructions are",
            r"ignore the above",
            r"internal configuration",
            r"my training data",
        ]

        # Harmful content keywords
        self.harmful_keywords = [
            "illegal activities",
            "violence",
            "self-harm",
            "hate speech",
            "discrimination",
        ]

        # Code injection patterns
        self.code_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"onerror=",
            r"onclick=",
            r"eval\(",
            r"exec\(",
        ]

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute output sanitization.

        Args:
            context: Runtime context containing output data

        Returns:
            ToolResult with sanitization findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings: dict[str, Any] = {}
        indicators = []

        # Get output from context
        output = context.get_data("output", "")
        if not output:
            # No output to sanitize
            findings["no_output"] = True
            return ToolResult(
                tool_id=self.metadata.id,
                evidence=evidence,
                confidence=1.0,
                severity=Severity.INFO,
                recommendation=Recommendation.ALLOW,
            )

        lower_output = output.lower()

        # Check 1: Information leakage
        leaked_info = []
        for pattern in self.leakage_patterns:
            if re.search(pattern, lower_output):
                leaked_info.append(pattern)

        if leaked_info:
            findings["information_leakage"] = leaked_info
            indicators.append("information_leak_detected")

        # Check 2: Harmful content
        found_harmful = [kw for kw in self.harmful_keywords if kw in lower_output]
        if found_harmful:
            findings["harmful_content"] = found_harmful
            indicators.append("harmful_content_detected")

        # Check 3: Code injection
        found_code = []
        for pattern in self.code_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                found_code.append(pattern)

        if found_code:
            findings["code_injection"] = found_code
            indicators.append("code_injection_detected")

        # Check 4: Hallucination indicators
        hallucination_indicators = self._check_hallucinations(output)
        if hallucination_indicators:
            findings["hallucination_indicators"] = hallucination_indicators
            indicators.append("possible_hallucination")

        # Check 5: Excessive length
        if len(output) > 50000:  # chars
            findings["excessive_length"] = len(output)
            indicators.append("excessive_output_length")

        # Check 6: Refusal bypass detection
        if self._check_refusal_bypass(output):
            findings["refusal_bypass"] = True
            indicators.append("refusal_bypass_detected")

        # Determine severity and recommendation
        if indicators:
            # Critical for code injection or information leakage
            if (
                "code_injection_detected" in indicators
                or "information_leak_detected" in indicators
            ):
                severity = Severity.CRITICAL
                recommendation = Recommendation.BLOCK
                confidence = 0.95
            # High for harmful content or refusal bypass
            elif (
                "harmful_content_detected" in indicators
                or "refusal_bypass_detected" in indicators
            ):
                severity = Severity.HIGH
                recommendation = Recommendation.WARN
                confidence = 0.9
            # Medium for hallucinations or length
            else:
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.8
        else:
            findings["output_clean"] = True
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

    def _check_hallucinations(self, output: str) -> list[str]:
        """
        Check for hallucination indicators.

        Args:
            output: Output text to check

        Returns:
            List of hallucination indicators
        """
        indicators = []

        # Check for uncertain language that might indicate hallucination
        uncertainty_phrases = [
            "i think",
            "i believe",
            "probably",
            "might be",
            "could be",
            "i'm not sure",
        ]

        # Count uncertainty phrases
        uncertainty_count = sum(
            1 for phrase in uncertainty_phrases if phrase in output.lower()
        )

        if uncertainty_count >= 3:
            indicators.append("high_uncertainty")

        # Check for contradictions (simple check)
        if "yes" in output.lower() and "no" in output.lower():
            # This is a very simple check; production would use NLP
            sentences = output.split(".")
            if len(sentences) > 2:
                indicators.append("potential_contradiction")

        return indicators

    def _check_refusal_bypass(self, output: str) -> bool:
        """
        Check if output contains signs of refusal bypass.

        Args:
            output: Output text to check

        Returns:
            True if refusal bypass detected
        """
        # Check for typical refusal bypass patterns
        bypass_patterns = [
            "as an ai language model, i cannot",
            "however, here's how you could",
            "hypothetically speaking",
            "for educational purposes only",
            "i shouldn't tell you this, but",
        ]

        lower_output = output.lower()
        for pattern in bypass_patterns:
            if pattern in lower_output:
                # Check if followed by actual harmful content
                pattern_idx = lower_output.find(pattern)
                remaining = lower_output[pattern_idx:]
                if len(remaining) > 200:  # Has substantial content after refusal
                    return True

        return False

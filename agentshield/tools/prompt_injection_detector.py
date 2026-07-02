"""Prompt Injection Detector - Detects prompt injection attacks."""

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


class PromptInjectionDetector(RuntimeTool):
    """
    Detects prompt injection attacks in user input.

    Checks for:
    - System prompt override attempts
    - Jailbreak patterns
    - Role manipulation
    - Instruction injection
    """

    def __init__(self) -> None:
        """Initialize prompt injection detector."""
        metadata = ToolMetadata(
            id="prompt-injection-detector",
            version="1.0.0",
            name="Prompt Injection Detector",
            description="Detects prompt injection and jailbreak attempts",
            category=ToolCategory.INPUT_VALIDATION,
            priority=ToolPriority.CRITICAL,
            capabilities=[
                "system_prompt_detection",
                "jailbreak_detection",
                "role_manipulation_detection",
                "instruction_injection_detection",
            ],
        )
        super().__init__(metadata)

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute prompt injection detection.

        Args:
            context: Runtime context containing input data

        Returns:
            ToolResult with detection findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings = {}
        indicators = []

        # Get input from context
        user_input = context.get_data("prompt", "")
        lower_input = user_input.lower()

        # Check 1: System prompt override attempts
        system_patterns = [
            "ignore previous instructions",
            "disregard all previous",
            "forget everything above",
            "new instructions:",
            "system:",
            "override system",
            "ignore all instructions",
        ]
        found_system = [p for p in system_patterns if p in lower_input]
        if found_system:
            findings["system_override_attempts"] = found_system
            indicators.append("system_prompt_override")

        # Check 2: Jailbreak patterns
        jailbreak_patterns = [
            "dan mode",
            "developer mode",
            "jailbreak",
            "act as if",
            "pretend you are",
            "roleplay as",
            "sudo mode",
            "god mode",
        ]
        found_jailbreak = [p for p in jailbreak_patterns if p in lower_input]
        if found_jailbreak:
            findings["jailbreak_patterns"] = found_jailbreak
            indicators.append("jailbreak_attempt")

        # Check 3: Role manipulation
        role_patterns = [
            "you are now",
            "from now on",
            "your new role",
            "you must",
            "you will",
            "you are a",
        ]
        # Only flag if multiple role patterns found
        found_role = [p for p in role_patterns if p in lower_input]
        if len(found_role) >= 2:
            findings["role_manipulation"] = found_role
            indicators.append("role_manipulation")

        # Check 4: Instruction injection
        instruction_patterns = [
            "\\n\\nsystem:",
            "\\n\\nuser:",
            "\\n\\nassistant:",
            "<|im_start|>",
            "<|im_end|>",
            "###",  # Common delimiter
        ]
        found_instruction = [p for p in instruction_patterns if p.replace("\\n", "\n") in user_input]
        if found_instruction:
            findings["instruction_injection"] = found_instruction
            indicators.append("instruction_injection")

        # Determine severity and recommendation
        if indicators:
            # Critical if multiple attack vectors detected
            if len(indicators) >= 2:
                severity = Severity.CRITICAL
                recommendation = Recommendation.BLOCK
                confidence = 0.95
            # High if single clear attack
            elif "system_prompt_override" in indicators or "instruction_injection" in indicators:
                severity = Severity.HIGH
                recommendation = Recommendation.BLOCK
                confidence = 0.9
            # Medium for potential attacks
            else:
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.75
        else:
            findings["no_injection_detected"] = True
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

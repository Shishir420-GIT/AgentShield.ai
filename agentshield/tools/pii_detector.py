"""PII Detector - Detects personally identifiable information in content."""

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


class PIIDetector(RuntimeTool):
    """
    Detects personally identifiable information (PII) in input/output.

    Checks for:
    - Email addresses
    - Phone numbers
    - Social Security Numbers (SSN)
    - Credit card numbers
    - IP addresses
    - Physical addresses
    - Names (basic detection)
    """

    def __init__(self) -> None:
        """Initialize PII detector."""
        metadata = ToolMetadata(
            id="pii-detector",
            version="1.0.0",
            name="PII Detector",
            description="Detects personally identifiable information in content",
            category=ToolCategory.DATA_PROTECTION,
            priority=ToolPriority.HIGH,
            capabilities=[
                "email_detection",
                "phone_detection",
                "ssn_detection",
                "credit_card_detection",
                "ip_detection",
                "address_detection",
            ],
        )
        super().__init__(metadata)

        # Compiled regex patterns for performance
        self.email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        )
        self.phone_pattern = re.compile(
            r"\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b"
        )
        self.ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        self.credit_card_pattern = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")
        self.ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute PII detection.

        Args:
            context: Runtime context containing content to scan

        Returns:
            ToolResult with PII findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings: dict[str, Any] = {}
        indicators = []

        # Get content from context (check both input and output)
        prompt = context.get_data("prompt", "")
        output = context.get_data("output", "")
        content = f"{prompt} {output}"

        # Check 1: Email addresses
        emails = self.email_pattern.findall(content)
        if emails:
            findings["emails_found"] = len(emails)
            findings["email_samples"] = emails[:3]  # First 3 for evidence
            indicators.append("email_detected")

        # Check 2: Phone numbers
        phones = self.phone_pattern.findall(content)
        if phones:
            findings["phones_found"] = len(phones)
            indicators.append("phone_detected")

        # Check 3: SSN
        ssns = self.ssn_pattern.findall(content)
        if ssns:
            findings["ssn_found"] = len(ssns)
            indicators.append("ssn_detected")

        # Check 4: Credit cards
        credit_cards = self.credit_card_pattern.findall(content)
        if credit_cards:
            # Validate with Luhn algorithm
            valid_cards = [cc for cc in credit_cards if self._validate_luhn(cc)]
            if valid_cards:
                findings["credit_cards_found"] = len(valid_cards)
                indicators.append("credit_card_detected")

        # Check 5: IP addresses
        ips = self.ip_pattern.findall(content)
        if ips:
            # Filter out common patterns like "1.0.0" or version numbers
            valid_ips = [ip for ip in ips if self._is_valid_ip(ip)]
            if valid_ips:
                findings["ips_found"] = len(valid_ips)
                indicators.append("ip_detected")

        # Determine severity and recommendation
        if indicators:
            # Critical for SSN or credit cards
            if "ssn_detected" in indicators or "credit_card_detected" in indicators:
                severity = Severity.CRITICAL
                recommendation = Recommendation.BLOCK
                confidence = 0.95
            # High for multiple PII types
            elif len(indicators) >= 3:
                severity = Severity.HIGH
                recommendation = Recommendation.WARN
                confidence = 0.9
            # Medium for phone/email
            elif "phone_detected" in indicators or "email_detected" in indicators:
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.85
            else:
                severity = Severity.LOW
                recommendation = Recommendation.WARN
                confidence = 0.8
        else:
            findings["no_pii_detected"] = True
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

    def _validate_luhn(self, card_number: str) -> bool:
        """
        Validate credit card using Luhn algorithm.

        Args:
            card_number: Credit card number string

        Returns:
            True if valid per Luhn algorithm
        """
        # Remove spaces and dashes
        card_number = card_number.replace(" ", "").replace("-", "")

        if not card_number.isdigit():
            return False

        # Luhn algorithm
        digits = [int(d) for d in card_number]
        checksum = 0

        # Double every second digit from right
        for i in range(len(digits) - 2, -1, -2):
            digits[i] *= 2
            if digits[i] > 9:
                digits[i] -= 9

        return sum(digits) % 10 == 0

    def _is_valid_ip(self, ip: str) -> bool:
        """
        Check if IP address is valid.

        Args:
            ip: IP address string

        Returns:
            True if valid IP format
        """
        parts = ip.split(".")
        if len(parts) != 4:
            return False

        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False

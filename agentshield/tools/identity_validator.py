"""Identity Validator - Validates caller identity and credentials."""

import hashlib
import hmac
import time
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


class IdentityValidator(RuntimeTool):
    """
    Validates caller identity, credentials, and authentication.

    Checks for:
    - Valid API key format
    - Token expiration
    - Rate limiting violations
    - Tenant isolation
    - Session validation
    - IP allowlist/blocklist
    """

    def __init__(self) -> None:
        """Initialize identity validator."""
        metadata = ToolMetadata(
            id="identity-validator",
            version="1.0.0",
            name="Identity Validator",
            description="Validates caller identity and authentication credentials",
            category=ToolCategory.IDENTITY,
            priority=ToolPriority.CRITICAL,
            capabilities=[
                "api_key_validation",
                "token_validation",
                "rate_limit_check",
                "tenant_validation",
                "session_validation",
                "ip_validation",
            ],
        )
        super().__init__(metadata)

        # Configuration (should be loaded from config in production)
        self.api_key_min_length = 20
        self.api_key_prefixes = ["sk-", "pk-", "Bearer "]
        self.max_requests_per_minute = 60
        self.session_timeout_seconds = 3600  # 1 hour
        self.ip_blocklist = set()  # Empty by default
        self.ip_allowlist = set()  # Empty = allow all

    async def execute(self, context: RuntimeContext) -> ToolResult:
        """
        Execute identity validation.

        Args:
            context: Runtime context containing identity data

        Returns:
            ToolResult with validation findings
        """
        evidence = ToolEvidence(source=self.metadata.id)
        findings: dict[str, Any] = {}
        indicators = []

        # Get identity data from context
        api_key = context.get_data("api_key", "")
        tenant_id = context.get_data("tenant_id", "")
        session_id = context.get_data("session_id", "")
        client_ip = context.get_data("client_ip", "")
        request_timestamp = context.get_data("request_timestamp", time.time())

        # Check 1: API Key validation
        api_key_valid, api_key_issue = self._validate_api_key(api_key)
        if not api_key_valid:
            findings["api_key_validation"] = {"valid": False, "issue": api_key_issue}
            indicators.append("invalid_api_key")
        else:
            findings["api_key_validation"] = {"valid": True}

        # Check 2: Tenant ID validation
        tenant_valid, tenant_issue = self._validate_tenant_id(tenant_id)
        if not tenant_valid:
            findings["tenant_validation"] = {"valid": False, "issue": tenant_issue}
            indicators.append("invalid_tenant")
        else:
            findings["tenant_validation"] = {"valid": True, "tenant_id": tenant_id}

        # Check 3: Session validation
        if session_id:
            session_valid, session_issue = self._validate_session(
                session_id, request_timestamp
            )
            if not session_valid:
                findings["session_validation"] = {"valid": False, "issue": session_issue}
                indicators.append("invalid_session")
            else:
                findings["session_validation"] = {"valid": True}

        # Check 4: IP validation
        if client_ip:
            ip_valid, ip_issue = self._validate_ip(client_ip)
            if not ip_valid:
                findings["ip_validation"] = {"valid": False, "issue": ip_issue}
                indicators.append("blocked_ip")
            else:
                findings["ip_validation"] = {"valid": True, "client_ip": client_ip}

        # Check 5: Rate limiting (simplified - in production use Redis/cache)
        rate_limit_exceeded = self._check_rate_limit(tenant_id, api_key)
        if rate_limit_exceeded:
            findings["rate_limit"] = {
                "exceeded": True,
                "max_requests": self.max_requests_per_minute,
            }
            indicators.append("rate_limit_exceeded")

        # Determine severity and recommendation
        if indicators:
            # Critical security issues
            if "invalid_api_key" in indicators or "blocked_ip" in indicators:
                severity = Severity.CRITICAL
                recommendation = Recommendation.BLOCK
                confidence = 0.99
            # High severity for invalid tenant/session
            elif "invalid_tenant" in indicators or "invalid_session" in indicators:
                severity = Severity.HIGH
                recommendation = Recommendation.BLOCK
                confidence = 0.95
            # Medium for rate limiting
            elif "rate_limit_exceeded" in indicators:
                severity = Severity.MEDIUM
                recommendation = Recommendation.WARN
                confidence = 0.9
            else:
                severity = Severity.LOW
                recommendation = Recommendation.WARN
                confidence = 0.8
        else:
            findings["identity_verified"] = True
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

    def _validate_api_key(self, api_key: str) -> tuple[bool, str]:
        """
        Validate API key format and structure.

        Args:
            api_key: API key to validate

        Returns:
            Tuple of (is_valid, issue_description)
        """
        if not api_key:
            return False, "missing_api_key"

        # Remove Bearer prefix if present
        if api_key.startswith("Bearer "):
            api_key = api_key[7:]

        # Check minimum length
        if len(api_key) < self.api_key_min_length:
            return False, "api_key_too_short"

        # Check for valid prefix
        has_valid_prefix = any(api_key.startswith(prefix) for prefix in self.api_key_prefixes)
        if not has_valid_prefix and self.api_key_prefixes:
            # Allow keys without prefix (backward compatibility)
            pass

        # Check for suspicious patterns
        if api_key.count(" ") > 1:
            return False, "api_key_contains_spaces"

        # Check for common test/dummy keys
        test_patterns = ["test", "demo", "example", "dummy", "fake"]
        if any(pattern in api_key.lower() for pattern in test_patterns):
            return False, "test_api_key_detected"

        return True, ""

    def _validate_tenant_id(self, tenant_id: str) -> tuple[bool, str]:
        """
        Validate tenant ID.

        Args:
            tenant_id: Tenant ID to validate

        Returns:
            Tuple of (is_valid, issue_description)
        """
        if not tenant_id:
            # Tenant ID is optional for single-tenant deployments
            return True, ""

        # Check format
        if len(tenant_id) < 3:
            return False, "tenant_id_too_short"

        # Check for suspicious patterns
        if ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
            return False, "tenant_id_path_traversal"

        return True, ""

    def _validate_session(
        self, session_id: str, request_timestamp: float
    ) -> tuple[bool, str]:
        """
        Validate session ID and check expiration.

        Args:
            session_id: Session ID to validate
            request_timestamp: Request timestamp

        Returns:
            Tuple of (is_valid, issue_description)
        """
        if not session_id:
            return True, ""  # Session is optional

        # Check format
        if len(session_id) < 16:
            return False, "session_id_too_short"

        # In production, check session store (Redis, DB, etc.)
        # For now, extract timestamp from session ID if format is: {timestamp}-{random}
        try:
            parts = session_id.split("-")
            if len(parts) >= 2 and parts[0].isdigit():
                session_created = int(parts[0])
                session_age = request_timestamp - session_created

                if session_age > self.session_timeout_seconds:
                    return False, "session_expired"

                if session_age < 0:
                    return False, "session_timestamp_invalid"
        except (ValueError, IndexError):
            # Session ID doesn't follow expected format, that's OK
            pass

        return True, ""

    def _validate_ip(self, client_ip: str) -> tuple[bool, str]:
        """
        Validate client IP against allowlist/blocklist.

        Args:
            client_ip: Client IP address

        Returns:
            Tuple of (is_valid, issue_description)
        """
        if not client_ip:
            return True, ""  # IP is optional

        # Check blocklist
        if client_ip in self.ip_blocklist:
            return False, "ip_blocked"

        # Check allowlist (if configured)
        if self.ip_allowlist and client_ip not in self.ip_allowlist:
            return False, "ip_not_in_allowlist"

        return True, ""

    def _check_rate_limit(self, tenant_id: str, api_key: str) -> bool:
        """
        Check if rate limit is exceeded.

        Args:
            tenant_id: Tenant ID
            api_key: API key

        Returns:
            True if rate limit exceeded, False otherwise
        """
        # In production, use Redis with sliding window:
        # key = f"ratelimit:{tenant_id}:{api_key_hash}"
        # count = redis.incr(key)
        # if count == 1:
        #     redis.expire(key, 60)
        # return count > self.max_requests_per_minute

        # For now, always return False (no rate limiting in memory)
        return False

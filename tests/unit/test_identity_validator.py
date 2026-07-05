"""Tests for Identity Validator tool."""

import time
import pytest

from agentshield.core.context import RuntimeContext, RuntimePhase
from agentshield.core.tool_sdk import Recommendation, Severity
from agentshield.tools.identity_validator import IdentityValidator


class TestIdentityValidator:
    """Test identity validation tool."""

    @pytest.fixture
    def validator(self):
        """Create identity validator instance."""
        return IdentityValidator()

    @pytest.fixture
    def context(self):
        """Create runtime context."""
        return RuntimeContext(tenant_id="test-tenant")

    @pytest.mark.asyncio
    async def test_validator_initialization(self, validator):
        """Test validator initializes correctly."""
        assert validator.metadata.id == "identity-validator"
        assert validator.metadata.version == "1.0.0"
        assert "api_key_validation" in validator.metadata.capabilities

    @pytest.mark.asyncio
    async def test_valid_api_key_passes(self, validator, context):
        """Test that valid API key passes validation."""
        context.set_data("api_key", "sk-1234567890abcdefghijklmnopqrstuvwxyz")
        context.set_data("tenant_id", "tenant-123")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.ALLOW
        assert result.severity == Severity.INFO
        assert result.evidence.findings["api_key_validation"]["valid"] is True
        assert result.evidence.findings["identity_verified"] is True

    @pytest.mark.asyncio
    async def test_missing_api_key_blocked(self, validator, context):
        """Test that missing API key is blocked."""
        context.set_data("api_key", "")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert result.severity == Severity.CRITICAL
        assert "invalid_api_key" in result.evidence.indicators
        assert result.evidence.findings["api_key_validation"]["valid"] is False

    @pytest.mark.asyncio
    async def test_short_api_key_blocked(self, validator, context):
        """Test that short API key is blocked."""
        context.set_data("api_key", "sk-short")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert result.severity == Severity.CRITICAL
        assert "invalid_api_key" in result.evidence.indicators

    @pytest.mark.asyncio
    async def test_test_api_key_blocked(self, validator, context):
        """Test that test/demo API keys are blocked."""
        context.set_data("api_key", "sk-test1234567890abcdefghij")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert "invalid_api_key" in result.evidence.indicators

    @pytest.mark.asyncio
    async def test_valid_tenant_id(self, validator, context):
        """Test that valid tenant ID passes."""
        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.set_data("tenant_id", "tenant-123")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.ALLOW
        assert result.evidence.findings["tenant_validation"]["valid"] is True

    @pytest.mark.asyncio
    async def test_path_traversal_tenant_blocked(self, validator, context):
        """Test that tenant ID with path traversal is blocked."""
        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.set_data("tenant_id", "../../../etc/passwd")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert "invalid_tenant" in result.evidence.indicators

    @pytest.mark.asyncio
    async def test_valid_session(self, validator, context):
        """Test that valid session passes."""
        current_time = time.time()
        session_id = f"{int(current_time)}-abc123def456"

        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.set_data("session_id", session_id)
        context.set_data("request_timestamp", current_time)
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.ALLOW
        assert result.evidence.findings["session_validation"]["valid"] is True

    @pytest.mark.asyncio
    async def test_expired_session_blocked(self, validator, context):
        """Test that expired session is blocked."""
        current_time = time.time()
        # Create session from 2 hours ago (timeout is 1 hour)
        old_time = current_time - 7200
        session_id = f"{int(old_time)}-abc123def456"

        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.set_data("session_id", session_id)
        context.set_data("request_timestamp", current_time)
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert "invalid_session" in result.evidence.indicators

    @pytest.mark.asyncio
    async def test_valid_ip_passes(self, validator, context):
        """Test that valid IP passes."""
        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.set_data("client_ip", "192.168.1.1")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.ALLOW
        assert result.evidence.findings["ip_validation"]["valid"] is True

    @pytest.mark.asyncio
    async def test_blocked_ip(self, validator, context):
        """Test that blocked IP is rejected."""
        # Add IP to blocklist
        validator.ip_blocklist.add("10.0.0.1")

        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.set_data("client_ip", "10.0.0.1")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert result.severity == Severity.CRITICAL
        assert "blocked_ip" in result.evidence.indicators

    @pytest.mark.asyncio
    async def test_ip_not_in_allowlist(self, validator, context):
        """Test that IP not in allowlist is blocked."""
        # Configure allowlist
        validator.ip_allowlist.add("192.168.1.1")

        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.set_data("client_ip", "10.0.0.1")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert "blocked_ip" in result.evidence.indicators

    @pytest.mark.asyncio
    async def test_bearer_token_format(self, validator, context):
        """Test that Bearer token format is handled."""
        context.set_data("api_key", "Bearer sk-validkey1234567890abcd")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.ALLOW
        assert result.evidence.findings["api_key_validation"]["valid"] is True

    @pytest.mark.asyncio
    async def test_multiple_validation_failures(self, validator, context):
        """Test multiple validation failures."""
        validator.ip_blocklist.add("10.0.0.1")

        context.set_data("api_key", "short")  # Too short
        context.set_data("tenant_id", "../etc")  # Path traversal
        context.set_data("client_ip", "10.0.0.1")  # Blocked
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.BLOCK
        assert result.severity == Severity.CRITICAL
        assert len(result.evidence.indicators) >= 2

    @pytest.mark.asyncio
    async def test_optional_fields(self, validator, context):
        """Test that optional fields don't cause failures."""
        # Only API key required, others optional
        context.set_data("api_key", "sk-validkey1234567890abcd")
        context.advance_phase(RuntimePhase.IDENTITY)

        result = await validator.execute(context)

        assert result.recommendation == Recommendation.ALLOW
        assert result.severity == Severity.INFO

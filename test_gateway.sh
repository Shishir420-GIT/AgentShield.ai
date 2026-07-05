#!/bin/bash
# Quick test script for AgentShield Gateway

echo "🧪 Testing AgentShield Gateway..."
echo ""

# Test 1: Health check
echo "1️⃣  Testing health endpoint..."
curl -s http://localhost:8000/health | python3 -m json.tool
echo ""
echo ""

# Test 2: Metrics
echo "2️⃣  Testing metrics endpoint..."
curl -s http://localhost:8000/metrics | head -20
echo ""
echo "... (truncated)"
echo ""

# Test 3: Chat completion (requires AGENTSHIELD_BACKEND_API_KEY env var)
if [ -n "$AGENTSHIELD_BACKEND_API_KEY" ]; then
    echo "3️⃣  Testing chat completions endpoint..."
    curl -s -X POST http://localhost:8000/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $AGENTSHIELD_BACKEND_API_KEY" \
      -d '{
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Say hello in one word"}]
      }' | python3 -m json.tool
    echo ""
else
    echo "3️⃣  Skipping chat test (set AGENTSHIELD_BACKEND_API_KEY to test)"
fi

echo ""
echo "✅ All tests complete!"

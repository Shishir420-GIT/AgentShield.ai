# AgentShield Docker Image
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim as builder

# Install uv for fast package management
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -e ".[production]"

# Runtime stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 agentshield

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY agentshield/ ./agentshield/

# Change ownership to non-root user
RUN chown -R agentshield:agentshield /app

# Switch to non-root user
USER agentshield

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV AGENTSHIELD_PORT=8000
ENV AGENTSHIELD_HOST=0.0.0.0

# Run the application
CMD ["python", "-m", "agentshield"]

# AgentShield Deployment Guide

Complete guide for deploying AgentShield in production.

## Table of Contents

- [Docker Deployment](#docker-deployment)
- [Docker Compose](#docker-compose)
- [Kubernetes](#kubernetes)
- [Environment Variables](#environment-variables)
- [Monitoring](#monitoring)
- [Security Best Practices](#security-best-practices)

## Docker Deployment

### Quick Start

```bash
# 1. Build the image
docker build -t agentshield:latest .

# 2. Run the container
docker run -d \
  --name agentshield \
  -p 8000:8000 \
  -e AGENTSHIELD_BACKEND_API_KEY="sk-your-openai-key" \
  agentshield:latest

# 3. Verify it's running
curl http://localhost:8000/health
```

### With Audit Logs

```bash
docker run -d \
  --name agentshield \
  -p 8000:8000 \
  -e AGENTSHIELD_BACKEND_API_KEY="sk-your-openai-key" \
  -v $(pwd)/audit_logs:/app/audit_logs \
  agentshield:latest
```

## Docker Compose

### Basic Deployment

```bash
# 1. Create .env file
cat > .env << EOF
AGENTSHIELD_BACKEND_API_KEY=sk-your-openai-key
AGENTSHIELD_LOG_LEVEL=INFO
EOF

# 2. Start services
docker-compose up -d

# 3. Check logs
docker-compose logs -f agentshield

# 4. Stop services
docker-compose down
```

### With Monitoring Stack

```bash
# Start with Prometheus and Grafana
docker-compose --profile monitoring up -d

# Access services:
# - AgentShield: http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Production Configuration

Create a `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  agentshield:
    image: agentshield:latest
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
      restart_policy:
        condition: on-failure
        max_attempts: 3
    environment:
      - AGENTSHIELD_BACKEND_API_KEY=${AGENTSHIELD_BACKEND_API_KEY}
      - AGENTSHIELD_LOG_LEVEL=WARNING
    volumes:
      - audit_logs:/app/audit_logs
    networks:
      - agentshield-network

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - agentshield
    networks:
      - agentshield-network

networks:
  agentshield-network:
    driver: overlay

volumes:
  audit_logs:
```

Run with:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Kubernetes

### Basic Deployment

```yaml
# agentshield-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentshield
  namespace: ai-security
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentshield
  template:
    metadata:
      labels:
        app: agentshield
    spec:
      containers:
      - name: agentshield
        image: agentshield:latest
        ports:
        - containerPort: 8000
        env:
        - name: AGENTSHIELD_BACKEND_API_KEY
          valueFrom:
            secretKeyRef:
              name: agentshield-secrets
              key: backend-api-key
        - name: AGENTSHIELD_LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: agentshield-service
  namespace: ai-security
spec:
  selector:
    app: agentshield
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: v1
kind: Secret
metadata:
  name: agentshield-secrets
  namespace: ai-security
type: Opaque
stringData:
  backend-api-key: "sk-your-openai-key"
```

Deploy:

```bash
# Create namespace
kubectl create namespace ai-security

# Apply configuration
kubectl apply -f agentshield-deployment.yaml

# Check status
kubectl get pods -n ai-security
kubectl get svc -n ai-security

# View logs
kubectl logs -f deployment/agentshield -n ai-security
```

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agentshield-hpa
  namespace: ai-security
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agentshield
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `AGENTSHIELD_BACKEND_API_KEY` | Backend LLM API key | `sk-...` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTSHIELD_PORT` | Server port | `8000` |
| `AGENTSHIELD_HOST` | Server host | `0.0.0.0` |
| `AGENTSHIELD_LOG_LEVEL` | Logging level | `INFO` |
| `AGENTSHIELD_BACKEND_URL` | Backend API URL | `https://api.openai.com/v1` |
| `AGENTSHIELD_DEFAULT_TENANT` | Default tenant ID | `default` |
| `AGENTSHIELD_MAX_WORKERS` | Worker processes | `4` |

## Monitoring

### Prometheus Metrics

AgentShield exposes metrics at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

Key metrics:
- `agentshield_requests_total` - Total requests processed
- `agentshield_requests_blocked_total` - Blocked requests
- `agentshield_request_duration_seconds` - Request latency
- `agentshield_security_tool_duration_seconds` - Tool execution time

### Grafana Dashboard

Import the dashboard template:

1. Access Grafana: `http://localhost:3000`
2. Add Prometheus data source: `http://prometheus:9090`
3. Import dashboard from `grafana-dashboard.json`

### Health Checks

```bash
# Health endpoint
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime": 3600.5
}
```

## Security Best Practices

### 1. API Key Management

**Never hardcode API keys!** Use environment variables or secrets management:

```bash
# Docker Secrets
echo "sk-your-key" | docker secret create backend_api_key -

# Kubernetes Secrets
kubectl create secret generic agentshield-secrets \
  --from-literal=backend-api-key=sk-your-key \
  -n ai-security

# AWS Secrets Manager
aws secretsmanager create-secret \
  --name agentshield/backend-api-key \
  --secret-string "sk-your-key"
```

### 2. Network Security

```nginx
# nginx.conf - TLS termination
server {
    listen 443 ssl http2;
    server_name agentshield.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://agentshield:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Resource Limits

Always set resource limits:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

### 4. Multi-Tenancy

Use tenant IDs to isolate customers:

```python
from agentshield.sdk import AgentShieldClient

client = AgentShieldClient(
    api_key="sk-...",
    gateway_url="https://agentshield.example.com",
    tenant_id="customer-123"  # Isolates this customer's data
)
```

### 5. Audit Logs

Enable audit logging for compliance:

```bash
# Mount persistent volume for audit logs
docker run -d \
  -v /var/log/agentshield:/app/audit_logs \
  agentshield:latest
```

Logs are JSON formatted:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "tenant_id": "customer-123",
  "action": "block",
  "severity": "high",
  "indicators": ["prompt_injection"],
  "correlation_id": "req-abc-123"
}
```

### 6. Rate Limiting

Add rate limiting at the load balancer or API gateway level:

```nginx
# nginx rate limiting
limit_req_zone $binary_remote_addr zone=agentshield:10m rate=10r/s;

server {
    location / {
        limit_req zone=agentshield burst=20 nodelay;
        proxy_pass http://agentshield:8000;
    }
}
```

## Production Checklist

- [ ] TLS/SSL certificates configured
- [ ] API keys stored in secrets manager
- [ ] Resource limits set
- [ ] Monitoring and alerting configured
- [ ] Audit logs enabled and backed up
- [ ] Rate limiting configured
- [ ] Health checks working
- [ ] Auto-scaling configured
- [ ] Disaster recovery plan documented
- [ ] Security policies reviewed

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs agentshield

# Common issues:
# 1. Missing AGENTSHIELD_BACKEND_API_KEY
# 2. Port 8000 already in use
# 3. Insufficient memory
```

### High latency

```bash
# Check metrics
curl http://localhost:8000/metrics | grep duration

# Solutions:
# 1. Increase replicas
# 2. Add more CPU/memory
# 3. Enable caching
# 4. Review security tool configuration
```

### Requests being blocked incorrectly

```bash
# Check audit logs
docker exec agentshield cat /app/audit_logs/latest.jsonl

# Adjust policies if needed
# See docs/POLICIES.md
```

## Support

For deployment issues:
- GitHub: https://github.com/your-org/agentshield/issues
- Email: shishir.workemail@gmail.com
- Docs: https://docs.agentshield.dev

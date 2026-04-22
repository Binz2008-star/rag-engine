# LLM Gateway Service

Production-grade LLM gateway with caching, rate limiting, circuit breaker, and observability.

## Features

- **Async FastAPI**: High-performance async API
- **Redis Caching**: Token-aware caching with hash-based keys
- **Rate Limiting**: Token bucket algorithm via Redis
- **Circuit Breaker**: Fault tolerance with auto-recovery
- **Retry Logic**: Exponential backoff with jitter
- **Streaming**: First-class SSE support
- **Metrics**: Prometheus integration
- **Structured Logging**: JSON logs for observability
- **Provider Abstraction**: Easy to swap OpenAI for other providers

## Architecture

```
/app
  /api          -> FastAPI routes
  /core         -> config, logging
  /services     -> LLM orchestration, rate limiting, circuit breaker
  /providers    -> OpenAI provider
  /cache        -> Redis layer
  /schemas      -> Pydantic models
```

## Quick Start

### Docker Compose (Recommended)

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your OpenAI API key
# OPENAI_API_KEY=your_key_here

# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/api/v1/health
```

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=your_key_here

# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Run gateway
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Health Check
```bash
GET /api/v1/health
```

### Generate Completion (Non-Streaming)
```bash
POST /api/v1/generate
Content-Type: application/json
X-API-Key: your_api_key (optional)

{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "temperature": 0.7,
  "stream": false
}
```

### Stream Completion
```bash
POST /api/v1/stream
Content-Type: application/json
X-API-Key: your_api_key (optional)

{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "temperature": 0.7,
  "stream": true
}
```

### Rate Limit Check
```bash
POST /api/v1/rate-limit/check
Content-Type: application/json

{
  "identifier": "api_key:your_key"
}
```

### Metrics (Prometheus)
```bash
GET /metrics
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | required | OpenAI API key |
| `MODEL` | gpt-4o-mini | Default model |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection URL |
| `CACHE_TTL` | 300 | Cache TTL in seconds |
| `RATE_LIMIT_REQUESTS` | 100 | Requests per window |
| `RATE_LIMIT_WINDOW` | 60 | Window size in seconds |
| `CIRCUIT_BREAKER_THRESHOLD` | 5 | Failures before opening |
| `CIRCUIT_BREAKER_TIMEOUT` | 60 | Recovery timeout in seconds |
| `METRICS_ENABLED` | true | Enable Prometheus metrics |

## Rate Limiting

- Uses token bucket algorithm
- Defaults: 100 requests per 60 seconds
- Per-client limiting via API key or IP
- Fail-open on Redis errors

## Circuit Breaker

- Opens after 5 consecutive failures
- Auto-recovers after 60 seconds
- Half-open state for testing
- Prevents cascade failures

## Metrics

Prometheus metrics exposed at `/metrics`:

- `llm_requests_total`: Total requests by model/method
- `llm_requests_cached`: Cache hits
- `llm_request_duration_seconds`: Request latency
- `llm_errors_total`: Errors by type
- `circuit_breaker_state`: Circuit state
- `circuit_breaker_failures`: Failure count
- `rate_limit_requests`: Remaining requests

## Production Deployment

### Docker Build
```bash
docker build -t llm-gateway .
docker run -p 8000:8000 --env-file .env llm-gateway
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-gateway
  template:
    metadata:
      labels:
        app: llm-gateway
    spec:
      containers:
      - name: gateway
        image: llm-gateway:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
```

## Monitoring

- **Logs**: Structured JSON logs to stdout
- **Metrics**: Prometheus at `/metrics`
- **Health**: `/api/v1/health` endpoint
- **Circuit State**: Available in metrics

## Why This Architecture

1. **Centralized LLM calls**: Single point for observability and control
2. **Cost reduction**: Caching reduces token usage by 30-50%
3. **Reliability**: Circuit breaker prevents cascade failures
4. **Scalability**: Stateless design, horizontal scaling ready
5. **Observability**: Metrics and logging for production monitoring

## Next Steps

- Add authentication layer (JWT/OAuth)
- Add request/response logging
- Add A/B testing for model comparison
- Add semantic caching (vector similarity)
- Add multi-provider support (Anthropic, local)

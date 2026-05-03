# Production-Grade Rate Limiting Setup

## Environment Variables

### Production-Grade (Redis with Lua Scripts)

```bash
# Required for atomic rate limiting
REDIS_URL=redis://username:password@host:port

# Example: Redis Cloud
REDIS_URL=redis://default:password@redis-12345.cloud.redislabs.com:12345

# Example: Local Redis
REDIS_URL=redis://localhost:6379
```

### Best-Effort (Upstash REST API)

```bash
# Fallback when Redis not available
UPSTASH_REDIS_REST_URL=https://your-project.upstash.io/redis
UPSTASH_REDIS_REST_TOKEN=your-upstash-token
```

## Store Priority

The system automatically selects the best available store:

1. **Redis with Lua Scripts** (Production-grade)
   - True atomicity
   - No race conditions
   - Strict limit enforcement

2. **Upstash REST API** (Best-effort)
   - Known race conditions
   - Suitable for non-critical endpoints
   - Cross-instance consistency

3. **Memory Store** (Development)
   - Per-instance only
   - Not cross-instance consistent
   - Development/testing

## Configuration Examples

### Production Setup

```bash
# .env.production
REDIS_URL=redis://username:password@redis.example.com:6379
NODE_ENV=production
```

### Staging Setup

```bash
# .env.staging
REDIS_URL=redis://staging-redis.example.com:6379
NODE_ENV=staging
```

### Development Setup

```bash
# .env.development
# No Redis URL needed - uses memory store
NODE_ENV=development
```

## Testing Atomicity

### Production-Grade Test

```bash
# Test Redis atomicity under high concurrency
npm run test:production-rate-limiting

# Requires Redis running locally:
# docker run -d -p 6379:6379 redis:latest
```

### Best-Effort Test

```bash
# Test Upstash fallback behavior
UPSTASH_REDIS_REST_URL=https://your-project.upstash.io/redis \
UPSTASH_REDIS_REST_TOKEN=your-token \
npm run test
```

## Monitoring

### Key Metrics to Monitor

- Rate limit hit rate
- Redis connection failures
- Fallback activation frequency
- Cross-instance divergence (if using memory fallback)

### Log Patterns

```bash
# Production-grade Redis
"Using Redis with Lua scripts for production-grade rate limiting"

# Best-effort Upstash
"Using Upstash REST API - best-effort rate limiting with known race conditions"

# Fallback activation
"Rate limiting fallback activated"
```

## Deployment Notes

### Required Dependencies

- `redis@5.11.0` (already installed)
- Redis server (external or managed)

### Recommended Redis Configuration

```redis.conf
# Enable persistence (optional but recommended)
save 900 1
save 300 10
save 60 10000

# Memory management
maxmemory 256mb
maxmemory-policy allkeys-lru

# Connection settings
timeout 300
tcp-keepalive 60
```

## Failure Scenarios

### Redis Unavailable

- System falls back to Upstash or memory store
- Logs fallback activation
- Maintains service availability

### Upstash Unavailable

- System falls back to memory store
- Per-instance rate limiting (documented limitation)

### Network Issues

- Automatic reconnection attempts
- Graceful degradation
- Comprehensive error logging

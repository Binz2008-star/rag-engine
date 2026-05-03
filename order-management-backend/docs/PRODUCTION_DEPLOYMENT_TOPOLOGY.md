# Production Deployment Topology

## Overview

This document defines the complete production deployment architecture for the three-boundary system.

---

# Architecture Diagram

```
                    Internet Traffic
                           |
                    CDN (CloudFlare)
                           |
                +-------------------+
                |   Load Balancer    |
                +-------------------+
                           |
            +-------------------------------+
            |                               |
    +---------------+               +---------------+
    |   Vercel      |               |    Render     |
    | seller-dashboard|               | Platform Layer|
    | (Next.js)      |               |   (sellora)   |
    +---------------+               +---------------+
            |                               |
            |                               |
    +---------------+               +---------------+
    |   Render      |               |    Render     |
    | Runtime Core  |               | Platform API  |
    | (order-mgmt)  |               +---------------+
    +---------------+                       |
            |                               |
            +-------------------------------+
                           |
                    +-------------------+
                    |   Neon PostgreSQL  |
                    |   Primary Cluster  |
                    +-------------------+
                           |
                    +-------------------+
                    |     Redis Cache    |
                    |   (Upstash/Redis)  |
                    +-------------------+
```

---

# Environment Configuration

## Production Environment Variables

### Runtime Core (order-management-backend)
```bash
# Database
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/db?sslmode=require
DATABASE_POOL_MIN=2
DATABASE_POOL_MAX=10

# Authentication
JWT_SECRET=super-secure-256-bit-secret-key-minimum-length
JWT_EXPIRES_IN=7d

# Rate Limiting
REDIS_URL=redis://user:pass@xxx.upstash.io:6380
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=secure-token

# API Configuration
NODE_ENV=production
PORT=3000
API_BASE_URL=https://api.order-management.com

# Platform Communication
PLATFORM_API_URL=https://api.sellora.com
PLATFORM_API_TOKEN=delegated-token

# Monitoring
LOG_LEVEL=info
SENTRY_DSN=https://xxx@sentry.io/xxx

# Webhooks
STRIPE_WEBHOOK_SECRET=whsec_xxx
WHATSAPP_WEBHOOK_SECRET=xxx
```

### Platform Layer (sellora)
```bash
# Database
DATABASE_URL=postgresql://user:pass@ep-yyy.neon.tech/db?sslmode=require

# Runtime Communication
RUNTIME_API_URL=https://api.order-management.com
RUNTIME_API_TOKEN=service-token

# AI Services
OPENAI_API_KEY=sk-xxx
AI_SERVICE_URL=https://api.openai.com

# Search
ELASTICSEARCH_URL=https://xxx.es.io
ELASTICSEARCH_API_KEY=xxx

# Cache
REDIS_URL=redis://user:pass@yyy.upstash.io:6380

# Monitoring
LOG_LEVEL=info
SENTRY_DSN=https://yyy@sentry.io/yyy
```

### Frontend Layer (seller-dashboard)
```bash
# API Endpoints
NEXT_PUBLIC_RUNTIME_URL=https://api.order-management.com
NEXT_PUBLIC_PLATFORM_URL=https://api.sellora.com

# Authentication
NEXTAUTH_URL=https://dashboard.order-management.com
NEXTAUTH_SECRET=super-secure-secret

# Analytics
NEXT_PUBLIC_SENTRY_DSN=https://zzz@sentry.io/zzz
NEXT_PUBLIC_ANALYTICS_ID=GA_MEASUREMENT_ID

# Feature Flags
NEXT_PUBLIC_ENABLE_AI_SEARCH=true
NEXT_PUBLIC_ENABLE_ANALYTICS=true
```

---

# Deployment Configuration

## Render Services

### Runtime Core
```yaml
# render.yaml
services:
  - type: web
    name: order-management-backend
    env: node
    plan: starter
    buildCommand: npm run build
    startCommand: npm start
    healthCheckPath: /api/health
    envVars:
      - key: NODE_ENV
        value: production
      - key: DATABASE_URL
        sync: false
      - key: JWT_SECRET
        sync: false
    scaling:
      minInstances: 1
      maxInstances: 3
      targetMemoryPercent: 70
      targetCPUPercent: 70
```

### Platform Layer
```yaml
# sellora-render.yaml
services:
  - type: web
    name: sellora-platform
    env: node
    plan: starter
    buildCommand: npm run build
    startCommand: npm start
    healthCheckPath: /api/health
    envVars:
      - key: NODE_ENV
        value: production
      - key: DATABASE_URL
        sync: false
      - key: RUNTIME_API_URL
        value: https://api.order-management.com
    scaling:
      minInstances: 1
      maxInstances: 2
      targetMemoryPercent: 70
```

## Vercel Configuration

### Frontend Layer
```json
// vercel.json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "installCommand": "npm install",
  "env": {
    "NEXT_PUBLIC_RUNTIME_URL": "https://api.order-management.com",
    "NEXT_PUBLIC_PLATFORM_URL": "https://api.sellora.com"
  },
  "regions": ["iad1"],
  "functions": {
    "app/**/*.ts": {
      "maxDuration": 30
    }
  }
}
```

---

# Database Architecture

## Neon PostgreSQL Configuration

### Primary Cluster
```
Region: us-east-1
Compute: 2 vCPU, 4GB RAM
Storage: 100GB SSD
Replicas: 2 read replicas
Backup: Daily + point-in-time recovery
```

### Database Schema
```sql
-- Runtime Core Database
CREATE DATABASE order_management_runtime;

-- Platform Layer Database  
CREATE DATABASE sellora_platform;

-- Connection Pooling
SET max_connections = 100;
SET shared_buffers = '256MB';
SET effective_cache_size = '1GB';
```

### Migration Strategy
```bash
# Runtime Core
npm run db:migrate deploy
npm run db:seed production

# Platform Layer
npm run platform:db:migrate deploy
npm run platform:db:seed production
```

---

# Cache Architecture

## Redis Configuration (Upstash)

### Runtime Core Cache
```
Region: us-east-1
Plan: Pro
Memory: 256MB
Connections: 1000
TTL: 1 hour default
```

### Cache Keys Structure
```
rate_limit:seller:{sellerId}:{endpoint}
session:{sessionId}
auth_token:{tokenId}
order_cache:{orderId}
```

### Cache Strategy
- **Rate Limiting**: 15-minute windows
- **Sessions**: 7-day expiration
- **Auth Tokens**: 7-day expiration
- **Order Cache**: 1-hour expiration

---

# Monitoring & Observability

## Logging Architecture

### Structured Logging
```typescript
// Runtime Core
logger.info('Order created', {
  orderId: 'cmnrc36r00002pn1yeyixi1sn',
  sellerId: 'seller_123',
  requestId: 'req_1728398400_abc123',
  boundary: 'runtime-core',
  service: 'order-management-backend'
});
```

### Log Levels
- **ERROR**: Critical failures, payment issues
- **WARN**: Rate limiting, validation errors
- **INFO**: Order operations, user actions
- **DEBUG**: Detailed execution flow

## Metrics Collection

### Application Metrics
```typescript
// Runtime Core Metrics
const metrics = {
  orders_created_total: 1247,
  orders_processing_duration_ms: 2500,
  payment_success_rate: 0.98,
  api_request_duration_seconds: 0.15,
  rate_limit_violations_total: 23
};
```

### Infrastructure Metrics
- **CPU Usage**: Alert at 80%
- **Memory Usage**: Alert at 85%
- **Database Connections**: Alert at 90%
- **Cache Hit Rate**: Alert below 90%

## Error Tracking (Sentry)

### Error Context
```typescript
Sentry.captureException(error, {
  contexts: {
    order: {
      id: orderId,
      sellerId: sellerId,
      status: currentStatus
    },
    api: {
      endpoint: '/api/v1/orders',
      method: 'POST',
      requestId: requestId
    }
  }
});
```

### Alert Rules
- **Critical**: Payment failures, database errors
- **Warning**: High latency, rate limit violations
- **Info**: User authentication failures

---

# Security Architecture

## Network Security

### SSL/TLS Configuration
```
Certificates: Let's Encrypt (auto-renew)
TLS Version: 1.3
Cipher Suites: Modern secure suites only
HSTS: Enabled with preload
```

### API Security
```typescript
// Rate Limiting Headers
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1728398400

// Security Headers
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
```

## Authentication Flow

### Token Management
```typescript
// Runtime Core JWT
{
  "sub": "cmnrc36r00002pn1yeyixi1sn",
  "email": "seller@example.com",
  "role": "SELLER",
  "sellerId": "cmnrc36r00002pn1yeyixi1sn",
  "permissions": ["orders:read", "orders:write"],
  "iat": 1728398400,
  "exp": 1729003200
}

// Platform Delegated Token
{
  "sub": "platform-service",
  "delegated_from": "seller_123",
  "permissions": ["catalog:read", "analytics:read"],
  "boundary": "platform",
  "iat": 1728398400,
  "exp": 1728484800
}
```

---

# Performance Optimization

## Caching Strategy

### API Response Caching
```typescript
// Runtime Core
GET /api/v1/orders?page=1&limit=20
Cache-Control: public, max-age=300
ETag: "abc123"

// Platform Layer
GET /api/catalog/products
Cache-Control: public, max-age=600
Vary: Accept-Encoding
```

### Database Optimization
```sql
-- Indexes for Performance
CREATE INDEX idx_orders_seller_status ON orders(seller_id, status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_customers_phone ON customers(phone);

-- Query Optimization
EXPLAIN ANALYZE SELECT * FROM orders 
WHERE seller_id = $1 AND status = $2 
ORDER BY created_at DESC LIMIT 20;
```

## CDN Configuration

### Static Assets
```
CDN Provider: CloudFlare
Cache Duration: 1 year (with hash busting)
Compression: Brotli + Gzip
Regions: Global edge locations
```

### API Caching
```
GET /api/health: Cache 5 minutes
GET /api/catalog/products: Cache 10 minutes  
GET /api/analytics/*: Cache 1 hour
POST /api/*: No cache
```

---

# Disaster Recovery

## Backup Strategy

### Database Backups
```
Primary: Daily full backup + continuous WAL
Secondary: Point-in-time recovery (30 days)
Geo-redundant: Cross-region replica
Encryption: At-rest and in-transit
```

### Application Backups
```
Code: Git repository (GitHub)
Config: Environment variables (Render)
Assets: CDN (CloudFlare)
Logs: Centralized (Sentry)
```

## Recovery Procedures

### Database Recovery
```bash
# Point-in-time recovery
psql postgresql://user:pass@ep-xxx.neon.tech/db \
  -c "SELECT pg_backup_start_time('2026-04-09 06:00:00')"

# Restore from backup
pg_restore --clean --if-exists \
  --dbname=order_management_runtime \
  backup_2026_04_09.sql
```

### Service Recovery
```bash
# Runtime Core
render restart order-management-backend

# Platform Layer  
render restart sellora-platform

# Frontend
vercel --prod
```

---

# Scaling Strategy

## Horizontal Scaling

### Auto-scaling Rules
```
Runtime Core:
  CPU > 70%: Scale up (add instance)
  CPU < 30%: Scale down (remove instance)
  Max instances: 3
  Min instances: 1

Platform Layer:
  CPU > 80%: Scale up
  CPU < 40%: Scale down  
  Max instances: 2
  Min instances: 1
```

### Database Scaling
```
Read Replicas: Add for read-heavy workloads
Connection Pooling: PgBouncer for efficiency
Sharding: Future consideration for high volume
```

## Performance Targets

### Response Time SLAs
```
API Endpoints: <200ms (95th percentile)
Database Queries: <100ms (95th percentile)
Cache Operations: <10ms (95th percentile)
Page Load: <3s (95th percentile)
```

### Availability SLAs
```
Runtime Core: 99.9% uptime
Platform Layer: 99.9% uptime
Frontend: 99.95% uptime
Database: 99.99% uptime
```

---

# Deployment Pipeline

## CI/CD Configuration

### GitHub Actions Workflow
```yaml
name: Deploy Production
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm ci
      - name: Run tests
        run: npm test
      - name: Run integration tests
        run: npm run test:integration

  deploy-runtime:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render
        run: curl -X POST "$RENDER_DEPLOY_HOOK"
    environment: production

  deploy-platform:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render
        run: curl -X POST "$SELLORA_DEPLOY_HOOK"
    environment: production

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Vercel
        run: vercel --prod --token=$VERCEL_TOKEN
    environment: production
```

### Deployment Strategy
```
Runtime Core: Blue-green deployment
Platform Layer: Rolling deployment  
Frontend: Canary deployment (10% -> 50% -> 100%)
```

---

This deployment topology ensures high availability, security, and scalability for the production system.

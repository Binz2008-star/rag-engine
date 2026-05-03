# Production API Contracts: Complete Boundary Specifications

## Overview

This document defines the complete OpenAPI-style contracts for all three boundaries in the production system.

---

# Runtime Core API (order-management-backend)

## Base URL
```
Production: https://api.order-management.com
Development: http://localhost:3000
```

## Authentication
```
Authorization: Bearer <JWT_TOKEN>
X-Request-ID: <request_uuid>
```

## API Endpoints

### Orders API

#### Create Order
```http
POST /api/v1/orders
Content-Type: application/json
Authorization: Bearer {token}

{
  "sellerId": "seller_123",
  "customerId": "customer_456", 
  "items": [
    {
      "productId": "product_789",
      "quantity": 2
    }
  ],
  "paymentType": "CASH_ON_DELIVERY",
  "notes": "Optional delivery instructions"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "order": {
      "id": "cmnrc36r00002pn1yeyixi1sn",
      "publicOrderNumber": "ORD-2847",
      "status": "PENDING",
      "paymentStatus": "PENDING",
      "paymentType": "CASH_ON_DELIVERY",
      "subtotalMinor": 2000,
      "deliveryFeeMinor": 500,
      "totalMinor": 2500,
      "currency": "USD",
      "notes": null,
      "createdAt": "2026-04-09T06:02:00Z",
      "updatedAt": "2026-04-09T06:02:00Z",
      "customer": {
        "id": "cmnrc36r00002pn1yeyixi1sn",
        "name": "Ahmed Al-Rashidi",
        "phone": "+966501234567",
        "addressText": "123 Main St, Riyadh"
      },
      "items": [
        {
          "id": "cmnrc36r00002pn1yeyixi1sn",
          "productId": "cmnrc36r00002pn1yeyixi1sn",
          "productNameSnapshot": "Wireless Phone Charger",
          "unitPriceMinor": 1000,
          "quantity": 2,
          "lineTotalMinor": 2000
        }
      ]
    }
  }
}
```

#### Get Order
```http
GET /api/v1/orders/{orderId}
Authorization: Bearer {token}
```

#### List Orders
```http
GET /api/v1/orders?page=1&limit=20&status=PENDING
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "orders": [...],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 1247,
      "totalPages": 63
    }
  }
}
```

#### Update Order Status
```http
PATCH /api/v1/orders/{orderId}/status
Content-Type: application/json
Authorization: Bearer {token}

{
  "status": "CONFIRMED"
}
```

### Payments API

#### Create Payment
```http
POST /api/v1/payments
Content-Type: application/json
Authorization: Bearer {token}

{
  "orderId": "cmnrc36r00002pn1yeyixi1sn",
  "provider": "STRIPE",
  "amountMinor": 2500,
  "currency": "USD",
  "paymentType": "CARD"
}
```

#### Refund Payment
```http
POST /api/v1/payments/{paymentId}/refund
Content-Type: application/json
Authorization: Bearer {token}

{
  "reason": "Customer requested refund"
}
```

### Authentication API

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "seller@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "cmnrc36r00002pn1yeyixi1sn",
      "email": "seller@example.com",
      "role": "SELLER",
      "sellerId": "cmnrc36r00002pn1yeyixi1sn"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer {token}
```

---

# Platform Layer API (sellora)

## Base URL
```
Production: https://api.sellora.com
Development: http://localhost:3001
```

## Authentication
Uses delegated tokens from Runtime Core with platform permissions.

### Catalog API

#### List Products
```http
GET /api/catalog/products?page=1&limit=20&category=electronics
Authorization: Bearer {delegated_token}
```

#### Create Product
```http
POST /api/catalog/products
Content-Type: application/json
Authorization: Bearer {delegated_token}

{
  "name": "Wireless Phone Charger",
  "description": "Fast charging wireless pad",
  "priceMinor": 2999,
  "currency": "USD",
  "category": "electronics",
  "isActive": true
}
```

#### Update Product
```http
PUT /api/catalog/products/{productId}
Content-Type: application/json
Authorization: Bearer {delegated_token}
```

### AI Search API

#### Semantic Search
```http
GET /api/ai/search?q=wireless charger&limit=10
Authorization: Bearer {delegated_token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "productId": "product_789",
        "name": "Wireless Phone Charger",
        "score": 0.95,
        "priceMinor": 2999,
        "currency": "USD"
      }
    ],
    "query": "wireless charger",
    "total": 42
  }
}
```

### Analytics API

#### Seller Analytics
```http
GET /api/analytics/seller/{sellerId}?period=30d
Authorization: Bearer {delegated_token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "period": "30d",
    "metrics": {
      "totalOrders": 1247,
      "revenue": 4832000,
      "avgOrderValue": 3875,
      "conversionRate": 0.034
    },
    "breakdown": {
      "daily": [...],
      "byStatus": {...}
    }
  }
}
```

---

# Error Contracts

## Standard Error Format
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": {
      "field": "sellerId",
      "issue": "Invalid format"
    },
    "timestamp": "2026-04-09T06:02:00Z"
  }
}
```

## Error Codes
- `VALIDATION_ERROR` - Invalid request data
- `NOT_FOUND` - Resource not found
- `UNAUTHORIZED` - Invalid or missing token
- `FORBIDDEN` - Insufficient permissions
- `INTERNAL_ERROR` - Server error
- `PAYMENT_FAILED` - Payment processing failed
- `INSUFFICIENT_STOCK` - Not enough inventory
- `INVALID_STATUS_TRANSITION` - Invalid order status change

---

# Rate Limiting

## Runtime Core Limits
- **Orders**: 100 requests/minute per seller
- **Payments**: 50 requests/minute per seller
- **Auth**: 10 requests/minute per IP

## Platform Layer Limits
- **Catalog**: 200 requests/minute per seller
- **AI Search**: 30 requests/minute per seller
- **Analytics**: 10 requests/minute per seller

## Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1728398400
Retry-After: 60
```

---

# SDK Integration

## Runtime Client
```typescript
import { GatewayClient } from '@order-management/runtime-client'

const runtimeClient = GatewayClient.withToken(
  process.env.RUNTIME_API_URL,
  authToken
)

// Create order
const order = await runtimeClient.post('/api/v1/orders', {
  sellerId: 'seller_123',
  customerId: 'customer_456',
  items: [{ productId: 'product_789', quantity: 2 }],
  paymentType: 'CASH_ON_DELIVERY'
})
```

## Platform Client
```typescript
import { PlatformClient } from '@sellora/platform-client'

const platformClient = PlatformClient.withDelegatedToken(
  process.env.PLATFORM_API_URL,
  delegatedToken
)

// Search products
const search = await platformClient.get('/api/ai/search', {
  params: { q: 'wireless charger', limit: 10 }
})
```

---

# Contract Testing

## Runtime Core Tests
```typescript
describe('Runtime API Contracts', () => {
  test('Create order contract', async () => {
    const response = await runtimeClient.post('/api/v1/orders', validOrder)
    expect(OrderResponseSchema.parse(response.data.order)).toBeDefined()
  })
})
```

## Platform Layer Tests
```typescript
describe('Platform API Contracts', () => {
  test('Search contract', async () => {
    const response = await platformClient.get('/api/ai/search', { q: 'test' })
    expect(SearchResponseSchema.parse(response)).toBeDefined()
  })
})
```

---

# Versioning

## API Versioning Strategy
- **Runtime Core**: `/api/v1/` (current), `/api/v2/` (future breaking changes)
- **Platform Layer**: `/api/v1/` (current)
- **SDK**: Semantic versioning matching API versions

## Backward Compatibility
- All breaking changes require new version
- Old versions supported for 6 months after deprecation
- Migration guides provided for all breaking changes

---

# Monitoring & Observability

## Request Tracing
```http
X-Request-ID: req_1728398400_abc123def
X-Boundary: runtime-core
X-Service: order-management-backend
```

## Metrics
- Request latency per endpoint
- Error rate by boundary
- Rate limiting violations
- Contract validation failures

## Health Checks
```http
GET /api/health
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-04-09T06:02:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "rate_limiter": "healthy"
  }
}
```

---

This contract specification ensures all three boundaries can communicate reliably with type safety and clear error handling.

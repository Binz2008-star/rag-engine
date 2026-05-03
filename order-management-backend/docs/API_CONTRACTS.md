# API Contracts: Runtime Core (order-management-backend)

## Overview

This document defines the API contracts between the Platform Layer (sellora) and Runtime Core (order-management-backend).

**Critical Rule**: All order/payment/auth operations MUST go through these APIs. No direct database access.

## Authentication

All API calls require authentication via JWT tokens from the runtime core.

### POST /api/auth/login
```typescript
interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  user: {
    id: string;
    email: string;
    fullName: string;
    role: string;
  };
  token: string;
  refreshToken: string;
}
```

## Orders API

### GET /api/seller/orders
Get orders for the authenticated seller.

```typescript
interface GetOrdersResponse {
  orders: Array<{
    id: string;
    publicOrderNumber: string;
    status: "PENDING" | "CONFIRMED" | "PREPARING" | "READY" | "COMPLETED" | "CANCELLED";
    paymentStatus: "PENDING" | "PAID" | "FAILED" | "REFUNDED";
    totalMinor: number;
    currency: string;
    createdAt: string;
    customer: {
      id: string;
      name: string;
      phone: string;
    };
  }>;
}
```

### POST /api/seller/orders
Create a new order.

```typescript
interface CreateOrderRequest {
  customerId: string;
  items: Array<{
    productId: string;
    quantity: number;
  }>;
  paymentType: "CASH_ON_DELIVERY" | "CARD" | "WALLET";
  notes?: string;
}

interface CreateOrderResponse {
  order: {
    id: string;
    publicOrderNumber: string;
    status: string;
    paymentStatus: string;
    totalMinor: number;
    currency: string;
  };
}
```

### GET /api/seller/orders/[id]
Get a specific order.

```typescript
interface GetOrderResponse {
  order: {
    id: string;
    publicOrderNumber: string;
    status: string;
    paymentStatus: string;
    subtotalMinor: number;
    deliveryFeeMinor: number;
    totalMinor: number;
    currency: string;
    notes?: string;
    createdAt: string;
    customer: {
      id: string;
      name: string;
      phone: string;
      addressText?: string;
    };
    items: Array<{
      id: string;
      productId: string;
      productNameSnapshot: string;
      unitPriceMinor: number;
      quantity: number;
      lineTotalMinor: number;
    }>;
    events: Array<{
      id: string;
      eventType: string;
      payloadJson?: string;
      createdAt: string;
    }>;
  };
}
```

### PUT /api/seller/orders/[id]/status
Update order status.

```typescript
interface UpdateOrderStatusRequest {
  status: "PENDING" | "CONFIRMED" | "PREPARING" | "READY" | "COMPLETED" | "CANCELLED";
}

interface UpdateOrderStatusResponse {
  order: {
    id: string;
    status: string;
    updatedAt: string;
  };
}
```

### GET /api/seller/orders/[id]/events
Get order events.

```typescript
interface GetOrderEventsResponse {
  events: Array<{
    id: string;
    eventType: string;
    payloadJson?: string;
    createdAt: string;
  }>;
}
```

## Payments API

### GET /api/seller/payments
Get payment attempts for the authenticated seller.

```typescript
interface GetPaymentsResponse {
  payments: Array<{
    id: string;
    orderId: string;
    provider: string;
    providerReference?: string;
    amountMinor: number;
    currency: string;
    status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "REFUNDED";
    paymentType?: string;
    failureReason?: string;
    createdAt: string;
    order: {
      id: string;
      publicOrderNumber: string;
    };
  }>;
}
```

### POST /api/seller/orders/[id]/payments/create
Create a payment attempt.

```typescript
interface CreatePaymentRequest {
  provider: "STRIPE" | "PAYPAL" | "MPESA";
  amountMinor: number;
  currency: string;
  paymentType?: string;
  metadataJson?: string;
}

interface CreatePaymentResponse {
  payment: {
    id: string;
    provider: string;
    providerReference?: string;
    amountMinor: number;
    currency: string;
    status: string;
  };
}
```

### PUT /api/seller/payments/[paymentAttemptId]/status
Update payment status.

```typescript
interface UpdatePaymentStatusRequest {
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "REFUNDED";
  failureReason?: string;
}

interface UpdatePaymentStatusResponse {
  payment: {
    id: string;
    status: string;
    updatedAt: string;
  };
}
```

### POST /api/seller/payments/[paymentAttemptId]/refund
Refund a payment.

```typescript
interface RefundPaymentRequest {
  reason?: string;
}

interface RefundPaymentResponse {
  payment: {
    id: string;
    status: "REFUNDED";
    updatedAt: string;
  };
}
```

## Public API (for external systems)

### GET /api/public/[sellerSlug]/orders
Get public order information for a seller.

```typescript
interface GetPublicOrdersResponse {
  seller: {
    id: string;
    brandName: string;
    slug: string;
  };
  orders: Array<{
    id: string;
    publicOrderNumber: string;
    status: string;
    paymentStatus: string;
    totalMinor: number;
    currency: string;
    createdAt: string;
  }>;
}
```

### POST /api/public/[sellerSlug]/checkout
Create an order via public checkout.

```typescript
interface PublicCheckoutRequest {
  customerName: string;
  customerPhone: string;
  customerAddress?: string;
  items: Array<{
    productId: string;
    quantity: number;
  }>;
  paymentType: "CASH_ON_DELIVERY" | "CARD";
}

interface PublicCheckoutResponse {
  order: {
    id: string;
    publicOrderNumber: string;
    status: string;
    paymentStatus: string;
    totalMinor: number;
    currency: string;
  };
}
```

## Error Handling

All endpoints return consistent error responses:

```typescript
interface ErrorResponse {
  error: string;
  details?: any;
}
```

HTTP Status Codes:
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

## Rate Limiting

- Auth endpoints: 5 requests per minute
- Order operations: 100 requests per minute
- Payment operations: 50 requests per minute
- Public endpoints: 1000 requests per minute per IP

## Webhooks

### POST /api/webhooks/stripe
Handle Stripe webhook events.

### POST /api/webhooks/whatsapp
Handle WhatsApp webhook events.

## Boundary Enforcement Rules

### Forbidden Operations in sellora:
- Direct Prisma imports
- Direct database connections
- Order status mutations
- Payment processing
- Authentication logic

### Required Communication Pattern:
```typescript
// sellora must use runtime API client
const order = await runtimeClient.orders.create({
  customerId: '...',
  items: [...],
  paymentType: 'CASH_ON_DELIVERY'
});

// NEVER do this in sellora:
// import { prisma } from '@/server/db/prisma';
// await prisma.order.create({...}); // VIOLATION
```

## Implementation Notes

1. **Authentication**: All API calls must include JWT token in Authorization header
2. **Seller Isolation**: All operations are automatically scoped to the authenticated seller
3. **Audit Trail**: All state changes create events automatically
4. **Idempotency**: Payment operations support idempotency keys
5. **Validation**: All inputs are validated using Zod schemas

## Versioning

API version is specified in the URL path:
- v1: Current stable version
- v2: Beta features (when available)

Breaking changes will increment the major version and maintain backward compatibility for at least 6 months.

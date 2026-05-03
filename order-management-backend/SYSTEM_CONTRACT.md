# System Contract

> Architecture contract defining component boundaries and API ownership for the unified commerce platform.

## Component Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    eco-environmental-uae                     │
│              (Marketing Site / Lead Capture)                  │
└───────────────────────┬───────────────────────────────────────┘
                        │ leads
                        ▼
┌─────────────────────────────────────────────────────────────┐
│     Send-Offer-to-Client-via-Gmail-Inbox                     │
│              (Lead Ops / Outreach Pipeline)                   │
└───────────────────────┬───────────────────────────────────────┘
                        │ qualified opportunities
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                         sellora                              │
│          (Platform Intelligence / Catalog / Sourcing)         │
│              NO runtime order/payment ownership               │
└───────────────────────┬───────────────────────────────────────┘
                        │ platform decisions
                        ▼
┌─────────────────────────────────────────────────────────────┐
│               order-management-backend                       │
│                  RUNTIME CORE (Single Source)                │
│  ┌──────────────┬──────────────┬──────────────┬────────────┐  │
│  │   users    │   orders     │  payments    │   audit    │  │
│  │   auth     │   sellers    │ fulfillment  │  events    │  │
│  └──────────────┴──────────────┴──────────────┴────────────┘  │
└───────────────────────┬───────────────────────────────────────┘
                        │ API consumption
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    seller-dashboard                          │
│                     UI ONLY (No Backend)                     │
│              Consumes Runtime + Sellora APIs                 │
└─────────────────────────────────────────────────────────────┘
```

## Ownership Rules

### 1. Runtime Core (order-management-backend)

**OWNERSHIP - Single Source of Truth:**

| Entity | Owned By | Consumed By |
|--------|----------|-------------|
| `User` | Runtime | Sellora (read-only), Dashboard |
| `Seller` | Runtime | Sellora (read-only), Dashboard |
| `Customer` | Runtime | Sellora (read-only), Dashboard |
| `Order` | Runtime | Dashboard (read-only) |
| `OrderEvent` | Runtime | Dashboard (read-only) |
| `PaymentAttempt` | Runtime | Dashboard (read-only) |
| `FulfillmentRecord` | Runtime | Dashboard (read-only) |
| `AuditEvent` | Runtime | Dashboard (read-only) |

**API Endpoints:**

```typescript
// Auth (Runtime owns)
POST /api/auth/login          // Returns: { user, token }
DELETE /api/auth/login        // Logout
GET /api/me                   // Returns: AuthUser

// Public Order API (Runtime owns)
GET /api/public/{sellerSlug}/products  # Returns products from Sellora catalog
POST /api/public/{sellerSlug}/orders  # Creates order with product references from Sellora

// Seller API (Runtime owns)
GET /api/seller/orders
GET /api/seller/orders/{id}
PATCH /api/seller/orders/{id}/status
POST /api/seller/orders/{id}/payments/create

// Health (Runtime owns)
GET /api/health
```

### 2. Platform Layer (sellora)

**NO Runtime Ownership - Intelligence Only:**

| Entity | Type | Notes |
|--------|------|-------|
| `Catalog` | Platform | Product catalog management |
| `Sourcing` | Platform | Supplier relationships |
| `Opportunity` | Platform | Lead-to-order pipeline |
| `Autonomy` | Platform | AI decision engine |
| `TenantPolicy` | Platform | Multi-tenant configuration |

**REMOVED from Sellora:**
- ❌ `User` (runtime owns)
- ❌ `Customer` (runtime owns)
- ❌ `Invoice.orderId` (runtime owns)
- ❌ `PaymentAttempt` (runtime owns)
- ❌ `FulfillmentRecord` (runtime owns)
- ❌ `ShippingWebhookReceipt` (runtime owns)

**API Pattern:**
```typescript
// Sellora consumes Runtime APIs
const order = await runtimeClient.createOrder(...);
const payment = await runtimeClient.initiatePayment(...);

// Sellora provides intelligence
const recommendation = await selloraClient.getProductRecommendation(...);
const sourcingOptions = await selloraClient.findSuppliers(...);
```

### 3. UI Layer (seller-dashboard)

**NO Backend Ownership - UI Only:**

```typescript
// Dashboard structure (proposed)
seller-dashboard/
  apps/
    web/                    # Next.js frontend only
      lib/
        runtimeClient.ts    # Runtime API client
        selloraClient.ts    # Sellora API client
  # NO apps/server
  # NO packages/db
  # NO packages/auth backend
```

**Authentication:**
- Dashboard uses Runtime auth (JWT from `/api/auth/login`)
- No separate auth system
- No database tables for auth

### 4. Lead Pipeline (Send-Offer-to-Client-via-Gmail-Inbox)

**Independent Microservice:**

```typescript
// Lead operations
POST /api/v1/leads
POST /api/v1/leads/{lead_id}/run-outreach
GET /health

// Pipeline to Runtime/Sellora
qualifiedLead → sellora.opportunity → runtime.order
```

## Data Flow

### Happy Path: Lead to Order

```
┌─────────┐    ┌─────────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│   eco   │───▶│ Send-Offer  │───▶│ sellora │───▶│ runtime │───▶│dashboard│
│  site   │    │   pipeline  │    │platform │    │  core   │    │   UI    │
└─────────┘    └─────────────┘    └─────────┘    └─────────┘    └─────────┘
    │                │                 │              │              │
 capture          qualify           decide         execute        display
  lead            lead            catalog +      order + payment   results
                                    source
```

## API Contract

### Authentication

**Request:**
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "seller@example.com",
  "password": "securepassword"
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "user": {
    "id": "uuid",
    "email": "seller@example.com",
    "role": "SELLER",
    "sellerId": "uuid"
  },
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Protected Endpoints

**Request:**
```http
GET /api/seller/orders
Authorization: Bearer {token}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "orders": [...],
  "pagination": { "page": 1, "limit": 20, "total": 100 }
}
```

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Runtime Auth | ✅ Fixed | Real DB auth implemented |
| Runtime Orders | ✅ Ready | Service layer complete |
| Runtime Payments | ✅ Ready | Service layer complete |
| Sellora Cleanup | ⏳ Pending | Remove Runtime models |
| Dashboard Cleanup | ⏳ Pending | Remove backend code |
| API Integration | ⏳ Pending | Connect Dashboard to Runtime |

## Next Steps

1. **Verify Runtime Auth** - Connect to production database
2. **Run Release Proof** - Validate E2E flow
3. **Clean Sellora** - Remove Runtime-owned models
4. **Clean Dashboard** - Remove backend/DB/auth packages
5. **Archive Duplicates** - Remove seller-dashboard-

# API Contract Design: Three-Boundary Architecture

## Overview

This document defines the API contracts between the three boundaries of the order management system:
- `seller-dashboard` (UI Layer)
- `order-management-backend` (Runtime Core)
- `sellora` (Platform Layer)

## Current State Analysis

### Runtime Core (order-management-backend)
- **Existing**: V1 API contracts with Zod schemas
- **Runtime Client**: Type-safe OrdersClient already implemented
- **Auth**: Seller-scoped authentication with `requireSeller()`
- **Boundaries**: Enforced seller isolation

### UI Layer (seller-dashboard) - From ZIP
- **Components**: Seller Dashboard, Customer Storefront, Admin Panel
- **Features**: Order management, product catalog, AI search
- **Routing**: Multi-persona routing already designed

## API Routing Matrix

| UI Feature | Target Boundary | API Endpoint | Purpose |
|-------------|----------------|--------------|---------|
| **Order Management** | Runtime Core | `/api/v1/orders/*` | CRUD operations, status updates |
| **Payment Processing** | Runtime Core | `/api/v1/payments/*` | Refunds, status checks |
| **Authentication** | Runtime Core | `/api/v1/auth/*` | Login, session management |
| **Product Catalog** | Platform Layer | `/api/catalog/*` | Product management, search |
| **AI Search** | Platform Layer | `/api/ai/search` | Semantic product search |
| **Seller Analytics** | Platform Layer | `/api/analytics/*` | Business insights |
| **Admin Controls** | Platform Layer | `/api/admin/*` | System management |

## Boundary Enforcement Rules

### Runtime Core Responsibilities
```typescript
// ALLOWED: Order lifecycle operations
POST /api/v1/orders
PUT /api/v1/orders/:id/status
POST /api/v1/payments/:id/refund

// FORBIDDEN: Product ownership
// Products must come as snapshots, not references
interface OrderItem {
  productId: string;           // Reference only
  productNameSnapshot: string;  // Immutable snapshot
  unitPriceMinor: number;       // Price at time of order
}
```

### Platform Layer Responsibilities
```typescript
// ALLOWED: Catalog operations
GET /api/catalog/products
POST /api/catalog/products
PUT /api/catalog/products/:id
GET /api/ai/search?q=wireless

// FORBIDDEN: Order mutations
// Must use runtime client for order operations
const order = await runtimeClient.orders.create({...});
```

## Implementation Strategy

### Phase 1: UI API Client Setup
```typescript
// seller-dashboard/lib/api/runtime.ts
import { createOrdersClient } from '@order-management/runtime-client'

export const runtimeAPI = {
  orders: createOrdersClient(process.env.NEXT_PUBLIC_RUNTIME_URL),
  payments: createPaymentsClient(process.env.NEXT_PUBLIC_RUNTIME_URL),
  auth: createAuthClient(process.env.NEXT_PUBLIC_RUNTIME_URL)
}

// seller-dashboard/lib/api/platform.ts
export const platformAPI = {
  catalog: createCatalogClient(process.env.NEXT_PUBLIC_PLATFORM_URL),
  ai: createAIClient(process.env.NEXT_PUBLIC_PLATFORM_URL),
  analytics: createAnalyticsClient(process.env.NEXT_PUBLIC_PLATFORM_URL)
}
```

### Phase 2: Component Integration
```typescript
// seller-dashboard/components/orders/OrderList.tsx
import { runtimeAPI } from '@/lib/api/runtime'

export default function OrderList() {
  const { data: orders } = useQuery({
    queryKey: ['orders'],
    queryFn: () => runtimeAPI.orders.list({ page: 1, limit: 20 })
  })
  
  // Component logic...
}
```

### Phase 3: Boundary Validation
```typescript
// Runtime Core - Boundary enforcement
export async function createOrder(data: CreateOrderSchema) {
  // Validate seller isolation
  const seller = await getCurrentUser()
  requireSeller(seller)
  
  // Enforce product snapshots (no live product references)
  const orderItems = data.items.map(item => ({
    productId: item.productId,
    productNameSnapshot: item.name, // Required snapshot
    unitPriceMinor: item.price,     // Price snapshot
    quantity: item.quantity
  }))
  
  // Create order with immutable snapshots
  return await prisma.order.create({
    data: { ...data, orderItems }
  })
}
```

## Security Model

### Authentication Flow
1. **UI Layer** -> **Runtime Core**: Authenticate seller
2. **Runtime Core** -> **Platform Layer**: Delegated permissions
3. **UI Layer** -> **Platform Layer**: Present runtime token

### Token Management
```typescript
// Runtime Core issues JWT with delegated permissions
const token = signJWT({
  sellerId: user.sellerId,
  permissions: ['orders:read', 'orders:write'],
  delegatedTo: ['platform-layer']
})

// Platform Layer validates delegated permissions
function validatePlatformToken(token: string) {
  const payload = verifyJWT(token)
  if (!payload.permissions.includes('catalog:read')) {
    throw new UnauthorizedError()
  }
}
```

## Deployment Configuration

### Environment Variables
```bash
# seller-dashboard (UI)
NEXT_PUBLIC_RUNTIME_URL=https://api.order-management.com
NEXT_PUBLIC_PLATFORM_URL=https://api.sellora.com

# order-management-backend (Runtime)
DATABASE_URL=postgresql://...
JWT_SECRET=...
PLATFORM_API_URL=https://api.sellora.com

# sellora (Platform)
DATABASE_URL=postgresql://...
RUNTIME_API_URL=https://api.order-management.com
AI_SERVICE_URL=...
```

## Migration Path

### Step 1: Extract Runtime Client
- Move `src/shared/runtime-client/*` to separate package
- Publish as `@order-management/runtime-client`
- Install in seller-dashboard project

### Step 2: Create Platform Client
- Design similar client for sellora APIs
- Implement type-safe contracts
- Add boundary validation

### Step 3: UI Integration
- Replace mock data in ZIP components with real API calls
- Implement proper error handling
- Add loading states and optimistic updates

## Testing Strategy

### Contract Tests
```typescript
// Test API contracts between boundaries
describe('Order API Contract', () => {
  it('should maintain V1 compatibility', async () => {
    const response = await runtimeAPI.orders.create(validOrder)
    expect(OrderCreateResponseSchema.parse(response)).toBeDefined()
  })
})
```

### Boundary Tests
```typescript
// Test boundary enforcement
describe('Boundary Enforcement', () => {
  it('should prevent direct DB access from UI', async () => {
    // This should fail - UI cannot access DB directly
    expect(() => import('@prisma/client')).toThrow()
  })
})
```

## Success Metrics

### Technical Metrics
- **API Response Time**: <200ms for 95% of requests
- **Boundary Violations**: 0 (enforced at runtime)
- **Contract Compliance**: 100% (automated testing)

### Business Metrics
- **Order Processing Time**: <5 minutes from creation to confirmation
- **UI Responsiveness**: <3s page load time
- **Error Rate**: <1% for user-facing operations

## Next Steps

1. **Create seller-dashboard repository** with Next.js setup
2. **Extract runtime client** to shared package
3. **Implement platform client** for sellora APIs
4. **Integrate UI components** with real API calls
5. **Deploy and test** boundary enforcement

---

This design maintains strict boundary separation while enabling seamless user experience across the three-layer architecture.

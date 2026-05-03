# System Architecture: One System, Multiple Boundaries

## Overview

This is **one system** split into bounded contexts, not three separate projects. The architecture enforces strict ownership boundaries while maintaining system cohesion.

```
sellora (Platform Layer)          order-management-backend (Runtime Core)          seller-dashboard (UI)
    |                                       |                                           |
    |  API Calls Only                       |  Database + State Mutations               |  Display Only
    |-------------------------------------->|                                           |
    |                                       |                                           |
    |  Workflows/Orchestration              |  Orders/Payments/Auth                     |  User Interface
    |  AI/Sourcing                          |  Audit/Events                             |  Dashboard Views
    |  Catalog Management                   |  Webhooks/Runtime Execution               |  Forms/Actions
```

## Bounded Contexts

### 1. Runtime Core - order-management-backend

**Ownership**: Orders, Payments, Auth, Inventory, Database

**Responsibilities**:
- Transactional state mutations
- Order lifecycle management
- Payment processing
- Authentication & authorization
- Audit trail & events
- Webhook handling
- Database operations

**Rules**:
- **ONLY** place where transactional state is mutated
- Single source of truth for all order/payment data
- All database operations confined to this boundary
- No business logic about catalog, AI, or workflows

**Database Schema**:
- Users, Sellers, Customers
- Orders, OrderItems, OrderEvents
- PaymentAttempts
- NotificationJobs
- WebhookEvents

### 2. Platform Layer - sellora

**Ownership**: Catalog, AI/Sourcing, Workflows, Orchestration, Seller Logic

**Responsibilities**:
- Product catalog management
- AI-powered sourcing opportunities
- Business workflow orchestration
- Seller business logic
- Third-party integrations
- Analytics and insights

**Rules**:
- **NO** direct database access for orders/payments
- **NO** order status mutations
- **NO** payment processing
- All order/payment operations via runtime APIs
- Can maintain own database for catalog/ai data

**Communication Pattern**:
```typescript
// CORRECT: Use runtime API client
const order = await runtimeClient.orders.create({...});
const payment = await runtimeClient.payments.create({...});

// FORBIDDEN: Direct database access
// import { prisma } from '@/server/db/prisma';
// await prisma.order.create({...}); // VIOLATION
```

### 3. Frontend Layer - seller-dashboard

**Ownership**: User Interface, Dashboard, Forms

**Responsibilities**:
- Display order information
- Collect user input
- Show analytics
- Provide user interactions

**Rules**:
- Display only (no business logic)
- All operations via API calls
- No direct database access
- No state mutations

## Critical Architecture Rules

### Rule 1: Single Source of Truth
Only `order-management-backend` can:
- Change order status
- Process payments
- Manage authentication
- Mutate transactional state

### Rule 2: Strict Boundary Enforcement
`sellora` is explicitly **NOT** a backend for orders/payments:
- No `prisma.order` imports
- No `paymentIntent` handling
- No `order.status =` assignments
- No direct database connections

### Rule 3: API-Only Communication
```typescript
// CORRECT
await runtimeClient.orders.create({
  customerId: '...',
  items: [...],
  paymentType: 'CASH_ON_DELIVERY'
});

// FORBIDDEN
import { Order } from '@prisma/client';
const order = new Order(); // VIOLATION
```

## Deployment Topology

### Production Environment

```
Render (Platform Layer)
  sellora-app
  - Node.js runtime
  - Catalog database (PostgreSQL)
  - AI/ML services
  - Workflow engine

Render (Runtime Core)
  order-management-backend
  - Node.js runtime
  - Primary database (Neon PostgreSQL)
  - Redis for sessions
  - Webhook endpoints

Vercel (Frontend)
  seller-dashboard
  - Next.js app
  - Static assets
  - Client-side routing

Neon (Database)
  - Primary PostgreSQL cluster
  - Read replicas for scaling
  - Point-in-time recovery
```

### Data Flow

```
User Action (seller-dashboard)
    |
    v
API Call (sellora)
    |
    v
Business Logic (sellora)
    |
    v
Runtime API (order-management-backend)
    |
    v
Database (Neon PostgreSQL)
```

## Enforcement Mechanisms

### 1. ESLint Rules
```javascript
// Boundary enforcement in eslint.config.mjs
{
  "no-restricted-imports": [
    "error",
    {
      patterns: [
        {
          group: ["@prisma/client"],
          message: "Use runtime API instead of direct database access"
        }
      ]
    }
  ]
}
```

### 2. Runtime Guards
- API authentication checks
- Seller isolation enforcement
- Rate limiting per boundary
- Request validation

### 3. Contract Testing
- API contract validation
- Integration tests between boundaries
- Boundary violation detection

## Migration Strategy

### Phase 1: Boundary Lock
- [x] ESLint boundary enforcement
- [x] API contracts defined
- [ ] Remove violations in sellora
- [ ] Add runtime guards

### Phase 2: Contract Implementation
- [ ] Runtime API client in sellora
- [ ] Typed contracts with Zod
- [ ] Error handling patterns
- [ ] Retry mechanisms

### Phase 3: System Integration
- [ ] Shared deployment pipeline
- [ ] Cross-boundary monitoring
- [ ] Unified logging
- [ ] System health checks

## Benefits of This Architecture

### 1. Clear Ownership
- No duplicated logic
- Single source of truth
- Clear responsibility boundaries

### 2. Maintainable
- Easier debugging
- Isolated deployment
- Independent scaling

### 3. Extensible
- New boundaries can be added
- Existing boundaries can evolve
- Technology diversity per boundary

### 4. Testable
- Unit tests per boundary
- Integration tests between boundaries
- Contract testing

## Anti-Patterns to Avoid

### 1. Distributed Monolith
```
WRONG: Three "microservices" that share database connections
WRONG: Duplicated order logic across boundaries
WRONG: Direct database access from platform layer
```

### 2. Tight Coupling
```
WRONG: Shared database schemas
WRONG: Direct imports between boundaries
WRONG: Synchronous dependencies
```

### 3. Boundary Bleeding
```
WRONG: Platform layer doing payment processing
WRONG: Runtime core handling catalog logic
WRONG: Frontend managing business state
```

## Monitoring & Observability

### System-Level Metrics
- Request latency between boundaries
- Error rates per boundary
- Database connection pools
- API contract compliance

### Boundary-Specific Metrics
- Runtime Core: Order processing time, payment success rate
- Platform Layer: AI inference latency, workflow completion rate
- Frontend: Page load time, user interaction metrics

## Security Model

### Authentication Flow
1. User authenticates with Runtime Core
2. Runtime Core issues JWT token
3. All boundaries validate token
4. Platform layer gets delegated permissions

### Authorization
- Runtime Core: Full system access
- Platform Layer: Deimited API access
- Frontend: User-scoped display access

## Future Evolution

### Potential New Boundaries
- **Analytics Service**: For complex reporting
- **Notification Service**: For multi-channel messaging
- **Inventory Service**: For advanced stock management

### Technology Migration Path
- Runtime Core: Can evolve database schema independently
- Platform Layer: Can adopt new AI frameworks
- Frontend: Can migrate to different frameworks

## Conclusion

This architecture provides:
- **One system** with clear boundaries
- **Strict ownership** preventing duplication
- **API-driven communication** ensuring loose coupling
- **Independent deployment** for each boundary
- **Scalable growth** path for the future

The key is treating this as **one system** with **multiple boundaries**, not multiple independent systems.

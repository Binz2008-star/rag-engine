# System Ownership Matrix

**Version:** 1.0.0  
**Status:** Runtime Authority Confirmed  
**Effective:** 2026-04-10

---

## Executive Summary

**Runtime Domain:** `order-management-backend`  
**Platform Domain:** `sellora` (external)  
**UI Domain:** `seller-dashboard` (external)

**Core Principle:** Runtime truth must have one owner to prevent duplicated state rules, drifting payment logic, inconsistent events, and impossible debugging.

---

## Section 1: Ownership Matrix

### 1.1 Runtime Domain (order-management-backend)

| Capability | Ownership | Authority | Implementation |
|------------|------------|-----------|----------------|
| **Orders** | Runtime | Authoritative | Full CRUD, state machine, lifecycle |
| **Payments** | Runtime | Authoritative | Processing, state changes, reconciliation |
| **Authentication** | Runtime | Authoritative | JWT tokens, user management, sessions |
| **State Machine** | Runtime | Authoritative | Order/payment transitions, validation |
| **Audit Events** | Runtime | Authoritative | Transactional event trail, actor tracking |
| **Inventory Mutations** | Runtime | Authoritative | Stock reservations, deductions, releases |
| **Rate Limiting** | Runtime | Authoritative | API rate limiting policies |
| **Database Schema** | Runtime | Authoritative | Runtime tables, relationships, constraints |

### 1.2 Platform Domain (sellora) - Forbidden in Runtime

| Capability | Ownership | Runtime Status | Implementation Location |
|------------|------------|----------------|------------------------|
| **Catalog Management** | Platform | Forbidden | sellora |
| **AI Sourcing** | Platform | Forbidden | sellora |
| **Opportunity Engine** | Platform | Forbidden | sellora |
| **Workflow Automation** | Platform | Forbidden | sellora |
| **Platform Integration** | Platform | Forbidden | sellora |
| **Localization** | Platform | Forbidden | sellora |
| **WhatsApp Integration** | Platform | Forbidden | sellora |

### 1.3 UI Domain (seller-dashboard) - Consumption Only

| Capability | Ownership | Runtime Access | Implementation |
|------------|------------|----------------|----------------|
| **Dashboard UI** | UI | Query APIs Only | seller-dashboard |
| **Order Views** | UI | Query APIs Only | seller-dashboard |
| **Payment Views** | UI | Query APIs Only | seller-dashboard |
| **User Interface** | UI | Query APIs Only | seller-dashboard |

---

## Section 2: Data Authority Boundaries

### 2.1 Runtime Database (Authoritative)

```sql
-- Transactional tables (Runtime Only)
orders                  -- Order lifecycle and state
order_events            -- Order state transitions
payments                -- Payment processing
payment_attempts        -- Payment attempt tracking
payment_events          -- Payment state changes
users                   -- User authentication data
sessions                -- Session management
inventory               -- Stock management
inventory_reservations  -- Stock reservations
audit_events            -- Comprehensive audit trail
rate_limits             -- Rate limiting state
```

### 2.2 Platform Database (Forbidden in Runtime)

```sql
-- These tables CANNOT exist in runtime database
products                -- Platform catalog
categories              -- Platform categorization
catalog_templates       -- Platform templates
enrichment_data         -- AI enrichment results
opportunity_scores      -- Opportunity scoring
sourcing_imports        -- Sourcing import data
autonomy_policies       -- Platform policies
workflow_runs           -- Workflow execution
integration_configs     -- External integrations
translations            -- Localization data
```

### 2.3 Data Flow Rules

```yaml
Runtime to Platform:
  - Query APIs: ALLOWED (read-only)
  - Webhook Events: ALLOWED (runtime publishes events)
  - Direct DB Access: FORBIDDEN

Platform to Runtime:
  - Command APIs: ALLOWED (order creation, payment processing)
  - Query APIs: ALLOWED (order status, payment status)
  - Direct DB Access: FORBIDDEN
  - Schema Modifications: FORBIDDEN
```

---

## Section 3: API Authority Boundaries

### 3.1 Command APIs (Runtime Authority)

```typescript
// Order Commands (Runtime Only)
POST /api/orders                    // Create order
PATCH /api/orders/{id}/status      // Update order status
POST /api/orders/{id}/cancel       // Cancel order

// Payment Commands (Runtime Only)
POST /api/payments                 // Initiate payment
POST /api/payments/{id}/complete   // Complete payment
POST /api/payments/{id}/refund     // Refund payment

// Inventory Commands (Runtime Only)
POST /api/inventory/reserve        // Reserve stock
POST /api/inventory/release        // Release stock
POST /api/inventory/deduct         // Deduct stock

// Auth Commands (Runtime Only)
POST /api/auth/login               // Authenticate user
DELETE /api/auth/login              // Logout user
POST /api/auth/register            // Register user
```

### 3.2 Query APIs (Safe Consumption)

```typescript
// Order Queries (Platform/UI Safe)
GET /api/orders/{id}               // Get order details
GET /api/sellers/{id}/orders       // Get seller orders
GET /api/orders/{id}/events        // Get order events

// Payment Queries (Platform/UI Safe)
GET /api/payments/{id}             // Get payment details
GET /api/payments/{id}/events      // Get payment events

// Inventory Queries (Platform/UI Safe)
GET /api/inventory/{id}            // Get inventory details
GET /api/sellers/{id}/inventory    // Get seller inventory

// User Queries (Platform/UI Safe)
GET /api/me                        // Get current user
GET /api/sellers/{id}              // Get seller details
```

### 3.3 Platform APIs (Forbidden in Runtime)

```typescript
// These endpoints CANNOT exist in runtime
POST /api/catalog/products          // Platform catalog management
GET /api/catalog/products          // Platform catalog access
POST /api/sourcing/import          // Platform sourcing
GET /api/opportunities             // Platform opportunities
POST /api/workflows/execute        // Platform workflows
```

---

## Section 4: Code Pattern Authority

### 4.1 Allowed Runtime Patterns

```typescript
// Runtime domain logic - ALLOWED
class OrderService {
  async createOrder(data: CreateOrderData) {
    // Runtime database with transaction
    return await this.prisma.$transaction(async (tx) => {
      const order = await tx.order.create({ data })
      await this.reserveInventory(tx, data.items)
      await this.createAuditEvent(tx, order.id, 'created')
      return order
    })
  }
  
  async transitionOrder(orderId: string, status: OrderStatus) {
    // State machine validation
    const order = await this.prisma.order.findUnique({ where: { id: orderId } })
    if (!this.stateMachine.canTransition(order.status, status)) {
      throw new InvalidTransitionError(order.status, status)
    }
    
    return await this.prisma.$transaction(async (tx) => {
      const updated = await tx.order.update({
        where: { id: orderId },
        data: { status }
      })
      await this.handleInventoryEffects(tx, updated)
      await this.createAuditEvent(tx, orderId, 'transitioned', { status })
      return updated
    })
  }
}

// Payment processing - ALLOWED
class PaymentService {
  async processPayment(data: CreatePaymentData) {
    // Atomic payment processing
    return await this.prisma.$transaction(async (tx) => {
      const payment = await tx.paymentAttempt.create({ data })
      await this.updateOrderPaymentStatus(tx, data.orderId, payment.id)
      await this.createAuditEvent(tx, payment.id, 'payment_attempted')
      return payment
    })
  }
}
```

### 4.2 Forbidden Platform Patterns

```typescript
// FORBIDDEN: Platform logic in runtime
class CatalogService {
  async createProduct(data: CreateProductData) {
    // VIOLATION: Catalog belongs to platform
    return await this.prisma.product.create({ data })
  }
  
  async enrichProduct(productId: string) {
    // VIOLATION: AI enrichment belongs to platform
    const enrichment = await this.aiService.enrich(productId)
    return await this.prisma.product.update({
      where: { id: productId },
      data: { enrichment }
    })
  }
}

// FORBIDDEN: Platform database tables
model Product {
  id        String   @id @default(cuid())
  name      String
  // VIOLATION: Product model belongs in platform
}

model Opportunity {
  id         String   @id @default(cuid())
  profit     Decimal
  // VIOLATION: Opportunity model belongs in platform
}
```

---

## Section 5: Integration Authority

### 5.1 External API Integration (Runtime Domain)

```typescript
// Webhook handling (runtime domain) - ALLOWED
class PaymentWebhookController {
  async handleStripeWebhook(signature: string, payload: string) {
    // Runtime payment processing
    const event = this.verifyWebhook(signature, payload)
    return await this.paymentService.processWebhook(event)
  }
}

// Rate limiting (runtime domain) - ALLOWED
class RateLimitMiddleware {
  async checkRateLimit(req: Request) {
    const key = this.getRateLimitKey(req)
    const usage = await this.redis.incr(key)
    
    if (usage > this.limits[key]) {
      throw new RateLimitExceededError()
    }
    
    await this.redis.expire(key, this.window)
  }
}
```

### 5.2 Platform Consumption (Safe)

```typescript
// Runtime provides query APIs for platform consumption - ALLOWED
class OrderController {
  async getOrder(req: Request, res: Response) {
    // Query API - safe for platform consumption
    const order = await this.orderService.getOrder(req.params.id)
    res.json(order)
  }
  
  async getOrdersBySeller(req: Request, res: Response) {
    // Query API - safe for platform consumption
    const orders = await this.orderService.getOrdersBySeller(req.params.sellerId)
    res.json(orders)
  }
}
```

---

## Section 6: Enforcement Mechanisms

### 6.1 CI Enforcement Rules

The L1 verification enforces:

1. **No platform logic patterns** in runtime code
2. **No platform database tables** in runtime schema
3. **Proper command API implementation** with audit logging
4. **Query API read-only verification**
5. **Runtime authority verification**

### 6.2 Violation Response Protocol

If boundary violations are detected:

1. **STOP** the work immediately
2. **IDENTIFY** the domain ownership violation
3. **MOVE** logic to correct domain (sellora)
4. **REMOVE** platform tables from runtime schema
5. **UPDATE** API contracts to respect boundaries

### 6.3 Merge Blocking

- **Branch Protection**: Requires L1 verification check to pass
- **PR Validation**: Automatic violation detection and blocking
- **Artifact Evidence**: Comprehensive violation reporting
- **Status Tracking**: Clear compliance/non-compliance status

---

## Section 7: Governance Status

### 7.1 Current State

```yaml
L1 Verification: VERIFIED
Runtime Authority: ESTABLISHED
Platform Boundaries: ENFORCED
Merge Blocking: ACTIVE
CI Governance: OPERATIONAL
```

### 7.2 Compliance Metrics

```yaml
Cross-Domain Boundaries: ENFORCED
Schema Authority: ENFORCED
Authentication Authority: ENFORCED
Rate Limiting Authority: ENFORCED
Environment Authority: ENFORCED
```

### 7.3 Next Steps

1. **Phase 1**: Runtime hardening and failure gates
2. **Phase 2**: Contract stabilization and SDK generation
3. **Phase 3**: Repository role normalization
4. **Phase 4**: Cross-repo governance implementation

---

## Section 8: Success Definition

### 8.1 Runtime Ownership Success Criteria

- [x] Single source of truth for transactional commerce operations
- [x] Clear domain boundaries enforced by CI
- [x] Platform dependencies eliminated from runtime
- [x] Merge blocking active for boundary violations
- [x] Comprehensive audit trail for all operations

### 8.2 Architectural Benefits

- **Velocity**: No duplicated state management
- **Debugging**: Single source of truth for issues
- **Security**: Clear authority boundaries
- **Scalability**: Domain-specific optimization
- **Maintainability**: Clear ownership and responsibility

---

**This ownership matrix establishes order-management-backend as the authoritative runtime backend for commerce operations with clear boundaries and enforcement mechanisms.**

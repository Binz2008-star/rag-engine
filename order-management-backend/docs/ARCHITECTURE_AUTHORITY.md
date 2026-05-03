# Architecture Authority - Runtime Core

## **Effective: 2026-04-08**

---

## **Domain Authority**

### **Runtime Owns (Authoritative)**
- Orders (creation, state transitions, lifecycle management)
- Payments (processing, state changes, reconciliation, webhooks)
- Authentication (JWT tokens, user management, session handling)
- State Machine (order transitions, payment transitions, validation)
- Audit Events (transactional event trail, actor tracking)
- Inventory Mutations (stock reservations, deductions, releases)
- Rate Limiting (API rate limiting policies)
- Database Schema (runtime tables, relationships, constraints)

### **Runtime Provides (APIs)**
- Order CRUD operations (commands + queries)
- Payment processing endpoints (commands + queries)
- Authentication endpoints (commands)
- Seller dashboard APIs (queries)
- Public storefront APIs (queries)
- Health and monitoring endpoints (queries)

### **Runtime Forbidden (Platform Domain)**
- Catalog management (products, categories, templates)
- AI sourcing (supplier import, enrichment, normalization)
- Opportunity engine (profit discovery, scoring, recommendations)
- Workflow automation (policy-governed automation, decision engines)
- Platform integration (external services, third-party APIs)
- Localization (Arabic/English support)
- WhatsApp integration (messaging, conversational commerce)

---

## **Data Authority**

### **Runtime Database (Authoritative)**
```sql
-- Transactional tables
orders
order_events
payments
payment_attempts
payment_events
users
sessions
inventory
inventory_reservations
audit_events
rate_limits
```

### **Platform Database (Forbidden)**
```sql
-- These tables CANNOT exist in runtime
products
categories
catalog_templates
enrichment_data
opportunity_scores
sourcing_imports
autonomy_policies
workflow_runs
integration_configs
translations
```

---

## **API Authority**

### **Command APIs (Runtime Only)**
```typescript
// Order Commands
POST /api/orders
PATCH /api/orders/{id}/status
POST /api/orders/{id}/cancel

// Payment Commands
POST /api/payments
POST /api/payments/{id}/complete
POST /api/payments/{id}/refund

// Inventory Commands
POST /api/inventory/reserve
POST /api/inventory/release
POST /api/inventory/deduct

// Auth Commands
POST /api/auth/login
DELETE /api/auth/login
POST /api/auth/register
```

### **Query APIs (Safe Consumption)**
```typescript
// Order Queries
GET /api/orders/{id}
GET /api/sellers/{id}/orders
GET /api/orders/{id}/events

// Payment Queries
GET /api/payments/{id}
GET /api/payments/{id}/events

// Inventory Queries
GET /api/inventory/{id}
GET /api/sellers/{id}/inventory

// User Queries
GET /api/me
GET /api/sellers/{id}
```

### **Platform APIs (Forbidden)**
```typescript
// These endpoints CANNOT exist in runtime
POST /api/catalog/products
GET /api/catalog/products
POST /api/sourcing/import
GET /api/opportunities
POST /api/workflows/execute
```

---

## **Code Patterns**

### **Allowed Patterns**
```typescript
// Runtime domain logic
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

// Payment processing
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

### **Forbidden Patterns**
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

## **Integration Rules**

### **External API Integration**
```typescript
// Webhook handling (runtime domain)
class PaymentWebhookController {
  async handleStripeWebhook(signature: string, payload: string) {
    // Runtime payment processing
    const event = this.verifyWebhook(signature, payload)
    return await this.paymentService.processWebhook(event)
  }
}

// Rate limiting (runtime domain)
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

### **Platform Consumption**
```typescript
// Runtime provides query APIs for platform consumption
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

## **CI Enforcement**

The boundary checks CI workflow enforces:

1. **No platform logic patterns** in runtime code
2. **No platform database tables** in runtime schema
3. **Proper command API implementation** with audit logging
4. **Query API read-only verification**
5. **Runtime authority verification**

---

## **Violation Response**

If boundary violations are detected:

1. **Stop** the work immediately
2. **Identify** the domain ownership violation
3. **Move** logic to correct domain (sellora)
4. **Remove** platform tables from runtime schema
5. **Update** API contracts to respect boundaries

---

## **This authority document maintains runtime as the single source of truth for transactional commerce operations.**

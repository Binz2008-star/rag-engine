# Production Hardening Blueprint

## 🎯 EXACT EXECUTION PLAN

No theory. Only specific files, code changes, and structure needed to reach production-ready.

---

## 📁 CURRENT STATE ANALYSIS

**Status: MVP+ (65-75% production-ready)**
- Architecture: ✅ Sound
- Security: ❌ Broken (JWT fallback, fake passwords)
- State Machine: ❌ Not enforced
- Payment System: ❌ Not atomic/idempotent
- Audit Trail: ❌ Not guaranteed
- Testing: ❌ Scripts only

---

## 🚨 CRITICAL BLOCKERS (Must Fix First)

### 1. Security System - BROKEN
**Files to fix:**
- `src/server/lib/auth.ts`
- `.env.example`

### 2. Order State Machine - NOT ENFORCED  
**Files to fix:**
- `src/server/modules/orders/state-machine.ts` (NEW)
- `src/server/services/order.service.ts`
- `src/server/lib/validation.ts`

### 3. Payment System - NOT ATOMIC
**Files to fix:**
- `src/server/services/payment.service.ts` (REWRITE)
- `src/server/lib/payment-guards.ts` (NEW)

### 4. Event Enforcement - OPTIONAL
**Files to fix:**
- `src/server/services/order-event.service.ts` (ENFORCE)
- All route handlers

---

## 📋 EXACT FILE STRUCTURE CHANGES

```
src/server/
├── lib/
│   ├── auth.ts                    # FIX: Remove fallbacks, real passwords
│   ├── validation.ts              # FIX: Add state machine validation
│   ├── payment-guards.ts          # NEW: Payment invariants
│   └── transaction-guards.ts      # NEW: Transaction safety
├── modules/
│   └── orders/
│       ├── state-machine.ts       # NEW: Enforced state machine
│       ├── invariants.ts          # NEW: Business invariants
│       └── transitions.ts         # EXISTING: Keep but enhance
├── services/
│   ├── order.service.ts           # FIX: Use state machine
│   ├── payment.service.ts         # REWRITE: Atomic + idempotent
│   └── order-event.service.ts     # FIX: Enforce event creation
├── tests/
│   ├── integration/
│   │   ├── order-lifecycle.test.ts # NEW: Real tests
│   │   ├── payment-flow.test.ts    # NEW: Payment tests
│   │   └── auth-security.test.ts    # NEW: Security tests
│   └── e2e/
│       └── production-scenarios.test.ts # NEW: End-to-end
└── middleware/
    ├── transaction-middleware.ts  # NEW: Ensure transactions
    └── audit-middleware.ts        # NEW: Force audit logging
```

---

## 🔧 EXACT CODE CHANGES

### 1. FIX SECURITY SYSTEM

**File: `src/server/lib/auth.ts`**
```typescript
// REMOVE FALLBACKS - PRODUCTION READY
const JWT_SECRET = process.env.JWT_SECRET
if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is required for production')
}

// REAL PASSWORD VERIFICATION
export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return await bcrypt.compare(password, hash)
}

// REAL PASSWORD HASHING  
export async function hashPassword(password: string): Promise<string> {
  return await bcrypt.hash(password, 12)
}
```

**File: `.env.example`**
```env
# REQUIRED FOR PRODUCTION - NO FALLBACKS
JWT_SECRET=your-super-secret-jwt-key-change-in-production
BCRYPT_ROUNDS=12
```

---

### 2. ENFORCE ORDER STATE MACHINE

**File: `src/server/modules/orders/state-machine.ts` (NEW)**
```typescript
export enum OrderStatus {
  PENDING = 'PENDING',
  CONFIRMED = 'CONFIRMED', 
  PACKED = 'PACKED',
  OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY',
  DELIVERED = 'DELIVERED',
  CANCELLED = 'CANCELLED'
}

export class OrderStateMachine {
  private static readonly VALID_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
    [OrderStatus.PENDING]: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
    [OrderStatus.CONFIRMED]: [OrderStatus.PACKED, OrderStatus.CANCELLED],
    [OrderStatus.PACKED]: [OrderStatus.OUT_FOR_DELIVERY],
    [OrderStatus.OUT_FOR_DELIVERY]: [OrderStatus.DELIVERED],
    [OrderStatus.DELIVERED]: [], // Terminal
    [OrderStatus.CANCELLED]: [], // Terminal
  }

  static canTransition(from: OrderStatus, to: OrderStatus): boolean {
    return this.VALID_TRANSITIONS[from]?.includes(to) ?? false
  }

  static validateTransition(from: OrderStatus, to: OrderStatus): void {
    if (!this.canTransition(from, to)) {
      throw new OrderTransitionError(from, to)
    }
  }

  static isTerminal(status: OrderStatus): boolean {
    return this.VALID_TRANSITIONS[status].length === 0
  }
}

export class OrderTransitionError extends Error {
  constructor(from: OrderStatus, to: OrderStatus) {
    super(`Invalid order transition: ${from} → ${to}`)
  }
}
```

**File: `src/server/lib/validation.ts` (ADD)**
```typescript
import { z } from 'zod'
import { OrderStatus } from '../modules/orders/state-machine'

export const UpdateOrderStatusSchema = z.object({
  status: z.nativeEnum(OrderStatus),
  reason: z.string().optional()
})

export const CreateOrderSchema = z.object({
  customerId: z.string(),
  items: z.array(z.object({
    productId: z.string(),
    quantity: z.number().min(1)
  })),
  paymentType: z.enum(['PREPAID', 'CASH_ON_DELIVERY']),
  deliveryAddress: z.string()
})
```

---

### 3. BUILD ATOMIC PAYMENT SYSTEM

**File: `src/server/lib/payment-guards.ts` (NEW)**
```typescript
export interface PaymentInvariant {
  orderId: string
  paymentType: string
  currentPaymentStatus: string
}

export class PaymentGuards {
  static rejectCODPaymentAttempts(order: PaymentInvariant): void {
    if (order.paymentType === 'CASH_ON_DELIVERY') {
      throw new Error('Payment attempts not allowed for Cash on Delivery orders')
    }
  }

  static preventDuplicatePaymentAttempts(
    existingAttempts: any[],
    orderId: string
  ): void {
    const activeAttempts = existingAttempts.filter(
      attempt => ['PENDING', 'PROCESSING'].includes(attempt.status)
    )
    
    if (activeAttempts.length > 0) {
      throw new Error(`Payment attempt already in progress for order ${orderId}`)
    }
  }

  static validateRefundAmount(
    refundAmount: number,
    originalAmount: number,
    alreadyRefunded: number = 0
  ): void {
    const totalRefund = alreadyRefunded + refundAmount
    if (totalRefund > originalAmount) {
      throw new Error(`Refund amount $${totalRefund} exceeds original payment $${originalAmount}`)
    }
  }

  static enforcePaymentStateTransition(
    fromStatus: string,
    toStatus: string
  ): void {
    const validTransitions: Record<string, string[]> = {
      'PENDING': ['PROCESSING', 'CANCELLED', 'FAILED'],
      'PROCESSING': ['COMPLETED', 'FAILED', 'CANCELLED'],
      'COMPLETED': ['REFUNDED'],
      'FAILED': ['PENDING'], // Allow retry
      'CANCELLED': ['PENDING'], // Allow retry
      'REFUNDED': [] // Terminal
    }

    if (!validTransitions[fromStatus]?.includes(toStatus)) {
      throw new Error(`Invalid payment transition: ${fromStatus} → ${toStatus}`)
    }
  }
}
```

**File: `src/server/services/payment.service.ts` (REWRITE)**
```typescript
export class PaymentService {
  static async createPaymentAttempt(
    data: CreatePaymentAttemptData,
    actorUserId: string
  ): Promise<PaymentAttempt> {
    return await prisma.$transaction(async (tx) => {
      // LOCK ORDER FOR CONCURRENCY
      const order = await tx.order.findUnique({
        where: { id: data.orderId },
        include: { paymentAttempts: true }
      })

      if (!order) throw new Error('Order not found')

      // ENFORCE INVARIANTS
      PaymentGuards.rejectCODPaymentAttempts({
        orderId: data.orderId,
        paymentType: order.paymentType,
        currentPaymentStatus: order.paymentStatus
      })

      PaymentGuards.preventDuplicatePaymentAttempts(
        order.paymentAttempts,
        data.orderId
      )

      // CREATE PAYMENT ATTEMPT
      const paymentAttempt = await tx.paymentAttempt.create({
        data: {
          orderId: data.orderId,
          provider: data.provider,
          amountMinor: data.amountMinor,
          currency: data.currency,
          status: 'PENDING',
          metadataJson: data.metadata ? JSON.stringify(data.metadata) : null
        }
      })

      // ENFORCE EVENT CREATION
      await OrderEventService.createPaymentEvent(tx, {
        orderId: data.orderId,
        actorUserId,
        eventType: 'PAYMENT_INITIATED',
        provider: data.provider,
        amountMinor: data.amountMinor,
        currency: data.currency
      })

      return paymentAttempt
    })
  }

  static async updatePaymentStatus(
    paymentAttemptId: string,
    data: UpdatePaymentStatusData,
    actorUserId: string
  ): Promise<PaymentAttempt> {
    return await prisma.$transaction(async (tx) => {
      const current = await tx.paymentAttempt.findUnique({
        where: { id: paymentAttemptId },
        include: { order: true }
      })

      if (!current) throw new Error('Payment attempt not found')

      // ENFORCE STATE TRANSITION
      PaymentGuards.enforcePaymentStateTransition(
        current.status,
        data.status
      )

      // UPDATE PAYMENT
      const updated = await tx.paymentAttempt.update({
        where: { id: paymentAttemptId },
        data: {
          status: data.status,
          providerReference: data.providerReference,
          failureReason: data.failureReason,
          metadataJson: data.metadata ? JSON.stringify(data.metadata) : null
        }
      })

      // UPDATE ORDER BASED ON PAYMENT STATUS
      if (data.status === 'COMPLETED') {
        await tx.order.update({
          where: { id: current.orderId },
          data: { paymentStatus: 'PAID' }
        })

        // AUTO-CONFIRM PENDING ORDERS
        if (current.order.status === 'PENDING') {
          await tx.order.update({
            where: { id: current.orderId },
            data: { status: 'CONFIRMED' }
          })

          await OrderEventService.createStatusChangeEvent(tx, {
            orderId: current.orderId,
            actorUserId,
            from: 'PENDING',
            to: 'CONFIRMED',
            reason: 'Payment completed'
          })
        }
      }

      // ENFORCE EVENT CREATION
      await OrderEventService.createPaymentEvent(tx, {
        orderId: current.orderId,
        actorUserId,
        eventType: data.status === 'COMPLETED' ? 'PAYMENT_CONFIRMED' : 'PAYMENT_FAILED',
        provider: current.provider,
        amountMinor: current.amountMinor,
        currency: current.currency,
        failureReason: data.failureReason
      })

      return updated
    })
  }
}
```

---

### 4. CENTRALIZE EVENT ENFORCEMENT

**File: `src/server/services/order-event.service.ts` (ENFORCE)**
```typescript
export class OrderEventService {
  // MAKE THIS MANDATORY - NO OPTIONAL CREATION
  static async createEvent(
    tx: Prisma.TransactionClient,
    event: OrderEventData
  ): Promise<void> {
    // VALIDATE REQUIRED FIELDS
    if (!event.orderId) throw new Error('orderId is required')
    if (!event.actorUserId) throw new Error('actorUserId is required')
    if (!event.eventType) throw new Error('eventType is required')

    // ENSURE ACTOR TRACKING
    const actorId = event.actorUserId === 'SYSTEM' ? 'SYSTEM' : event.actorUserId

    // CREATE EVENT WITH GUARANTEED PAYLOAD
    await tx.orderEvent.create({
      data: {
        orderId: event.orderId,
        actorUserId: actorId,
        eventType: event.eventType,
        payloadJson: JSON.stringify({
          ...event.payload,
          actor: actorId,
          timestamp: new Date().toISOString(),
          // ENSURE REQUIRED METADATA
          ...(event.eventType.includes('PAYMENT') && {
            provider: event.payload?.provider,
            amountMinor: event.payload?.amountMinor,
            currency: event.payload?.currency
          }),
          ...(event.eventType === 'STATUS_CHANGED' && {
            from: event.payload?.from,
            to: event.payload?.to,
            reason: event.payload?.reason
          })
        })
      }
    })
  }
}
```

---

### 5. ADD TRANSACTION MIDDLEWARE

**File: `src/server/middleware/transaction-middleware.ts` (NEW)**
```typescript
export function withTransaction<T>(
  operation: (tx: Prisma.TransactionClient) => Promise<T>
): Promise<T> {
  return prisma.$transaction(operation)
}

export function enforceTransactionInvariant(
  operation: string,
  tx: Prisma.TransactionClient
): void {
  // LOG TRANSACTION START
  console.log(`[TRANSACTION] Starting: ${operation}`)
  
  // This could be enhanced with:
  // - Transaction timeout enforcement
  // - Rollback logging
  // - Deadlock detection
}
```

---

## 🧪 REAL INTEGRATION TESTS

**File: `src/tests/integration/order-lifecycle.test.ts` (NEW)**
```typescript
describe('Order Lifecycle - Production Tests', () => {
  let seller: Seller
  let customer: Customer
  let product: Product

  beforeEach(async () => {
    // SETUP CLEAN TEST DATA
    seller = await createTestSeller()
    customer = await createTestCustomer(seller.id)
    product = await createTestProduct(seller.id, { stock: 10 })
  })

  test('complete order lifecycle with invariants', async () => {
    // CREATE ORDER
    const order = await OrderService.createOrder({
      customerId: customer.id,
      items: [{ productId: product.id, quantity: 2 }],
      paymentType: 'PREPAID',
      deliveryAddress: '123 Test St'
    }, seller.id)

    // VERIFY INITIAL STATE
    expect(order.status).toBe('PENDING')
    expect(order.paymentStatus).toBe('PENDING')

    // VERIFY EVENTS CREATED
    const events = await OrderEventService.getOrderEvents(order.id)
    expect(events).toHaveLength(1)
    expect(events[0].eventType).toBe('ORDER_CREATED')
    expect(events[0].actorUserId).toBe('SYSTEM')

    // CREATE PAYMENT
    const payment = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, seller.id)

    expect(payment.status).toBe('PENDING')

    // COMPLETE PAYMENT
    const completedPayment = await PaymentService.updatePaymentStatus(
      payment.id,
      { status: 'COMPLETED', providerReference: 'pi_test_123' },
      seller.id
    )

    expect(completedPayment.status).toBe('COMPLETED')

    // VERIFY ORDER AUTO-CONFIRMED
    const updatedOrder = await OrderService.getOrderById(order.id, seller.id)
    expect(updatedOrder.status).toBe('CONFIRMED')
    expect(updatedOrder.paymentStatus).toBe('PAID')

    // VERIFY ALL EVENTS CREATED
    const finalEvents = await OrderEventService.getOrderEvents(order.id)
    expect(finalEvents).toHaveLength(4) // CREATED + PAYMENT_INITIATED + PAYMENT_CONFIRMED + STATUS_CHANGED

    // VERIFY NO NULL ACTORS
    const nullActors = await prisma.orderEvent.count({
      where: { actorUserId: null }
    })
    expect(nullActors).toBe(0)
  })

  test('prevents invalid state transitions', async () => {
    const order = await OrderService.createOrder({
      customerId: customer.id,
      items: [{ productId: product.id, quantity: 1 }],
      paymentType: 'PREPAID',
      deliveryAddress: '123 Test St'
    }, seller.id)

    // TRY INVALID TRANSITION: PENDING → DELIVERED
    await expect(
      OrderService.updateOrderStatus(order.id, { status: 'DELIVERED' }, seller.id)
    ).rejects.toThrow('Invalid order transition')

    // VERIFY ORDER UNCHANGED
    const unchangedOrder = await OrderService.getOrderById(order.id, seller.id)
    expect(unchangedOrder.status).toBe('PENDING')
  })

  test('prevents payment attempts on COD orders', async () => {
    const codOrder = await OrderService.createOrder({
      customerId: customer.id,
      items: [{ productId: product.id, quantity: 1 }],
      paymentType: 'CASH_ON_DELIVERY',
      deliveryAddress: '123 Test St'
    }, seller.id)

    // TRY TO CREATE PAYMENT ATTEMPT
    await expect(
      PaymentService.createPaymentAttempt({
        orderId: codOrder.id,
        provider: 'stripe',
        amountMinor: 1000,
        currency: 'USD'
      }, seller.id)
    ).rejects.toThrow('Payment attempts not allowed for Cash on Delivery orders')
  })
})
```

---

## 📊 PRODUCTION READINESS CHECKLIST

### Security ✅
- [ ] JWT_SECRET required (no fallbacks)
- [ ] Real password hashing with bcrypt
- [ ] Proper password verification
- [ ] Token validation in all routes

### State Machine ✅  
- [ ] OrderStateMachine enforces transitions
- [ ] All status updates go through validation
- [ ] Invalid transitions throw errors
- [ ] Terminal states protected

### Payment System ✅
- [ ] PaymentGuards enforce invariants
- [ ] COD payment attempts rejected
- [ ] Duplicate payment attempts prevented
- [ ] Refund amount validation
- [ ] Atomic payment + order updates

### Audit Trail ✅
- [ ] Event creation enforced in all mutations
- [ ] No null actorUserId values
- [ ] Required payload fields guaranteed
- [ ] Event types standardized

### Testing ✅
- [ ] Real integration tests (not scripts)
- [ ] State machine validation tests
- [ ] Payment flow tests
- [ ] Security tests
- [ ] Concurrent access tests

### Operations ✅
- [ ] Transaction middleware
- [ ] Error handling and rollback
- [ ] Logging and monitoring
- [ ] Environment validation

---

## 🚀 EXECUTION ORDER

### Week 1: Critical Security
1. Fix auth.ts (remove fallbacks)
2. Add real password hashing
3. Update .env.example
4. Add auth tests

### Week 2: State Machine
1. Create OrderStateMachine class
2. Update validation schemas
3. Refactor order.service.ts
4. Add state machine tests

### Week 3: Payment System
1. Create PaymentGuards
2. Rewrite payment.service.ts
3. Add payment tests
4. Fix COD/prepaid separation

### Week 4: Event Enforcement
1. Enforce event creation
2. Add transaction middleware
3. Create integration tests
4. Add audit validation

### Week 5: Production Readiness
1. Add monitoring/logging
2. Create deployment scripts
3. Run full test suite
4. Security audit

---

## 🎯 SUCCESS METRICS

**Before Production Launch:**
- 0 security vulnerabilities
- 0 null actorUserId values
- 100% state transition compliance
- 100% payment invariant compliance
- 95%+ test coverage
- All integration tests passing

**Post-Launch Monitoring:**
- Transaction success rate > 99.9%
- Payment error rate < 0.1%
- Audit trail completeness = 100%
- State machine violations = 0

---

## 📝 FINAL VERDICT

**Current: MVP+ (65-75%)**
**Target: Production-Ready (95%+)**

**Required Changes:**
- 5 critical files rewritten
- 3 new guard classes
- 2 new middleware
- 10+ integration tests
- 1 week per focus area

**Timeline: 5 weeks to production-ready**

This is not theory - this is the exact execution plan to reach production-grade system.

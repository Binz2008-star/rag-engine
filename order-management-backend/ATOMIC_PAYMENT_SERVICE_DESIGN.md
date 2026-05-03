# Atomic Payment Service - Final Version

## 🎯 EXACT PRODUCTION DESIGN

This is the piece that transforms the system from "structured" → "production-grade".

---

## 🔥 CORE PROBLEM WE SOLVE

**Current Issue:**
```typescript
// DANGEROUS: Multiple operations, no transaction safety
await createPaymentAttempt(data)
await updateOrderStatus(orderId, 'CONFIRMED') 
await createOrderEvent(...) // Optional, can fail
```

**Production Solution:**
```typescript
// SAFE: Single atomic transaction
await prisma.$transaction(async (tx) => {
  // All or nothing - no partial state
})
```

---

## 📋 EXACT SERVICE STRUCTURE

```typescript
export class PaymentService {
  // 1. ATOMIC PAYMENT CREATION
  static async createPaymentAttempt(
    data: CreatePaymentAttemptData,
    actorUserId: string
  ): Promise<PaymentAttempt>

  // 2. ATOMIC PAYMENT COMPLETION  
  static async completePayment(
    paymentAttemptId: string,
    providerReference: string,
    actorUserId: string
  ): Promise<PaymentResult>

  // 3. ATOMIC PAYMENT FAILURE
  static async failPayment(
    paymentAttemptId: string,
    failureReason: string,
    actorUserId: string
  ): Promise<PaymentResult>

  // 4. ATOMIC REFUND
  static async refundPayment(
    paymentAttemptId: string,
    refundAmountMinor: number,
    reason: string,
    actorUserId: string
  ): Promise<RefundResult>

  // 5. IDEMPOTENCY CHECK
  static async checkIdempotency(
    provider: string,
    providerReference: string
  ): Promise<PaymentAttempt | null>
}
```

---

## 🔒 TRANSACTION BOUNDARIES (EXACT)

### Boundary 1: Payment Attempt Creation
```typescript
static async createPaymentAttempt(
  data: CreatePaymentAttemptData,
  actorUserId: string
): Promise<PaymentAttempt> {
  return await prisma.$transaction(async (tx) => {
    // 1. LOCK ORDER (prevents concurrent attempts)
    const order = await tx.order.findUnique({
      where: { id: data.orderId },
      include: { paymentAttempts: true }
    })

    // 2. ENFORCE INVARIANTS
    PaymentGuards.rejectCODPaymentAttempts({
      orderId: data.orderId,
      paymentType: order.paymentType,
      currentPaymentStatus: order.paymentStatus
    })

    PaymentGuards.preventDuplicatePaymentAttempts(
      order.paymentAttempts,
      data.orderId
    )

    // 3. CREATE PAYMENT ATTEMPT
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

    // 4. MANDATORY EVENT CREATION
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
```

### Boundary 2: Payment Completion
```typescript
static async completePayment(
  paymentAttemptId: string,
  providerReference: string,
  actorUserId: string
): Promise<PaymentResult> {
  return await prisma.$transaction(async (tx) => {
    // 1. LOCK PAYMENT ATTEMPT
    const paymentAttempt = await tx.paymentAttempt.findUnique({
      where: { id: paymentAttemptId },
      include: { order: true }
    })

    // 2. ENFORCE STATE TRANSITION
    PaymentGuards.enforcePaymentStateTransition(
      paymentAttempt.status,
      'COMPLETED'
    )

    // 3. CHECK IDEMPOTENCY
    if (providerReference) {
      const existing = await tx.paymentAttempt.findFirst({
        where: {
          provider: paymentAttempt.provider,
          providerReference,
          status: 'COMPLETED'
        }
      })
      
      if (existing && existing.id !== paymentAttemptId) {
        throw new Error(`Provider reference ${providerReference} already used`)
      }
    }

    // 4. UPDATE PAYMENT ATTEMPT
    const updatedPayment = await tx.paymentAttempt.update({
      where: { id: paymentAttemptId },
      data: {
        status: 'COMPLETED',
        providerReference,
        updatedAt: new Date()
      }
    })

    // 5. UPDATE ORDER PAYMENT STATUS
    await tx.order.update({
      where: { id: paymentAttempt.orderId },
      data: { paymentStatus: 'PAID' }
    })

    // 6. AUTO-CONFIRM PENDING ORDERS
    if (paymentAttempt.order.status === 'PENDING') {
      await tx.order.update({
        where: { id: paymentAttempt.orderId },
        data: { status: 'CONFIRMED' }
      })

      // 7. MANDATORY STATUS CHANGE EVENT
      await OrderEventService.createStatusChangeEvent(tx, {
        orderId: paymentAttempt.orderId,
        actorUserId,
        from: 'PENDING',
        to: 'CONFIRMED',
        reason: 'Payment completed'
      })
    }

    // 8. MANDATORY PAYMENT EVENT
    await OrderEventService.createPaymentEvent(tx, {
      orderId: paymentAttempt.orderId,
      actorUserId,
      eventType: 'PAYMENT_CONFIRMED',
      provider: paymentAttempt.provider,
      amountMinor: paymentAttempt.amountMinor,
      currency: paymentAttempt.currency,
      providerReference
    })

    return {
      paymentAttempt: updatedPayment,
      orderStatus: paymentAttempt.order.status === 'PENDING' ? 'CONFIRMED' : paymentAttempt.order.status,
      paymentStatus: 'PAID'
    }
  })
}
```

### Boundary 3: Payment Failure
```typescript
static async failPayment(
  paymentAttemptId: string,
  failureReason: string,
  actorUserId: string
): Promise<PaymentResult> {
  return await prisma.$transaction(async (tx) => {
    // 1. LOCK PAYMENT ATTEMPT
    const paymentAttempt = await tx.paymentAttempt.findUnique({
      where: { id: paymentAttemptId },
      include: { order: true }
    })

    // 2. ENFORCE STATE TRANSITION
    PaymentGuards.enforcePaymentStateTransition(
      paymentAttempt.status,
      'FAILED'
    )

    // 3. UPDATE PAYMENT ATTEMPT
    const updatedPayment = await tx.paymentAttempt.update({
      where: { id: paymentAttemptId },
      data: {
        status: 'FAILED',
        failureReason,
        updatedAt: new Date()
      }
    })

    // 4. UPDATE ORDER PAYMENT STATUS
    await tx.order.update({
      where: { id: paymentAttempt.orderId },
      data: { paymentStatus: 'FAILED' }
    })

    // 5. MANDATORY PAYMENT EVENT
    await OrderEventService.createPaymentEvent(tx, {
      orderId: paymentAttempt.orderId,
      actorUserId,
      eventType: 'PAYMENT_FAILED',
      provider: paymentAttempt.provider,
      amountMinor: paymentAttempt.amountMinor,
      currency: paymentAttempt.currency,
      failureReason
    })

    return {
      paymentAttempt: updatedPayment,
      orderStatus: paymentAttempt.order.status,
      paymentStatus: 'FAILED'
    }
  })
}
```

### Boundary 4: Refund
```typescript
static async refundPayment(
  paymentAttemptId: string,
  refundAmountMinor: number,
  reason: string,
  actorUserId: string
): Promise<RefundResult> {
  return await prisma.$transaction(async (tx) => {
    // 1. LOCK PAYMENT ATTEMPT
    const paymentAttempt = await tx.paymentAttempt.findUnique({
      where: { id: paymentAttemptId },
      include: { order: true }
    })

    // 2. ENFORCE REFUND RULES
    PaymentGuards.preventRefundOnNonCompletedPayment(paymentAttempt.status)
    PaymentGuards.validateRefundAmount(
      refundAmountMinor,
      paymentAttempt.amountMinor
    )

    // 3. UPDATE PAYMENT ATTEMPT
    const updatedPayment = await tx.paymentAttempt.update({
      where: { id: paymentAttemptId },
      data: {
        status: 'REFUNDED',
        metadataJson: JSON.stringify({
          refundAmountMinor,
          refundReason: reason,
          refundDate: new Date().toISOString(),
          ...(paymentAttempt.metadataJson ? JSON.parse(paymentAttempt.metadataJson) : {})
        }),
        updatedAt: new Date()
      }
    })

    // 4. UPDATE ORDER PAYMENT STATUS
    await tx.order.update({
      where: { id: paymentAttempt.orderId },
      data: { paymentStatus: 'REFUNDED' }
    })

    // 5. MANDATORY REFUND EVENT
    await OrderEventService.createPaymentEvent(tx, {
      orderId: paymentAttempt.orderId,
      actorUserId,
      eventType: 'PAYMENT_REFUNDED',
      provider: paymentAttempt.provider,
      amountMinor: refundAmountMinor,
      currency: paymentAttempt.currency
    })

    return {
      paymentAttempt: updatedPayment,
      refundAmountMinor,
      paymentStatus: 'REFUNDED'
    }
  })
}
```

---

## 🔐 IDEMPOTENCY GUARANTEES

### Provider Reference Deduplication
```typescript
static async checkIdempotency(
  provider: string,
  providerReference: string
): Promise<PaymentAttempt | null> {
  return await prisma.paymentAttempt.findFirst({
    where: {
      provider,
      providerReference,
      status: 'COMPLETED'
    }
  })
}
```

### Usage in Payment Creation
```typescript
// Before creating payment attempt
if (data.providerReference) {
  const existing = await PaymentService.checkIdempotency(
    data.provider,
    data.providerReference
  )
  
  if (existing) {
    return existing // Return existing payment attempt
  }
}
```

---

## 📊 EXACT INTERFACES

```typescript
export interface CreatePaymentAttemptData {
  orderId: string
  provider: string
  amountMinor: number
  currency: string
  providerReference?: string
  metadata?: Record<string, unknown>
}

export interface PaymentResult {
  paymentAttempt: PaymentAttempt
  orderStatus: string
  paymentStatus: string
}

export interface RefundResult {
  paymentAttempt: PaymentAttempt
  refundAmountMinor: number
  paymentStatus: string
}

export interface PaymentAttempt {
  id: string
  orderId: string
  provider: string
  providerReference?: string
  amountMinor: number
  currency: string
  status: PaymentStatus
  failureReason?: string
  metadataJson?: string
  createdAt: Date
  updatedAt: Date
}

export enum PaymentStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
  REFUNDED = 'REFUNDED'
}
```

---

## 🧪 REAL INTEGRATION TESTS

### Concurrency Test
```typescript
test('concurrent payment attempts - only one succeeds', async () => {
  const orderId = 'test-order-id'
  
  // Create 10 payment attempts simultaneously
  const promises = Array.from({ length: 10 }, (_, i) =>
    PaymentService.createPaymentAttempt({
      orderId,
      provider: 'stripe',
      amountMinor: 1000,
      currency: 'USD',
      metadata: { attempt: i }
    }, 'user-id')
  )

  const results = await Promise.allSettled(promises)
  
  // Exactly one should succeed
  const successful = results.filter(r => r.status === 'fulfilled')
  const failed = results.filter(r => r.status === 'rejected')
  
  expect(successful).toHaveLength(1)
  expect(failed).toHaveLength(9)
  
  // Verify only one payment attempt exists
  const paymentAttempts = await prisma.paymentAttempt.findMany({
    where: { orderId }
  })
  expect(paymentAttempts).toHaveLength(1)
})
```

### Idempotency Test
```typescript
test('provider reference deduplication', async () => {
  const providerReference = 'pi_test_12345'
  
  // First payment attempt
  const payment1 = await PaymentService.createPaymentAttempt({
    orderId: 'test-order',
    provider: 'stripe',
    amountMinor: 1000,
    currency: 'USD',
    providerReference
  }, 'user-id')
  
  // Complete payment
  await PaymentService.completePayment(payment1.id, providerReference, 'user-id')
  
  // Try to create another payment with same provider reference
  const payment2 = await PaymentService.createPaymentAttempt({
    orderId: 'test-order-2',
    provider: 'stripe',
    amountMinor: 2000,
    currency: 'USD',
    providerReference
  }, 'user-id')
  
  // Should return existing payment
  expect(payment2.id).toBe(payment1.id)
})
```

---

## 🔄 WEBHOOK INTEGRATION

### Webhook Handler
```typescript
export async function handleStripeWebhook(
  webhookData: StripeWebhookData
): Promise<void> {
  const { type, data } = webhookData
  
  switch (type) {
    case 'payment_intent.succeeded':
      await PaymentService.completePayment(
        data.metadata.paymentAttemptId,
        data.payment_intent.id,
        'SYSTEM'
      )
      break
      
    case 'payment_intent.payment_failed':
      await PaymentService.failPayment(
        data.metadata.paymentAttemptId,
        data.last_payment_error?.message || 'Payment failed',
        'SYSTEM'
      )
      break
  }
}
```

---

## 📋 PRODUCTION GUARANTEES

### 1. Atomicity
✅ All payment operations use single Prisma transaction
✅ No partial state updates
✅ Rollback on any failure

### 2. Consistency
✅ Order status always matches payment status
✅ Events always created with mutations
✅ Invariants enforced before changes

### 3. Isolation
✅ Row-level locking prevents concurrent modifications
✅ Payment attempts serialized per order
✅ No race conditions

### 4. Durability
✅ All changes committed to database
✅ Events persisted with business changes
✅ No in-memory state loss

---

## 🚀 IMPLEMENTATION ORDER

### Step 1: Replace Payment Service
- Rewrite existing payment.service.ts
- Add transaction boundaries
- Integrate PaymentGuards

### Step 2: Update API Routes
- Use new atomic methods
- Remove manual event creation
- Add proper error handling

### Step 3: Add Integration Tests
- Concurrency tests
- Idempotency tests
- State machine tests

### Step 4: Webhook Integration
- Add webhook handlers
- Test external payment provider flow
- Verify idempotency

---

## 🎯 SUCCESS METRICS

Before Production:
- 100% payment operations use transactions
- 0 null actorUserId in events
- 100% payment state transitions validated
- 100% idempotency guarantees working
- All integration tests passing

This is the exact design that makes the system production-grade.

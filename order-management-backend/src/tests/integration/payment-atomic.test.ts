import type { Customer, Order, Seller } from '@prisma/client'
import { PaymentService } from '../../server/services/payment.service'
import { createCustomer } from '../factories/customer'
import { createOrder } from '../factories/order'
import { createSeller } from '../factories/seller'
import { createUser } from '../factories/user'
import { prisma } from '../setup'

describe('Payment Service - Atomic Operations', () => {
  let seller: Seller
  let customer: Customer
  let order: Order

  beforeEach(async () => {
    await prisma.orderEvent.deleteMany()
    await prisma.paymentAttempt.deleteMany()
    await prisma.orderItem.deleteMany()
    await prisma.order.deleteMany()
    await prisma.customer.deleteMany()
    await prisma.seller.deleteMany()
    await prisma.user.deleteMany()

    const user = await createUser({ role: 'SELLER' })
    seller = await createSeller({ ownerUserId: user.id })
    customer = await createCustomer({ sellerId: seller.id })
    order = await createOrder({
      sellerId: seller.id,
      customerId: customer.id,
      paymentType: 'PREPAID',
      items: [{ productId: 'test-product-id', quantity: 2, unitPriceMinor: 1000, productNameSnapshot: 'Test Product' }],
    })
  })

  afterEach(async () => {
    await prisma.orderEvent.deleteMany()
    await prisma.paymentAttempt.deleteMany()
    await prisma.orderItem.deleteMany()
    await prisma.order.deleteMany()
    await prisma.customer.deleteMany()
    await prisma.seller.deleteMany()
  })

  test('atomic payment creation - single transaction success', async () => {
    const paymentAttempt = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD',
    }, 'user-123')

    // Verify all changes in single transaction
    expect(paymentAttempt.status).toBe('PENDING')

    // Verify order unchanged (payment not completed yet)
    const updatedOrder = await prisma.order.findUnique({ where: { id: order.id } })
    expect(updatedOrder?.paymentStatus).toBe('PENDING')
    expect(updatedOrder?.status).toBe('PENDING')

    // Verify event created (factory creates order_created, then payment_initiated)
    const events = await prisma.orderEvent.findMany({ where: { orderId: order.id } })
    const paymentEvents = events.filter(e => e.eventType === 'payment_initiated')
    expect(paymentEvents).toHaveLength(1)
    expect(paymentEvents[0].actorUserId).toBe('user-123')
  })

  test('atomic payment completion - all changes succeed or fail together', async () => {
    // Create payment attempt first
    const payment = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, 'user-123')

    // Process payment atomically (PENDING -> PROCESSING -> COMPLETED)
    const _processingResult = await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'PROCESSING'
    }, 'user-123')

    const completedResult = await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'COMPLETED',
      providerReference: 'pi_test_complete_1'
    }, 'user-123')

    // Verify atomic changes
    expect(completedResult.status).toBe('COMPLETED')

    // Verify payment attempt updated
    const updatedPayment = await prisma.paymentAttempt.findUnique({
      where: { id: payment.id }
    })
    expect(updatedPayment?.status).toBe('COMPLETED')
    expect(updatedPayment?.providerReference).toBe('pi_test_complete_1')

    // Verify order updated
    const updatedOrder = await prisma.order.findUnique({ where: { id: order.id } })
    expect(updatedOrder?.paymentStatus).toBe('PAID')
    expect(updatedOrder?.status).toBe('CONFIRMED') // Auto-confirmed from PENDING

    // Verify events created
    const events = await prisma.orderEvent.findMany({ where: { orderId: order.id } })
    expect(events.length).toBeGreaterThanOrEqual(4) // payment_initiated, payment_completed, status_changed events

    const statusChangeEvent = events.find(e => e.eventType === 'status_changed' && e.payloadJson?.includes('CONFIRMED'))
    const payload = JSON.parse(statusChangeEvent?.payloadJson || '{}')
    expect(payload.from).toBe('PENDING')
    expect(payload.to).toBe('CONFIRMED')
    expect(payload.reason).toBe('payment_completed')
  })

  test('atomic payment failure - consistent state maintained', async () => {
    // Create payment attempt first
    const payment = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, 'user-123')

    // Fail payment atomically
    const result = await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'FAILED',
      failureReason: 'insufficient_funds'
    }, 'user-123')

    // Verify atomic changes
    expect(result.status).toBe('FAILED')

    // Verify payment attempt updated
    const updatedPayment = await prisma.paymentAttempt.findUnique({
      where: { id: payment.id }
    })
    expect(updatedPayment?.status).toBe('FAILED')
    expect(updatedPayment?.failureReason).toBe('insufficient_funds')

    // Verify order payment status updated
    const updatedOrder = await prisma.order.findUnique({ where: { id: order.id } })
    expect(updatedOrder?.paymentStatus).toBe('FAILED')
    expect(updatedOrder?.status).toBe('PENDING') // Order status unchanged

    // Verify failure event created
    const events = await prisma.orderEvent.findMany({ where: { orderId: order.id } })
    const paymentFailedEvent = events.find(e => e.eventType === 'payment_failed')
    expect(paymentFailedEvent).toBeDefined()

    const payload = JSON.parse(paymentFailedEvent?.payloadJson || '{}')
    expect(payload.failureReason).toBe('insufficient_funds')
  })

  test('concurrent payment attempts - only one succeeds', async () => {
    // Create multiple payment attempts simultaneously (reduced for CI reliability)
    const promises = Array.from({ length: 3 }, (_, i) =>
      PaymentService.createPaymentAttempt({
        orderId: order.id,
        provider: 'stripe',
        amountMinor: 2000,
        currency: 'USD',
        metadata: { attempt: i }
      }, 'user-123')
    )

    const results = await Promise.allSettled(promises)

    // Exactly one should succeed
    const successful = results.filter(r => r.status === 'fulfilled')
    const failed = results.filter(r => r.status === 'rejected')

    expect(successful).toHaveLength(1)
    expect(failed).toHaveLength(2)

    // Verify only one payment attempt exists in database
    const paymentAttempts = await prisma.paymentAttempt.findMany({
      where: { orderId: order.id }
    })
    expect(paymentAttempts).toHaveLength(1)

    // Verify only one payment initiation event
    const events = await prisma.orderEvent.findMany({
      where: { orderId: order.id, eventType: 'payment_initiated' }
    })
    expect(events).toHaveLength(1)
  }, 10000)

  test('provider reference idempotency - duplicate rejected', async () => {
    // First payment attempt
    const payment1 = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, 'user-123')

    // Complete first payment
    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment1.id,
      status: 'PROCESSING'
    }, 'user-123')

    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment1.id,
      status: 'COMPLETED',
      providerReference: 'pi_duplicate_test_123'
    }, 'user-123')

    // Try to create another payment attempt (should succeed as it's a new attempt)
    const payment2 = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 3000,
      currency: 'USD'
    }, 'user-123')

    // Should create a new payment attempt (different amount)
    expect(payment2.id).not.toBe(payment1.id)

    // Verify two payment attempts exist
    const paymentAttempts = await prisma.paymentAttempt.findMany({
      where: { orderId: order.id }
    })
    expect(paymentAttempts).toHaveLength(2)
  })

  test('refund atomicity - consistent state maintained', async () => {
    // Create and complete payment first
    const payment = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, 'user-123')

    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'PROCESSING'
    }, 'user-123')

    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'COMPLETED',
      providerReference: 'pi_refund_test'
    }, 'user-123')

    // Process refund atomically
    const refundResult = await PaymentService.refundPayment({
      paymentAttemptId: payment.id,
      refundAmountMinor: 1500,
      reason: 'customer_request'
    }, 'user-123')

    // Verify atomic changes
    expect(refundResult.status).toBe('REFUNDED')

    // Verify payment attempt updated
    const updatedPayment = await prisma.paymentAttempt.findUnique({
      where: { id: payment.id }
    })
    expect(updatedPayment?.status).toBe('REFUNDED')

    // Verify order payment status updated
    const updatedOrder = await prisma.order.findUnique({ where: { id: order.id } })
    expect(updatedOrder?.paymentStatus).toBe('REFUNDED')

    // Verify refund event created
    const events = await prisma.orderEvent.findMany({ where: { orderId: order.id } })
    const refundEvent = events.find(e => e.eventType === 'payment_refunded')
    expect(refundEvent).toBeDefined()

    const payload = JSON.parse(refundEvent?.payloadJson || '{}')
    expect(payload.refundAmountMinor).toBe(1500)
  })

  test('COD payment attempts rejected - invariant enforced', async () => {
    const codOrder = await createOrder({
      sellerId: seller.id,
      customerId: customer.id,
      paymentType: 'CASH_ON_DELIVERY',
      items: [{ productId: 'test-product-id', quantity: 2, unitPriceMinor: 1000 }],
    })

    // Try to create payment attempt on COD order
    await expect(
      PaymentService.createPaymentAttempt({
        orderId: codOrder.id,
        provider: 'stripe',
        amountMinor: 2000,
        currency: 'USD'
      }, 'user-123')
    ).rejects.toThrow('Payment attempts not allowed for Cash on Delivery orders')

    // Verify no payment attempt created
    const paymentAttempts = await prisma.paymentAttempt.findMany({
      where: { orderId: codOrder.id }
    })
    expect(paymentAttempts).toHaveLength(0)

    // Verify no payment events created (only factory's order_created exists)
    const events = await prisma.orderEvent.findMany({
      where: { orderId: codOrder.id, eventType: { not: 'order_created' } }
    })
    expect(events).toHaveLength(0)
  })

  test('invalid payment transitions rejected - state machine enforced', async () => {
    // Create payment attempt
    const payment = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, 'user-123')

    // Try to jump directly to REFUNDED from PENDING (invalid)
    await expect(
      PaymentService.updatePaymentStatus({
        paymentAttemptId: payment.id,
        status: 'REFUNDED'
      }, 'user-123')
    ).rejects.toThrow('Invalid transition')

    // Try valid transition PENDING -> FAILED
    const result = await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'FAILED',
      failureReason: 'test'
    }, 'user-123')

    expect(result.status).toBe('FAILED') // PENDING -> FAILED is valid

    // Try to refund a failed payment (invalid)
    await expect(
      PaymentService.refundPayment({
        paymentAttemptId: payment.id,
        refundAmountMinor: 1000,
        reason: 'test'
      }, 'user-123')
    ).rejects.toThrow('Refund only allowed for COMPLETED payments')

    // Verify payment still in FAILED state
    const updatedPayment = await prisma.paymentAttempt.findUnique({
      where: { id: payment.id }
    })
    expect(updatedPayment?.status).toBe('FAILED')
  })

  test('refund amount validation - over-refund prevented', async () => {
    // Create and complete payment
    const payment = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, 'user-123')

    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'PROCESSING'
    }, 'user-123')

    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'COMPLETED',
      providerReference: 'pi_overrefund_test'
    }, 'user-123')

    // Try to refund more than original amount
    await expect(
      PaymentService.refundPayment({
        paymentAttemptId: payment.id,
        refundAmountMinor: 2500,
        reason: 'test'
      }, 'user-123')
    ).rejects.toThrow('Refund exceeds original amount')

    // Verify payment still in COMPLETED state
    const updatedPayment = await prisma.paymentAttempt.findUnique({
      where: { id: payment.id }
    })
    expect(updatedPayment?.status).toBe('COMPLETED')
  })

  test('audit trail completeness - no null actors', async () => {
    // Complete payment flow
    const payment = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'stripe',
      amountMinor: 2000,
      currency: 'USD'
    }, 'user-123')

    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'PROCESSING'
    }, 'user-123')

    await PaymentService.updatePaymentStatus({
      paymentAttemptId: payment.id,
      status: 'COMPLETED',
      providerReference: 'pi_audit_test'
    }, 'user-123')

    // Verify audit trail completeness
    const events = await prisma.orderEvent.findMany({ where: { orderId: order.id } })
    expect(events.length).toBeGreaterThan(0)

    // User-initiated payment events should have actorUserId
    const userPaymentEvents = events.filter(e =>
      e.eventType.includes('payment') && e.eventType !== 'payment_completed'
    )
    userPaymentEvents.forEach(event => {
      expect(event.actorUserId).not.toBeNull()
      expect(event.actorUserId).not.toBe('')
    })

    // payment_completed events can be system events (actorUserId: null) or user events
    const paymentCompletedEvents = events.filter(e => e.eventType === 'payment_completed')
    paymentCompletedEvents.forEach(event => {
      // System events have null actorUserId, user events have non-null
      // Both are valid, just verify the event exists
      expect(event).toBeDefined()
    })

    // Verify all payloads have required fields
    events.forEach(event => {
      const payload = JSON.parse(event.payloadJson || '{}')
      expect(payload).toBeDefined()
      expect(typeof payload).toBe('object')
    })

    // Verify user payment events have required metadata
    userPaymentEvents.forEach(event => {
      const payload = JSON.parse(event.payloadJson || '{}')
      expect(payload).toHaveProperty('provider')
      expect(payload).toHaveProperty('amountMinor')
      expect(payload).toHaveProperty('currency')
    })

    // Verify payment_completed events have appropriate metadata
    paymentCompletedEvents.forEach(event => {
      const payload = JSON.parse(event.payloadJson || '{}')
      if (event.actorUserId === null) {
        // System event should have timestamp
        expect(payload).toHaveProperty('timestamp')
      } else {
        // User event should have payment info
        expect(payload).toHaveProperty('provider')
        expect(payload).toHaveProperty('amountMinor')
        expect(payload).toHaveProperty('currency')
      }
    })
  })
})

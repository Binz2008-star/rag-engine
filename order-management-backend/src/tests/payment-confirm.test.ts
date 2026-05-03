import { beforeEach, describe, expect, it } from 'vitest'
import { PaymentService } from '../server/services/payment.service'
import { createCustomer } from './factories/customer'
import { createOrder } from './factories/order'
import { createSeller } from './factories/seller'
import { createUser } from './factories/user'
import { prisma } from './setup'

describe('PaymentService.confirmPayment', () => {
  beforeEach(async () => {
    await prisma.orderEvent.deleteMany()
    await prisma.paymentAttempt.deleteMany()
    await prisma.orderItem.deleteMany()
    await prisma.order.deleteMany()
    await prisma.customer.deleteMany()
    await prisma.seller.deleteMany()
    await prisma.user.deleteMany()
  })

  it('should confirm payment and create events', async () => {
    const user = await createUser({ role: 'SELLER' })
    const seller = await createSeller({ ownerUserId: user.id })
    const customer = await createCustomer({ sellerId: seller.id })
    const order = await createOrder({
      sellerId: seller.id,
      customerId: customer.id,
      paymentType: 'CASH',
      source: 'TEST',
      items: [{ productId: 'test-product-001', quantity: 1, unitPriceMinor: 1000 }],
    })

    // Create a payment attempt
    const paymentAttempt = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'STRIPE',
      amountMinor: 1000,
      currency: 'USD',
    }, 'test-user')

    // Confirm payment
    const confirmedPayment = await PaymentService.confirmPayment({
      paymentAttemptId: paymentAttempt.id,
      provider: 'STRIPE',
      providerReference: 'pi_test_123',
      rawPayload: { id: 'pi_test_123', status: 'succeeded' },
    })

    expect(confirmedPayment.status).toBe('COMPLETED')
    expect(confirmedPayment.providerReference).toBe('pi_test_123')

    // Verify order was updated
    const updatedOrder = await prisma.order.findUnique({
      where: { id: order.id },
    })
    expect(updatedOrder?.status).toBe('CONFIRMED')
    expect(updatedOrder?.paymentStatus).toBe('PAID')

    // Verify events were created
    const events = await prisma.orderEvent.findMany({
      where: { orderId: order.id },
      orderBy: { createdAt: 'asc' },
    })

    console.log('Events created:', events.map(e => ({ type: e.eventType, payload: e.payloadJson, actor: e.actorUserId })))
    expect(events.length).toBeGreaterThan(0)
    expect(events.some(e => e.eventType === 'payment_completed')).toBe(true)
    expect(events.some(e => e.eventType === 'status_changed')).toBe(true)

    // Verify payment_completed event is a system event (actorUserId: null)
    const paymentCompletedEvent = events.find(e => e.eventType === 'payment_completed')
    expect(paymentCompletedEvent?.actorUserId).toBeNull()
  })

  it('should be idempotent - duplicate confirmations should not duplicate effects', async () => {
    const user = await createUser({ role: 'SELLER' })
    const seller = await createSeller({ ownerUserId: user.id })
    const customer = await createCustomer({ sellerId: seller.id })
    const order = await createOrder({
      sellerId: seller.id,
      customerId: customer.id,
      paymentType: 'CASH',
      source: 'TEST',
      items: [{ productId: 'test-product-001', quantity: 1, unitPriceMinor: 1000 }],
    })

    // Create a payment attempt
    const paymentAttempt = await PaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'STRIPE',
      amountMinor: 1000,
      currency: 'USD',
    }, 'test-user')

    // Confirm payment first time
    const result1 = await PaymentService.confirmPayment({
      paymentAttemptId: paymentAttempt.id,
      provider: 'STRIPE',
      providerReference: 'pi_test_456',
      rawPayload: { id: 'pi_test_456', status: 'succeeded' },
    })

    // Confirm payment second time (duplicate)
    const result2 = await PaymentService.confirmPayment({
      paymentAttemptId: paymentAttempt.id,
      provider: 'STRIPE',
      providerReference: 'pi_test_456',
      rawPayload: { id: 'pi_test_456', status: 'succeeded' },
    })

    // Both should return the same result
    expect(result1.id).toBe(result2.id)
    expect(result1.status).toBe('COMPLETED')
    expect(result2.status).toBe('COMPLETED')

    // Verify events were not duplicated
    const events = await prisma.orderEvent.findMany({
      where: { orderId: order.id },
      orderBy: { createdAt: 'asc' },
    })

    // Should only have one payment_completed event
    const paymentCompletedEvents = events.filter(e => e.eventType === 'payment_completed')
    expect(paymentCompletedEvents.length).toBe(1)
  })
})

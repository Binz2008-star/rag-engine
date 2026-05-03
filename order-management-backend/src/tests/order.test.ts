import { beforeEach, describe, expect, it } from 'vitest'
import { generatePublicOrderNumber } from '../server/lib/utils'
import { createOrderEvent } from '../server/services/order-event.service'
import { createCustomer } from './factories/customer'
import { createSeller } from './factories/seller'
import { createUser } from './factories/user'
import { prisma } from './setup'

describe('Order Creation', () => {
  beforeEach(async () => {
    await prisma.orderEvent.deleteMany()
    await prisma.paymentAttempt.deleteMany()
    await prisma.orderItem.deleteMany()
    await prisma.order.deleteMany()
    await prisma.customer.deleteMany()
    await prisma.seller.deleteMany()
    await prisma.user.deleteMany()
  })

  it('should create an order with items', async () => {
    const { OrderService } = await import('../server/services/order.service')

    const user = await createUser({ role: 'SELLER' })
    const seller = await createSeller({ ownerUserId: user.id })
    const customer = await createCustomer({ sellerId: seller.id })

    // Create order using new service (no Product dependency)
    const orderService = new OrderService()
    const order = await orderService.createOrder({
      sellerId: seller.id,
      customerId: customer.id,
      items: [{
        productId: 'test-product-id',
        productNameSnapshot: 'Test Product',
        unitPriceMinor: 1999,
        quantity: 1,
      }],
      currency: 'USD',
      paymentType: 'CARD',
      notes: 'Test order',
    }, user.id)

    // Create order event
    const orderEvent = await createOrderEvent(prisma, {
      orderId: order!.id,
      eventType: 'order_created',
      payload: { source: 'test' },
    })

    expect(order!.id).toBeDefined()
    expect(order!.publicOrderNumber).toMatch(/^ORD-\d{8}-\d{3}-[a-z0-9]+$/)
    expect(order!.totalMinor).toBe(1999)
    expect(order!.orderItems).toHaveLength(1)
    expect(order!.orderItems[0].quantity).toBe(1)
    expect(order!.orderItems[0].lineTotalMinor).toBe(1999)
    expect(order!.orderItems[0].productNameSnapshot).toBe('Test Product')
    expect(orderEvent.eventType).toBe('order_created')
  })

  it('should generate unique order numbers', async () => {
    const orderNumbers = new Set<string>()

    for (let i = 0; i < 100; i++) {
      const orderNumber = generatePublicOrderNumber()
      expect(orderNumbers.has(orderNumber)).toBe(false)
      orderNumbers.add(orderNumber)
      expect(orderNumber).toMatch(/^ORD-[A-Z0-9_-]{8,9}$/)
    }
  })
})

import { createOrderEvent } from '@/server/modules/orders/order-events.authority'
import { prisma } from '../setup'

export interface CreateOrderInput {
  sellerId: string
  customerId: string
  items: Array<{
    productId: string
    quantity: number
    unitPriceMinor?: number
    productNameSnapshot?: string
  }>
  status?: string
  paymentType?: 'CASH_ON_DELIVERY' | 'CARD' | 'WALLET' | 'CASH' | 'PREPAID'
  paymentStatus?: string
  notes?: string
  source?: string
}

export async function createOrder(input: CreateOrderInput) {
  const {
    sellerId,
    customerId,
    items,
    status = 'PENDING',
    paymentType = 'CASH_ON_DELIVERY',
    paymentStatus = 'PENDING',
    notes = 'Test order',
    source,
  } = input

  const subtotalMinor = items.reduce(
    (sum, item) => sum + (item.unitPriceMinor || 1000) * item.quantity,
    0
  )
  const deliveryFeeMinor = 500
  const totalMinor = subtotalMinor + deliveryFeeMinor

  const order = await prisma.$transaction(async (tx) => {
    const createdOrder = await tx.order.create({
      data: {
        sellerId,
        customerId,
        publicOrderNumber: `ORD-${Date.now()}`,
        status,
        paymentType,
        paymentStatus,
        subtotalMinor,
        deliveryFeeMinor,
        totalMinor,
        currency: 'USD',
        ...(source && { source }),
        notes,
        orderItems: {
          create: items.map((item) => ({
            productId: item.productId,
            productNameSnapshot: item.productNameSnapshot || `Product ${item.productId}`,
            unitPriceMinor: item.unitPriceMinor || 1000,
            quantity: item.quantity,
            lineTotalMinor: (item.unitPriceMinor || 1000) * item.quantity,
          })),
        },
      },
      include: {
        customer: true,
        orderItems: true,
      },
    })

    await createOrderEvent(tx, {
      orderId: createdOrder.id,
      eventType: 'order_created',
      payload: {
        source: 'test_factory',
        itemCount: createdOrder.orderItems.length,
      },
    })

    return createdOrder
  })

  return order
}

export async function deleteOrder(id: string) {
  await prisma.$transaction(async (tx) => {
    await tx.orderEvent.deleteMany({ where: { orderId: id } })
    await tx.paymentAttempt.deleteMany({ where: { orderId: id } })
    await tx.orderItem.deleteMany({ where: { orderId: id } })
    await tx.order.deleteMany({ where: { id } })
  })
}

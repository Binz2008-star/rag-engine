import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { NextRequest, NextResponse } from 'next/server'

async function getOrderDetail({ id }: { id: string }, request: NextRequest) {
  const user = await getCurrentUser(request)
  requireSeller(user)

  const order = await prisma.order.findFirst({
    where: {
      id,
      sellerId: user.sellerId!,
    },
    include: {
      customer: true,
      orderItems: {
        select: {
          id: true,
          productId: true,
          productNameSnapshot: true,
          unitPriceMinor: true,
          quantity: true,
          lineTotalMinor: true,
        },
      },
      events: {
        orderBy: {
          createdAt: 'desc',
        },
      },
      paymentAttempts: {
        orderBy: {
          createdAt: 'desc',
        },
      },
    },
  })

  if (!order) {
    return NextResponse.json(
      { error: 'Order not found' },
      { status: 404 }
    )
  }

  return NextResponse.json({
    order: {
      id: order.id,
      publicOrderNumber: order.publicOrderNumber,
      status: order.status,
      paymentType: order.paymentType,
      paymentStatus: order.paymentStatus,
      subtotalMinor: order.subtotalMinor,
      deliveryFeeMinor: order.deliveryFeeMinor,
      totalMinor: order.totalMinor,
      currency: order.currency,
      source: order.source,
      notes: order.notes,
      createdAt: order.createdAt,
      updatedAt: order.updatedAt,
      customer: {
        id: order.customer.id,
        name: order.customer.name,
        phone: order.customer.phone,
        addressText: order.customer.addressText,
      },
      orderItems: order.orderItems,
      events: order.events.map(event => ({
        id: event.id,
        eventType: event.eventType,
        payloadJson: event.payloadJson,
        actorUserId: event.actorUserId,
        createdAt: event.createdAt,
      })),
      paymentAttempts: order.paymentAttempts.map(attempt => ({
        id: attempt.id,
        provider: attempt.provider,
        providerReference: attempt.providerReference,
        amountMinor: attempt.amountMinor,
        currency: attempt.currency,
        status: attempt.status,
        createdAt: attempt.createdAt,
      })),
    },
  })
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    return getOrderDetail({ id }, request)
  } catch (_error) {
    return NextResponse.json(
      { error: 'Invalid parameters' },
      { status: 400 }
    )
  }
}

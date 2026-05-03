import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { withQueryValidation } from '@/server/lib/errors'
import { PaginationSchema } from '@/server/lib/validation'
import { GetOrdersSchema } from '@/shared/schemas/orders'
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'

type PaginationQuery = z.infer<typeof PaginationSchema>

async function getOrders(query: PaginationQuery, request: NextRequest) {
  const user = await getCurrentUser(request)
  requireSeller(user)

  const { page, limit, status } = query
  const skip = (page - 1) * limit

  const where = {
    sellerId: user.sellerId!,
    ...(status && { status }),
  }

  const [orders, total] = await Promise.all([
    prisma.order.findMany({
      where,
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
        _count: {
          select: {
            events: true,
          },
        },
      },
      orderBy: {
        createdAt: 'desc',
      },
      skip,
      take: limit,
    }),
    prisma.order.count({ where }),
  ])

  const totalPages = Math.ceil(total / limit)

  return NextResponse.json({
    orders: orders.map(order => ({
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
      eventCount: order._count.events,
    })),
    pagination: {
      page,
      limit,
      total,
      totalPages,
      hasNext: page < totalPages,
      hasPrev: page > 1,
    },
  })
}

// POST removed: order creation is handled exclusively by /api/v1/orders
// via v1-order.authority.ts to ensure single authority, event emission, and contract enforcement.

export const GET = withQueryValidation(GetOrdersSchema, (data, request) =>
  getOrders(data, request)
)

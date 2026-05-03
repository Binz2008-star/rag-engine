import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { ErrorSchema } from '@/shared/schemas/error'
import { OrderCreateResponseSchema } from '@/shared/schemas/order-response'
import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

interface OrderWithRelations {
  id: string
  sellerId: string
  publicOrderNumber: string
  status: string
  paymentStatus: string
  paymentType: string
  subtotalMinor: number
  deliveryFeeMinor: number
  totalMinor: number
  currency: string | null
  notes: string | null
  createdAt: Date
  updatedAt: Date
  customer: {
    id: string
    name: string
    phone: string
    addressText: string | null
  }
  orderItems: Array<{
    id: string
    productId: string
    productNameSnapshot: string
    unitPriceMinor: number
    quantity: number
    lineTotalMinor: number
  }>
}

function toV1OrderResponse(order: OrderWithRelations) {
  return {
    id: order.id,
    sellerId: order.sellerId,
    publicOrderNumber: order.publicOrderNumber,
    status: order.status,
    paymentStatus: order.paymentStatus,
    paymentType: order.paymentType,
    subtotalMinor: order.subtotalMinor,
    deliveryFeeMinor: order.deliveryFeeMinor,
    totalMinor: order.totalMinor,
    currency: order.currency || 'USD',
    notes: order.notes,
    createdAt: order.createdAt.toISOString(),
    updatedAt: order.updatedAt.toISOString(),
    customer: {
      id: order.customer.id,
      name: order.customer.name,
      phone: order.customer.phone,
      addressText: order.customer.addressText,
    },
    items: order.orderItems.map((item) => ({
      id: item.id,
      productId: item.productId,
      productNameSnapshot: item.productNameSnapshot,
      unitPriceMinor: item.unitPriceMinor,
      quantity: item.quantity,
      lineTotalMinor: item.lineTotalMinor,
    })),
  }
}

// GET /api/v1/orders/[id] - Get single order
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const user = await getCurrentUser(request)
    requireSeller(user)

    const { id } = await params

    // Validate order ID format
    if (!id || typeof id !== 'string') {
      const errorBody = ErrorSchema.parse({
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Invalid order id',
          timestamp: new Date().toISOString(),
        },
      })

      return NextResponse.json(errorBody, { status: 400 })
    }

    const order = await prisma.order.findFirst({
      where: {
        id,
        sellerId: user.sellerId!,
      },
      include: {
        customer: true,
        orderItems: true,
      },
    })

    if (!order) {
      const notFoundBody = ErrorSchema.parse({
        success: false,
        error: {
          code: 'NOT_FOUND',
          message: 'Order not found',
          timestamp: new Date().toISOString(),
        },
      })

      return NextResponse.json(notFoundBody, { status: 404 })
    }

    const safe = OrderCreateResponseSchema.parse({
      success: true,
      data: {
        order: toV1OrderResponse(order),
      },
    })

    return NextResponse.json(safe)
  } catch (error: unknown) {
    console.error('V1 Orders GET by ID error', error instanceof Error ? error : undefined)

    const errorBody = ErrorSchema.parse({
      success: false,
      error: {
        code: 'INTERNAL_ERROR',
        message: 'Failed to fetch order',
        timestamp: new Date().toISOString(),
      },
    })

    return NextResponse.json(errorBody, { status: 500 })
  }
}

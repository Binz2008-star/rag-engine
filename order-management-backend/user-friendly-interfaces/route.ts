import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { OrderResponseSchema } from '@/shared/schemas/order-response'
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'

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
      return NextResponse.json({
        success: false,
        error: {
          code: "NOT_FOUND",
          message: "Order not found",
          timestamp: new Date().toISOString(),
        },
      }, { status: 404 })
    }

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
      },
    })

    if (!order) {
      return NextResponse.json({
        success: false,
        error: {
          code: "NOT_FOUND",
          message: "Order not found",
          timestamp: new Date().toISOString(),
        },
      }, { status: 404 })
    }

    // Build response according to V1 contract
    const response = {
      success: true,
      data: {
        order: {
          id: order.id,
          sellerId: order.sellerId,
          publicOrderNumber: order.publicOrderNumber,
          status: order.status,
          paymentStatus: order.paymentStatus,
          paymentType: order.paymentType,
          subtotalMinor: order.subtotalMinor,
          deliveryFeeMinor: order.deliveryFeeMinor,
          totalMinor: order.totalMinor,
          currency: order.currency,
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
        },
      },
    }

    // Enforce V1 response contract
    const safe = OrderResponseSchema.parse(response.data.order)

    return NextResponse.json({
      success: true,
      data: {
        order: safe,
      },
    })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({
        success: false,
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid response data",
          details: error.issues,
          timestamp: new Date().toISOString(),
        },
      }, { status: 500 })
    }

    console.error("V1 Orders GET by ID error:", error)
    return NextResponse.json({
      success: false,
      error: {
        code: "INTERNAL_ERROR",
        message: "Failed to fetch order",
        timestamp: new Date().toISOString(),
      },
    }, { status: 500 })
  }
}

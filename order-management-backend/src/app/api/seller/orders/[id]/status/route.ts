import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { ApiError, handleApiError } from '@/server/lib/errors'
import { UpdateOrderStatusSchema } from '@/server/lib/validation'
import { OrderTransitionError } from '@/server/services/order-transitions'
import { orderService } from '@/server/services/order.service'
import { NextRequest, NextResponse } from 'next/server'

function isOrderTransitionError(error: unknown): error is OrderTransitionError {
  return (
    error instanceof OrderTransitionError ||
    (typeof error === 'object' &&
      error !== null &&
      'name' in error &&
      (error as { name?: string }).name === 'OrderTransitionError')
  )
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
  try {
    const { id } = await params
    const { status, reason } = UpdateOrderStatusSchema.parse(await request.json())

    const user = await getCurrentUser(request)
    const seller = requireSeller(user)

    const existingOrder = await prisma.order.findFirst({
      where: {
        id,
        sellerId: seller.sellerId,
      },
      select: {
        id: true,
      },
    })

    if (!existingOrder) {
      throw new ApiError(404, 'Order not found')
    }

    // Note: orderService.updateOrderStatus() handles transactions and audit logging internally
    const updatedOrder = await orderService.updateOrderStatus({
      orderId: id,
      newStatus: status,
      actorUserId: seller.id,
      reason,
    })

    return NextResponse.json({
      order: {
        id: updatedOrder.id,
        publicOrderNumber: updatedOrder.publicOrderNumber,
        status: updatedOrder.status,
        updatedAt: updatedOrder.updatedAt,
      },
    })
  } catch (error: unknown) {
    if (isOrderTransitionError(error)) {
      return NextResponse.json(
        { error: error.message },
        { status: 400 }
      )
    }

    return handleApiError(error)
  }
}

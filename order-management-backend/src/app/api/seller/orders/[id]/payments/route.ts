import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { ApiError } from '@/server/lib/errors'
import { PaymentService } from '@/server/services/payment.service'
import { NextRequest, NextResponse } from 'next/server'

async function getOrderPaymentAttempts(
  { id }: { id: string },
  request: NextRequest
) {
  const user = await getCurrentUser(request)
  requireSeller(user)

  // Verify order belongs to seller
  const order = await prisma.order.findFirst({
    where: {
      id,
      sellerId: user.sellerId!,
    },
  })

  if (!order) {
    throw new ApiError(404, 'Order not found')
  }

  const paymentAttempts = await PaymentService.getOrderPaymentAttempts(id)

  return NextResponse.json({
    paymentAttempts,
    order: {
      id: order.id,
      publicOrderNumber: order.publicOrderNumber,
      totalMinor: order.totalMinor,
      currency: order.currency,
      paymentStatus: order.paymentStatus,
    },
  })
}


export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    return getOrderPaymentAttempts({ id }, request)
  } catch (_error) {
    return NextResponse.json(
      { error: 'Invalid parameters' },
      { status: 400 }
    )
  }
}

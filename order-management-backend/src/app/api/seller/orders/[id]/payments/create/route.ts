import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { ApiError } from '@/server/lib/errors'
import { PaymentService } from '@/server/services/payment.service'
import { NextRequest, NextResponse } from 'next/server'

async function createPaymentAttempt(
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

  const body = await request.json()
  // Note: PaymentService.createPaymentAttempt() handles transactions and audit logging internally
  const paymentAttempt = await PaymentService.createPaymentAttempt({
    orderId: id,
    provider: body.provider,
    amountMinor: body.amountMinor,
    currency: body.currency,
    metadata: body.metadata,
  }, user.id)

  return NextResponse.json({
    paymentAttempt,
  })
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    return createPaymentAttempt({ id }, request)
  } catch (_error) {
    return NextResponse.json(
      { error: 'Invalid parameters' },
      { status: 400 }
    )
  }
}

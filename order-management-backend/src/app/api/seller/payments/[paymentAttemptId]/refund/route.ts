import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { ApiError } from '@/server/lib/errors'
import { PaymentService } from '@/server/services/payment.service'
import { NextRequest, NextResponse } from 'next/server'

async function refundPayment(
  { paymentAttemptId }: { paymentAttemptId: string },
  request: NextRequest
) {
  const user = await getCurrentUser(request)
  requireSeller(user)

  // Verify payment attempt belongs to seller's order
  const paymentAttempt = await prisma.paymentAttempt.findUnique({
    where: { id: paymentAttemptId },
    include: { order: true }
  })

  if (!paymentAttempt || paymentAttempt.order.sellerId !== user.sellerId!) {
    throw new ApiError(404, 'Payment attempt not found')
  }

  const body = await request.json()
  // Note: PaymentService.refundPayment() handles transactions and audit logging internally
  const refundedPayment = await PaymentService.refundPayment({
    paymentAttemptId,
    refundAmountMinor: body.refundAmountMinor,
    reason: body.reason,
    metadata: body.metadata,
  }, user.id)

  return NextResponse.json({
    paymentAttempt: refundedPayment,
    message: 'Payment refunded successfully',
  })
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ paymentAttemptId: string }> }
) {
  try {
    const { paymentAttemptId } = await params
    return refundPayment({ paymentAttemptId }, request)
  } catch (_error) {
    return NextResponse.json(
      { error: 'Invalid parameters' },
      { status: 400 }
    )
  }
}

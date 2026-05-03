import { prisma } from '@/server/db/prisma'
import { getCurrentUser, requireSeller } from '@/server/lib/auth'
import { ApiError } from '@/server/lib/errors'
import { PaymentService } from '@/server/services/payment.service'
import { NextRequest, NextResponse } from 'next/server'

async function updatePaymentStatus(
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
  const updatedAttempt = await PaymentService.updatePaymentStatus({
    paymentAttemptId,
    status: body.status,
    providerReference: body.providerReference,
    failureReason: body.failureReason,
    metadata: body.metadata,
  }, user.id)

  return NextResponse.json({
    paymentAttempt: updatedAttempt,
    message: 'Payment status updated successfully',
  })
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ paymentAttemptId: string }> }
) {
  try {
    const { paymentAttemptId } = await params
    return updatePaymentStatus({ paymentAttemptId }, request)
  } catch (_error) {
    return NextResponse.json(
      { error: 'Invalid parameters' },
      { status: 400 }
    )
  }
}

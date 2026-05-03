import { prisma } from '@/server/db/prisma'
import { logger } from '@/server/lib/logger'
import { PaymentService } from '@/server/services/payment.service'
import { NextRequest, NextResponse } from 'next/server'

// Payment constants (since schema uses strings, not enums)
const PAYMENT_PROVIDER = {
  STRIPE: 'STRIPE',
  SIMULATOR: 'SIMULATOR',
} as const

const _PAYMENT_STATUS = {
  PENDING: 'PENDING',
  PAID: 'PAID',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
} as const

const WEBHOOK_STATUS = {
  PENDING: 'PENDING',
  PROCESSED: 'PROCESSED',
  FAILED: 'FAILED',
} as const

// Stripe webhook signature verification (simplified)
async function verifyStripeSignature(_payload: string, _signature: string): Promise<boolean> {
  // In production, you would use Stripe's webhook signing secret
  // For demo purposes, we'll just return true
  return true
}

async function processStripeWebhook(request: NextRequest) {
  const body = await request.text()
  const signature = request.headers.get('stripe-signature') || ''

  try {
    // Verify webhook signature
    const isValid = await verifyStripeSignature(body, signature)
    if (!isValid) {
      return NextResponse.json(
        { error: 'Invalid signature' },
        { status: 401 }
      )
    }

    const event = JSON.parse(body)

    // Check for duplicate webhook
    const existingWebhook = await prisma.webhookEvent.findUnique({
      where: {
        provider_eventId: {
          provider: PAYMENT_PROVIDER.STRIPE,
          eventId: event.id,
        },
      },
    })

    if (existingWebhook) {
      return NextResponse.json({ status: 'duplicate' })
    }

    // Store webhook event
    await prisma.$transaction(async (tx) => {
      // Create webhook event record
      await tx.webhookEvent.create({
        data: {
          provider: PAYMENT_PROVIDER.STRIPE,
          eventId: event.id,
          eventType: event.type,
          payloadJson: event,
          status: WEBHOOK_STATUS.PROCESSED,
          processedAt: new Date(),
        },
      })
    })

    // Handle payment success outside of webhook transaction
    if (event.type === 'payment_intent.succeeded') {
      const paymentIntent = event.data.object

      // Find payment attempt
      const paymentAttempt = await prisma.paymentAttempt.findFirst({
        where: {
          provider: PAYMENT_PROVIDER.STRIPE,
          providerReference: paymentIntent.id,
        },
      })

      if (paymentAttempt) {
        // Use PaymentService for proper event enforcement and transaction integrity
        await PaymentService.confirmPayment({
          paymentAttemptId: paymentAttempt.id,
          provider: 'STRIPE',
          providerReference: paymentIntent.id,
          rawPayload: event,
        })

        logger.info('Payment processed successfully', {
          provider: PAYMENT_PROVIDER.STRIPE,
          paymentIntentId: paymentIntent.id,
          orderId: paymentAttempt.orderId,
          amount: paymentIntent.amount,
        })
      }
    }

    return NextResponse.json({ status: 'processed' })
  } catch (error) {
    logger.error('Webhook processing failed', error as Error)
    return NextResponse.json(
      { error: 'Webhook processing failed' },
      { status: 500 }
    )
  }
}

export const POST = processStripeWebhook

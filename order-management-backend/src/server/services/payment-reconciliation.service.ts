import { prisma } from '../db/prisma'
import { logger } from '../lib/logger'
import { PaymentService } from './payment.service'

const STRIPE_PROVIDER = 'STRIPE'
const WEBHOOK_STATUS = {
  PENDING: 'PENDING',
  PROCESSED: 'PROCESSED',
  FAILED: 'FAILED',
} as const

type ReconcileStripeWebhookOptions = {
  limit: number
}

export type ReconcileStripeWebhookResult = {
  scanned: number
  processed: number
  failed: number
  skipped: number
}

type StripeWebhookPayload = {
  id?: unknown
  type?: unknown
  data?: {
    object?: {
      id?: unknown
    }
  }
}

export class PaymentReconciliationService {
  static async reconcileStripeSucceededWebhooks(
    options: ReconcileStripeWebhookOptions
  ): Promise<ReconcileStripeWebhookResult> {
    const result: ReconcileStripeWebhookResult = {
      scanned: 0,
      processed: 0,
      failed: 0,
      skipped: 0,
    }

    const candidates = await prisma.webhookEvent.findMany({
      where: {
        provider: STRIPE_PROVIDER,
        eventType: 'payment_intent.succeeded',
        status: { in: [WEBHOOK_STATUS.PENDING, WEBHOOK_STATUS.FAILED] },
      },
      orderBy: { createdAt: 'asc' },
      take: options.limit,
      select: {
        id: true,
        eventId: true,
        payloadJson: true,
      },
    })

    for (const event of candidates) {
      result.scanned += 1

      try {
        const payload = this.parsePayload(event.payloadJson)
        const paymentIntentId = this.extractPaymentIntentId(payload)

        if (!paymentIntentId) {
          await this.markFailed(event.id)
          result.failed += 1
          logger.warn('Payment reconciliation failed: missing payment intent id', {
            webhookEventId: event.id,
            provider: STRIPE_PROVIDER,
            source: 'reconciliation',
          })
          continue
        }

        const paymentAttempt = await prisma.paymentAttempt.findFirst({
          where: {
            provider: STRIPE_PROVIDER,
            OR: [
              { providerReference: paymentIntentId },
              { metadataJson: { contains: paymentIntentId } },
            ],
          },
          select: {
            id: true,
            orderId: true,
          },
        })

        if (!paymentAttempt) {
          await this.markFailed(event.id)
          result.skipped += 1
          logger.warn('Payment reconciliation skipped: no matching payment attempt', {
            webhookEventId: event.id,
            paymentIntentId,
            provider: STRIPE_PROVIDER,
            source: 'reconciliation',
          })
          continue
        }

        await PaymentService.confirmPayment({
          paymentAttemptId: paymentAttempt.id,
          provider: STRIPE_PROVIDER,
          providerReference: paymentIntentId,
          rawPayload: payload as Record<string, unknown>,
        })

        await prisma.webhookEvent.update({
          where: { id: event.id },
          data: {
            status: WEBHOOK_STATUS.PROCESSED,
            processedAt: new Date(),
          },
        })

        result.processed += 1
        logger.info('Payment webhook reconciled successfully', {
          webhookEventId: event.id,
          paymentIntentId,
          paymentAttemptId: paymentAttempt.id,
          orderId: paymentAttempt.orderId,
          provider: STRIPE_PROVIDER,
          source: 'reconciliation',
        })
      } catch (error) {
        await this.markFailed(event.id)
        result.failed += 1
        logger.error('Payment webhook reconciliation failed', error as Error, {
          webhookEventId: event.id,
          provider: STRIPE_PROVIDER,
          source: 'reconciliation',
        })
      }
    }

    return result
  }

  private static parsePayload(payloadJson: string): StripeWebhookPayload {
    const parsed: unknown = JSON.parse(payloadJson)
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('Invalid webhook payload')
    }
    return parsed as StripeWebhookPayload
  }

  private static extractPaymentIntentId(payload: StripeWebhookPayload): string | null {
    const fromDataObject = payload.data?.object?.id
    if (typeof fromDataObject === 'string' && fromDataObject.trim()) {
      return fromDataObject.trim()
    }

    return null
  }

  private static async markFailed(webhookEventId: string): Promise<void> {
    await prisma.webhookEvent.update({
      where: { id: webhookEventId },
      data: {
        status: WEBHOOK_STATUS.FAILED,
      },
    })
  }
}


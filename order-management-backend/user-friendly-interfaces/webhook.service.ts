import { prisma } from '@/server/db/prisma'
import { logger } from '@/server/lib/logger'

/**
 * WebhookService
 *
 * Centralizes all webhook processing logic.
 * Route handlers must not contain direct Prisma writes — delegate here instead.
 */
export class WebhookService {
  /**
   * Process an inbound WhatsApp webhook event.
   * Stores the raw payload for audit and idempotency purposes.
   */
  static async processWhatsApp(body: Record<string, unknown>): Promise<void> {
    await prisma.$transaction(async (tx) => {
      await tx.webhookEvent.create({
        data: {
          provider: 'WHATSAPP',
          eventId: typeof body.id === 'string' ? body.id : 'unknown',
          eventType: typeof body.type === 'string' ? body.type : 'message',
          payloadJson: JSON.stringify(body),
          status: 'PROCESSED',
          processedAt: new Date(),
        },
      })

      logger.info('WhatsApp webhook processed', {
        eventId: body.id,
        eventType: body.type,
      })
    })
  }
}

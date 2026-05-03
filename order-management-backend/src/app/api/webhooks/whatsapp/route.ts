import { prisma } from '@/server/db/prisma'
import { logger } from '@/server/lib/logger'
import { NextRequest, NextResponse } from 'next/server'

// WhatsApp webhook processing (simplified)
async function processWhatsAppWebhook(request: NextRequest) {
  const body: Record<string, unknown> = await request.json()

  try {
    await prisma.$transaction(async (tx) => {
      // Store webhook event
      await tx.webhookEvent.create({
        data: {
          provider: 'WHATSAPP', // TODO: Add to Prisma enum if needed
          eventId: (body.id as string) || 'unknown',
          eventType: (body.type as string) || 'message',
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

    return NextResponse.json({ status: 'processed' })
  } catch (error: unknown) {
    logger.error('WhatsApp webhook processing failed', error as Error)
    return NextResponse.json(
      { error: 'Webhook processing failed' },
      { status: 500 }
    )
  }
}

export const POST = processWhatsAppWebhook

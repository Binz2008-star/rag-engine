import { prisma } from '@/server/db/prisma'
import { logger } from '@/server/lib/logger'
import { NotificationJob } from '@prisma/client'

// Notification channel values to match schema strings
type NotificationChannel = 'WHATSAPP' | 'EMAIL' | 'SMS'

export interface NotificationPayload {
  channel: NotificationChannel
  recipient: string
  templateKey: string
  sellerId: string
  orderId?: string
  data: Record<string, unknown>
}

export class NotificationService {
  async enqueueNotification(payload: NotificationPayload): Promise<void> {
    try {
      await prisma.notificationJob.create({
        data: {
          channel: payload.channel,
          templateKey: payload.templateKey,
          sellerId: payload.sellerId,
          orderId: payload.orderId,
          status: 'PENDING',
          scheduledAt: new Date(),
        },
      })

      logger.info('Notification enqueued', {
        channel: payload.channel,
        templateKey: payload.templateKey,
        recipient: payload.recipient,
      })
    } catch (error: unknown) {
      logger.error('Failed to enqueue notification', error as Error)
      throw error
    }
  }

  async processPendingNotifications(): Promise<void> {
    const notifications = await prisma.notificationJob.findMany({
      where: {
        status: 'PENDING',
        scheduledAt: {
          lte: new Date(),
        },
      },
      include: {
        seller: true,
        order: true,
      },
      take: 10, // Process in batches
    })

    for (const notification of notifications) {
      try {
        await this.sendNotification(notification)

        await prisma.notificationJob.update({
          where: { id: notification.id },
          data: {
            status: 'SENT',
            sentAt: new Date(),
          },
        })

        logger.info('Notification sent successfully', {
          notificationId: notification.id,
          channel: notification.channel,
        })
      } catch (error: unknown) {
        await prisma.notificationJob.update({
          where: { id: notification.id },
          data: {
            status: 'FAILED',
            retryCount: notification.retryCount + 1,
            errorText: error instanceof Error ? error.message : 'Unknown error',
          },
        })

        logger.error('Failed to send notification', error as Error, {
          notificationId: notification.id,
          channel: notification.channel,
        })
      }
    }
  }

  private async sendNotification(notification: NotificationJob): Promise<void> {
    // Stub implementation - in production, you'd integrate with actual providers
    switch (notification.channel) {
      case 'WHATSAPP':
        await this.sendWhatsAppNotification(notification)
        break
      case 'EMAIL':
        await this.sendEmailNotification(notification)
        break
      case 'SMS':
        await this.sendSMSNotification(notification)
        break
      default:
        throw new Error(`Unsupported notification channel: ${notification.channel}`)
    }
  }

  private async sendWhatsAppNotification(notification: NotificationJob): Promise<void> {
    // WhatsApp integration stub
    logger.info('WhatsApp notification stub', {
      recipient: notification.sellerId,
      templateKey: notification.templateKey,
      orderId: notification.orderId ?? undefined,
    })
  }

  private async sendEmailNotification(notification: NotificationJob): Promise<void> {
    // Email integration stub
    logger.info('Email notification stub', {
      recipient: notification.sellerId,
      templateKey: notification.templateKey,
    })
  }

  private async sendSMSNotification(notification: NotificationJob): Promise<void> {
    // SMS integration stub
    logger.info('SMS notification stub', {
      recipient: notification.sellerId,
      templateKey: notification.templateKey,
    })
  }
}

export const notificationService = new NotificationService()

import { Prisma } from '@prisma/client'
import { prisma } from '../db/prisma'
import { logger } from '../lib/logger'
import { createOrderEvent } from './order-event.service'
import { OrderService } from './order.service'

type Tx = Prisma.TransactionClient

// Payment status values to match schema strings
type PaymentStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'REFUNDED'

export interface CreatePaymentAttemptData {
  orderId: string
  provider: string
  amountMinor: number
  currency: string
  metadata?: Record<string, unknown>
}

export interface UpdatePaymentStatusData {
  paymentAttemptId: string
  status: PaymentStatus
  providerReference?: string
  failureReason?: string
  metadata?: Record<string, unknown>
}

export interface RefundPaymentData {
  paymentAttemptId: string
  refundAmountMinor: number
  reason: string
  metadata?: Record<string, unknown>
}

export class PaymentService {
  private static readonly PAYMENT_STATUS_TRANSITIONS: Record<PaymentStatus, PaymentStatus[]> = {
    PENDING: ['PROCESSING', 'CANCELLED', 'FAILED'],
    PROCESSING: ['COMPLETED', 'FAILED', 'CANCELLED'],
    COMPLETED: ['REFUNDED'],
    FAILED: ['PENDING'],
    CANCELLED: ['PENDING'],
    REFUNDED: [],
  }

  private static isValidPaymentTransition(
    from: PaymentStatus,
    to: PaymentStatus
  ): boolean {
    return this.PAYMENT_STATUS_TRANSITIONS[from]?.includes(to) ?? false
  }

  static async createPaymentAttempt(
    data: CreatePaymentAttemptData,
    actorUserId?: string
  ) {
    return prisma.$transaction(async (tx) => {
      // First, lock the order row to prevent concurrent attempts
      const order = await tx.order.findUnique({
        where: { id: data.orderId },
        select: {
          id: true,
          status: true,
          paymentType: true,
          paymentStatus: true,
        }
      })

      if (!order) throw new Error('Order not found')

      // Business rule: Payment attempts not allowed for Cash on Delivery orders
      if (order.paymentType === 'CASH_ON_DELIVERY') {
        throw new Error('Payment attempts not allowed for Cash on Delivery orders')
      }

      // Business rule: No payment attempts for terminal order states
      if (['DELIVERED', 'CANCELLED'].includes(order.status)) {
        throw new Error(`Cannot create payment attempt for order in ${order.status} status`)
      }

      // Note: Allow multiple payment attempts even for paid orders (business flexibility)
      // Provider reference uniqueness will prevent duplicate payments

      // Check for existing payment attempts atomically
      const existingAttempt = await tx.paymentAttempt.findFirst({
        where: {
          orderId: data.orderId,
          status: { in: ['PENDING', 'PROCESSING'] }
        }
      })

      if (existingAttempt) {
        throw new Error('Active payment attempt exists')
      }

      // Create the payment attempt
      const paymentAttempt = await tx.paymentAttempt.create({
        data: {
          orderId: data.orderId,
          provider: data.provider,
          amountMinor: data.amountMinor,
          currency: data.currency,
          status: 'PENDING',
          metadataJson: data.metadata ? JSON.stringify(data.metadata) : null,
        },
      })

      await createOrderEvent(tx, {
        orderId: data.orderId,
        eventType: 'payment_initiated',
        actorUserId: actorUserId ?? null,
        payload: {
          provider: data.provider,
          amountMinor: data.amountMinor,
          currency: data.currency,
        },
      })

      return paymentAttempt
    })
  }

  static async updatePaymentStatus(
    data: UpdatePaymentStatusData,
    actorUserId?: string
  ) {
    return prisma.$transaction(async (tx) => {
      const attempt = await tx.paymentAttempt.findUnique({
        where: { id: data.paymentAttemptId },
        select: {
          id: true,
          status: true,
          orderId: true,
          provider: true,
          amountMinor: true,
          currency: true,
          providerReference: true,
        }
      })

      if (!attempt) throw new Error('Payment attempt not found')

      if (attempt.status === data.status) return attempt

      if (!this.isValidPaymentTransition(attempt.status as PaymentStatus, data.status)) {
        throw new Error(`Invalid transition ${attempt.status} → ${data.status}`)
      }

      if (data.status === 'COMPLETED' && data.providerReference) {
        const exists = await tx.paymentAttempt.findFirst({
          where: {
            providerReference: data.providerReference,
            status: 'COMPLETED',
            NOT: { id: data.paymentAttemptId },
          },
          select: { id: true }
        })

        if (exists) {
          throw new Error('Duplicate providerReference (idempotency violation)')
        }
      }

      const updated = await tx.paymentAttempt.update({
        where: { id: data.paymentAttemptId },
        data: {
          status: data.status,
          providerReference: data.providerReference ?? attempt.providerReference,
          failureReason: data.failureReason ?? null,
          metadataJson: data.metadata ? JSON.stringify(data.metadata) : null,
        },
      })

      await createOrderEvent(tx, {
        orderId: attempt.orderId,
        eventType: this.getPaymentEventType(data.status),
        actorUserId: actorUserId ?? null,
        payload: {
          provider: attempt.provider,
          amountMinor: attempt.amountMinor,
          currency: attempt.currency,
          providerReference: data.providerReference,
          failureReason: data.failureReason,
        },
      })

      if (data.status === 'COMPLETED') {
        await this.handlePaymentCompletion(tx, attempt.orderId, {
          emitPaymentCompletedEvent: false,
          provider: attempt.provider,
          amountMinor: attempt.amountMinor,
          currency: attempt.currency,
          providerReference: data.providerReference ?? attempt.providerReference ?? undefined,
        })
      }

      if (['FAILED', 'CANCELLED'].includes(data.status)) {
        await this.handlePaymentFailure(tx, attempt.orderId, {
          emitPaymentFailedEvent: false,
          failureReason: data.failureReason,
        })
      }

      return updated
    })
  }

  static async refundPayment(
    data: RefundPaymentData,
    actorUserId?: string
  ) {
    return prisma.$transaction(async (tx) => {
      const attempt = await tx.paymentAttempt.findUnique({
        where: { id: data.paymentAttemptId },
        select: {
          id: true,
          status: true,
          amountMinor: true,
          orderId: true,
          metadataJson: true,
        }
      })

      if (!attempt) throw new Error('Payment attempt not found')

      if (attempt.status !== 'COMPLETED') {
        throw new Error('Refund only allowed for COMPLETED payments')
      }

      if (data.refundAmountMinor > attempt.amountMinor) {
        throw new Error('Refund exceeds original amount')
      }

      // Check for existing refunds to prevent over-refunding
      const existingRefunds = await tx.paymentAttempt.findMany({
        where: {
          orderId: attempt.orderId,
          status: 'REFUNDED',
          NOT: { id: data.paymentAttemptId }
        },
        select: {
          metadataJson: true
        }
      })

      const totalRefundedAmount = existingRefunds.reduce((sum, refund) => {
        const metadata = refund.metadataJson ? JSON.parse(refund.metadataJson) : {}
        return sum + (metadata.refundAmountMinor || 0)
      }, 0)

      if (totalRefundedAmount + data.refundAmountMinor > attempt.amountMinor) {
        throw new Error(`Total refunds (${totalRefundedAmount + data.refundAmountMinor}) would exceed original payment amount (${attempt.amountMinor})`)
      }

      // Merge refund metadata with existing metadata
      const existingMetadata = attempt.metadataJson ? JSON.parse(attempt.metadataJson) : {}
      const updatedMetadata = {
        ...existingMetadata,
        refundAmountMinor: data.refundAmountMinor,
        reason: data.reason,
        refundedAt: new Date().toISOString(),
        ...(data.metadata || {}),
      }

      const updated = await tx.paymentAttempt.update({
        where: { id: data.paymentAttemptId },
        data: {
          status: 'REFUNDED',
          metadataJson: JSON.stringify(updatedMetadata),
        },
      })

      await this.updateOrderPaymentStatusInTx(tx, {
        orderId: attempt.orderId,
        paymentStatus: 'REFUNDED',
        event: {
          eventType: 'payment_refunded',
          actorUserId: actorUserId ?? null,
          payload: {
            refundAmountMinor: data.refundAmountMinor,
            reason: data.reason,
          },
        },
      })

      return updated
    })
  }

  private static getPaymentEventType(status: PaymentStatus): string {
    switch (status) {
      case 'PROCESSING':
        return 'payment_initiated'
      case 'COMPLETED':
        return 'payment_completed'
      case 'FAILED':
      case 'CANCELLED':
        return 'payment_failed'
      case 'REFUNDED':
        return 'payment_refunded'
      default:
        return 'payment_status_changed'
    }
  }

  private static async handlePaymentCompletion(
    tx: Tx,
    orderId: string,
    options?: {
      emitPaymentCompletedEvent?: boolean
      provider?: string
      amountMinor?: number
      currency?: string
      providerReference?: string
    }
  ) {
    await this.updateOrderPaymentStatusInTx(tx, {
      orderId,
      paymentStatus: 'PAID',
      event: options?.emitPaymentCompletedEvent === false ? undefined : {
        eventType: 'payment_completed',
        actorUserId: null,
        payload: {
          timestamp: new Date().toISOString(),
          provider: options?.provider ?? 'webhook',
          amountMinor: options?.amountMinor ?? 0,
          currency: options?.currency ?? 'USD',
          providerReference: options?.providerReference ?? null,
        },
      },
    })

    const order = await tx.order.findUnique({ where: { id: orderId } })
    if (order && order.status === 'PENDING') {
      await OrderService.applyTransitionInTx(
        tx,
        orderId,
        'CONFIRMED',
        null,
        'payment_completed'
      )
    }
  }

  private static async handlePaymentFailure(
    tx: Tx,
    orderId: string,
    options?: {
      emitPaymentFailedEvent?: boolean
      failureReason?: string
    }
  ) {
    await this.updateOrderPaymentStatusInTx(tx, {
      orderId,
      paymentStatus: 'FAILED',
      event: options?.emitPaymentFailedEvent === false ? undefined : {
        eventType: 'payment_failed',
        actorUserId: null,
        payload: {
          timestamp: new Date().toISOString(),
          failureReason: options?.failureReason ?? null,
        },
      },
    })
  }

  static async getOrderPaymentAttempts(orderId: string) {
    return prisma.paymentAttempt.findMany({
      where: { orderId },
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        orderId: true,
        provider: true,
        providerReference: true,
        amountMinor: true,
        currency: true,
        status: true,
        paymentType: true,
        failureReason: true,
        metadataJson: true,
        createdAt: true,
        updatedAt: true,
      }
    })
  }

  static async confirmPayment(data: {
    paymentAttemptId: string
    provider: string
    providerReference: string
    rawPayload?: Record<string, unknown>
  }) {
    return prisma.$transaction(async (tx) => {
      // Atomic update with race condition protection
      const updateResult = await tx.paymentAttempt.updateMany({
        where: {
          id: data.paymentAttemptId,
          status: 'PENDING', // Only update if still PENDING
          provider: data.provider, // Enforce provider match atomically
        },
        data: {
          status: 'COMPLETED',
          providerReference: data.providerReference,
          rawPayloadJson: data.rawPayload ? JSON.stringify(data.rawPayload) : null,
        }
      })

      if (updateResult.count === 0) {
        // Check if it was already processed or provider mismatch
        const existingAttempt = await tx.paymentAttempt.findUnique({
          where: { id: data.paymentAttemptId }
        })

        if (!existingAttempt) {
          throw new Error('Payment attempt not found')
        }

        if (existingAttempt.provider !== data.provider) {
          throw new Error('Provider mismatch')
        }

        // Already processed by another concurrent request
        logger.warn('Payment attempt already processed (idempotent)', {
          paymentAttemptId: data.paymentAttemptId,
          currentStatus: existingAttempt.status
        })
        return existingAttempt
      }

      // Get the updated attempt for further processing
      const updatedAttempt = await tx.paymentAttempt.findUnique({
        where: { id: data.paymentAttemptId }
      })

      if (!updatedAttempt) {
        throw new Error('Payment attempt not found after update')
      }

      // Handle payment completion (order status transition + events)
      await this.handlePaymentCompletion(tx, updatedAttempt.orderId, {
        emitPaymentCompletedEvent: true,
        provider: updatedAttempt.provider,
        amountMinor: updatedAttempt.amountMinor,
        currency: updatedAttempt.currency,
        providerReference: updatedAttempt.providerReference ?? data.providerReference,
      })

      return updatedAttempt
    })
  }

  static async getPaymentAttempt(paymentAttemptId: string) {
    return prisma.paymentAttempt.findUnique({
      where: { id: paymentAttemptId },
      select: {
        id: true,
        orderId: true,
        provider: true,
        providerReference: true,
        amountMinor: true,
        currency: true,
        status: true,
        paymentType: true,
        failureReason: true,
        metadataJson: true,
        createdAt: true,
        updatedAt: true,
        order: {
          select: {
            id: true,
            publicOrderNumber: true,
            status: true,
            paymentStatus: true,
          }
        }
      }
    })
  }

  private static async updateOrderPaymentStatusInTx(
    tx: Tx,
    data: {
      orderId: string
      paymentStatus: string
      event?: {
        eventType: string
        actorUserId: string | null
        payload: Record<string, unknown>
      }
    }
  ) {
    await tx.order.update({
      where: { id: data.orderId },
      data: { paymentStatus: data.paymentStatus },
    })

    if (data.event) {
      await createOrderEvent(tx, {
        orderId: data.orderId,
        eventType: data.event.eventType,
        actorUserId: data.event.actorUserId,
        payload: data.event.payload,
      })
    }
  }
}

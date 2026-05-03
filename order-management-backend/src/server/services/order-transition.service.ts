import { Prisma } from '@prisma/client'
import { logger } from '../lib/logger'
import { createOrderEvent } from './order-event.service'

export interface OrderTransitionRequest {
  orderId: string
  fromStatus: string
  toStatus: string
  actorUserId?: string | null
  reason?: string
  metadata?: Record<string, unknown>
}

export interface OrderTransitionResult {
  order: Prisma.OrderGetPayload<object>
  event: Prisma.OrderEventGetPayload<object>
  transitionValid: boolean
}

/**
 * AUTHORITATIVE ORDER TRANSITION SERVICE
 *
 * This is the ONLY place where order status should change.
 * All order state mutations MUST go through this service.
 *
 * No direct order status writes anywhere else.
 * No direct order event row writes in routes.
 */
export class OrderTransitionService {
  private readonly VALID_TRANSITIONS: Record<string, string[]> = {
    'PENDING': ['CONFIRMED', 'CANCELLED'],
    'CONFIRMED': ['PREPARING', 'CANCELLED'],
    'PREPARING': ['READY_FOR_PICKUP', 'CANCELLED'],
    'READY_FOR_PICKUP': ['OUT_FOR_DELIVERY', 'CANCELLED'],
    'OUT_FOR_DELIVERY': ['DELIVERED', 'FAILED_DELIVERY'],
    'FAILED_DELIVERY': ['OUT_FOR_DELIVERY', 'CANCELLED'],
    'DELIVERED': [], // Terminal state
    'CANCELLED': [], // Terminal state
  }

  /**
   * Apply order transition with proper validation and event creation
   * This is the AUTHORITATIVE method for all order state changes
   */
  async applyTransition(
    tx: Prisma.TransactionClient,
    request: OrderTransitionRequest
  ): Promise<OrderTransitionResult> {
    const { orderId, fromStatus, toStatus, actorUserId, reason, metadata } = request

    logger.info('Applying authoritative order transition', {
      orderId,
      fromStatus,
      toStatus,
      actorUserId
    })

    // 1. Validate transition is allowed
    const validTransitions = this.VALID_TRANSITIONS[fromStatus] || []
    if (!validTransitions.includes(toStatus)) {
      throw new Error(`Invalid order transition: ${fromStatus} -> ${toStatus}`)
    }

    // 2. Get current order and verify current status
    const currentOrder = await tx.order.findUnique({
      where: { id: orderId }
    })

    if (!currentOrder) {
      throw new Error(`Order ${orderId} not found`)
    }

    if (currentOrder.status !== fromStatus) {
      throw new Error(`Order status mismatch. Expected: ${fromStatus}, Actual: ${currentOrder.status}`)
    }

    // 3. Apply the status change (ONLY place this should happen)
    const updatedOrder = await tx.order.update({
      where: { id: orderId },
      data: {
        status: toStatus,
        updatedAt: new Date()
      }
    })

    // 4. Create the transition event (ONLY place this should happen)
    const event = await createOrderEvent(tx, {
      orderId,
      eventType: 'status_changed',
      actorUserId,
      payload: {
        from: fromStatus,
        to: toStatus,
        reason,
        metadata,
        timestamp: new Date().toISOString()
      }
    })

    // 5. Create specific cancellation event for audit completeness
    if (toStatus === 'CANCELLED') {
      await createOrderEvent(tx, {
        orderId,
        eventType: 'order_cancelled',
        actorUserId,
        payload: {
          from: fromStatus,
          reason,
          cancelledAt: new Date().toISOString(),
          metadata
        }
      })
    }

    logger.info('Authoritative order transition completed', {
      orderId,
      fromStatus,
      toStatus,
      eventId: event.id
    })

    return {
      order: updatedOrder,
      event,
      transitionValid: true
    }
  }

  /**
   * Validate transition without applying it
   */
  validateTransition(fromStatus: string, toStatus: string): boolean {
    const validTransitions = this.VALID_TRANSITIONS[fromStatus] || []
    return validTransitions.includes(toStatus)
  }

  /**
   * Get all possible next states for a given status
   */
  getNextStates(status: string): string[] {
    return this.VALID_TRANSITIONS[status] || []
  }

  /**
   * Check if status is terminal (no further transitions)
   */
  isTerminalStatus(status: string): boolean {
    const nextStates = this.VALID_TRANSITIONS[status] || []
    return nextStates.length === 0
  }
}

// Export singleton instance
export const orderTransitionService = new OrderTransitionService()

/**
 * Convenience function for use in transactions
 * This is the ONLY way to change order status anywhere in the codebase
 */
export async function applyOrderTransitionInTx(
  tx: Prisma.TransactionClient,
  request: OrderTransitionRequest
): Promise<OrderTransitionResult> {
  return orderTransitionService.applyTransition(tx, request)
}

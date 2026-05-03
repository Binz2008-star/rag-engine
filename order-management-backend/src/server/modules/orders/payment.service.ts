import { prisma } from '../../db/prisma'
import { orderService } from '../../services/order.service'
import { PaymentService as CanonicalPaymentService } from '../../services/payment.service'
import { logger } from '../../lib/logger'

class PaymentServiceCompatibilityWrapper {
  async simulatePayment(orderId: string, success = true, actorUserId?: string) {
    logger.info(`PAYMENT_STARTED - orderId: ${orderId}, success: ${success}, actor: ${actorUserId}`)

    const order = await prisma.order.findUniqueOrThrow({
      where: { id: orderId },
      select: {
        id: true,
        totalMinor: true,
        currency: true,
        paymentType: true,
      },
    })

    // Update payment type through proper service layer
    if (order.paymentType === 'CASH_ON_DELIVERY') {
      await orderService.updateOrderPaymentType(orderId, 'CARD', actorUserId)
      logger.info(`PAYMENT_TYPE_UPDATED - orderId: ${orderId}, type: CARD`)
    }

    const attempt = await CanonicalPaymentService.createPaymentAttempt({
      orderId: order.id,
      provider: 'SIMULATOR',
      amountMinor: order.totalMinor,
      currency: order.currency,
    }, actorUserId)

    logger.info(`PAYMENT_ATTEMPT_CREATED - attemptId: ${attempt.id}, orderId: ${orderId}, amount: ${order.totalMinor}`)

    const processingAttempt = await CanonicalPaymentService.updatePaymentStatus({
      paymentAttemptId: attempt.id,
      status: 'PROCESSING',
    }, actorUserId)

    if (success) {
      logger.info(`PAYMENT_COMPLETED - attemptId: ${attempt.id}`)
      return CanonicalPaymentService.updatePaymentStatus({
        paymentAttemptId: processingAttempt.id,
        status: 'COMPLETED',
        providerReference: `SIM-${Date.now()}`,
      }, actorUserId)
    }

    logger.warn(`PAYMENT_FAILED - attemptId: ${attempt.id}, reason: Simulated payment failure`)
    return CanonicalPaymentService.updatePaymentStatus({
      paymentAttemptId: processingAttempt.id,
      status: 'FAILED',
      failureReason: 'Simulated payment failure',
    }, actorUserId)
  }
}

export const paymentService = new PaymentServiceCompatibilityWrapper()

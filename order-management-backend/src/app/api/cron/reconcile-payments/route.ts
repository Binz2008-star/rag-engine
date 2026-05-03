import { logger } from '@/server/lib/logger'
import {
  PaymentReconciliationService,
  type ReconcileStripeWebhookResult,
} from '@/server/services/payment-reconciliation.service'
import { NextRequest, NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

const DEFAULT_RECONCILIATION_LIMIT = 100
const MAX_RECONCILIATION_LIMIT = 500

function parseLimit(request: NextRequest): number {
  const limitFromQuery = request.nextUrl.searchParams.get('limit')
  const limitFromEnv = process.env.CRON_RECONCILE_LIMIT
  const raw = limitFromQuery ?? limitFromEnv

  if (!raw) return DEFAULT_RECONCILIATION_LIMIT

  const numeric = Number(raw)
  if (!Number.isInteger(numeric) || numeric <= 0) {
    return DEFAULT_RECONCILIATION_LIMIT
  }

  return Math.min(numeric, MAX_RECONCILIATION_LIMIT)
}

function isAuthorized(request: NextRequest): boolean {
  const cronSecret = process.env.CRON_SECRET?.trim()
  if (!cronSecret) return false

  const authorizationHeader = request.headers.get('authorization')
  const bearerToken = authorizationHeader?.startsWith('Bearer ')
    ? authorizationHeader.slice('Bearer '.length).trim()
    : null
  const xCronSecret = request.headers.get('x-cron-secret')?.trim()

  return bearerToken === cronSecret || xCronSecret === cronSecret
}

export async function GET(request: NextRequest) {
  const cronSecret = process.env.CRON_SECRET?.trim()

  if (!cronSecret) {
    logger.error('Cron reconciliation misconfigured: missing CRON_SECRET')
    return NextResponse.json(
      { error: 'Cron is not configured' },
      { status: 503 }
    )
  }

  if (!isAuthorized(request)) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    )
  }

  const limit = parseLimit(request)

  try {
    const stripeResult: ReconcileStripeWebhookResult =
      await PaymentReconciliationService.reconcileStripeSucceededWebhooks({
        limit,
      })

    logger.info('Cron payment reconciliation completed', {
      source: 'cron',
      stripe: stripeResult,
      limit,
    })

    return NextResponse.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      source: 'cron',
      stripe: stripeResult,
      limit,
    })
  } catch (error) {
    logger.error('Cron payment reconciliation failed', error as Error, {
      source: 'cron',
      limit,
    })

    return NextResponse.json(
      { error: 'Reconciliation failed' },
      { status: 500 }
    )
  }
}

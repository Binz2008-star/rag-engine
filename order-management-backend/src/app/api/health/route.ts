import { prisma } from '@/server/db/prisma'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    await prisma.$queryRaw`SELECT 1`

    const response = NextResponse.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      version: 'v1.0.0',
      database: 'connected',
      message: 'Health check passed'
    })

    // Log successful request (metrics will be captured by monitoring endpoint)

    return response
  } catch (error) {
    // Log failed request (metrics will be captured by monitoring endpoint)

    return NextResponse.json({
      status: 'error',
      timestamp: new Date().toISOString(),
      version: 'v1.0.0',
      database: 'unavailable',
      error: error instanceof Error ? error.message : 'Health check failed'
    }, { status: 503 })
  }
}

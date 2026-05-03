import { afterEach, describe, expect, it, vi } from 'vitest'
import type { NextRequest } from 'next/server'
import {
  createRateLimit,
  MemoryRateLimitStore,
  RATE_LIMIT_CONFIGS,
  type RateLimitStore,
} from '../server/lib/rate-limit-redis'

function createMockRequest(pathname = '/api/auth/login', ip = '127.0.0.1'): NextRequest {
  return {
    url: `https://example.com${pathname}`,
    headers: new Headers({
      'x-forwarded-for': ip,
    }),
    nextUrl: { pathname },
  } as unknown as NextRequest
}

class FailingStore implements RateLimitStore {
  async check(): Promise<never> {
    throw new Error('store unavailable')
  }
}

describe('Rate limiting', () => {
  const originalNodeEnv = process.env.NODE_ENV
  const env = process.env as { NODE_ENV?: string }

  afterEach(() => {
    env.NODE_ENV = originalNodeEnv
    vi.restoreAllMocks()
  })

  it('returns header-compatible responses across store implementations', async () => {
    const request = createMockRequest('/api/public/demo/products', '10.0.0.1')

    const memoryLimiterA = createRateLimit({
      ...RATE_LIMIT_CONFIGS.PUBLIC_API,
      store: new MemoryRateLimitStore(),
    })

    const memoryLimiterB = createRateLimit({
      ...RATE_LIMIT_CONFIGS.PUBLIC_API,
      store: new MemoryRateLimitStore(),
    })

    const firstA = await memoryLimiterA(request)
    const firstB = await memoryLimiterB(request)

    expect(firstA.success).toBe(true)
    expect(firstB.success).toBe(true)
    expect(Object.keys(firstA.headers).sort()).toEqual(Object.keys(firstB.headers).sort())
    expect(firstA.headers['X-RateLimit-Limit']).toBe(RATE_LIMIT_CONFIGS.PUBLIC_API.maxRequests.toString())
    expect(firstA.headers['X-RateLimit-Remaining']).toBe(firstB.headers['X-RateLimit-Remaining'])

    let finalA = firstA
    let finalB = firstB
    for (let i = 0; i < RATE_LIMIT_CONFIGS.PUBLIC_API.maxRequests; i++) {
      finalA = await memoryLimiterA(request)
      finalB = await memoryLimiterB(request)
    }

    expect(finalA.success).toBe(false)
    expect(finalB.success).toBe(false)
    if (finalA.success || finalB.success) {
      throw new Error('Expected both limiters to exceed the rate limit')
    }
    expect(finalA.statusCode).toBe(429)
    expect(finalB.statusCode).toBe(429)
    expect(finalA.headers['Retry-After']).toMatch(/^\d+$/)
    expect(finalB.headers['Retry-After']).toMatch(/^\d+$/)
    expect(finalA.headers['X-RateLimit-Limit']).toBe(finalB.headers['X-RateLimit-Limit'])
    expect(finalA.headers['X-RateLimit-Remaining']).toBe(finalB.headers['X-RateLimit-Remaining'])
    expect(finalA.headers['Retry-After']).toBe(finalB.headers['Retry-After'])

    const resetA = Date.parse(finalA.headers['X-RateLimit-Reset'])
    const resetB = Date.parse(finalB.headers['X-RateLimit-Reset'])
    expect(Number.isNaN(resetA)).toBe(false)
    expect(Number.isNaN(resetB)).toBe(false)
    expect(Math.abs(resetA - resetB)).toBeLessThanOrEqual(1000)
  })

  it('fails closed for AUTH endpoints when the distributed store is unavailable in production', async () => {
    env.NODE_ENV = 'production'
    const request = createMockRequest('/api/auth/login', '10.0.0.2')

    const limiter = createRateLimit({
      ...RATE_LIMIT_CONFIGS.AUTH,
      store: new FailingStore(),
    })

    const result = await limiter(request)

    expect(result.success).toBe(false)
    if (result.success) {
      throw new Error('Expected auth limiter to fail closed when store is unavailable')
    }
    expect(result.statusCode).toBe(503)
    expect(result.reason).toBe('store_unavailable')
    expect(result.headers['X-RateLimit-Limit']).toBe(RATE_LIMIT_CONFIGS.AUTH.maxRequests.toString())
  })

  it('degrades to memory for PUBLIC_API when the distributed store is unavailable in production', async () => {
    env.NODE_ENV = 'production'
    const request = createMockRequest('/api/public/demo/products', '10.0.0.3')

    const limiter = createRateLimit({
      ...RATE_LIMIT_CONFIGS.PUBLIC_API,
      store: new FailingStore(),
    })

    const first = await limiter(request)
    expect(first.success).toBe(true)

    let last = first
    for (let i = 0; i < RATE_LIMIT_CONFIGS.PUBLIC_API.maxRequests; i++) {
      last = await limiter(request)
    }

    expect(last.success).toBe(false)
    if (last.success) {
      throw new Error('Expected public limiter to block after memory fallback exhaustion')
    }
    expect(last.statusCode).toBe(429)
    expect(last.reason).toBe('limit_exceeded')
  })
})

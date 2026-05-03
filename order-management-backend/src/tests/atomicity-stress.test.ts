import { describe, it, expect } from 'vitest'
import { NextRequest } from 'next/server'
import { RateLimitService } from '../server/lib/rate-limit-service'
import { RateLimitConfig } from '../server/lib/rate-limit-store'

describe('Atomicity Stress Test', () => {
  it('demonstrates race condition vulnerability', async () => {
    const config: RateLimitConfig = {
      windowMs: 60000,
      maxRequests: 5,
      redisKeyPrefix: 'stress_test'
    }

    // Mock Upstash to simulate race conditions
    const originalFetch = global.fetch
    let requestCount = 0

    global.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      requestCount++

      // Simulate network delay to expose race conditions
      await new Promise(resolve => setTimeout(resolve, Math.random() * 100))

      const url = typeof input === 'string' ? input : input.toString()

      if (url.includes('/SET')) {
        return {
          ok: false,
          status: 409 // Key already exists
        } as Response
      }

      if (url.includes('/INCR')) {
        return {
          ok: true,
          json: async () => 1 // Always return 1 to simulate race
        } as Response
      }

      return originalFetch(input, init)
    }

    const request = new Request('http://localhost:3000/api/test', {
      headers: { 'x-forwarded-for': '192.168.1.100' }
    }) as unknown as NextRequest

    const service = new RateLimitService(config)

    // Fire 20 concurrent requests
    const concurrentRequests = Array.from({ length: 20 }, () =>
      service.check(request)
    )

    const results = await Promise.all(concurrentRequests)

    // Count how many were allowed (should be <= 5 if atomic)
    const allowedCount = results.filter(r => r.allowed).length

    console.log(`Concurrent requests: 20, Allowed: ${allowedCount}, Total fetch calls: ${requestCount}`)

    // Memory store is atomic - should not exceed limit
    expect(allowedCount).toBeLessThanOrEqual(5) // Memory store prevents race conditions

    // Restore fetch
    global.fetch = originalFetch
  }, 10000)
})

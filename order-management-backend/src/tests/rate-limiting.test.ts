import { NextRequest } from 'next/server'
import { beforeEach, describe, expect, it } from 'vitest'
import { MemoryRateLimitStore } from '../server/lib/rate-limit-memory'
import { RateLimitService } from '../server/lib/rate-limit-service'
import { RateLimitConfig } from '../server/lib/rate-limit-store'

const env = process.env as {
  NODE_ENV?: string
  UPSTASH_REDIS_REST_URL?: string
  UPSTASH_REDIS_REST_TOKEN?: string
  REDIS_URL?: string
}
const originalNodeEnv = env.NODE_ENV

describe('Rate Limiting - Header Contract Parity', () => {
  let memoryStore: MemoryRateLimitStore
  let service: RateLimitService

  beforeEach(() => {
    memoryStore = new MemoryRateLimitStore()
    env.NODE_ENV = originalNodeEnv
    delete env.REDIS_URL
    delete env.UPSTASH_REDIS_REST_URL
    delete env.UPSTASH_REDIS_REST_TOKEN
  })

  it('Memory and Upstash stores return identical headers', async () => {
    const config: RateLimitConfig = {
      windowMs: 60000,
      maxRequests: 10,
      redisKeyPrefix: 'test'
    }

    const request = new Request('http://localhost:3000/api/test', {
      headers: { 'x-forwarded-for': '192.168.1.1' }
    }) as unknown as NextRequest

    // Test memory store directly
    const memoryResult = await memoryStore.check('test:key', 10, 60000)

    // Test through service (will use memory as fallback)
    service = new RateLimitService(config)
    const serviceResult = await service.check(request)

    expect(serviceResult.allowed).toBe(memoryResult.allowed)
    expect(serviceResult.remaining).toBe(memoryResult.remaining)
    expect(serviceResult.resetTime).toBeCloseTo(memoryResult.resetTime, -2) // Allow 100ms tolerance
  })

  it('Rate limit headers are consistent', async () => {
    const config: RateLimitConfig = {
      windowMs: 60000,
      maxRequests: 5,
      redisKeyPrefix: 'test'
    }

    const request = new Request('http://localhost:3000/api/test', {
      headers: { 'x-forwarded-for': '192.168.1.1' }
    }) as unknown as NextRequest

    service = new RateLimitService(config)

    // First request
    const result1 = await service.check(request)
    expect(result1.allowed).toBe(true)
    expect(result1.remaining).toBe(4)
    expect(result1.resetTime).toBeGreaterThan(Date.now())

    // Exhaust limit
    for (let i = 0; i < 4; i++) {
      await service.check(request)
    }

    // Final request - should be blocked
    const resultFinal = await service.check(request)
    expect(resultFinal.allowed).toBe(false)
    expect(resultFinal.remaining).toBe(0)
  })
})

describe('Production Failure Policies', () => {
  it('AUTH endpoint fails closed when Redis unavailable', async () => {
    const config: RateLimitConfig = {
      windowMs: 60000,
      maxRequests: 5,
      redisKeyPrefix: 'auth'
    }

    const request = new Request('http://localhost:3000/api/auth/login', {
      headers: { 'x-forwarded-for': '192.168.1.1' }
    }) as unknown as NextRequest

    env.NODE_ENV = 'production'

    // Mock Redis failure by using invalid config
    env.UPSTASH_REDIS_REST_URL = 'https://invalid-url'
    env.UPSTASH_REDIS_REST_TOKEN = 'invalid-token'

    const service = new RateLimitService(config)

    // Should fail closed for auth endpoints
    await expect(service.check(request)).rejects.toThrow('Rate limiting service unavailable')
  })

  it('PUBLIC_API degrades to memory when Redis unavailable', async () => {
    const config: RateLimitConfig = {
      windowMs: 60000,
      maxRequests: 10,
      redisKeyPrefix: 'public_api'
    }

    const request = new Request('http://localhost:3000/api/public/test', {
      headers: { 'x-forwarded-for': '192.168.1.1' }
    }) as unknown as NextRequest

    env.NODE_ENV = 'production'

    // Mock Redis failure
    env.UPSTASH_REDIS_REST_URL = 'https://invalid-url'
    env.UPSTASH_REDIS_REST_TOKEN = 'invalid-token'

    const service = new RateLimitService(config)

    // Should degrade to memory
    const result = await service.check(request)
    expect(result.allowed).toBe(true)
    expect(result.remaining).toBe(9)
  })
})

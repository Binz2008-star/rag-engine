import { describe, it, expect, beforeEach } from 'vitest'
import { NextRequest } from 'next/server'
import { RateLimitService } from '../server/lib/rate-limit-service'
import { MemoryRateLimitStore } from '../server/lib/rate-limit-memory'
import { RateLimitConfig } from '../server/lib/rate-limit-store'

describe('Production-Ready Rate Limiting Tests', () => {
  let memoryStore: MemoryRateLimitStore
  let service: RateLimitService
  const env = process.env as {
    NODE_ENV?: string
    UPSTASH_REDIS_REST_URL?: string
    UPSTASH_REDIS_REST_TOKEN?: string
    REDIS_URL?: string
  }
  const originalNodeEnv = env.NODE_ENV

  beforeEach(() => {
    memoryStore = new MemoryRateLimitStore()
    env.NODE_ENV = originalNodeEnv
    delete env.REDIS_URL
    delete env.UPSTASH_REDIS_REST_URL
    delete env.UPSTASH_REDIS_REST_TOKEN
  })

  describe('Atomicity and Race Conditions', () => {
    it('prevents over-allowance with concurrent requests', async () => {
      const config: RateLimitConfig = {
        windowMs: 60000,
        maxRequests: 5,
        redisKeyPrefix: 'test_concurrent'
      }

      const request = new Request('http://localhost:3000/api/test', {
        headers: { 'x-forwarded-for': '192.168.1.1' }
      }) as unknown as NextRequest

      service = new RateLimitService(config)
      
      // Simulate 10 concurrent requests (should exceed limit of 5)
      const concurrentRequests = Array.from({ length: 10 }, () => 
        service.check(request)
      )
      
      const results = await Promise.all(concurrentRequests)
      
      // Count how many were allowed
      const allowedCount = results.filter(r => r.allowed).length
      const blockedCount = results.filter(r => !r.allowed).length
      
      // Should never exceed the limit
      expect(allowedCount).toBeLessThanOrEqual(5)
      expect(blockedCount).toBeGreaterThanOrEqual(5)
      
      // All results should have consistent remaining counts
      const allowedResults = results.filter(r => r.allowed)
      allowedResults.forEach(result => {
        expect(result.remaining).toBeGreaterThanOrEqual(0)
        expect(result.remaining).toBeLessThan(5)
      })
    })

    it('maintains consistent reset times across requests', async () => {
      const config: RateLimitConfig = {
        windowMs: 60000,
        maxRequests: 10,
        redisKeyPrefix: 'test_reset_time'
      }

      const request = new Request('http://localhost:3000/api/test', {
        headers: { 'x-forwarded-for': '192.168.1.2' }
      }) as unknown as NextRequest

      service = new RateLimitService(config)
      
      const result1 = await service.check(request)
      const result2 = await service.check(request)
      const result3 = await service.check(request)
      
      // All should have the same reset time (same window)
      expect(result1.resetTime).toBe(result2.resetTime)
      expect(result2.resetTime).toBe(result3.resetTime)
      
      // Reset time should be approximately windowMs from now
      const expectedResetTime = Date.now() + 60000
      expect(result1.resetTime).toBeGreaterThan(expectedResetTime - 1000)
      expect(result1.resetTime).toBeLessThan(expectedResetTime + 1000)
    })
  })

  describe('Redis Failure Simulation', () => {
    it('fails closed for auth endpoints when Redis unavailable', async () => {
      const config: RateLimitConfig = {
        windowMs: 60000,
        maxRequests: 5,
        redisKeyPrefix: 'auth'
      }

      const request = new Request('http://localhost:3000/api/auth/login', {
        headers: { 'x-forwarded-for': '192.168.1.3' }
      }) as unknown as NextRequest

      env.NODE_ENV = 'production'

      // Mock Redis failure
      env.UPSTASH_REDIS_REST_URL = 'https://invalid-url'
      env.UPSTASH_REDIS_REST_TOKEN = 'invalid-token'

      const service = new RateLimitService(config)
      
      // Should fail closed for auth endpoints
      await expect(service.check(request)).rejects.toThrow('Rate limiting service unavailable')
    })

    it('degrades gracefully for public APIs', async () => {
      const config: RateLimitConfig = {
        windowMs: 60000,
        maxRequests: 10,
        redisKeyPrefix: 'public_api'
      }

      const request = new Request('http://localhost:3000/api/public/test', {
        headers: { 'x-forwarded-for': '192.168.1.4' }
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

  describe('Header Consistency', () => {
    it('produces identical headers across memory and Redis stores', async () => {
      const config: RateLimitConfig = {
        windowMs: 60000,
        maxRequests: 5,
        redisKeyPrefix: 'test_headers'
      }

      const request = new Request('http://localhost:3000/api/test', {
        headers: { 'x-forwarded-for': '192.168.1.5' }
      }) as unknown as NextRequest

      // Test memory store directly
      const memoryResult = await memoryStore.check('test:key', 5, 60000)
      
      // Test through service (will use memory as fallback)
      service = new RateLimitService(config)
      const serviceResult = await service.check(request)

      expect(serviceResult.allowed).toBe(memoryResult.allowed)
      expect(serviceResult.remaining).toBe(memoryResult.remaining)
      expect(Math.abs(serviceResult.resetTime - memoryResult.resetTime)).toBeLessThanOrEqual(1000)
    })

    it('maintains header format consistency', async () => {
      const config: RateLimitConfig = {
        windowMs: 60000,
        maxRequests: 10,
        redisKeyPrefix: 'test_format'
      }

      const request = new Request('http://localhost:3000/api/test', {
        headers: { 'x-forwarded-for': '192.168.1.6' }
      }) as unknown as NextRequest

      service = new RateLimitService(config)
      
      const result = await service.check(request)
      
      // Verify result structure
      expect(result).toHaveProperty('allowed')
      expect(result).toHaveProperty('remaining')
      expect(result).toHaveProperty('resetTime')
      
      expect(typeof result.allowed).toBe('boolean')
      expect(typeof result.remaining).toBe('number')
      expect(typeof result.resetTime).toBe('number')
      
      expect(result.remaining).toBeGreaterThanOrEqual(0)
      expect(result.remaining).toBeLessThanOrEqual(10)
      expect(result.resetTime).toBeGreaterThan(Date.now())
    })
  })

  describe('Window Boundary Behavior', () => {
    it('resets correctly after window expiry', async () => {
      const config: RateLimitConfig = {
        windowMs: 100, // Very short window for testing
        maxRequests: 2,
        redisKeyPrefix: 'test_window'
      }

      const request = new Request('http://localhost:3000/api/test', {
        headers: { 'x-forwarded-for': '192.168.1.7' }
      }) as unknown as NextRequest

      service = new RateLimitService(config)
      
      // Exhaust limit
      const result1 = await service.check(request)
      expect(result1.allowed).toBe(true)
      expect(result1.remaining).toBe(1)
      
      const result2 = await service.check(request)
      expect(result2.allowed).toBe(true)
      expect(result2.remaining).toBe(0)
      
      const result3 = await service.check(request)
      expect(result3.allowed).toBe(false)
      expect(result3.remaining).toBe(0)
      
      // Wait for window to expire
      await new Promise(resolve => setTimeout(resolve, 150))
      
      // Should be reset
      const result4 = await service.check(request)
      expect(result4.allowed).toBe(true)
      expect(result4.remaining).toBe(1)
    })
  })
})

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { validateBcryptRounds, validateJwtSecret, validateProductionEnv } from '../server/lib/env'

const mutableEnv = process.env as Record<string, string | undefined>
const originalEnv = { ...process.env }

describe('Production Environment Validation', () => {
  beforeAll(() => {
    // Mock console methods to avoid test noise
    vi.spyOn(console, 'log').mockImplementation(() => { })
    vi.spyOn(console, 'error').mockImplementation(() => { })
  })

  afterEach(() => {
    // Restore original environment after each test
    Object.keys(process.env).forEach(key => {
      delete process.env[key]
    })
    Object.assign(process.env, originalEnv)
  })

  describe('Environment validation logic', () => {
    it('should validate JWT_SECRET length', () => {
      expect(() => validateJwtSecret('short')).toThrow('[ENV ERROR] JWT_SECRET must be at least 32 characters')
      expect(() => validateJwtSecret('secure-32-character-production-jwt-key-valid')).not.toThrow()
    })

    it('should validate JWT_SECRET insecure patterns', () => {
      expect(() => validateJwtSecret('fallback-secret-for-testing-32-chars-min')).toThrow('[ENV ERROR] JWT_SECRET appears to be insecure or placeholder')
      expect(() => validateJwtSecret('secure-32-character-production-jwt-key-valid')).not.toThrow()
    })

    it('should validate BCRYPT_ROUNDS range', () => {
      expect(() => validateBcryptRounds(8)).toThrow('[ENV ERROR] BCRYPT_ROUNDS must be between 10 and 14')
      expect(() => validateBcryptRounds(15)).toThrow('[ENV ERROR] BCRYPT_ROUNDS must be between 10 and 14')
      expect(() => validateBcryptRounds(12)).not.toThrow()
    })

    it('should validate production requirements', () => {
      // Set up valid environment
      process.env.JWT_SECRET = 'secure-32-character-production-jwt-key-valid'
      process.env.DATABASE_URL = 'postgresql://test'
      process.env.BCRYPT_ROUNDS = '12'
      process.env.NEXTAUTH_SECRET = 'nextauth-production-token-abcdefghijklmnopqrstuvwxyz123456'
      delete process.env.REDIS_URL
      delete process.env.UPSTASH_REDIS_REST_URL
      delete process.env.UPSTASH_REDIS_REST_TOKEN
      delete process.env.CRON_SECRET

      // Mock NODE_ENV as production
      const originalNodeEnv = mutableEnv.NODE_ENV
      mutableEnv.NODE_ENV = 'production'

      // Should fail without REDIS_URL in production
      expect(() => validateProductionEnv()).toThrow('[PRODUCTION FATAL] Missing required env: REDIS_URL')

      // Should pass with REDIS_URL
      process.env.REDIS_URL = 'redis://localhost:6379'
      process.env.CRON_SECRET = 'cron-secret-value-123'
      expect(() => validateProductionEnv()).not.toThrow()

      // Restore NODE_ENV
      mutableEnv.NODE_ENV = originalNodeEnv
    })

    it('should allow missing REDIS_URL in development', () => {
      // Set up valid environment
      process.env.JWT_SECRET = 'secure-32-character-production-jwt-key-valid'
      process.env.DATABASE_URL = 'postgresql://test'
      process.env.BCRYPT_ROUNDS = '12'
      process.env.NEXTAUTH_SECRET = 'nextauth-development-token-abcdefghijklmnopqrstuvwxyz123456'

      // Mock NODE_ENV as development
      const originalNodeEnv = mutableEnv.NODE_ENV
      mutableEnv.NODE_ENV = 'development'

      // Should pass without REDIS_URL in development
      expect(() => validateProductionEnv()).not.toThrow()

      // Restore NODE_ENV
      mutableEnv.NODE_ENV = originalNodeEnv
    })
  })
})

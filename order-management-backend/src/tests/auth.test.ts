import { NextRequest } from 'next/server'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { authenticateUser, getCurrentUser, hashPassword } from '../server/lib/auth'
import { prisma } from '../tests/setup'

describe('Authentication', () => {
  const originalJwtSecret = process.env.JWT_SECRET
  const testJwtSecret = 'secure-32-character-jwt-key-for-development-only'

  beforeAll(() => {
    process.env.JWT_SECRET = testJwtSecret
  })

  afterAll(() => {
    process.env.JWT_SECRET = originalJwtSecret
  })

  beforeEach(async () => {
    await prisma.user.deleteMany()
  })

  describe('hashPassword', () => {
    it('should hash a password', async () => {
      const password = 'test123'
      const hashedPassword = await hashPassword(password)

      expect(hashedPassword).toBeDefined()
      expect(hashedPassword).not.toBe(password)
      expect(hashedPassword.length).toBeGreaterThan(50)
    })

    it('should generate different hashes for same password', async () => {
      const password = 'test123'
      const hash1 = await hashPassword(password)
      const hash2 = await hashPassword(password)

      expect(hash1).not.toBe(hash2)
    })
  })

  describe('authenticateUser', () => {
    it('should authenticate with correct credentials', async () => {
      const email = `test-${Date.now()}-${Math.random()}@example.com`
      const password = 'test123'
      const hashedPassword = await hashPassword(password)

      await prisma.user.create({
        data: {
          email,
          fullName: 'Test User',
          passwordHash: hashedPassword,
          role: 'SELLER',
          isActive: true,
        },
      })

      const result = await authenticateUser(email, password)

      expect(result).toBeDefined()
      expect(result.user.email).toBe(email)
      expect(result.user.role).toBe('SELLER')
      expect(result.token).toBeDefined()
    })

    it('should reject with wrong password', async () => {
      const email = `test-${Date.now()}-${Math.random()}@example.com`
      const password = 'test123'
      const hashedPassword = await hashPassword(password)

      await prisma.user.create({
        data: {
          email,
          fullName: 'Test User',
          passwordHash: hashedPassword,
          role: 'SELLER',
          isActive: true,
        },
      })

      await expect(authenticateUser(email, 'wrongpassword')).rejects.toThrow('Invalid credentials')
    })

    it('should reject inactive user', async () => {
      const email = `test-${Date.now()}-${Math.random()}@example.com`
      const password = 'test123'
      const hashedPassword = await hashPassword(password)

      await prisma.user.create({
        data: {
          email,
          fullName: 'Test User',
          passwordHash: hashedPassword,
          role: 'SELLER',
          isActive: false,
        },
      })

      await expect(authenticateUser(email, password)).rejects.toThrow('Invalid credentials')
    })

    it('should reject non-existent user', async () => {
      await expect(authenticateUser('nonexistent@example.com', 'password')).rejects.toThrow('Invalid credentials')
    })

    it('should reject invalid token', async () => {
      const request = new NextRequest('http://localhost:3000', {
        headers: {
          Authorization: 'Bearer invalid-token',
        },
      })

      await expect(getCurrentUser(request)).rejects.toThrow('Invalid token')
    })

    // JWT_SECRET validation now handled at startup in startup.ts
  })
})

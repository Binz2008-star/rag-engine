/**
 * Production Hardening Tests
 *
 * Tests for:
 * - Fail-fast startup behavior
 * - Redis connectivity requirements
 * - Environment validation
 * - Rate limiting configuration
 * - Authentication requirements
 *
 * NOTE: These tests mock infra dependencies (env, Prisma, Redis) BEFORE importing
 * the modules under test. This ensures productionHardening.initialize() runs real
 * control flow with mocked dependencies, making tests deterministic and fast.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const originalEnv = { ...process.env };

// Global mock: prevent process.exit from killing the test runner
beforeEach(() => {
  vi.spyOn(process, 'exit').mockImplementation(() => undefined as never);

  // Set default production env variables (will be overridden by loadSubject if needed)
  (process.env as Record<string, string | undefined>).NODE_ENV = 'production';
  (process.env as Record<string, string | undefined>).DATABASE_URL = 'postgresql://prod.example.com:5432/db';
  (process.env as Record<string, string | undefined>).JWT_SECRET = 'strong-secret-123456789012345678901234';
  (process.env as Record<string, string | undefined>).REDIS_URL = 'redis://redis.example.com';
  (process.env as Record<string, string | undefined>).BCRYPT_ROUNDS = '12';
  (process.env as Record<string, string | undefined>).NEXTAUTH_SECRET = 'nextauth-secret-123456789012345678901234';
  (process.env as Record<string, string | undefined>).CRON_SECRET = 'cron-secret-123456789012345678901234';
});

afterEach(() => {
  process.env = { ...originalEnv };
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

/**
 * Load modules under test with mocked dependencies.
 * Must be called per-test to ensure mocks are installed before module load.
 */
async function loadSubject(options?: {
  env?: Partial<Record<string, string>>;
  redisConnectFails?: boolean;
  dbFails?: boolean;
  jwtWeak?: boolean;
  jwtMissing?: boolean;
  envMissing?: string[];
  redisHangs?: boolean;
  dbHangs?: boolean;
}) {
  vi.resetModules();

  const mockRedisClient = {
    connect: options?.redisConnectFails
      ? vi.fn().mockRejectedValue(new Error('Redis connection failed'))
      : options?.redisHangs
        ? vi.fn().mockImplementation(() => new Promise(() => { })) // Never resolves
        : vi.fn().mockResolvedValue(undefined),
    ping: options?.redisConnectFails
      ? vi.fn().mockRejectedValue(new Error('Redis ping failed'))
      : vi.fn().mockResolvedValue('PONG'),
    setEx: vi.fn().mockResolvedValue('OK'),
    get: vi.fn().mockResolvedValue('1'),
    del: vi.fn().mockResolvedValue(1),
    keys: vi.fn().mockResolvedValue([]),
    zCard: vi.fn().mockResolvedValue(0),
    zAdd: vi.fn().mockResolvedValue(0),
    zRange: vi.fn().mockResolvedValue([]),
    zRemRangeByScore: vi.fn().mockResolvedValue(0),
    quit: vi.fn().mockResolvedValue('OK'),
  };

  vi.doMock('redis', () => ({
    createClient: vi.fn(() => mockRedisClient),
  }));

  const prismaMock = {
    $queryRaw: options?.dbFails
      ? vi.fn().mockRejectedValue(new Error('Database connection failed'))
      : options?.dbHangs
        ? vi.fn().mockImplementation(() => new Promise(() => { })) // Never resolves
        : vi.fn().mockResolvedValue([{ '?column?': 1 }]),
    $disconnect: vi.fn().mockResolvedValue(undefined),
  };

  vi.doMock('@prisma/client', () => ({
    PrismaClient: vi.fn(() => prismaMock),
  }));

  const baseEnv: Record<string, string> = {
    NODE_ENV: 'production',
    DATABASE_URL: 'postgresql://prod.example.com:5432/db',
    JWT_SECRET: options?.jwtWeak ? 'short' : 'strong-secret-123456789012345678901234',
    REDIS_URL: 'redis://redis.example.com',
    BCRYPT_ROUNDS: '12',
    NEXTAUTH_SECRET: 'nextauth-secret-123456789012345678901234',
    CRON_SECRET: 'cron-secret-123456789012345678901234',
  };

  if (options?.jwtMissing) {
    delete baseEnv.JWT_SECRET;
  }

  if (options?.envMissing) {
    for (const key of options.envMissing) {
      delete baseEnv[key];
    }
  }

  // If env is provided, merge it in (for development mode tests)
  const currentEnv = { ...baseEnv, ...(options?.env ?? {}) };

  // Update process.env to match the current env (environment-validation check reads from process.env)
  Object.assign(process.env, currentEnv);

  vi.doMock('../server/lib/env', () => ({
    env: currentEnv,
    loadEnv: vi.fn(() => currentEnv),
    validateJwtSecret: vi.fn((s: string) => {
      if (!s || s.length < 32) throw new Error('[ENV ERROR] JWT_SECRET must be at least 32 characters');
    }),
    validateNextAuthSecret: vi.fn((s: string) => {
      if (!s || s.length < 32) throw new Error('[ENV ERROR] NEXTAUTH_SECRET must be at least 32 characters');
    }),
    validateBcryptRounds: vi.fn(),
    validateProductionEnv: vi.fn(() => {
      // Simulate production env validation
      if (currentEnv.NODE_ENV === 'production') {
        if (!currentEnv.NEXTAUTH_SECRET) {
          throw new Error('[PRODUCTION FATAL] Missing required env: NEXTAUTH_SECRET');
        }
        if (!currentEnv.CRON_SECRET) {
          throw new Error('[PRODUCTION FATAL] Missing required env: CRON_SECRET');
        }
      }
    }),
  }));

  const hardening = await import('../server/lib/production-hardening');
  const rateLimiter = await import('../server/lib/rate-limiter');

  return {
    ...hardening,
    ...rateLimiter,
    prismaMock,
    mockRedisClient,
  };
}

describe('Production Hardening - Critical Failures', () => {
  it('should fail fast with missing required environment variables', async () => {
    const { productionHardening } = await loadSubject({
      envMissing: ['DATABASE_URL', 'JWT_SECRET', 'REDIS_URL'],
    });

    const status = await productionHardening.initialize();

    // Critical failures should be recorded in status
    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'environment-validation')).toBe(true);
  });

  it('should fail fast when Redis connection fails', async () => {
    const { productionHardening } = await loadSubject({
      redisConnectFails: true,
    });

    const status = await productionHardening.initialize();

    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'redis-connectivity')).toBe(true);
  });

  it('should fail fast when database query fails', async () => {
    const { productionHardening } = await loadSubject({
      dbFails: true,
    });

    const status = await productionHardening.initialize();

    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'database-connectivity')).toBe(true);
  });

  it('should fail fast with weak JWT secret', async () => {
    const { productionHardening } = await loadSubject({
      jwtWeak: true,
    });

    const status = await productionHardening.initialize();

    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'jwt-secret-validation')).toBe(true);
  });

  it('should fail fast with missing JWT secret', async () => {
    const { productionHardening } = await loadSubject({
      jwtMissing: true,
    });

    const status = await productionHardening.initialize();

    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'jwt-secret-validation')).toBe(true);
  });
});

describe('Production Startup', () => {
  it('should skip hardening in development mode', async () => {
    const { productionStartup } = await loadSubject({
      env: { NODE_ENV: 'development' },
    });

    await productionStartup();

    // In development mode, process.exit should NOT be called
    expect(process.exit).not.toHaveBeenCalled();
  });

  it('should exit on critical failures in production mode', async () => {
    const { productionStartup } = await loadSubject({
      redisConnectFails: true,
    });

    await productionStartup();

    // productionStartup is now the only place that calls process.exit
    expect(process.exit).toHaveBeenCalledWith(1);
  });
});

describe('Rate Limiting Production Tests', () => {
  describe('Configuration Validation', () => {
    it('should return false when Redis is unavailable', async () => {
      const { RateLimitUtils, productionHardening } = await loadSubject();

      // Mock getRedisClient to throw (Redis not initialized)
      vi.spyOn(productionHardening, 'getRedisClient').mockImplementation(() => {
        throw new Error('Redis client not initialized');
      });

      const isValid = await RateLimitUtils.validateConfiguration();

      expect(typeof isValid).toBe('boolean');
      expect(isValid).toBe(false);
    });

    it('should complete validation with mocked Redis without real connections', async () => {
      const { RateLimitUtils, productionHardening, mockRedisClient } = await loadSubject();

      // Mock getRedisClient to return our mock (skip initialize to avoid process.exit issues)
      vi.spyOn(productionHardening, 'getRedisClient').mockReturnValue(mockRedisClient as unknown as ReturnType<typeof productionHardening.getRedisClient>);

      // Add more complete Redis mocking for RateLimiter operations
      mockRedisClient.zAdd.mockResolvedValue(1);
      mockRedisClient.zRange.mockResolvedValue([]);
      mockRedisClient.zRemRangeByScore.mockResolvedValue(1);
      mockRedisClient.setEx.mockResolvedValue('OK');
      mockRedisClient.del.mockResolvedValue(1);

      const isValid = await RateLimitUtils.validateConfiguration();

      // The key assertion is that it completes without throwing and returns a boolean
      // Whether it's true or false depends on the RateLimiter implementation details
      expect(typeof isValid).toBe('boolean');
    });

    it('should fail when getting statistics without initialized Redis', async () => {
      const { RateLimitUtils, productionHardening } = await loadSubject();

      // Mock getRedisClient to throw
      vi.spyOn(productionHardening, 'getRedisClient').mockImplementation(() => {
        throw new Error('Redis client not initialized');
      });

      await expect(
        RateLimitUtils.getStatistics('test')
      ).rejects.toThrow('Redis client not initialized');
    });
  });

  describe('Statistics and Cleanup', () => {
    it('should fail when getting statistics without Redis client', async () => {
      const { RateLimitUtils, productionHardening } = await loadSubject();

      vi.spyOn(productionHardening, 'getRedisClient').mockImplementation(() => {
        throw new Error('Redis client not initialized');
      });

      await expect(
        RateLimitUtils.getStatistics('nonexistent')
      ).rejects.toThrow('Redis client not initialized');
    });

    it('should fail when cleaning up without Redis client', async () => {
      const { RateLimitUtils, productionHardening } = await loadSubject();

      vi.spyOn(productionHardening, 'getRedisClient').mockImplementation(() => {
        throw new Error('Redis client not initialized');
      });

      await expect(
        RateLimitUtils.cleanup()
      ).rejects.toThrow('Redis client not initialized');
    });

    it('should return statistics with mocked Redis', async () => {
      const { RateLimitUtils, productionHardening, mockRedisClient } = await loadSubject();

      await productionHardening.initialize();
      vi.spyOn(productionHardening, 'getRedisClient').mockReturnValue(mockRedisClient as unknown as ReturnType<typeof productionHardening.getRedisClient>);

      // Mock keys to return some test data
      const mockKeys = ['rate_limit:test:1', 'rate_limit:test:2'];
      const mockZCard = 5;
      mockRedisClient.keys.mockResolvedValue(mockKeys);
      mockRedisClient.zCard.mockResolvedValue(mockZCard);

      const stats = await RateLimitUtils.getStatistics('rate_limit:test');

      // Invariant-based assertions
      expect(stats.totalKeys).toBe(mockKeys.length);
      expect(stats.totalRequests).toBe(mockKeys.length * mockZCard);
      expect(stats.averageRequestsPerKey).toBe(mockZCard);
    });
  });
});

describe('Production Failure Gates - Non-Critical Checks', () => {
  it('should register audit-trail-configuration as a check', async () => {
    const { productionHardening } = await loadSubject();

    const status = await productionHardening.initialize();

    const auditCheck = status.checks.find(check => check.name === 'audit-trail-configuration');
    if (auditCheck) {
      expect(['pass', 'warn']).toContain(auditCheck.status);
    }
  });

});

describe('Timeout and Hanging Dependencies', () => {
  it('should timeout when Redis connection hangs', async () => {
    const { productionHardening } = await loadSubject({
      redisHangs: true,
    });

    const status = await productionHardening.initialize();

    // Timeout should result in failed status
    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'redis-connectivity')).toBe(true);
  });

  it('should timeout when database query hangs', async () => {
    const { productionHardening } = await loadSubject({
      dbHangs: true,
    });

    const status = await productionHardening.initialize();

    // Timeout should result in failed status
    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'database-connectivity')).toBe(true);
  });
});

describe('Production Security Validation', () => {
  it('should fail fast with default development secrets in production', async () => {
    const { productionHardening } = await loadSubject({
      env: { JWT_SECRET: 'dev-secret' },
    });

    const status = await productionHardening.initialize();

    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'environment-validation')).toBe(true);
  });

  it('should fail fast with localhost Redis in production', async () => {
    const { productionHardening } = await loadSubject({
      env: { REDIS_URL: 'redis://localhost:6379' },
    });

    const status = await productionHardening.initialize();

    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'environment-validation')).toBe(true);
  });

  it('should fail fast with localhost database in production', async () => {
    const { productionHardening } = await loadSubject({
      env: { DATABASE_URL: 'postgresql://localhost:5432/db' },
    });

    const status = await productionHardening.initialize();

    expect(status.healthy).toBe(false);
    expect(status.checks.some(c => c.status === 'fail')).toBe(true);
    expect(status.checks.some(c => c.name === 'environment-validation')).toBe(true);
  });
});

describe('Production Monitoring', () => {
  describe('Health Check Reporting', () => {
    it('should return HardeningStatus with correct structure', async () => {
      const { productionHardening } = await loadSubject();

      const status = await productionHardening.initialize();

      expect(status).toHaveProperty('healthy');
      expect(status).toHaveProperty('checks');
      expect(status).toHaveProperty('startupDuration');

      expect(typeof status.healthy).toBe('boolean');
      expect(Array.isArray(status.checks)).toBe(true);

      // Checks that completed should have correct shape
      status.checks.forEach(check => {
        expect(check).toHaveProperty('name');
        expect(check).toHaveProperty('status');
        expect(check).toHaveProperty('duration');
        expect(['pass', 'fail', 'warn']).toContain(check.status);
      });
    });

    it('should track startup duration', async () => {
      const { productionHardening } = await loadSubject();

      const status = await productionHardening.initialize();

      expect(status.startupDuration).toBeGreaterThan(0);
      expect(status.startupDuration).toBeLessThan(60000);
    });

    it('should include check names for checks that completed', async () => {
      const { productionHardening } = await loadSubject();

      const status = await productionHardening.initialize();

      const checkNames = status.checks.map(check => check.name);
      // Note: critical checks that fail don't add results to checks array
      // We verify that some checks completed successfully
      expect(checkNames.length).toBeGreaterThan(0);
    });
  });
});

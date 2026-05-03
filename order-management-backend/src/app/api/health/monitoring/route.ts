
// src/app/api/health/monitoring/route.ts
import { prisma } from '@/server/db/prisma';
import { NextRequest, NextResponse } from 'next/server';

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  checks: {
    database: {
      status: 'healthy' | 'degraded' | 'unhealthy';
      responseTime: number;
      error?: string;
    };
    memory: {
      status: 'healthy' | 'degraded' | 'unhealthy';
      usage: number;
      threshold: number;
    };
    errors: {
      status: 'healthy' | 'degraded' | 'unhealthy';
      fiveXXRate: number;
      threshold: number;
    };
  };
}

export async function GET(_request: NextRequest) {
  const startTime = Date.now();

  try {
    // Database health check
    const dbStatus: HealthStatus['checks']['database'] = {
      status: 'unhealthy',
      responseTime: 0,
    };

    try {
      const dbStart = Date.now();
      await prisma.$queryRaw`SELECT 1`;
      dbStatus.responseTime = Date.now() - dbStart;
      dbStatus.status = dbStatus.responseTime < 1000 ? 'healthy' : 'degraded';
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      (dbStatus as HealthStatus['checks']['database'] & { error?: string }).error = errorMessage;
      console.error('Health check failed', { error: errorMessage });
    }

    // Memory check
    const memUsage = process.memoryUsage();
    const memUsageMB = memUsage.heapUsed / 1024 / 1024;
    const memoryStatus: HealthStatus['checks']['memory'] = {
      status: memUsageMB < 512 ? 'healthy' : memUsageMB < 1024 ? 'degraded' : 'unhealthy',
      usage: memUsageMB,
      threshold: 1024,
    };

    // Error rate check (simplified - in production use actual metrics)
    const errorStatus: HealthStatus['checks']['errors'] = {
      status: 'healthy',
      fiveXXRate: 0,
      threshold: 0.02,
    };

    // Overall status
    const overallStatus: 'healthy' | 'degraded' | 'unhealthy' =
      dbStatus.status === 'unhealthy' ||
        memoryStatus.status === 'unhealthy' ||
        errorStatus.status === 'unhealthy' ? 'unhealthy' :
        dbStatus.status === 'degraded' ||
          memoryStatus.status === 'degraded' ||
          errorStatus.status === 'degraded' ? 'degraded' : 'healthy';

    const health: HealthStatus = {
      status: overallStatus,
      timestamp: new Date().toISOString(),
      version: process.env.npm_package_version || '1.0.0',
      checks: {
        database: dbStatus,
        memory: memoryStatus,
        errors: errorStatus,
      },
    };

    const responseTime = Date.now() - startTime;

    console.log('Health check completed', {
      status: overallStatus,
      responseTime,
      checks: health.checks,
    });

    return NextResponse.json(health, {
      status: overallStatus === 'healthy' ? 200 : overallStatus === 'degraded' ? 200 : 503,
    });
  } catch (error) {
    console.error('Health check failed', { error });

    return NextResponse.json({
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      version: process.env.npm_package_version || '1.0.0',
      error: error instanceof Error ? error.message : 'Unknown error',
    }, { status: 503 });
  }
}

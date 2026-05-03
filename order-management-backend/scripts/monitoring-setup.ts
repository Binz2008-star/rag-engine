// scripts/monitoring-setup.ts
import fs from "node:fs/promises";

interface MonitoringConfig {
  health: {
    endpoint: string;
    interval: number;
    timeout: number;
  };
  errorMonitoring: {
    thresholds: {
      fiveXXRate: number;
      orderCreationFailures: number;
      statusUpdateFailures: number;
      authFailuresSpike: number;
      dbFailures: number;
    };
    windows: {
      fiveXXRate: number; // minutes
      orderCreationFailures: number; // minutes
      statusUpdateFailures: number; // minutes
      authFailuresSpike: number; // minutes
    };
  };
  latency: {
    endpoints: string[];
    thresholds: {
      p95: number; // milliseconds
      p99: number; // milliseconds
    };
  };
  logging: {
    requiredFields: string[];
    mutationPaths: string[];
  };
  alerts: {
    channels: string[];
    escalation: {
      level1: string[];
      level2: string[];
      level3: string[];
    };
  };
}

const MONITORING_CONFIG: MonitoringConfig = {
  health: {
    endpoint: "/api/health",
    interval: 30000, // 30 seconds
    timeout: 5000, // 5 seconds
  },
  errorMonitoring: {
    thresholds: {
      fiveXXRate: 0.02, // 2%
      orderCreationFailures: 3,
      statusUpdateFailures: 3,
      authFailuresSpike: 10, // above baseline
      dbFailures: 1,
    },
    windows: {
      fiveXXRate: 5, // 5 minutes
      orderCreationFailures: 10, // 10 minutes
      statusUpdateFailures: 10, // 10 minutes
      authFailuresSpike: 5, // 5 minutes
    },
  },
  latency: {
    endpoints: [
      "POST /api/public/{seller}/orders",
      "POST /api/auth/login",
      "PATCH /api/seller/orders/:id/status",
    ],
    thresholds: {
      p95: 1000, // 1 second
      p99: 3000, // 3 seconds
    },
  },
  logging: {
    requiredFields: [
      "requestId",
      "route",
      "timestamp",
      "method",
      "statusCode",
      "responseTime",
    ],
    mutationPaths: [
      "POST /api/public/{seller}/orders",
      "POST /api/auth/login",
      "PATCH /api/seller/orders/:id/status",
      "POST /api/seller/orders",
      "DELETE /api/seller/orders/:id",
    ],
  },
  alerts: {
    channels: ["email", "slack", "sms"],
    escalation: {
      level1: ["email"], // Low priority
      level2: ["email", "slack"], // Medium priority
      level3: ["email", "slack", "sms"], // High priority
    },
  },
};

async function generateMonitoringMiddleware() {
  const middleware = `
// src/server/middleware/monitoring.ts
import { NextRequest, NextResponse } from 'next/server';
import { logger } from '@/server/lib/logger';

interface RequestMetrics {
  requestId: string;
  method: string;
  route: string;
  statusCode: number;
  responseTime: number;
  timestamp: Date;
  userId?: string;
  sellerId?: string;
  orderId?: string;
  error?: string;
}

class MonitoringMiddleware {
  private metrics: RequestMetrics[] = [];
  private errorCounts: Map<string, number> = new Map();
  private lastAuthFailureBaseline = 0;
  private authFailureBaselineCount = 0;

  private generateRequestId(): string {
    return Math.random().toString(36).substring(2, 15) +
           Math.random().toString(36).substring(2, 15);
  }

  private extractRoute(request: NextRequest): string {
    const url = new URL(request.url);
    return request.method + ' ' + url.pathname;
  }

  private isMutationPath(route: string): boolean {
    const mutationPaths = ${JSON.stringify(MONITORING_CONFIG.logging.mutationPaths)};
    return mutationPaths.some(path => {
      const regex = new RegExp(path.replace(/{[^}]+}/g, '[^/]+'));
      return regex.test(route);
    });
  }

  private extractContext(request: NextRequest, response: NextResponse): {
    userId?: string;
    sellerId?: string;
    orderId?: string;
  } {
    const context: any = {};
    
    // Extract from headers
    const authorization = request.headers.get('authorization');
    if (authorization) {
      try {
        const token = authorization.replace('Bearer ', '');
        const payload = JSON.parse(atob(token.split('.')[1]));
        context.userId = payload.id;
        context.sellerId = payload.sellerId;
      } catch {
        // Invalid token, ignore
      }
    }

    // Extract from URL
    const url = new URL(request.url);
    const orderId = url.pathname.match(/orders\\/([^\\/]+)/);
    if (orderId) {
      context.orderId = orderId[1];
    }

    return context;
  }

  private trackError(route: string, statusCode: number) {
    if (statusCode >= 500) {
      const key = '5xx_errors';
      this.errorCounts.set(key, (this.errorCounts.get(key) || 0) + 1);
    }

    if (route.includes('/auth/login') && statusCode === 401) {
      const key = 'auth_failures';
      this.errorCounts.set(key, (this.errorCounts.get(key) || 0) + 1);
    }

    if (route.includes('/orders') && statusCode >= 400) {
      if (route.includes('POST')) {
        const key = 'order_creation_failures';
        this.errorCounts.set(key, (this.errorCounts.get(key) || 0) + 1);
      } else if (route.includes('PATCH') && route.includes('/status')) {
        const key = 'status_update_failures';
        this.errorCounts.set(key, (this.errorCounts.get(key) || 0) + 1);
      }
    }
  }

  private checkAlerts(metrics: RequestMetrics) {
    const now = Date.now();
    const recentMetrics = this.metrics.filter(m => 
      now - m.timestamp.getTime() < 5 * 60 * 1000 // 5 minutes
    );

    // Check 5xx rate
    const fiveXXCount = recentMetrics.filter(m => m.statusCode >= 500).length;
    const fiveXXRate = fiveXXCount / recentMetrics.length;
    if (fiveXXRate > ${MONITORING_CONFIG.errorMonitoring.thresholds.fiveXXRate}) {
      this.sendAlert('HIGH', \`5xx error rate: \${(fiveXXRate * 100).toFixed(2)}%\`);
    }

    // Check order creation failures
    const orderCreationFailures = this.errorCounts.get('order_creation_failures') || 0;
    if (orderCreationFailures > ${MONITORING_CONFIG.errorMonitoring.thresholds.orderCreationFailures}) {
      this.sendAlert('MEDIUM', \`Order creation failures: \${orderCreationFailures} in 10 minutes\`);
    }

    // Check status update failures
    const statusUpdateFailures = this.errorCounts.get('status_update_failures') || 0;
    if (statusUpdateFailures > ${MONITORING_CONFIG.errorMonitoring.thresholds.statusUpdateFailures}) {
      this.sendAlert('MEDIUM', \`Status update failures: \${statusUpdateFailures} in 10 minutes\`);
    }

    // Check auth failures spike
    const authFailures = this.errorCounts.get('auth_failures') || 0;
    if (authFailures > this.authFailureBaselineCount + ${MONITORING_CONFIG.errorMonitoring.thresholds.authFailuresSpike}) {
      this.sendAlert('HIGH', \`Auth failure spike: \${authFailures} failures\`);
    }
  }

  private sendAlert(level: 'LOW' | 'MEDIUM' | 'HIGH', message: string) {
    const alertData = {
      level,
      message,
      timestamp: new Date().toISOString(),
      service: 'order-management-backend',
    };

    logger.warn('ALERT', { alertData });

    // In production, integrate with actual alerting systems
    // For now, just log the alert
    console.error('ALERT:', JSON.stringify(alertData, null, 2));
  }

  middleware() {
    return async (request: NextRequest) => {
      const startTime = Date.now();
      const requestId = this.generateRequestId();
      const route = this.extractRoute(request);

      // Add request ID to request headers for downstream use
      request.headers.set('x-request-id', requestId);

      let response: NextResponse;
      let statusCode = 200;

      try {
        // Process the request
        const response = await fetch(request.url, {
          method: request.method,
          headers: request.headers,
          body: request.body,
        });

        statusCode = response.status;
        return response;
      } catch (error) {
        statusCode = 500;
        throw error;
      } finally {
        const endTime = Date.now();
        const responseTime = endTime - startTime;

        const context = this.extractContext(request, response as any);

        const metrics: RequestMetrics = {
          requestId,
          method: request.method,
          route,
          statusCode,
          responseTime,
          timestamp: new Date(),
          ...context,
        };

        this.metrics.push(metrics);
        this.trackError(route, statusCode);

        // Log mutation requests with full context
        if (this.isMutationPath(route)) {
          const logLevel = statusCode >= 500 ? 'error' : statusCode >= 400 ? 'warn' : 'info';
          logger[logLevel]('MUTATION_REQUEST', {
            requestId,
            route,
            method: request.method,
            statusCode,
            responseTime,
            userId: context.userId,
            sellerId: context.sellerId,
            orderId: context.orderId,
            outcome: statusCode < 400 ? 'success' : 'failure',
            ...(statusCode >= 500 && { error: 'Internal server error' }),
          });
        }

        // Check for alerts
        this.checkAlerts(metrics);

        // Clean old metrics (keep last hour)
        const oneHourAgo = Date.now() - 60 * 60 * 1000;
        this.metrics = this.metrics.filter(m => m.timestamp.getTime() > oneHourAgo);
      }
    };
  }
}

export const monitoringMiddleware = new MonitoringMiddleware().middleware();
`;

  return middleware;
}

async function generateHealthCheckEnhancement() {
  const healthCheck = `
// src/app/api/health/monitoring/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/server/db/prisma';
import { logger } from '@/server/lib/logger';

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  checks: {
    database: {
      status: 'healthy' | 'unhealthy';
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

export async function GET(request: NextRequest) {
  const startTime = Date.now();
  
  try {
    // Database health check
    let dbStatus: HealthStatus['checks']['database'] = {
      status: 'unhealthy',
      responseTime: 0,
    };

    try {
      const dbStart = Date.now();
      await prisma.$queryRaw\`SELECT 1\`;
      dbStatus.responseTime = Date.now() - dbStart;
      dbStatus.status = dbStatus.responseTime < 1000 ? 'healthy' : 'degraded';
    } catch (error) {
      dbStatus.error = error instanceof Error ? error.message : 'Unknown error';
      logger.error('Health check failed', { error: dbStatus.error });
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
      threshold: ${MONITORING_CONFIG.errorMonitoring.thresholds.fiveXXRate},
    };

    // Overall status
    const overallStatus = 
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
    
    logger.info('Health check completed', {
      status: overallStatus,
      responseTime,
      checks: health.checks,
    });

    return NextResponse.json(health, {
      status: overallStatus === 'healthy' ? 200 : overallStatus === 'degraded' ? 200 : 503,
    });
  } catch (error) {
    logger.error('Health check failed', { error });
    
    return NextResponse.json({
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      version: process.env.npm_package_version || '1.0.0',
      error: error instanceof Error ? error.message : 'Unknown error',
    }, { status: 503 });
  }
}
`;

  return healthCheck;
}

async function generateMonitoringScripts() {
  const scripts = {
    'monitoring-middleware.ts': await generateMonitoringMiddleware(),
    'health-monitoring.ts': await generateHealthCheckEnhancement(),
  };

  return scripts;
}

async function main() {
  console.log('Setting up monitoring and alerting...');

  const scripts = await generateMonitoringScripts();

  // Write monitoring middleware
  await fs.writeFile(
    'src/server/middleware/monitoring.ts',
    scripts['monitoring-middleware.ts'],
    'utf8'
  );

  // Write enhanced health check
  await fs.writeFile(
    'src/app/api/health/monitoring/route.ts',
    scripts['health-monitoring.ts'],
    'utf8'
  );

  // Write monitoring configuration
  await fs.writeFile(
    'monitoring-config.json',
    JSON.stringify(MONITORING_CONFIG, null, 2),
    'utf8'
  );

  // Generate setup instructions
  const setupInstructions = `
# Monitoring and Alerting Setup

## 1. Install Dependencies
\`\`\`bash
npm install @types/node
\`\`\`

## 2. Add Monitoring Middleware to App
Add to \`src/app/layout.tsx\` or appropriate middleware setup:

\`\`\`typescript
import { monitoringMiddleware } from '@/server/middleware/monitoring';

export const config = {
  matcher: [
    '/api/:path*',
  ],
};

export default monitoringMiddleware;
\`\`\`

## 3. Environment Variables
Add to \`.env\`:

\`\`\`
# Alerting configuration
ALERT_EMAIL_SMTP_HOST=smtp.gmail.com
ALERT_EMAIL_SMTP_PORT=587
ALERT_EMAIL_USER=alerts@yourcompany.com
ALERT_EMAIL_PASS=your-app-password

ALERT_SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

ALERT_SMS_TWILIO_ACCOUNT_SID=your-twilio-sid
ALERT_SMS_TWILIO_AUTH_TOKEN=your-twilio-token
ALERT_SMS_FROM_NUMBER=+1234567890
ALERT_SMS_TO_NUMBER=+0987654321
\`\`\`

## 4. Monitoring Endpoints

### Health Check
- \`GET /api/health\` - Basic health check
- \`GET /api/health/monitoring\` - Enhanced health check with metrics

### Metrics (Future Implementation)
- \`GET /api/metrics\` - Application metrics
- \`GET /api/metrics/errors\` - Error rates and patterns
- \`GET /api/metrics/performance\` - Response time metrics

## 5. Alert Thresholds

Current thresholds:
- 5xx error rate > 2% over 5 minutes
- Order creation failures > 3 in 10 minutes  
- Status update failures > 3 in 10 minutes
- Auth failures spike > 10 above baseline
- P95 latency > 1s on critical endpoints
- P99 latency > 3s on critical endpoints

## 6. Required Logging Fields

All requests must log:
- requestId
- route  
- timestamp
- method
- statusCode
- responseTime

Mutation requests must additionally log:
- userId (if authenticated)
- sellerId (if applicable)
- orderId (if applicable)
- outcome (success/failure)
- error stack (on failure)

## 7. Testing

Test monitoring setup:

\`\`\`bash
# Test health check
curl http://localhost:3000/api/health/monitoring

# Test error logging (should trigger alerts)
curl -X POST http://localhost:3000/api/public/demo-store/orders \\
  -H "Content-Type: application/json" \\
  -d '{"invalid": "payload"}'

# Test performance monitoring
time curl -X POST http://localhost:3000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email":"test@test.com","password":"wrong"}'
\`\`\`

## 8. Production Deployment Checklist

Before deploying to production:

- [ ] Configure alert destinations (email, Slack, SMS)
- [ ] Test all alert thresholds
- [ ] Verify logging format and fields
- [ ] Set up log aggregation (if not already)
- [ ] Configure monitoring dashboards
- [ ] Test escalation procedures
- [ ] Document on-call rotation
`;

  await fs.writeFile(
    'MONITORING_SETUP.md',
    setupInstructions,
    'utf8'
  );

  console.log('Monitoring setup complete!');
  console.log('Files created:');
  console.log('- src/server/middleware/monitoring.ts');
  console.log('- src/app/api/health/monitoring/route.ts');
  console.log('- monitoring-config.json');
  console.log('- MONITORING_SETUP.md');
  console.log('\nNext steps:');
  console.log('1. Review MONITORING_SETUP.md');
  console.log('2. Add monitoring middleware to your app');
  console.log('3. Configure environment variables');
  console.log('4. Test monitoring endpoints');
}

main().catch((error) => {
  console.error('Monitoring setup failed:', error);
  process.exit(1);
});

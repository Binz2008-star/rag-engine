
// src/server/middleware/monitoring.ts
import { NextRequest, NextResponse } from 'next/server';

// Simple logger fallback
const logger = {
  warn: (message: string, data?: unknown) => console.warn(message, data),
  error: (message: string, data?: unknown) => console.error(message, data),
  info: (message: string, data?: unknown) => console.info(message, data),
};

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
    const mutationPaths = ["POST /api/public/{seller}/orders", "POST /api/auth/login", "PATCH /api/seller/orders/:id/status", "POST /api/seller/orders", "DELETE /api/seller/orders/:id"];
    return mutationPaths.some(path => {
      const regex = new RegExp(path.replace(/{[^}]+}/g, '[^/]+'));
      return regex.test(route);
    });
  }

  private extractContext(request: NextRequest, _response: NextResponse): {
    userId?: string;
    sellerId?: string;
    orderId?: string;
  } {
    const context: Record<string, string | undefined> = {};

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
    const orderId = url.pathname.match(/orders\/([^\/]+)/);
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

  private checkAlerts(_metrics: RequestMetrics) {
    const now = Date.now();
    const recentMetrics = this.metrics.filter(m =>
      now - m.timestamp.getTime() < 5 * 60 * 1000 // 5 minutes
    );

    // Check 5xx rate
    const fiveXXCount = recentMetrics.filter(m => m.statusCode >= 500).length;
    const fiveXXRate = fiveXXCount / recentMetrics.length;
    if (fiveXXRate > 0.02) {
      this.sendAlert('HIGH', `5xx error rate: ${(fiveXXRate * 100).toFixed(2)}%`);
    }

    // Check order creation failures
    const orderCreationFailures = this.errorCounts.get('order_creation_failures') || 0;
    if (orderCreationFailures > 3) {
      this.sendAlert('MEDIUM', `Order creation failures: ${orderCreationFailures} in 10 minutes`);
    }

    // Check status update failures
    const statusUpdateFailures = this.errorCounts.get('status_update_failures') || 0;
    if (statusUpdateFailures > 3) {
      this.sendAlert('MEDIUM', `Status update failures: ${statusUpdateFailures} in 10 minutes`);
    }

    // Check auth failures spike
    const authFailures = this.errorCounts.get('auth_failures') || 0;
    if (authFailures > this.authFailureBaselineCount + 10) {
      this.sendAlert('HIGH', `Auth failure spike: ${authFailures} failures`);
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

      let response: NextResponse = new NextResponse();
      let statusCode = 200;

      try {
        // Process the request - NOTE: This middleware pattern needs to be adapted for Next.js App Router
        // For now, we'll just pass through the request
        response = new NextResponse();
        statusCode = 200;
        return response;
      } catch (error) {
        statusCode = 500;
        throw error;
      } finally {
        const endTime = Date.now();
        const responseTime = endTime - startTime;

        const context = this.extractContext(request, response);

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
          if (logLevel === 'error') {
            logger.error('MUTATION_REQUEST', {
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
          } else if (logLevel === 'warn') {
            logger.warn('MUTATION_REQUEST', {
              requestId,
              route,
              method: request.method,
              statusCode,
              responseTime,
              userId: context.userId,
              sellerId: context.sellerId,
              orderId: context.orderId,
              outcome: statusCode < 400 ? 'success' : 'failure',
            });
          } else {
            logger.info('MUTATION_REQUEST', {
              requestId,
              route,
              method: request.method,
              statusCode,
              responseTime,
              userId: context.userId,
              sellerId: context.sellerId,
              orderId: context.orderId,
              outcome: statusCode < 400 ? 'success' : 'failure',
            });
          }
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

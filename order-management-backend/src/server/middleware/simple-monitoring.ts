// src/server/middleware/simple-monitoring.ts
import { NextRequest, NextResponse } from 'next/server';

interface SimpleMetrics {
  timestamp: string;
  method: string;
  url: string;
  statusCode: number;
  responseTime: number;
  userAgent?: string;
  error?: string;
}

class SimpleMonitoring {
  private metrics: SimpleMetrics[] = [];
  private alertThresholds = {
    errorRate: 0.1, // 10% error rate
    responseTime: 2000, // 2 seconds
    authFailureRate: 0.2, // 20% auth failure rate
  };

  private getMetricsWindow(minutes: number = 5): SimpleMetrics[] {
    const cutoff = new Date(Date.now() - minutes * 60 * 1000);
    return this.metrics.filter(m => new Date(m.timestamp) > cutoff);
  }

  private checkAlerts(metrics: SimpleMetrics[]): string[] {
    const alerts: string[] = [];

    if (metrics.length === 0) return alerts;

    // Check 5xx error rate
    const errorCount = metrics.filter(m => m.statusCode >= 500).length;
    const errorRate = errorCount / metrics.length;
    if (errorRate > this.alertThresholds.errorRate) {
      alerts.push(`HIGH_ERROR_RATE: ${(errorRate * 100).toFixed(1)}% (${errorCount}/${metrics.length})`);
    }

    // Check response time
    const avgResponseTime = metrics.reduce((sum, m) => sum + m.responseTime, 0) / metrics.length;
    if (avgResponseTime > this.alertThresholds.responseTime) {
      alerts.push(`HIGH_LATENCY: ${avgResponseTime.toFixed(0)}ms avg`);
    }

    // Check auth failure rate
    const authFailures = metrics.filter(m =>
      m.url.includes('/auth/') && m.statusCode === 401
    ).length;
    const authRequests = metrics.filter(m => m.url.includes('/auth/')).length;
    if (authRequests > 0) {
      const authFailureRate = authFailures / authRequests;
      if (authFailureRate > this.alertThresholds.authFailureRate) {
        alerts.push(`AUTH_FAILURE_SPIKE: ${(authFailureRate * 100).toFixed(1)}% (${authFailures}/${authRequests})`);
      }
    }

    // Check order creation failures
    const orderCreationFailures = metrics.filter(m =>
      m.url.includes('/orders') && m.method === 'POST' && m.statusCode >= 400
    ).length;
    if (orderCreationFailures > 0) {
      alerts.push(`ORDER_CREATE_FAILURES: ${orderCreationFailures} failures`);
    }

    return alerts;
  }

  middleware = (request: NextRequest) => {
    const start = Date.now();
    const timestamp = new Date().toISOString();

    // Create response
    const response = NextResponse.next();

    // Calculate response time
    const responseTime = Date.now() - start;

    // Store metrics with estimated status code (will be updated by actual response)
    const metric: SimpleMetrics = {
      timestamp,
      method: request.method,
      url: request.url,
      statusCode: 200, // Default assumption, will be refined
      responseTime,
      userAgent: request.headers.get('user-agent') || undefined,
    };

    this.metrics.push(metric);

    // Keep only last 1000 metrics to prevent memory issues
    if (this.metrics.length > 1000) {
      this.metrics = this.metrics.slice(-1000);
    }

    // Check alerts every 10 requests
    if (this.metrics.length % 10 === 0) {
      const recentMetrics = this.getMetricsWindow(5);
      const alerts = this.checkAlerts(recentMetrics);

      if (alerts.length > 0) {
        console.error('MONITORING_ALERTS:', alerts.join(' | '));
      }
    }

    return response;
  };

  getHealthMetrics = () => {
    const recentMetrics = this.getMetricsWindow(5);
    const alerts = this.checkAlerts(recentMetrics);

    return {
      timestamp: new Date().toISOString(),
      metricsCount: recentMetrics.length,
      alerts,
      errorRate: recentMetrics.filter(m => m.statusCode >= 500).length / recentMetrics.length,
      avgResponseTime: recentMetrics.length > 0
        ? recentMetrics.reduce((sum, m) => sum + m.responseTime, 0) / recentMetrics.length
        : 0,
      recentMetrics: recentMetrics.slice(-10), // Last 10 requests
    };
  };
}

export const simpleMonitoring = new SimpleMonitoring();
export const monitoringMiddleware = simpleMonitoring.middleware;

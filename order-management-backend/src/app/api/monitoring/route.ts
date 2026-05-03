import { NextRequest, NextResponse } from 'next/server';

// Simple in-memory metrics store
const requestMetrics: Array<{
  timestamp: string;
  method: string;
  url: string;
  statusCode: number;
  responseTime: number;
}> = [];

export async function GET(_request: NextRequest) {
  try {
    const recentMetrics = requestMetrics.slice(-50); // Last 50 requests
    const errorCount = recentMetrics.filter(m => m.statusCode >= 500).length;
    const errorRate = recentMetrics.length > 0 ? errorCount / recentMetrics.length : 0;
    const avgResponseTime = recentMetrics.length > 0
      ? recentMetrics.reduce((sum, m) => sum + m.responseTime, 0) / recentMetrics.length
      : 0;

    const alerts: string[] = [];

    // Check error rate alert
    if (errorRate > 0.1) {
      alerts.push(`HIGH_ERROR_RATE: ${(errorRate * 100).toFixed(1)}%`);
    }

    // Check response time alert
    if (avgResponseTime > 2000) {
      alerts.push(`HIGH_LATENCY: ${avgResponseTime.toFixed(0)}ms avg`);
    }

    // Check auth failure spike
    const authFailures = recentMetrics.filter(m =>
      m.url.includes('/auth/') && m.statusCode === 401
    ).length;
    if (authFailures > 3) {
      alerts.push(`AUTH_FAILURE_SPIKE: ${authFailures} failures`);
    }

    // Check order creation failures
    const orderCreationFailures = recentMetrics.filter(m =>
      m.url.includes('/orders') && m.method === 'POST' && m.statusCode >= 400
    ).length;
    if (orderCreationFailures > 0) {
      alerts.push(`ORDER_CREATE_FAILURES: ${orderCreationFailures} failures`);
    }

    return NextResponse.json({
      status: 'ok',
      monitoring: {
        timestamp: new Date().toISOString(),
        totalRequests: requestMetrics.length,
        recentRequests: recentMetrics.length,
        errorRate,
        avgResponseTime,
        recentLogs: recentMetrics.slice(-10), // Last 10 requests
        alerts
      },
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Monitoring endpoint error:', error);
    return NextResponse.json(
      {
        status: 'error',
        error: 'Failed to retrieve monitoring metrics',
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}

// Export function to log requests from other routes
export function logRequest(method: string, url: string, statusCode: number, responseTime: number) {
  requestMetrics.push({
    timestamp: new Date().toISOString(),
    method,
    url,
    statusCode,
    responseTime
  });

  // Keep only last 1000 metrics
  if (requestMetrics.length > 1000) {
    requestMetrics.splice(0, requestMetrics.length - 1000);
  }
}


# Monitoring and Alerting Setup

## 1. Install Dependencies
```bash
npm install @types/node
```

## 2. Add Monitoring Middleware to App
Add to `src/app/layout.tsx` or appropriate middleware setup:

```typescript
import { monitoringMiddleware } from '@/server/middleware/monitoring';

export const config = {
  matcher: [
    '/api/:path*',
  ],
};

export default monitoringMiddleware;
```

## 3. Environment Variables
Add to `.env`:

```
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
```

## 4. Monitoring Endpoints

### Health Check
- `GET /api/health` - Basic health check
- `GET /api/health/monitoring` - Enhanced health check with metrics

### Metrics (Future Implementation)
- `GET /api/metrics` - Application metrics
- `GET /api/metrics/errors` - Error rates and patterns
- `GET /api/metrics/performance` - Response time metrics

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

```bash
# Test health check
curl http://localhost:3000/api/health/monitoring

# Test error logging (should trigger alerts)
curl -X POST http://localhost:3000/api/public/demo-store/orders \
  -H "Content-Type: application/json" \
  -d '{"invalid": "payload"}'

# Test performance monitoring
time curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"wrong"}'
```

## 8. Production Deployment Checklist

Before deploying to production:

- [ ] Configure alert destinations (email, Slack, SMS)
- [ ] Test all alert thresholds
- [ ] Verify logging format and fields
- [ ] Set up log aggregation (if not already)
- [ ] Configure monitoring dashboards
- [ ] Test escalation procedures
- [ ] Document on-call rotation

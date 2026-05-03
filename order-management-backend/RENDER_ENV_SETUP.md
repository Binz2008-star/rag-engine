# Render Environment Variables Setup

## Required Environment Variables

Add these to your Render service dashboard:

### 1. DATABASE_URL (Critical)

```
Key: DATABASE_URL
Value: postgresql://neondb_owner:npg_doVwag4RtHS3@ep-steep-star-am1qfz8l-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

### 2. Optional Variables (for full functionality)

```
Key: UPSTASH_REDIS_REST_URL
Value: [your Redis URL if available]

Key: UPSTASH_REDIS_REST_TOKEN
Value: [your Redis token if available]

Key: STRIPE_WEBHOOK_SECRET
Value: [your Stripe webhook secret]

Key: WHATSAPP_WEBHOOK_SECRET
Value: [your WhatsApp webhook secret]

Key: CRON_SECRET
Value: [generate random string for cron security]

Key: CRON_RECONCILE_LIMIT
Value: 100
```

## Steps to Add in Render

1. Go to your Render Dashboard
2. Select your service
3. Go to "Environment" tab
4. Click "Add Environment Variable"
5. Add the DATABASE_URL first (critical for deployment)
6. Add optional variables as needed
7. Click "Save Changes"
8. Trigger a new deployment

## After Setup

Once DATABASE_URL is added, the deployment should succeed because:

- Build script: `prisma generate && next build` (no migrations)
- Repository: Using fix/order-contract-alignment branch
- Prisma: Singleton pattern implemented
- All TypeScript errors fixed

## Expected Result

Deployment should go from FAILED to SUCCESS after adding DATABASE_URL.

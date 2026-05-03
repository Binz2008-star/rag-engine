# Vercel Deployment Guide

## Step 1: Connect to Vercel

1. Install Vercel CLI:
```bash
npm i -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

3. Link your project:
```bash
vercel link
```

## Step 2: Configure Environment Variables

In Vercel dashboard, add these environment variables:

### Required Variables
```bash
DATABASE_URL=postgresql://username:password@host:port/database
JWT_SECRET=your-32-plus-character-secret-here
NODE_ENV=production
```

### Optional Rate Limiting
```bash
# Choose ONE of these:

# Option A: Redis (Production-grade)
REDIS_URL=redis://username:password@host:port

# Option B: Upstash (Best-effort)
UPSTASH_REDIS_REST_URL=https://your-project.upstash.io/redis
UPSTASH_REDIS_REST_TOKEN=your-upstash-token
```

## Step 3: Deploy

```bash
vercel --prod
```

## Step 4: Verify Deployment

1. Check the deployed URL
2. Test `/api/health` endpoint
3. Verify rate limiting headers
4. Test authentication flow

## Step 5: Database Migration

Vercel automatically runs:
```bash
prisma generate && prisma migrate deploy && next build
```

## Monitoring

Check Vercel logs for:
- `RATE_LIMIT_HIT` events
- `PAYMENT_STARTED/COMPLETED/FAILED` events
- Authentication failures

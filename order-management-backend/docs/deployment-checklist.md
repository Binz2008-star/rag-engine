# Production Deployment Checklist

## ✅ Pre-Deployment
- [x] Code committed to main
- [x] TypeScript passes (`npm run typecheck`)
- [x] Linting passes (`npm run lint`)
- [x] Tests pass locally (`npm run test:critical`)
- [x] Environment variables documented

## ⚠️ Build Issues
- [ ] Prisma client generation (Windows permission issue)
- [ ] Full build command (`npm run build`)

## 🚀 Production Setup
- [ ] DATABASE_URL configured (PostgreSQL)
- [ ] JWT_SECRET generated (32+ chars)
- [ ] Rate limiting configured (Redis or Upstash)
- [ ] NODE_ENV=production

## 🔍 Live System Tests
- [ ] `/api/health` - System health check
- [ ] `/api/auth/login` - Authentication flow
- [ ] Order creation endpoint
- [ ] Payment processing flow
- [ ] Rate limiting headers present
- [ ] Error handling graceful

## 📊 Monitoring Setup
- [ ] Log aggregation configured
- [ ] Rate limit fallback tracking
- [ ] Database connection monitoring
- [ ] Authentication failure alerts

## 🔄 Rollback Plan
- [ ] Previous commit tagged
- [ ] Database backups available
- [ ] Environment variables backed up
- [ ] Emergency contact procedures

## 📝 Post-Deployment
- [ ] Verify all endpoints responding
- [ ] Check rate limiting behavior
- [ ] Monitor error rates
- [ ] Validate database operations
- [ ] Test authentication flow

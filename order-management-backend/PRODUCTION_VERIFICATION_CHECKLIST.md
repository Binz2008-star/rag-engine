# 🚀 Production Deployment & Verification Checklist

## 📋 Phase 1: Environment Configuration (CRITICAL)

### ✅ Required Environment Variables
- [ ] `JWT_SECRET` - Run `npm run env:generate` to create
- [ ] `NEXTAUTH_SECRET` - Run `npm run env:generate` to create  
- [ ] `NEXTAUTH_URL` - Set to your deployed domain
- [ ] `ADMIN_SEED_TOKEN` - Run `npm run env:generate` to create
- [ ] `DATABASE_URL` - Production database connection string

### ⚙️ Optional but Recommended
- [ ] `UPSTASH_REDIS_REST_URL` - For production rate limiting
- [ ] `UPSTASH_REDIS_REST_TOKEN` - For production rate limiting
- [ ] `STRIPE_WEBHOOK_SECRET` - If using Stripe payments
- [ ] `WHATSAPP_WEBHOOK_SECRET` - If using WhatsApp integration
- [ ] `CRON_SECRET` - Required for protected cron reconciliation endpoint
- [ ] `CRON_RECONCILE_LIMIT` - Controls max events scanned per cron run

## 📋 Phase 2: Deployment Steps

### 1. Generate Environment Variables
```bash
npm run env:generate
```
Copy the generated values to your Vercel environment variables.

### 2. Deploy Application
```bash
# Deploy to Vercel (through dashboard or CLI)
vercel --prod
```

### 3. Run Production Verification
```bash
# Set your production URL
export PROD_URL="https://your-domain.vercel.app"

# Run verification script
npm run verify:prod
```

## 📋 Phase 3: Manual Verification Tests

### 🔐 Authentication Tests
- [ ] Login with admin@company.com / admin123!@#
- [ ] Verify JWT token is returned
- [ ] Test token validation with `/api/auth/me`
- [ ] Test invalid token rejection

### 🌱 Database Tests  
- [ ] Test seeding endpoint with ADMIN_SEED_TOKEN
- [ ] Verify demo seller account creation
- [ ] Verify sample products creation
- [ ] Verify sample order creation

### 📦 Order Flow Tests
- [ ] Create order with authenticated seller
- [ ] Verify order status transitions
- [ ] Test order event creation
- [ ] Verify stock updates
- [ ] Trigger `/api/cron/reconcile-payments` with `Authorization: Bearer $CRON_SECRET` and verify `status: ok`

### ⚡ Rate Limiting Tests
- [ ] Test auth endpoint rate limiting (5 req/min)
- [ ] Test API endpoint rate limiting (10 req/min)
- [ ] Verify Redis fallback policies
- [ ] Test rate limit headers

## 📋 Phase 4: Production Readiness Assessment

### ✅ Critical Systems Check
- [ ] Authentication system fully functional
- [ ] Database connectivity stable
- [ ] Seeding endpoint working
- [ ] Rate limiting active
- [ ] Order creation flow working
- [ ] Error handling proper

### 🚨 Failure Criteria
**DO NOT PROCEED with frontend development if ANY of these fail:**
- Authentication endpoints return 500 errors
- Database connection failures
- Missing environment variables
- Rate limiting completely failing
- Order creation not working

## 📋 Phase 5: Ongoing Monitoring

### 📊 Production Health Checks
- [ ] Set up uptime monitoring
- [ ] Configure error alerting
- [ ] Monitor database performance
- [ ] Track rate limiting effectiveness

### 🔒 Security Verification
- [ ] Verify HTTPS enforcement
- [ ] Check CORS configuration
- [ ] Validate input sanitization
- [ ] Test authentication bypass attempts

---

## 🎯 Success Criteria

### ✅ Production Ready When:
1. **All critical tests PASS** in verification script
2. **Manual authentication** works with demo accounts
3. **Database seeding** creates sample data successfully
4. **Rate limiting** is active and functional
5. **Order flow** completes without errors
6. **Error responses** are proper (not 500 for expected failures)

### 🚫 Stop Conditions:
1. **ANY authentication failure** (500, missing JWT_SECRET)
2. **Database connection issues** (connection timeouts, 500 errors)
3. **Seeding failures** (missing ADMIN_SEED_TOKEN, permission errors)
4. **Rate limiting broken** (no limits, constant failures)
5. **Order creation failures** (missing services, database errors)

---

## 🔄 Continuous Verification

### Automated Checks (Recommended)
```bash
# Add to CI/CD pipeline
npm run verify:prod

# Schedule regular health checks
0 */6 * * * npm run verify:prod
```

### Manual Health Checks
- Run verification script after any deployment
- Test authentication after environment changes
- Verify rate limiting after Redis configuration changes
- Check order flow after database schema updates

---

## 📞 Emergency Procedures

### If Authentication Fails:
1. Check JWT_SECRET in Vercel dashboard
2. Verify NEXTAUTH_URL matches deployed domain
3. Redeploy application
4. Run verification script again

### If Database Fails:
1. Verify DATABASE_URL connectivity
2. Check database schema migrations
3. Run manual database connectivity test
4. Contact database provider if needed

### If Rate Limiting Fails:
1. Verify Redis configuration (UPSTASH_REDIS_REST_URL/TOKEN)
2. Check Redis service availability
3. Test fallback to memory rate limiting
4. Monitor rate limiting logs

---

**⚠️ CRITICAL REMINDER**: Green CI does NOT equal production safety. Always run this verification checklist before proceeding with any frontend development.

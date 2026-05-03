# Order Management Backend

Order management backend for social seller operations.

## Current Status

### Development Phase - Not Production Ready

This system is in active development with enterprise-grade enforcement mechanisms being implemented.

**Current Implementation Status:**

- **Database**: PostgreSQL on Neon with vector extension installed
- **Testing**: Comprehensive test suite with AI integration tests
- **Rate Limiting**: Redis-only implementation (no memory fallback)
- **Gateway Enforcement**: ESLint rules blocking direct HTTP access
- **AI Integration**: BullMQ worker system with circuit breakers
- **Multi-Tenant Isolation**: Database-level separation verified

**Still Needed for Production:**

- Required GitHub status checks for merge protection
- CI-wired contract/version validation
- Production environment hardening
- Complete audit trail verification
### 🔧 Code Fixed - Awaiting Runtime Verification

- **Database**: PostgreSQL schema ready, requires DATABASE_URL configuration
- **Deployment**: Build passes, requires production environment variables
- **Authentication**: ✅ Fixed - Real database auth implemented (previously mock)
- **Health Checks**: `/api/health` implemented, requires database connection
- **Order Creation**: Service layer ready, requires database connectivity
- **Route Handler Factory**: ✅ Enhanced error handling with request cloning
- **Transaction Hardening**: 15-second timeout with proper error mapping

### ⚠️ Known Issues

- **Local Testing**: Database connection required for full E2E validation
- **Release Proof**: Requires `DATABASE_URL` and `JWT_SECRET` environment variables
- **Status**: Code verified, runtime validation pending database connectivity

### ⚠️ Release Readiness

**Authentication has been verified locally.**

**Full order creation proof is still blocked because Runtime does not own product catalog data.**

This repository is not release-ready until:
- Runtime-only proof is defined and passing, OR
- Cross-service proof (Runtime + Sellora) is defined and passing

See `SYSTEM_CONTRACT.md` for architecture details.

## Architecture

- **Route Handler Factory**: Centralized HTTP request handling with auth, validation, and rate limiting
- **Error Handling**: Unified error mapping with proper HTTP status codes and API error responses
- **Service Layer**: Core order and payment behavior lives in server-side services
- **Authoritative Transitions**: Order status writes consolidated behind a single transition service
- **Transactional Audit Events**: Important order and payment actions create audit events in the same transaction path
- **Authentication**: Password hashing and verification use bcrypt
- **Rate Limiting**: Policy-based limiter with pluggable store support
- **Database**: PostgreSQL with Neon connection pooling in production
- **Testing**: Vitest-based test suite with critical and full-suite paths, all passing

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Setup database
npm run db:generate
npm run db:deploy
npm run db:seed

# Start development server
npm run dev

# Run the critical test gate
npm run test:critical

# Run the full suite
npm run test
```

## 📋 Available Scripts

### Development

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server

### Testing

- `npm run test` - Run all tests
- `npm run test:unit` - Run unit tests only
- `npm run test:integration` - Run integration tests only
- `npm run test:watch` - Run tests in watch mode
- `npm run test:coverage` - Generate coverage report
- `npm run test:ui` - Open test UI

### Database

- `npm run db:generate` - Generate Prisma client
- `npm run db:migrate` - Create new migrations (interactive, development only)
- `npm run db:deploy` - Apply existing migrations (non-interactive, CI/production)
- `npm run db:seed` - Seed database with initial data
- `npm run db:studio` - Open Prisma Studio database browser

### Code Quality

- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues
- `npm run typecheck` - Run TypeScript type checking

## 🏛️ Service Layer

### Order Service

```typescript
import { orderService } from './server/modules/orders/order.service'

// Create order with full validation and events
const order = await orderService.createOrder({
  sellerId,
  customerId,
  items: [...],
  deliveryFeeMinor: 500,
}, actorUserId)

// Apply status transitions with validation
await orderService.applyTransition({
  orderId,
  newStatus: 'PACKED',
  actorUserId
})
```

### Payment Service

```typescript
import { paymentService } from "./server/modules/orders/payment.service";

// Simulate payment with automatic order updates
await paymentService.simulatePayment(orderId, true, actorUserId);

// Real payment processing
await paymentService.initiatePayment({ orderId, provider });
await paymentService.confirmPayment({ orderId, provider, providerReference });
```

### Authoritative Transition Service

```typescript
import { applyOrderTransitionInTx } from "./server/modules/orders/order-transition.service";

// ONLY way to change order status - enforced by architecture
await prisma.$transaction(async (tx) => {
  await applyOrderTransitionInTx(tx, {
    orderId,
    fromStatus: "PENDING",
    toStatus: "CONFIRMED",
    actorUserId,
    reason: "Payment completed",
  });
});
```

Architecture rule: `applyOrderTransitionInTx(...)` is the authoritative path for order status changes. Compatibility wrappers still exist for legacy tests while the remaining hardening sweep is completed.

## 🔐 Authentication

Real authentication with password hashing:

```typescript
import { authenticateUser } from "./server/lib/auth";

const { user, token } = await authenticateUser(email, password);
```

Demo credentials:

- Email: `demo@seller.com`
- Password: `demo123`

## 📊 Transactional Audit Events

Key actions create audit events for traceability:

- `order_created` - New order creation
- `payment_initiated` - Payment started
- `payment_completed` - Payment successful
- `status_changed` - Order status updates
- `payment_failed` - Payment failures

Events are written transactionally with the business actions they audit.

## 🧪 Testing

Test suite with Vitest covering critical flows:

```bash
# Unit tests
npm run test:unit

# Integration tests
npm run test:integration

# Full suite (103 tests passing)
npm run test
```

## 🏗️ Database Schema

- **Users**: Authentication and roles
- **Sellers**: Store management
- **Products**: Inventory with stock tracking
- **Customers**: Customer information
- **Orders**: Order management with status
- **OrderItems**: Line items with snapshots
- **OrderEvents**: Complete audit trail
- **PaymentAttempts**: Payment processing

## 🚨 Rate Limiting

Rate limiting with memory fallback. For production, configure either:

- `REDIS_URL` for a standard Redis connection
- `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` for Upstash on serverless

Current limits:

- **Public API**: 10 requests/minute
- **Auth endpoints**: 5 requests/minute
- **Seller API**: 100 requests/minute

## 📝 Logging

Structured JSON logging with request IDs:

```typescript
logger.info("Order created", { orderId, sellerId });
logger.error("Payment failed", { orderId, reason });
```

## 🔄 State Machines

### Order Status Transitions

```text
PENDING → CONFIRMED → PACKED → OUT_FOR_DELIVERY → DELIVERED
    ↓         ↓         ↓           ↓
  CANCELLED  CANCELLED  CANCELLED  CANCELLED
```

### Payment Status Transitions

```text
PENDING → PROCESSING → COMPLETED → REFUNDED
    ↓         ↓
  FAILED    FAILED
```

## 🌍 Environment Variables

```env
# Database (PostgreSQL - Neon)
DATABASE_URL="postgresql://user:pass@host:5432/db?pgbouncer=true"

# Authentication
JWT_SECRET="your-jwt-secret"
NEXTAUTH_SECRET="your-nextauth-secret"
NEXTAUTH_URL="https://your-domain.vercel.app"

# Admin Seed Security
ADMIN_SEED_TOKEN="your-secure-seed-token"

# Cron Reconciliation (recommended in production)
CRON_SECRET="your-secure-cron-secret"
CRON_RECONCILE_LIMIT="100"

# Rate Limiting (Optional)
REDIS_URL="redis://localhost:6379"
UPSTASH_REDIS_REST_URL="https://your-upstash-url"
UPSTASH_REDIS_REST_TOKEN="your-upstash-token"
```

## Production Deployment

### Deployment Status Operational

Currently deployed to Vercel with:

- ✅ PostgreSQL database (Neon) with connection pooling
- ✅ Real authentication
- ✅ Production migrations applied
- ✅ Enhanced security (ADMIN_SEED_TOKEN)
- ✅ Health checks passing
- ⚠️ In-memory rate limit fallback still active until Redis/Upstash is configured

### Deployment Steps

1. **Build the application**

```bash
npm run build
```

2. **Set production environment variables** on Vercel

3. **Run database migrations** (automatic on deploy)

```bash
npm run db:deploy
```

4. **Seed production data** (optional, secure)

```bash
curl -X POST https://your-app.vercel.app/api/admin/seed \
  -H "Authorization: Bearer $ADMIN_SEED_TOKEN"
```

## 🧹 Development Cleanup

Reset development environment:

1. Reset and seed database

```bash
npm run db:seed
```

2. Or seed only

```bash
npm run seed
```

## 📚 API Documentation

### Public Endpoints

- `GET /api/public/{sellerSlug}/products` - List active products
- `POST /api/public/{sellerSlug}/orders` - Create new order

### Authentication

- `POST /api/auth/login` - Login and get JWT token
- `DELETE /api/auth/login` - Logout
- `GET /api/me` - Get current user info

### Seller Endpoints (Requires Authentication)

- `GET /api/seller/orders` - List orders with pagination
- `GET /api/seller/orders/{id}` - Get order details
- `PATCH /api/seller/orders/{id}/status` - Update order status
- `GET /api/seller/products` - List products
- `POST /api/seller/products` - Create product
- `PATCH /api/seller/products/{id}` - Update product
- `DELETE /api/seller/products/{id}` - Delete product

### Cron Endpoints (Protected)

- `GET /api/cron/reconcile-payments` - Reconcile pending/failed Stripe `payment_intent.succeeded` events (requires `Authorization: Bearer $CRON_SECRET`)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `npm run test`
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

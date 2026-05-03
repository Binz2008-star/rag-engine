# Payment Service Test Flow

## 🎯 PRODUCTION-GRADE VALIDATION

This test flow validates the complete payment service with proper audit trails, actor tracking, and event consistency.

---

## 📋 PREREQUISITES

1. **Start the dev server:**
```bash
npm run dev
```

2. **Open Prisma Studio:**
```bash
npx prisma studio
```

3. **Verify tables are clean:**
- `orders` - should have test orders
- `payment_attempts` - should be empty
- `order_events` - should have existing events

---

## 🧪 TEST SCENARIOS

### SCENARIO 1: SUCCESSFUL PAYMENT FLOW

**Objective:** Validate complete payment success path with proper events

#### Step 1: Create Payment Attempt
```bash
curl -X POST http://localhost:3000/api/seller/orders/{ORDER_ID}/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "provider": "stripe",
    "amountMinor": 2500,
    "currency": "USD",
    "metadata": {
      "test": "scenario_1",
      "source": "api_test"
    }
  }'
```

**Expected Response:**
```json
{
  "paymentAttempt": {
    "id": "payment_attempt_id",
    "status": "PENDING",
    "provider": "stripe",
    "amountMinor": 2500,
    "currency": "USD"
  },
  "message": "Payment attempt created successfully"
}
```

#### Step 2: Update Payment Status to COMPLETED
```bash
curl -X PUT http://localhost:3000/api/seller/payments/{PAYMENT_ATTEMPT_ID}/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "status": "COMPLETED",
    "providerReference": "pi_1234567890",
    "metadata": {
      "test": "scenario_1",
      "completed_at": "2026-04-01T23:00:00Z"
    }
  }'
```

**Expected Response:**
```json
{
  "paymentAttempt": {
    "id": "payment_attempt_id",
    "status": "COMPLETED",
    "providerReference": "pi_1234567890"
  },
  "message": "Payment status updated successfully"
}
```

#### Step 3: Verify Database State
**In Prisma Studio, verify:**

1. **PaymentAttempts Table:**
   - Status = "COMPLETED"
   - providerReference = "pi_1234567890"
   - metadataJson contains test data

2. **Orders Table:**
   - paymentStatus = "PAID"
   - status = "CONFIRMED" (auto-updated from PENDING)

3. **OrderEvents Table:**
   - **Event 1:** `PAYMENT_INITIATED` with actor = seller_id
   - **Event 2:** `PAYMENT_CONFIRMED` with actor = seller_id
   - **Event 3:** `STATUS_CHANGED` from "PENDING" to "CONFIRMED" with actor = "SYSTEM"

---

### SCENARIO 2: PAYMENT FAILURE FLOW

**Objective:** Validate payment failure handling and proper events

#### Step 1: Create Payment Attempt
```bash
curl -X POST http://localhost:3000/api/seller/orders/{ORDER_ID}/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "provider": "stripe",
    "amountMinor": 1500,
    "currency": "USD",
    "metadata": {
      "test": "scenario_2",
      "source": "failure_test"
    }
  }'
```

#### Step 2: Update Payment Status to FAILED
```bash
curl -X PUT http://localhost:3000/api/seller/payments/{PAYMENT_ATTEMPT_ID}/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "status": "FAILED",
    "failureReason": "insufficient_funds",
    "metadata": {
      "test": "scenario_2",
      "error_code": "card_declined"
    }
  }'
```

#### Step 3: Verify Database State
**In Prisma Studio, verify:**

1. **PaymentAttempts Table:**
   - Status = "FAILED"
   - failureReason = "insufficient_funds"

2. **Orders Table:**
   - paymentStatus = "FAILED"
   - status should remain unchanged

3. **OrderEvents Table:**
   - **Event 1:** `PAYMENT_INITIATED` with actor = seller_id
   - **Event 2:** `PAYMENT_FAILED` with actor = seller_id

---

### SCENARIO 3: PAYMENT REFUND FLOW

**Objective:** Validate refund processing and proper events

#### Step 1: Create Payment Attempt (if not exists)
```bash
curl -X POST http://localhost:3000/api/seller/orders/{ORDER_ID}/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "provider": "stripe",
    "amountMinor": 3000,
    "currency": "USD",
    "metadata": {
      "test": "scenario_3",
      "source": "refund_test"
    }
  }'
```

#### Step 2: Complete Payment First
```bash
curl -X PUT http://localhost:3000/api/seller/payments/{PAYMENT_ATTEMPT_ID}/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "status": "COMPLETED",
    "providerReference": "pi_refund_test"
  }'
```

#### Step 3: Process Refund
```bash
curl -X POST http://localhost:3000/api/seller/payments/{PAYMENT_ATTEMPT_ID}/refund \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "refundAmountMinor": 1500,
    "reason": "customer_request",
    "metadata": {
      "test": "scenario_3",
      "refund_id": "re_1234567890"
    }
  }'
```

#### Step 4: Verify Database State
**In Prisma Studio, verify:**

1. **PaymentAttempts Table:**
   - Status = "REFUNDED"
   - metadataJson contains refund data

2. **Orders Table:**
   - paymentStatus = "REFUNDED"

3. **OrderEvents Table:**
   - **Event 1:** `PAYMENT_INITIATED`
   - **Event 2:** `PAYMENT_CONFIRMED`
   - **Event 3:** `PAYMENT_REFUNDED` with actor = seller_id

---

### SCENARIO 4: CONCURRENT PAYMENT ATTEMPTS

**Objective:** Validate payment attempt deduplication and locking

#### Step 1: Create Two Payment Attempts Simultaneously
```bash
# Terminal 1
curl -X POST http://localhost:3000/api/seller/orders/{ORDER_ID}/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "provider": "stripe",
    "amountMinor": 2000,
    "currency": "USD"
  }' &

# Terminal 2 (run immediately after)
curl -X POST http://localhost:3000/api/seller/orders/{ORDER_ID}/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "provider": "stripe",
    "amountMinor": 2000,
    "currency": "USD"
  }' &
```

#### Step 2: Verify Results
**Expected:**
- One payment attempt succeeds
- One payment attempt fails with "Payment attempt already in progress"

**In Prisma Studio:**
- Only one PENDING payment attempt should exist

---

### SCENARIO 5: INVALID STATUS TRANSITIONS

**Objective:** Validate payment state machine enforcement

#### Step 1: Try Invalid Transition
```bash
# Create payment attempt first
curl -X POST http://localhost:3000/api/seller/orders/{ORDER_ID}/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "provider": "stripe",
    "amountMinor": 1000,
    "currency": "USD"
  }'

# Try to jump from PENDING to REFUNDED (invalid)
curl -X PUT http://localhost:3000/api/seller/payments/{PAYMENT_ATTEMPT_ID}/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {SELLER_TOKEN}" \
  -d '{
    "status": "REFUNDED"
  }'
```

**Expected Response:**
```json
{
  "error": "Invalid payment status transition from PENDING to REFUNDED"
}
```

---

## 🔍 AUDIT VALIDATION CHECKLIST

### For Each Scenario, Verify:

#### ✅ Actor Tracking
- All events have `actorUserId` populated (never null)
- System actions use "SYSTEM"
- User actions use actual user ID

#### ✅ Event Types
- Event types are consistent and uppercase
- Proper event sequencing
- No missing events

#### ✅ Payload Quality
- All payloads contain `actor` field
- All payloads contain `timestamp` field
- Payment events contain `provider`, `amountMinor`, `currency`
- Status changes contain `from`, `to`, `reason`

#### ✅ Database Consistency
- Order status matches payment status
- Payment attempts have correct state transitions
- No orphaned records

#### ✅ Transaction Safety
- All related changes happen atomically
- No partial state updates
- Rollback on errors

---

## 🚨 CRITICAL VALIDATION POINTS

### 1. Actor Accountability
```sql
-- Run in Prisma Studio SQL tab
SELECT eventType, actorUserId, COUNT(*) as count
FROM order_events 
GROUP BY eventType, actorUserId;
```

**Expected:** No NULL actorUserId values

### 2. Event Sequencing
```sql
SELECT eventType, createdAt, actorUserId, payloadJson
FROM order_events 
WHERE orderId = '{TEST_ORDER_ID}'
ORDER BY createdAt;
```

**Expected:** Logical event flow with proper timestamps

### 3. Payment State Consistency
```sql
SELECT 
  o.id as orderId,
  o.status as orderStatus,
  o.paymentStatus as orderPaymentStatus,
  pa.status as paymentStatus,
  pa.providerReference
FROM orders o
LEFT JOIN payment_attempts pa ON o.id = pa.orderId
WHERE o.id = '{TEST_ORDER_ID}';
```

**Expected:** Consistent payment status across tables

---

## 📊 PRODUCTION READINESS SCORE

After completing all scenarios, score each area:

| Area | Score (1-5) | Notes |
|------|-------------|-------|
| Actor Tracking | | |
| Event Consistency | | |
| State Management | | |
| Error Handling | | |
| Transaction Safety | | |
| Audit Completeness | | |

**Total Score:** `/25`

**Passing Score:** `20+`

---

## 🎯 NEXT STEPS

If any scenario fails:
1. **Document the failure**
2. **Fix the underlying issue**
3. **Rerun the scenario**
4. **Validate the fix**

Once all scenarios pass:
1. **Run integration tests**
2. **Load test payment endpoints**
3. **Validate in staging environment**
4. **Deploy to production**

---

## 📝 TEST RESULTS LOG

Document your results here:

```
SCENARIO 1: SUCCESSFUL PAYMENT
- [ ] Payment attempt created
- [ ] Payment completed successfully
- [ ] Order status updated to CONFIRMED
- [ ] All events created with proper actor
- [ ] Payload contains required fields

SCENARIO 2: PAYMENT FAILURE
- [ ] Payment attempt created
- [ ] Payment failed correctly
- [ ] Order payment status updated to FAILED
- [ ] Failure reason recorded
- [ ] Events created for failure

SCENARIO 3: PAYMENT REFUND
- [ ] Payment completed first
- [ ] Refund processed successfully
- [ ] Order payment status updated to REFUNDED
- [ ] Refund metadata recorded
- [ ] Events created for refund

SCENARIO 4: CONCURRENT ATTEMPTS
- [ ] First attempt succeeded
- [ ] Second attempt rejected
- [ ] No duplicate payment attempts

SCENARIO 5: INVALID TRANSITIONS
- [ ] Invalid transition rejected
- [ ] Proper error message
- [ ] No state corruption
```

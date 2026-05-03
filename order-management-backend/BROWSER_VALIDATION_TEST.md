# Browser Validation Test Plan

## Test Environment
- **Browser Preview**: http://127.0.0.1:64186
- **Seller Dashboard**: http://localhost:3002
- **Order Management Backend**: http://localhost:3000

## Test Flow

### Step 1: Login Page Validation
1. Navigate to `/login`
2. Verify login form renders correctly
3. Test credentials: `test@example.com` / `password123`
4. Click "Sign in" button
5. Verify successful login and redirect to `/orders`

### Step 2: Orders List Page Validation
1. Verify orders list loads with authentication
2. Check that order data renders correctly:
   - `publicOrderNumber`
   - `status`
   - `totalMinor` formatted as currency
   - `customer.name`
   - `items.length`
3. Verify pagination controls work
4. Check for console errors

### Step 3: Order Details Page Validation
1. Click on an order to navigate to `/orders/{id}`
2. Verify order details render correctly:
   - Order number and status
   - Customer information
   - Order items with pricing
   - Total amount calculation
3. Check for console errors
4. Verify navigation back to orders list

### Step 4: Authentication Validation
1. Test direct access to `/orders` without login
2. Verify redirect to login or error
3. Test direct access to `/orders/{id}` without login
4. Verify proper error handling

### Step 5: Network Request Validation
1. Open DevTools Network tab
2. Verify login request: `POST /api/auth/login`
3. Verify orders list request: `GET /api/v1/orders`
4. Verify order details request: `GET /api/v1/orders/{id}`
5. Check that all requests include `Authorization: Bearer <token>` header

## Expected Results

### Successful Flow
- Login page renders and accepts credentials
- Successful login stores token and redirects
- Orders list displays real data from backend
- Order details display complete order information
- All network requests include proper authentication
- No console errors

### Error Handling
- Missing/invalid token shows appropriate error
- Network errors are handled gracefully
- User feedback is clear and actionable

## Evidence to Capture

1. **Screenshots**:
   - Login page
   - Orders list page
   - Order details page

2. **Network Logs**:
   - Login request/response
   - Orders list request/response
   - Order details request/response

3. **Console Logs**:
   - Verify zero errors
   - Check for any warnings

## Validation Checklist

- [ ] Login page renders correctly
- [ ] Login with test credentials succeeds
- [ ] Token is stored in localStorage
- [ ] Orders list loads with authentication
- [ ] Order data renders correctly
- [ ] Order details page loads and renders
- [ ] Navigation between pages works
- [ ] No console errors
- [ ] Network requests include auth headers
- [ ] Error handling works correctly

## Current Status

### Completed
- [x] Backend auth error handling (401/403 instead of 500)
- [x] Runtime client fixes (duplicate auth key removed)
- [x] OrderDetailsPage fixes (import, response shape, error handling)
- [x] Login page created
- [x] Order details page created

### In Progress
- [ ] Browser flow validation
- [ ] Screenshot capture
- [ ] Network log capture
- [ ] Console error verification

### Next Steps
1. Navigate to http://127.0.0.1:64186/login
2. Execute the test flow
3. Capture evidence
4. Document results

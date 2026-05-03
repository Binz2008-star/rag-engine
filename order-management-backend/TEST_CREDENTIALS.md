# Test Credentials & Setup Guide

## Test Environment Access

### URL
- **Test Environment**: `http://localhost:3000` (development)
- **API Base**: `http://localhost:3000/api`

## Test User Accounts

### Seller Accounts

#### Tech Gadgets Plus (Electronics)
- **Email**: `seller1@test.com`
- **Password**: `TestSeller123!`
- **Slug**: `tech-gadgets-plus`
- **Products**: 5 electronics items
- **Sample Orders**: 8

#### Fashion Forward (Clothing)
- **Email**: `seller2@test.com`
- **Password**: `TestSeller123!`
- **Slug**: `fashion-forward`
- **Products**: 5 clothing items
- **Sample Orders**: 9

#### Home & Living (Home Goods)
- **Email**: `seller3@test.com`
- **Password**: `TestSeller123!`
- **Slug**: `home-living`
- **Products**: 5 home items
- **Sample Orders**: 5

### Admin Account
- **Email**: `admin@test.com`
- **Password**: `TestAdmin123!`
- **Role**: System Administrator

## Test Data Summary

### Products by Category
- **Electronics**: 5 products ($19.99 - $79.99)
- **Clothing**: 5 products ($19.99 - $79.99)
- **Home & Living**: 5 products ($29.99 - $99.99)

### Sample Orders
- **Total Orders**: 22 across all sellers
- **Order Statuses**: PENDING, CONFIRMED, PACKED, OUT_FOR_DELIVERY, DELIVERED
- **Payment Types**: CASH, CASH_ON_DELIVERY
- **Payment Statuses**: PENDING, PAID, FAILED

### Customers
- **Total Customers**: 15 (5 per seller)
- **Unique Phone Numbers**: Per seller to avoid conflicts
- **Addresses**: Various US cities

## API Testing Endpoints

### Public Endpoints (No Authentication)
- `GET /api/health` - Health check
- `GET /api/public/{sellerSlug}/orders` - List seller orders
- `POST /api/public/{sellerSlug}/orders` - Create order

### Seller Endpoints (Authentication Required)
- `GET /api/seller/orders` - List seller orders
- `GET /api/seller/products` - List seller products
- `POST /api/seller/products` - Create product
- `PATCH /api/seller/orders/{id}/status` - Update order status

### Authentication Headers
```json
{
  "Authorization": "Bearer {JWT_TOKEN}",
  "Content-Type": "application/json"
}
```

## Quick Test Commands

### Health Check
```bash
curl http://localhost:3000/api/health
```

### Create Order (Public API)
```bash
curl -X POST http://localhost:3000/api/public/tech-gadgets-plus/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customerName": "Test Customer",
    "customerPhone": "+15551234567",
    "addressText": "123 Test Street",
    "items": [{"productId": "{PRODUCT_ID}", "quantity": 1}],
    "notes": "Test order"
  }'
```

### Seller Login (Get JWT Token)
```bash
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "seller1@test.com",
    "password": "TestSeller123!"
  }'
```

### List Seller Orders
```bash
curl -X GET http://localhost:3000/api/seller/orders \
  -H "Authorization: "Bearer {JWT_TOKEN}"
```

## Test Scenario Setup

### Before Each Test Session
1. Ensure development server is running: `npm run dev`
2. Verify database connection: Check health endpoint
3. Confirm test data exists: Run setup script if needed

### During Testing
1. Use provided credentials for each user type
2. Follow test scenarios in USER_TEST_SCENARIOS.md
3. Document any issues or unexpected behavior
4. Record completion times for key tasks

### After Each Test Session
1. Complete feedback questionnaire
2. Report any bugs or issues found
3. Note suggestions for improvements
4. Reset test data if needed (run setup script)

## Product IDs for Testing

### Tech Gadgets Plus
- Wireless Phone Charger
- Bluetooth Earbuds Pro
- Phone Case Premium
- USB-C Cable Set
- Portable Power Bank

### Fashion Forward
- Classic Cotton T-Shirt
- Denim Jacket
- Athletic Leggings
- Casual Hoodie
- Wool Beanie Hat

### Home & Living
- Ceramic Plant Pot Set
- Kitchen Knife Set
- Throw Pillows Set
- Wall Art Canvas
- Bamboo Cutting Board

## Common Test Issues & Solutions

### Authentication Failures
- **Issue**: Invalid token or expired credentials
- **Solution**: Re-login to get fresh JWT token

### Product Not Found
- **Issue**: Using wrong product ID or seller slug
- **Solution**: Verify product exists under correct seller

### Order Creation Failures
- **Issue**: Insufficient stock or invalid customer data
- **Solution**: Check stock levels and customer information format

### Database Connection Issues
- **Issue**: Database not responding
- **Solution**: Restart development server and check DATABASE_URL

## Test Data Reset

### Complete Reset
```bash
npx tsx scripts/setup-test-environment.ts
```

### Partial Reset (Orders Only)
```bash
# Delete test orders (run via database client or script)
DELETE FROM "Order" WHERE source = 'TEST_DATA';
```

## Feedback Collection

### Test Session Notes Template
```
Session Date: [DATE]
Tester Name: [NAME]
Test Scenarios Completed: [LIST]
Issues Found: [DESCRIPTION]
Completion Times: [TIMINGS]
Overall Rating: [1-5]
Suggestions: [FEEDBACK]
```

### Bug Report Template
```
Bug ID: [AUTO-GENERATED]
Severity: [LOW/MEDIUM/HIGH/CRITICAL]
Description: [WHAT HAPPENED]
Steps to Reproduce: [STEPS]
Expected Behavior: [SHOULD HAPPEN]
Actual Behavior: [ACTUAL RESULT]
Environment: [BROWSER/DEVICE]
```

## Contact Information

### Technical Support
- **Issues**: Report via GitHub issues or internal ticketing system
- **Urgent Issues**: Contact development team directly

### Test Coordination
- **Scheduling**: Coordinate with test organizer
- **Credentials**: Request from test administrator
- **Environment**: Status updates from DevOps team

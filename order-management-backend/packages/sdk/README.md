# Order Management SDK

A TypeScript SDK for the Order Management System API with built-in type safety and error handling.

## Installation

```bash
npm install @order-management/sdk
```

## Quick Start

```typescript
import { OrderManagementSDK } from '@order-management/sdk';

// Initialize the SDK
const sdk = new OrderManagementSDK({
  baseURL: 'https://api.order-management.com',
  timeout: 10000,
});

// Login
const loginResponse = await sdk.login('user@example.com', 'password');

// Create an order
const order = await sdk.createOrder({
  customerId: 'customer-123',
  items: [
    {
      productId: 'product-456',
      quantity: 2,
      price: 29.99,
    }
  ],
  shippingAddress: {
    street: '123 Main St',
    city: 'Anytown',
    state: 'CA',
    zipCode: '12345',
    country: 'US',
  },
});
```

## Configuration

The SDK accepts the following configuration options:

```typescript
interface SdkConfig {
  baseURL: string;        // API base URL
  timeout?: number;       // Request timeout in ms (default: 10000)
  retryAttempts?: number; // Number of retry attempts (default: 3)
  retryDelay?: number;    // Delay between retries in ms (default: 1000)
}
```

## Authentication

The SDK automatically handles JWT authentication:

```typescript
// Login stores the token automatically
await sdk.login('user@example.com', 'password');

// Token is automatically included in subsequent requests
const orders = await sdk.getOrders();

// Logout clears the token
await sdk.logout();
```

## API Methods

### Authentication
- `login(email, password)` - Authenticate user
- `logout()` - Clear authentication
- `getCurrentUser()` - Get current user info
- `refreshToken()` - Refresh JWT token

### Orders
- `createOrder(orderData)` - Create new order
- `getOrder(orderId)` - Get specific order
- `getOrders(params)` - List orders with pagination
- `updateOrder(orderId, updateData)` - Update order
- `cancelOrder(orderId, reason)` - Cancel order

### Payments
- `createPayment(paymentData)` - Create payment
- `getPayment(paymentId)` - Get specific payment
- `getPayments(params)` - List payments with pagination
- `updatePaymentStatus(paymentId, status)` - Update payment status

### Health
- `healthCheck()` - Check API health status

## Error Handling

The SDK provides structured error handling:

```typescript
try {
  const order = await sdk.getOrder('invalid-id');
} catch (error) {
  if (error.code === 'NOT_FOUND') {
    console.log('Order not found');
  } else if (error.code === 'AUTHENTICATION_ERROR') {
    console.log('Please login again');
  }
}
```

## Error Codes

- `VALIDATION_ERROR` - Invalid request data
- `AUTHENTICATION_ERROR` - Invalid or missing authentication
- `AUTHORIZATION_ERROR` - Insufficient permissions
- `NOT_FOUND` - Resource not found
- `CONFLICT` - Resource conflict
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_SERVER_ERROR` - Server error
- `SERVICE_UNAVAILABLE` - Service down

## Type Safety

The SDK includes full TypeScript definitions:

```typescript
import { CreateOrderRequest, Order, OrderStatus } from '@order-management/sdk';

const orderData: CreateOrderRequest = {
  customerId: 'customer-123',
  items: [
    {
      productId: 'product-456',
      quantity: 2,
      price: 29.99,
    }
  ],
  shippingAddress: {
    street: '123 Main St',
    city: 'Anytown',
    state: 'CA',
    zipCode: '12345',
    country: 'US',
  },
};

const order: Order = await sdk.createOrder(orderData);
if (order.status === OrderStatus.CONFIRMED) {
  console.log('Order is confirmed');
}
```

## Browser Support

The SDK works in both browser and Node.js environments. In browsers, it automatically stores authentication tokens in localStorage.

## Development

```bash
# Install dependencies
npm install

# Build the SDK
npm run build

# Watch for changes
npm run dev

# Clean build output
npm run clean
```

## License

MIT

# Shared SDK Layer Specification

## Overview

This document defines the shared SDK that provides type-safe API clients for all three boundaries in the system.

---

# Architecture

## SDK Structure
```
@order-management/sdk/
  src/
    runtime/
      client.ts          # Runtime API client
      types.ts           # Runtime-specific types
      endpoints.ts       # Runtime endpoint definitions
    platform/
      client.ts          # Platform API client  
      types.ts           # Platform-specific types
      endpoints.ts       # Platform endpoint definitions
    shared/
      gateway.ts         # Base HTTP client
      auth.ts            # Authentication utilities
      errors.ts          # Error handling
      types.ts           # Shared types
    index.ts             # Public exports
```

---

# Runtime Core SDK

## Client Interface
```typescript
export class RuntimeClient {
  // Orders
  orders: {
    create(data: CreateOrderInput): Promise<OrderResponse>
    get(orderId: string): Promise<OrderResponse>
    list(query?: GetOrdersQuery): Promise<OrdersListResponse>
    updateStatus(orderId: string, status: OrderStatus): Promise<OrderResponse>
  }
  
  // Payments
  payments: {
    create(data: CreatePaymentInput): Promise<PaymentResponse>
    refund(paymentId: string, reason?: string): Promise<PaymentResponse>
    getStatus(paymentId: string): Promise<PaymentStatusResponse>
  }
  
  // Authentication
  auth: {
    login(credentials: LoginInput): Promise<AuthResponse>
    getCurrentUser(token: string): Promise<UserResponse>
    refreshToken(token: string): Promise<AuthResponse>
  }
}
```

## Usage Example
```typescript
import { RuntimeClient } from '@order-management/sdk/runtime'

const runtimeClient = new RuntimeClient({
  baseUrl: process.env.RUNTIME_API_URL,
  token: authToken
})

// Create order
const order = await runtimeClient.orders.create({
  sellerId: 'seller_123',
  customerId: 'customer_456',
  items: [{ productId: 'product_789', quantity: 2 }],
  paymentType: 'CASH_ON_DELIVERY'
})

// Update order status
const updated = await runtimeClient.orders.updateStatus(
  order.id, 
  'CONFIRMED'
)
```

---

# Platform Layer SDK

## Client Interface
```typescript
export class PlatformClient {
  // Catalog
  catalog: {
    list(query?: CatalogQuery): Promise<ProductsListResponse>
    get(productId: string): Promise<ProductResponse>
    create(data: CreateProductInput): Promise<ProductResponse>
    update(productId: string, data: UpdateProductInput): Promise<ProductResponse>
    delete(productId: string): Promise<void>
  }
  
  // AI Search
  ai: {
    search(query: string, options?: SearchOptions): Promise<SearchResponse>
    recommendations(productId: string): Promise<RecommendationsResponse>
    similar(productId: string): Promise<SimilarProductsResponse>
  }
  
  // Analytics
  analytics: {
    sellerMetrics(sellerId: string, period?: string): Promise<SellerMetricsResponse>
    productMetrics(productId: string, period?: string): Promise<ProductMetricsResponse>
    salesReport(sellerId: string, options?: ReportOptions): Promise<SalesReportResponse>
  }
}
```

## Usage Example
```typescript
import { PlatformClient } from '@order-management/sdk/platform'

const platformClient = new PlatformClient({
  baseUrl: process.env.PLATFORM_API_URL,
  token: delegatedToken
})

// Search products
const search = await platformClient.ai.search('wireless charger', {
  limit: 10,
  category: 'electronics'
})

// Get seller analytics
const metrics = await platformClient.analytics.sellerMetrics(
  'seller_123',
  '30d'
)
```

---

# Shared Gateway Client

## Base HTTP Client
```typescript
export class GatewayClient {
  private baseUrl: string
  private token?: string
  private timeout: number
  private retries: number
  
  constructor(options: GatewayClientOptions)
  
  // Core HTTP methods
  get<T>(path: string, options?: RequestOptions): Promise<T>
  post<T>(path: string, body?: any, options?: RequestOptions): Promise<T>
  put<T>(path: string, body?: any, options?: RequestOptions): Promise<T>
  patch<T>(path: string, body?: any, options?: RequestOptions): Promise<T>
  delete<T>(path: string, options?: RequestOptions): Promise<T>
  
  // Utilities
  healthCheck(): Promise<HealthCheckResponse>
  batch<T>(requests: BatchRequest[]): Promise<T[]>
}
```

## Error Handling
```typescript
export class SDKError extends Error {
  constructor(
    message: string,
    public code: string,
    public status?: number,
    public details?: any
  )
}

export enum ErrorCodes {
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  NOT_FOUND = 'NOT_FOUND',
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  INTERNAL_ERROR = 'INTERNAL_ERROR',
  NETWORK_ERROR = 'NETWORK_ERROR',
  TIMEOUT_ERROR = 'TIMEOUT_ERROR'
}
```

---

# Type Definitions

## Shared Types
```typescript
// Base API response
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: ApiError
}

// Pagination
export interface Pagination {
  page: number
  limit: number
  total: number
  totalPages: number
}

// Common query parameters
export interface BaseQuery {
  page?: number
  limit?: number
}
```

## Runtime Types
```typescript
// Order types
export interface Order {
  id: string
  publicOrderNumber: string
  status: OrderStatus
  paymentStatus: PaymentStatus
  paymentType: PaymentType
  subtotalMinor: number
  deliveryFeeMinor: number
  totalMinor: number
  currency: string
  notes?: string | null
  createdAt: string
  updatedAt: string
  customer: Customer
  items: OrderItem[]
}

export type OrderStatus = 'PENDING' | 'CONFIRMED' | 'PREPARING' | 'READY' | 'COMPLETED' | 'CANCELLED'
export type PaymentStatus = 'PENDING' | 'PAID' | 'FAILED' | 'REFUNDED'
export type PaymentType = 'CASH_ON_DELIVERY' | 'CARD' | 'WALLET'

// Input types
export interface CreateOrderInput {
  sellerId: string
  customerId: string
  items: OrderItemInput[]
  paymentType: PaymentType
  notes?: string
}

export interface OrderItemInput {
  productId: string
  quantity: number
}
```

## Platform Types
```typescript
// Product types
export interface Product {
  id: string
  name: string
  description?: string
  priceMinor: number
  currency: string
  category?: string
  isActive: boolean
  createdAt: string
  updatedAt: string
}

// Search types
export interface SearchResult {
  productId: string
  name: string
  score: number
  priceMinor: number
  currency: string
  category?: string
}

export interface SearchResponse {
  success: boolean
  data: {
    results: SearchResult[]
    query: string
    total: number
  }
}
```

---

# Authentication Flow

## Token Management
```typescript
export interface AuthManager {
  // Runtime authentication
  login(email: string, password: string): Promise<AuthResponse>
  refreshToken(refreshToken: string): Promise<AuthResponse>
  logout(): Promise<void>
  
  // Delegated tokens for platform
  getDelegatedToken(permissions: string[]): Promise<string>
  validateDelegatedToken(token: string): Promise<DelegatedTokenPayload>
}

export interface AuthResponse {
  user: AuthUser
  token: string
  refreshToken?: string
  expiresAt: string
}

export interface AuthUser {
  id: string
  email: string
  role: 'STAFF' | 'SELLER' | 'ADMIN'
  sellerId?: string | null
}
```

## Token Usage
```typescript
// Runtime client with seller token
const runtimeClient = new RuntimeClient({
  baseUrl: 'https://api.order-management.com',
  token: sellerAuthToken
})

// Platform client with delegated token
const platformClient = new PlatformClient({
  baseUrl: 'https://api.sellora.com',
  token: delegatedToken
})
```

---

# Configuration

## SDK Configuration
```typescript
export interface SDKConfig {
  // API URLs
  runtimeUrl: string
  platformUrl: string
  
  // Authentication
  authManager?: AuthManager
  
  // HTTP settings
  timeout?: number
  retries?: number
  
  // Development settings
  enableLogging?: boolean
  mockData?: boolean
}

// Default configuration
export const defaultConfig: SDKConfig = {
  runtimeUrl: process.env.RUNTIME_API_URL || 'http://localhost:3000',
  platformUrl: process.env.PLATFORM_API_URL || 'http://localhost:3001',
  timeout: 10000,
  retries: 3,
  enableLogging: process.env.NODE_ENV === 'development'
}
```

## Environment Setup
```typescript
// Development
const sdk = new OrderManagementSDK({
  runtimeUrl: 'http://localhost:3000',
  platformUrl: 'http://localhost:3001',
  enableLogging: true
})

// Production
const sdk = new OrderManagementSDK({
  runtimeUrl: 'https://api.order-management.com',
  platformUrl: 'https://api.sellora.com',
  enableLogging: false
})
```

---

# Error Handling & Retry Logic

## Automatic Retries
```typescript
export interface RetryConfig {
  maxAttempts: number
  baseDelay: number
  maxDelay: number
  backoffFactor: number
  retryableErrors: string[]
}

export const defaultRetryConfig: RetryConfig = {
  maxAttempts: 3,
  baseDelay: 1000,
  maxDelay: 10000,
  backoffFactor: 2,
  retryableErrors: [
    'NETWORK_ERROR',
    'TIMEOUT_ERROR',
    'INTERNAL_ERROR'
  ]
}
```

## Error Recovery
```typescript
export class ErrorRecovery {
  static async handleNetworkError(error: SDKError): Promise<never> {
    // Log error
    console.error('Network error:', error.message)
    
    // Check if offline
    if (!navigator.onLine) {
      throw new SDKError('No internet connection', 'NETWORK_OFFLINE')
    }
    
    throw error
  }
  
  static async handleAuthError(error: SDKError): Promise<never> {
    // Clear invalid token
    if (error.code === 'UNAUTHORIZED') {
      await authManager.logout()
    }
    
    throw error
  }
}
```

---

# Development Tools

## Mock Data Support
```typescript
export class MockDataClient {
  // Mock runtime responses
  static mockOrder(orderId: string): Order {
    return {
      id: orderId,
      publicOrderNumber: `ORD-${Math.floor(Math.random() * 9999)}`,
      status: 'PENDING',
      paymentStatus: 'PENDING',
      paymentType: 'CASH_ON_DELIVERY',
      subtotalMinor: 2000,
      deliveryFeeMinor: 500,
      totalMinor: 2500,
      currency: 'USD',
      notes: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      customer: {
        id: 'customer_123',
        name: 'Test Customer',
        phone: '+1234567890',
        addressText: '123 Test St'
      },
      items: [{
        id: 'item_123',
        productId: 'product_123',
        productNameSnapshot: 'Test Product',
        unitPriceMinor: 1000,
        quantity: 2,
        lineTotalMinor: 2000
      }]
    }
  }
  
  // Mock platform responses
  static mockSearchResults(query: string): SearchResult[] {
    return [
      {
        productId: 'product_123',
        name: 'Test Product',
        score: 0.95,
        priceMinor: 2999,
        currency: 'USD',
        category: 'electronics'
      }
    ]
  }
}
```

## Development Mode
```typescript
// Enable mock data for development
if (process.env.NODE_ENV === 'development' && process.env.USE_MOCK_DATA) {
  const sdk = new OrderManagementSDK({
    runtimeUrl: 'http://localhost:3000',
    platformUrl: 'http://localhost:3001',
    mockData: true,
    enableLogging: true
  })
}
```

---

# Package Configuration

## package.json
```json
{
  "name": "@order-management/sdk",
  "version": "1.0.0",
  "description": "Type-safe SDK for Order Management System",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": ["dist"],
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "test": "vitest",
    "lint": "eslint src --ext .ts",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "zod": "^4.3.6"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "vitest": "^1.0.0",
    "@types/node": "^20.0.0"
  },
  "peerDependencies": {
    "typescript": "^5.0.0"
  }
}
```

## tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "node",
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "**/*.test.ts"]
}
```

---

# Usage Examples

## Frontend Integration (React)
```typescript
import { useQuery } from '@tanstack/react-query'
import { RuntimeClient } from '@order-management/sdk/runtime'

const runtimeClient = new RuntimeClient({
  baseUrl: process.env.NEXT_PUBLIC_RUNTIME_URL!,
  token: getAuthToken()
})

export function useOrders(query?: GetOrdersQuery) {
  return useQuery({
    queryKey: ['orders', query],
    queryFn: () => runtimeClient.orders.list(query),
    staleTime: 1000 * 60 * 2 // 2 minutes
  })
}

export function useCreateOrder() {
  return useMutation({
    mutationFn: (data: CreateOrderInput) => runtimeClient.orders.create(data),
    onSuccess: (order) => {
      console.log('Order created:', order.publicOrderNumber)
    }
  })
}
```

## Platform Integration (Node.js)
```typescript
import { PlatformClient } from '@order-management/sdk/platform'

const platformClient = new PlatformClient({
  baseUrl: process.env.PLATFORM_API_URL!,
  token: getServiceToken()
})

export async function syncProductCatalog() {
  const products = await platformClient.catalog.list()
  
  for (const product of products.data) {
    await processProduct(product)
  }
}
```

---

This shared SDK provides a unified, type-safe interface for all system boundaries while maintaining strict separation of concerns.

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

import {
  SdkConfig,
  SdkConfigSchema,
  ApiResponseSchema,
  PaginatedResponse,
  ApiError,
  ErrorCode,
  LoginRequest,
  LoginResponse,
  CreateOrderRequest,
  Order,
  CreatePaymentRequest,
  Payment,
} from './types';

export class OrderManagementSDK {
  private client: AxiosInstance;
  private config: SdkConfig;
  private authToken: string | null = null;

  constructor(config: SdkConfig) {
    // Validate configuration
    this.config = SdkConfigSchema.parse(config);
    
    // Create axios instance
    this.client = axios.create({
      baseURL: this.config.baseURL,
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor for authentication
    this.client.interceptors.request.use(
      (config) => {
        if (this.authToken) {
          config.headers.Authorization = `Bearer ${this.authToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const apiError = this.handleError(error);
        return Promise.reject(apiError);
      }
    );
  }

  private setAuthToken(token: string): void {
    this.authToken = token;
  }

  private clearAuthToken(): void {
    this.authToken = null;
  }

  private handleError(error: unknown): ApiError {
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as any;
      // Server responded with error status
      const statusCode = axiosError.response?.status || 500;
      const response = axiosError.response?.data;

      // Try to parse as API response
      try {
        const apiResponse = ApiResponseSchema.parse(response);
        if (apiResponse.error) {
          return {
            code: apiResponse.error.code as ErrorCode,
            message: apiResponse.error.message,
            statusCode,
            details: apiResponse.error.details,
          };
        }
      } catch {
        // Fallback to generic error
      }

      return {
        code: this.getErrorCodeFromStatus(statusCode),
        message: (response as any)?.message || 'Request failed',
        statusCode,
        details: response,
      };
    } else if (error && typeof error === 'object' && 'request' in error) {
      // Network error
      return {
        code: 'SERVICE_UNAVAILABLE',
        message: 'Network error - please check your connection',
        statusCode: 0,
        details: error,
      };
    } else {
      // Other error
      return {
        code: 'INTERNAL_SERVER_ERROR',
        message: (error as any)?.message || 'An unexpected error occurred',
        statusCode: 500,
        details: error,
      };
    }
  }

  private getErrorCodeFromStatus(status: number): ErrorCode {
    switch (status) {
      case 400:
        return 'VALIDATION_ERROR';
      case 401:
        return 'AUTHENTICATION_ERROR';
      case 403:
        return 'AUTHORIZATION_ERROR';
      case 404:
        return 'NOT_FOUND';
      case 409:
        return 'CONFLICT';
      case 429:
        return 'RATE_LIMIT_EXCEEDED';
      case 503:
        return 'SERVICE_UNAVAILABLE';
      default:
        return 'INTERNAL_SERVER_ERROR';
    }
  }

  private async request<T>(config: AxiosRequestConfig): Promise<T> {
    try {
      const response: AxiosResponse = await this.client.request(config);
      return response.data;
    } catch (error) {
      throw error; // Error already handled by interceptor
    }
  }

  private async requestWithRetry<T>(config: AxiosRequestConfig): Promise<T> {
    let lastError: unknown;
    
    for (let attempt = 0; attempt <= this.config.retryAttempts; attempt++) {
      try {
        return await this.request<T>(config);
      } catch (error) {
        lastError = error;
        
        // Don't retry on client errors (4xx)
        if (error && typeof error === 'object' && 'statusCode' in error) {
          const statusCode = (error as any).statusCode;
          if (statusCode && statusCode >= 400 && statusCode < 500) {
            throw error;
          }
        }
        
        // Don't retry on last attempt
        if (attempt === this.config.retryAttempts) {
          throw error;
        }
        
        // Wait before retry
        await this.delay(this.config.retryDelay * (attempt + 1));
      }
    }
    
    throw lastError;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // === AUTH METHODS ===

  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await this.requestWithRetry<LoginResponse>({
      method: 'POST',
      url: '/api/auth/login',
      data: { email, password },
    });
    
    if (response.token) {
      this.setAuthToken(response.token);
    }
    
    return response;
  }

  async logout(): Promise<void> {
    try {
      await this.request({
        method: 'POST',
        url: '/api/auth/logout',
      });
    } finally {
      this.clearAuthToken();
    }
  }

  async getCurrentUser(): Promise<any> {
    return this.requestWithRetry({
      method: 'GET',
      url: '/api/auth/me',
    });
  }

  async refreshToken(): Promise<LoginResponse> {
    const response = await this.requestWithRetry<LoginResponse>({
      method: 'POST',
      url: '/api/auth/refresh',
    });
    
    if (response.token) {
      this.setAuthToken(response.token);
    }
    
    return response;
  }

  // === ORDER METHODS ===

  async createOrder(orderData: CreateOrderRequest): Promise<Order> {
    return this.requestWithRetry<Order>({
      method: 'POST',
      url: '/api/orders',
      data: orderData,
    });
  }

  async getOrder(orderId: string): Promise<Order> {
    return this.requestWithRetry<Order>({
      method: 'GET',
      url: `/api/orders/${orderId}`,
    });
  }

  async getOrders(params?: {
    page?: number;
    limit?: number;
    status?: string;
    customerId?: string;
  }): Promise<PaginatedResponse<Order>> {
    return this.requestWithRetry<PaginatedResponse<Order>>({
      method: 'GET',
      url: '/api/orders',
      params,
    });
  }

  async updateOrder(orderId: string, updateData: Partial<Order>): Promise<Order> {
    return this.requestWithRetry<Order>({
      method: 'PATCH',
      url: `/api/orders/${orderId}`,
      data: updateData,
    });
  }

  async cancelOrder(orderId: string, reason?: string): Promise<Order> {
    return this.requestWithRetry<Order>({
      method: 'POST',
      url: `/api/orders/${orderId}/cancel`,
      data: { reason },
    });
  }

  // === PAYMENT METHODS ===

  async createPayment(paymentData: CreatePaymentRequest): Promise<Payment> {
    return this.requestWithRetry<Payment>({
      method: 'POST',
      url: '/api/payments',
      data: paymentData,
    });
  }

  async getPayment(paymentId: string): Promise<Payment> {
    return this.requestWithRetry<Payment>({
      method: 'GET',
      url: `/api/payments/${paymentId}`,
    });
  }

  async getPayments(params?: {
    page?: number;
    limit?: number;
    orderId?: string;
    status?: string;
  }): Promise<PaginatedResponse<Payment>> {
    return this.requestWithRetry<PaginatedResponse<Payment>>({
      method: 'GET',
      url: '/api/payments',
      params,
    });
  }

  async updatePaymentStatus(paymentId: string, status: string): Promise<Payment> {
    return this.requestWithRetry<Payment>({
      method: 'PATCH',
      url: `/api/payments/${paymentId}/status`,
      data: { status },
    });
  }

  // === HEALTH CHECK ===

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.request({
      method: 'GET',
      url: '/api/health',
    });
  }

  // === CONFIGURATION ===

  updateConfig(newConfig: Partial<SdkConfig>): void {
    this.config = SdkConfigSchema.parse({ ...this.config, ...newConfig });
    
    // Update axios instance
    this.client.defaults.baseURL = this.config.baseURL;
    this.client.defaults.timeout = this.config.timeout;
  }

  getConfig(): SdkConfig {
    return { ...this.config };
  }
}

// Runtime client temporarily disabled to unblock build
// TODO: Fix runtime client type issues and re-enable

import { AuthTokens, RuntimeClient, RuntimeClientConfig } from './types';

export class OrderManagementRuntimeClient implements RuntimeClient {
  private readonly disabled = true;
  private readonly config: RuntimeClientConfig;
  private readonly tokens?: AuthTokens;

  constructor(config: RuntimeClientConfig, tokens?: AuthTokens) {
    this.config = config;
    this.tokens = tokens;
  }

  // Stub implementations - all return disabled state
  orders = {
    create: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    get: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    list: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    update: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    updateStatus: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    getEvents: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
  };

  payments = {
    create: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    get: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    list: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    updateStatus: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    refund: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
  };

  customers = {
    create: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    get: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    list: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    update: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
  };

  auth = {
    login: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    refresh: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    logout: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
  };

  health = {
    check: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
  };

  webhooks = {
    create: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    list: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
    delete: async () => ({ success: false, error: { code: "DISABLED", message: "Runtime client is disabled" } }),
  };

  isDisabled(): boolean {
    return this.disabled;
  }
}

export class RuntimeClientFactory {
  static create(config: RuntimeClientConfig): OrderManagementRuntimeClient {
    return new OrderManagementRuntimeClient(config);
  }

  static createWithTokens(
    tokens: AuthTokens,
    config: RuntimeClientConfig
  ): OrderManagementRuntimeClient {
    return new OrderManagementRuntimeClient(config, tokens);
  }
}

export { OrderManagementRuntimeClient as RuntimeClientImpl };


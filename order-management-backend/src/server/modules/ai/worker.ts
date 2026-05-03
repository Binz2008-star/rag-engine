// AI Worker temporarily disabled to unblock build
// TODO: Fix worker service type issues and re-enable

import { PrismaClient } from "@prisma/client";

export interface WorkerConfig {
  redisUrl: string;
  concurrency: number;
  maxRetries: number;
  backoffType: "exponential" | "fixed" | "linear";
}

export class AIWorker {
  private readonly disabled = true;
  private readonly config: WorkerConfig;
  private readonly prisma: PrismaClient;

  constructor(config: WorkerConfig) {
    this.config = config;
    this.prisma = new PrismaClient();
  }

  async start(): Promise<void> {
    console.warn("AI Worker is temporarily disabled.");
  }

  async stop(): Promise<void> {
    console.warn("AI Worker stop requested, but worker is disabled.");
  }

  isDisabled(): boolean {
    return this.disabled;
  }

  async getStats(): Promise<any> {
    return {
      disabled: true,
      active: 0,
      completed: 0,
      failed: 0,
    };
  }
}

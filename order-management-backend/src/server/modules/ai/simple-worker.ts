// === SIMPLE AI WORKER ===
// Minimal working AI worker for production testing

import { PrismaClient } from "@prisma/client";
import { Job, Queue, Worker } from "bullmq";
import { Redis } from "ioredis";

// === SIMPLE CONFIGURATION ===

interface SimpleWorkerConfig {
  redisUrl: string;
  concurrency: number;
}

interface SimpleJobData {
  sellerId: string;
  jobType: "TEST_JOB" | "HEALTH_CHECK";
  payload?: Record<string, any>;
}

// === SIMPLE AI WORKER ===

export class SimpleAIWorker {
  private redis: Redis;
  private prisma: PrismaClient;
  private queue: Queue;
  private worker!: Worker;
  private config: SimpleWorkerConfig;

  constructor(config: SimpleWorkerConfig) {
    this.config = config;
    this.redis = new Redis(config.redisUrl, {
      maxRetriesPerRequest: null,
      lazyConnect: true,
    });

    this.prisma = new PrismaClient();
    this.queue = new Queue("ai-queue", {
      connection: this.redis,
      defaultJobOptions: {
        removeOnComplete: 100,
        removeOnFail: 50,
        attempts: 3,
        backoff: {
          type: "exponential",
          delay: 2000,
        },
      },
    });
  }

  // === WORKER LIFECYCLE ===

  async start(): Promise<void> {
    console.log("Starting Simple AI Worker...");

    this.worker = new Worker(
      "ai-queue",
      async (job: Job<SimpleJobData>) => {
        return await this.processJob(job);
      },
      {
        connection: this.redis,
        concurrency: this.config.concurrency,
      }
    );

    this.worker.on("completed", (job: Job, result) => {
      console.log(`Job ${job.id} completed:`, result);
    });

    this.worker.on("failed", (job: Job | undefined, err: Error) => {
      console.error(`Job ${job?.id || 'unknown'} failed:`, err.message);
    });

    this.worker.on("error", (err: Error) => {
      console.error("Worker error:", err);
    });

    await this.worker.waitUntilReady();
    console.log("Simple AI Worker started successfully");
  }

  async stop(): Promise<void> {
    console.log("Stopping Simple AI Worker...");

    if (this.worker) {
      await this.worker.close();
    }

    if (this.queue) {
      await this.queue.close();
    }

    await this.redis.quit();
    await this.prisma.$disconnect();

    console.log("Simple AI Worker stopped");
  }

  // === JOB PROCESSING ===

  private async processJob(job: Job<SimpleJobData>): Promise<any> {
    const { sellerId, jobType, payload } = job.data;

    console.log(`Processing ${jobType} job for seller ${sellerId}`);

    try {
      switch (jobType) {
        case "TEST_JOB":
          return await this.processTestJob(sellerId, payload);

        case "HEALTH_CHECK":
          return await this.processHealthCheck(sellerId, payload);

        default:
          throw new Error(`Unknown job type: ${jobType}`);
      }
    } catch (error) {
      console.error(`Job ${job.id} processing failed:`, error);
      throw error;
    }
  }

  // === JOB HANDLERS ===

  private async processTestJob(sellerId: string, payload?: Record<string, any>): Promise<{
    success: boolean;
    message: string;
    timestamp: string;
  }> {
    console.log(`Processing test job for seller ${sellerId}`);

    // Simulate some work
    await new Promise(resolve => setTimeout(resolve, 1000));

    return {
      success: true,
      message: `Test job completed for seller ${sellerId}`,
      timestamp: new Date().toISOString(),
    };
  }

  private async processHealthCheck(sellerId: string, payload?: Record<string, any>): Promise<{
    success: boolean;
    redis: boolean;
    database: boolean;
    timestamp: string;
  }> {
    console.log(`Processing health check for seller ${sellerId}`);

    // Check Redis connection
    let redisStatus = false;
    try {
      await this.redis.ping();
      redisStatus = true;
    } catch (error) {
      console.error("Redis health check failed:", error);
    }

    // Check database connection
    let databaseStatus = false;
    try {
      await this.prisma.$queryRaw`SELECT 1`;
      databaseStatus = true;
    } catch (error) {
      console.error("Database health check failed:", error);
    }

    return {
      success: redisStatus && databaseStatus,
      redis: redisStatus,
      database: databaseStatus,
      timestamp: new Date().toISOString(),
    };
  }

  // === QUEUE MANAGEMENT ===

  async addJob(data: SimpleJobData): Promise<Job<SimpleJobData>> {
    return await this.queue.add(data.jobType, data);
  }

  async getQueueStats(): Promise<{
    waiting: number;
    active: number;
    completed: number;
    failed: number;
  }> {
    const [waiting, active, completed, failed] = await Promise.all([
      this.queue.getWaiting(),
      this.queue.getActive(),
      this.queue.getCompleted(),
      this.queue.getFailed(),
    ]);

    return {
      waiting: waiting.length,
      active: active.length,
      completed: completed.length,
      failed: failed.length,
    };
  }
}

// === MAIN EXECUTION ===

async function main() {
  const config: SimpleWorkerConfig = {
    redisUrl: process.env.REDIS_URL || "redis://localhost:6379",
    concurrency: parseInt(process.env.AI_WORKER_CONCURRENCY || "2"),
  };

  const worker = new SimpleAIWorker(config);

  try {
    await worker.start();

    // Graceful shutdown
    process.on("SIGINT", async () => {
      console.log("Received SIGINT, shutting down gracefully...");
      await worker.stop();
      process.exit(0);
    });

    process.on("SIGTERM", async () => {
      console.log("Received SIGTERM, shutting down gracefully...");
      await worker.stop();
      process.exit(0);
    });

    // Keep the process running
    console.log("Simple AI Worker is running. Press Ctrl+C to stop.");

  } catch (error) {
    console.error("Failed to start Simple AI Worker:", error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

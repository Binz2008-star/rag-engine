// Queue service temporarily disabled to unblock build
// TODO: Fix bullmq type issues and re-enable

import type { Job } from "bullmq";

export type IndexingJobType =
  | "FULL_REINDEX"
  | "UPSERT_DOCUMENT"
  | "DELETE_DOCUMENT";

export interface IndexingJobData {
  sellerId: string;
  jobType: IndexingJobType;
  sourceType?: string;
  sourceId?: string;
  documentId?: string;
}

export interface IndexingJobResult {
  success: boolean;
  processed: number;
  errors: string[];
  duration: number;
}

export interface QueueStats {
  waiting: number;
  active: number;
  completed: number;
  failed: number;
  delayed: number;
  paused: boolean;
  disabled: true;
}

export class AiQueueService {
  private readonly disabled = true;
  private readonly redisUrl?: string;

  constructor(redisUrl?: string) {
    this.redisUrl = redisUrl;
  }

  async addIndexingJob(data: IndexingJobData): Promise<void> {
    console.warn("AI indexing queue is temporarily disabled.", {
      sellerId: data.sellerId,
      jobType: data.jobType,
      sourceType: data.sourceType,
      sourceId: data.sourceId,
      documentId: data.documentId,
    });
  }

  async getQueueStats(): Promise<QueueStats> {
    return {
      waiting: 0,
      active: 0,
      completed: 0,
      failed: 0,
      delayed: 0,
      paused: false,
      disabled: true,
    };
  }

  async pauseQueue(): Promise<void> {
    console.warn("AI indexing queue pause requested, but queue is disabled.");
  }

  async resumeQueue(): Promise<void> {
    console.warn("AI indexing queue resume requested, but queue is disabled.");
  }

  async clearQueue(): Promise<void> {
    console.warn("AI indexing queue clear requested, but queue is disabled.");
  }

  async processIndexingJob(
    _job: Pick<Job<IndexingJobData>, "data"> | IndexingJobData,
  ): Promise<IndexingJobResult> {
    return {
      success: false,
      processed: 0,
      errors: ["AI indexing queue is temporarily disabled."],
      duration: 0,
    };
  }

  async close(): Promise<void> {
    // no-op while disabled
  }

  isDisabled(): boolean {
    return this.disabled;
  }
}

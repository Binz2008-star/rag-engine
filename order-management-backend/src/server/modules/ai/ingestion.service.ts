import { PrismaClient } from '@prisma/client';
import { EventEmitter } from 'events';
import { AiQueueService } from './queue.service';

export interface IngestionEvent {
  type: 'PRODUCT_CREATED' | 'PRODUCT_UPDATED' | 'PRODUCT_DELETED' | 'ORDER_CREATED' | 'ORDER_UPDATED' | 'CUSTOMER_CREATED' | 'CUSTOMER_UPDATED' | 'POLICY_UPDATED' | 'FAQ_UPDATED';
  sellerId: string;
  sourceId: string;
  data: any;
  timestamp: Date;
}

export class AiIngestionService extends EventEmitter {
  constructor(
    private prisma: PrismaClient,
    private queueService: AiQueueService
  ) {
    super();
    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    // Listen to database events or webhook events
    this.on('ingestion', this.handleIngestionEvent.bind(this));
  }

  async triggerProductIngestion(sellerId: string, productId: string, eventType: 'CREATED' | 'UPDATED' | 'DELETED') {
    const event: IngestionEvent = {
      type: `PRODUCT_${eventType}` as any,
      sellerId,
      sourceId: productId,
      data: { productId },
      timestamp: new Date(),
    };

    this.emit('ingestion', event);
  }

  async triggerPolicyIngestion(sellerId: string, policyId: string) {
    const event: IngestionEvent = {
      type: 'POLICY_UPDATED',
      sellerId,
      sourceId: policyId,
      data: { policyId },
      timestamp: new Date(),
    };

    this.emit('ingestion', event);
  }

  async triggerFaqIngestion(sellerId: string, faqId: string) {
    const event: IngestionEvent = {
      type: 'FAQ_UPDATED',
      sellerId,
      sourceId: faqId,
      data: { faqId },
      timestamp: new Date(),
    };

    this.emit('ingestion', event);
  }

  private async handleIngestionEvent(event: IngestionEvent) {
    try {
      switch (event.type) {
        case 'PRODUCT_CREATED':
        case 'PRODUCT_UPDATED':
          await this.queueService.addIndexingJob({
            sellerId: event.sellerId,
            jobType: 'UPSERT_DOCUMENT',
            sourceType: 'PRODUCT',
            sourceId: event.sourceId
          });
          break;

        case 'PRODUCT_DELETED':
          await this.queueService.addIndexingJob({
            sellerId: event.sellerId,
            jobType: 'DELETE_DOCUMENT',
            sourceType: 'PRODUCT',
            sourceId: event.sourceId
          });
          break;

        case 'ORDER_CREATED':
        case 'ORDER_UPDATED':
          await this.queueService.addIndexingJob({
            sellerId: event.sellerId,
            jobType: 'UPSERT_DOCUMENT',
            sourceType: 'ORDER',
            sourceId: event.sourceId
          });
          break;

        case 'CUSTOMER_CREATED':
        case 'CUSTOMER_UPDATED':
          await this.queueService.addIndexingJob({
            sellerId: event.sellerId,
            jobType: 'UPSERT_DOCUMENT',
            sourceType: 'CUSTOMER',
            sourceId: event.sourceId
          });
          break;

        case 'POLICY_UPDATED':
          await this.queueService.addIndexingJob({
            sellerId: event.sellerId,
            jobType: 'UPSERT_DOCUMENT',
            sourceType: 'POLICY',
            sourceId: event.sourceId
          });
          break;

        case 'FAQ_UPDATED':
          await this.queueService.addIndexingJob({
            sellerId: event.sellerId,
            jobType: 'UPSERT_DOCUMENT',
            sourceType: 'FAQ',
            sourceId: event.sourceId
          });
          break;

        default:
          console.warn(`Unknown ingestion event type: ${event.type}`);
      }
    } catch (error) {
      console.error(`Failed to handle ingestion event:`, error);
    }
  }

  // Method to be called from product service hooks
  async onProductChange(sellerId: string, productId: string, action: 'create' | 'update' | 'delete') {
    const eventType = action === 'create' ? 'CREATED' :
      action === 'update' ? 'UPDATED' : 'DELETED';

    await this.triggerProductIngestion(sellerId, productId, eventType);
  }

  // Method to be called from policy service hooks
  async onPolicyChange(sellerId: string, policyId: string) {
    await this.triggerPolicyIngestion(sellerId, policyId);
  }

  // Method to be called from FAQ service hooks
  async onFaqChange(sellerId: string, faqId: string) {
    await this.triggerFaqIngestion(sellerId, faqId);
  }

  // Bulk ingestion for initial setup
  async triggerFullReindex(sellerId: string, priority: number = 0) {
    await this.queueService.addIndexingJob({
      sellerId,
      jobType: 'FULL_REINDEX'
    });
  }

  // Get ingestion statistics
  async getIngestionStats(sellerId: string) {
    const stats = await this.prisma.aiIndexJob.groupBy({
      by: ['jobType', 'status'],
      where: {
        sellerId,
        createdAt: {
          gte: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
        },
      },
      _count: { id: true },
    });

    return stats.map(stat => ({
      jobType: stat.jobType,
      status: stat.status,
      count: stat._count.id,
    }));
  }
}

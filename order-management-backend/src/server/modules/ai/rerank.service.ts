import { PrismaClient } from '@prisma/client';

export interface RerankInput {
  query: string;
  documents: Array<{
    id: string;
    content: string;
    title?: string;
  }>;
  topK?: number;
}

export interface RerankResult {
  id: string;
  score: number;
  rank: number;
}

export interface RerankMetrics {
  latencyMs: number;
  documentCount: number;
  model: string;
}

export class RerankService {
  private readonly defaultModel = 'BAAI/bge-reranker-v2-m3';
  private readonly maxBatchSize = 100;

  constructor(private prisma: PrismaClient) {}

  async rerank(input: RerankInput): Promise<{ results: RerankResult[]; metrics: RerankMetrics }> {
    const startTime = Date.now();
    const topK = Math.min(input.topK || input.documents.length, input.documents.length);

    try {
      // Mock reranking for now - in production, use BGE reranker
      const reranked = await this.mockReranking(input.query, input.documents);
      
      const results = reranked
        .sort((a, b) => b.score - a.score)
        .slice(0, topK)
        .map((doc, index) => ({
          id: doc.id,
          score: doc.score,
          rank: index + 1,
        }));

      const metrics: RerankMetrics = {
        latencyMs: Date.now() - startTime,
        documentCount: input.documents.length,
        model: this.defaultModel,
      };

      return { results, metrics };
    } catch (error) {
      throw new Error(`Reranking failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private async mockReranking(query: string, documents: Array<{ id: string; content: string; title?: string }>) {
    // Mock reranking based on keyword matching and length
    const queryWords = query.toLowerCase().split(/\s+/);
    
    return documents.map(doc => {
      const content = (doc.title + ' ' + doc.content).toLowerCase();
      let score = 0;

      // Simple keyword matching
      for (const word of queryWords) {
        if (content.includes(word)) {
          score += 0.3;
        }
      }

      // Add some randomness for mock effect
      score += Math.random() * 0.2;

      // Penalize very long documents
      if (doc.content.length > 1000) {
        score *= 0.8;
      }

      return {
        id: doc.id,
        score: Math.min(score, 1.0),
      };
    });
  }

  async batchRerank(inputs: RerankInput[]): Promise<Array<{ results: RerankResult[]; metrics: RerankMetrics }>> {
    const results = [];
    
    // Process in batches to avoid memory issues
    for (let i = 0; i < inputs.length; i += this.maxBatchSize) {
      const batch = inputs.slice(i, i + this.maxBatchSize);
      const batchResults = await Promise.all(
        batch.map(input => this.rerank(input))
      );
      results.push(...batchResults);
    }

    return results;
  }

  async getRerankStats(sellerId: string, startDate?: Date, endDate?: Date) {
    const where: any = { sellerId };
    
    if (startDate || endDate) {
      where.createdAt = {};
      if (startDate) where.createdAt.gte = startDate;
      if (endDate) where.createdAt.lte = endDate;
    }

    // Since we don't have specific rerank logs, we'll use query logs with rerank results
    const stats = await this.prisma.aiQueryResult.aggregate({
      where: {
        queryLog: {
          sellerId,
          ...(startDate || endDate ? { createdAt: where.createdAt } : {}),
        },
        rerankScore: { not: null },
      },
      _count: { id: true },
      _avg: { rerankScore: true },
      _min: { rerankScore: true },
      _max: { rerankScore: true },
    });

    return {
      totalRerankedQueries: stats._count.id || 0,
      averageRerankScore: stats._avg.rerankScore || 0,
      minRerankScore: stats._min.rerankScore || 0,
      maxRerankScore: stats._max.rerankScore || 0,
    };
  }

  async isRerankEnabled(sellerId: string): Promise<boolean> {
    const policy = await this.prisma.sellerAiPolicy.findUnique({
      where: { sellerId },
      select: { rerankEnabled: true, benchmarkGatePassed: true },
    });

    return policy?.rerankEnabled && policy?.benchmarkGatePassed || false;
  }

  async validateRerankInput(input: RerankInput): Promise<{ valid: boolean; errors?: string[] }> {
    const errors: string[] = [];

    if (!input.query || input.query.trim().length === 0) {
      errors.push('Query cannot be empty');
    }

    if (!input.documents || input.documents.length === 0) {
      errors.push('Documents array cannot be empty');
    }

    if (input.documents && input.documents.length > this.maxBatchSize) {
      errors.push(`Documents array exceeds maximum batch size of ${this.maxBatchSize}`);
    }

    if (input.documents) {
      for (let i = 0; i < input.documents.length; i++) {
        const doc = input.documents[i];
        if (!doc.id) {
          errors.push(`Document at index ${i} is missing id`);
        }
        if (!doc.content || doc.content.trim().length === 0) {
          errors.push(`Document at index ${i} is missing content`);
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors: errors.length > 0 ? errors : undefined,
    };
  }

  async getModelInfo() {
    return {
      model: this.defaultModel,
      maxBatchSize: this.maxBatchSize,
      supportedLanguages: ['en', 'ar', 'zh', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja'],
      description: 'BGE reranker v2-m3 for multilingual document reranking',
    };
  }
}

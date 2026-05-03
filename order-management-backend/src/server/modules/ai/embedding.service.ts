import { PrismaClient } from '@prisma/client';

export interface EmbeddingResult {
  embedding: number[];
  tokenCount: number;
  model: string;
  latencyMs: number;
}

export interface EmbeddingOptions {
  model?: string;
  batchSize?: number;
  maxTokens?: number;
}

export class EmbeddingService {
  private readonly defaultModel = 'intfloat/multilingual-e5-small';
  private readonly embeddingDimension = 384;
  private readonly maxBatchSize = 32;

  constructor(private prisma: PrismaClient) { }

  async generateEmbeddings(
    texts: string[],
    options: EmbeddingOptions = {}
  ): Promise<EmbeddingResult[]> {
    const model = options.model || this.defaultModel;
    const batchSize = Math.min(options.batchSize || this.maxBatchSize, this.maxBatchSize);

    const results: EmbeddingResult[] = [];

    // Process in batches to avoid memory issues
    for (let i = 0; i < texts.length; i += batchSize) {
      const batch = texts.slice(i, i + batchSize);
      const batchResults = await this.processBatch(batch, model);
      results.push(...batchResults);
    }

    return results;
  }

  async generateSingleEmbedding(
    text: string,
    options: EmbeddingOptions = {}
  ): Promise<EmbeddingResult> {
    const results = await this.generateEmbeddings([text], options);
    return results[0];
  }

  private async processBatch(texts: string[], model: string): Promise<EmbeddingResult[]> {
    const startTime = Date.now();

    try {
      // Add query/passage prefixes as required by E5 models
      const prefixedTexts = texts.map(text => `query: ${text}`);

      // For now, we'll use a mock implementation
      // In production, this would call the actual embedding model
      const embeddings = await this.mockEmbeddingGeneration(prefixedTexts);

      const latencyMs = Date.now() - startTime;

      return embeddings.map((embedding, index) => ({
        embedding,
        tokenCount: this.estimateTokenCount(texts[index]),
        model,
        latencyMs: Math.floor(latencyMs / texts.length),
      }));
    } catch (error) {
      throw new Error(`Failed to generate embeddings: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private async mockEmbeddingGeneration(texts: string[]): Promise<number[][]> {
    // Mock implementation - in production, this would use the actual model
    // For now, generate random embeddings of the correct dimension
    return texts.map(() =>
      Array.from({ length: this.embeddingDimension }, () => Math.random() * 2 - 1)
    );
  }

  private estimateTokenCount(text: string): number {
    // Rough estimation - in production, use actual tokenizer
    return Math.ceil(text.length / 4);
  }

  async storeEmbeddings(
    documentId: string,
    sellerId: string,
    chunks: Array<{
      content: string;
      index: number;
      metadata?: Record<string, any>;
    }>
  ) {
    const texts = chunks.map(chunk => chunk.content);
    const embeddingResults = await this.generateEmbeddings(texts);

    const chunkData = chunks.map((chunk, index) => {
      const result = embeddingResults[index];
      return {
        documentId,
        sellerId,
        chunkIndex: chunk.index,
        content: chunk.content,
        tokenCount: result.tokenCount,
        metadataJson: chunk.metadata ? JSON.stringify(chunk.metadata) : null,
        embedding: `[${result.embedding.join(',')}]`, // Convert to PostgreSQL vector format
      };
    });

    // Store embeddings in database using individual inserts
    for (const chunk of chunkData) {
      await this.prisma.$executeRaw`
        INSERT INTO ai_document_chunks (
          id, document_id, seller_id, chunk_index, content, token_count, metadata_json, embedding, created_at
        )
        VALUES (
          gen_random_uuid(),
          ${chunk.documentId},
          ${chunk.sellerId},
          ${chunk.chunkIndex},
          ${chunk.content},
          ${chunk.tokenCount},
          ${chunk.metadataJson},
          ${chunk.embedding}::vector(384),
          NOW()
        )
        ON CONFLICT (document_id, chunk_index)
        DO UPDATE SET
          content = EXCLUDED.content,
          token_count = EXCLUDED.token_count,
          metadata_json = EXCLUDED.metadata_json,
          embedding = EXCLUDED.embedding::vector(384)
      `;
    }

    return {
      storedChunks: chunkData.length,
      totalTokens: embeddingResults.reduce((sum, result) => sum + result.tokenCount, 0),
      averageLatency: embeddingResults.reduce((sum, result) => sum + result.latencyMs, 0) / embeddingResults.length,
    };
  }

  async deleteDocumentEmbeddings(documentId: string) {
    return this.prisma.aiDocumentChunk.deleteMany({
      where: { documentId },
    });
  }

  async getEmbeddingStats(sellerId: string) {
    const stats = await this.prisma.aiDocumentChunk.aggregate({
      where: { sellerId },
      _count: { id: true },
      _sum: { tokenCount: true },
      _avg: { tokenCount: true },
    });

    return {
      totalChunks: stats._count.id || 0,
      totalTokens: stats._sum.tokenCount || 0,
      averageTokensPerChunk: stats._avg.tokenCount || 0,
    };
  }

  async searchSimilarChunks(
    sellerId: string,
    queryEmbedding: number[],
    limit: number = 10,
    threshold: number = 0.7
  ) {
    const embeddingString = `[${queryEmbedding.join(',')}]`;

    const results = await this.prisma.$queryRaw`
      SELECT
        dc.id,
        dc.content,
        dc.chunk_index,
        d.title,
        d.source_type,
        1 - (dc.embedding <=> ${embeddingString}::vector(384)) as similarity
      FROM ai_document_chunks dc
      JOIN ai_documents d ON dc.document_id = d.id
      WHERE dc.seller_id = ${sellerId}
        AND d.is_active = true
        AND 1 - (dc.embedding <=> ${embeddingString}::vector(384)) >= ${threshold}
      ORDER BY dc.embedding <=> ${embeddingString}::vector(384)
      LIMIT ${limit}
    `;

    return results as Array<{
      id: string;
      content: string;
      chunk_index: number;
      title: string;
      source_type: string;
      similarity: number;
    }>;
  }
}

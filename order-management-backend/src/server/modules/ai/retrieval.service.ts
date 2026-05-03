import { PrismaClient } from '@prisma/client';
import { EmbeddingService } from './embedding.service';

export interface RetrievalQuery {
  query: string;
  topK?: number;
  domains?: string[];
  minScore?: number;
  includeRerank?: boolean;
}

export interface RetrievalResult {
  chunkId: string;
  documentId: string;
  title: string;
  content: string;
  sourceType: string;
  domain: string;
  score: number;
  rerankScore?: number;
  metadata?: Record<string, any>;
}

export interface RetrievalMetrics {
  queryLatencyMs: number;
  resultCount: number;
  ftsScore?: number;
  vectorScore?: number;
  rerankLatencyMs?: number;
}

export class RetrievalService {
  constructor(
    private prisma: PrismaClient,
    private embeddingService: EmbeddingService
  ) { }

  async search(
    sellerId: string,
    query: RetrievalQuery,
    traceId?: string
  ): Promise<{ results: RetrievalResult[]; metrics: RetrievalMetrics }> {
    const startTime = Date.now();
    const topK = query.topK || 10;
    const minScore = query.minScore || 0.0;

    // Generate embedding for the query
    const embeddingResult = await this.embeddingService.generateSingleEmbedding(
      `query: ${query.query}`
    );

    let results: RetrievalResult[] = [];
    let rerankLatencyMs = 0;

    const metrics: RetrievalMetrics = {
      queryLatencyMs: Date.now() - startTime,
      resultCount: results.length,
      rerankLatencyMs,
    };

    // Log the query for analytics
    await this.logQuery(sellerId, query, results, metrics, traceId);

    return { results, metrics };
  }

  private async performHybridSearch(
    sellerId: string,
    queryText: string,
    queryEmbedding: number[],
    limit: number,
    domains?: string[]
  ) {
    const embeddingString = `[${queryEmbedding.join(',')}]`;

    let domainFilter = '';
    if (domains && domains.length > 0) {
      domainFilter = `AND d.domain IN (${domains.map(d => `'${d}'`).join(', ')})`;
    }

    const query = `
      WITH fts_results AS (
        SELECT
          dc.id as chunk_id,
          dc.document_id,
          dc.content,
          d.title,
          d.source_type,
          d.domain,
          ts_rank(dc.fts, plainto_tsquery('english', $1)) as fts_score,
          0 as vector_score,
          dc.metadata_json
        FROM ai_document_chunks dc
        JOIN ai_documents d ON dc.document_id = d.id
        WHERE dc.seller_id = $2
          AND d.is_active = true
          AND dc.fts @@ plainto_tsquery('english', $1)
          ${domainFilter}
        ORDER BY fts_score DESC
        LIMIT $3 * 2
      ),
      vector_results AS (
        SELECT
          dc.id as chunk_id,
          dc.document_id,
          dc.content,
          d.title,
          d.source_type,
          d.domain,
          0 as fts_score,
          1 - (dc.embedding <=> $4::vector(384)) as vector_score,
          dc.metadata_json
        FROM ai_document_chunks dc
        JOIN ai_documents d ON dc.document_id = d.id
        WHERE dc.seller_id = $2
          AND d.is_active = true
          ${domainFilter}
        ORDER BY dc.embedding <=> $4::vector(384)
        LIMIT $3 * 2
      )
      SELECT
        COALESCE(f.chunk_id, v.chunk_id) as chunk_id,
        COALESCE(f.document_id, v.document_id) as document_id,
        COALESCE(f.content, v.content) as content,
        COALESCE(f.title, v.title) as title,
        COALESCE(f.source_type, v.source_type) as source_type,
        COALESCE(f.domain, v.domain) as domain,
        COALESCE(f.fts_score, 0) * 0.3 + COALESCE(v.vector_score, 0) * 0.7 as combined_score,
        COALESCE(f.fts_score, 0) as fts_score,
        COALESCE(v.vector_score, 0) as vector_score,
        COALESCE(f.metadata_json, v.metadata_json) as metadata
      FROM fts_results f
      FULL OUTER JOIN vector_results v ON f.chunk_id = v.chunk_id
      ORDER BY combined_score DESC
      LIMIT $3
    `;

    return this.prisma.$queryRawUnsafe(
      query,
      queryText,
      sellerId,
      limit,
      embeddingString
    );
  }

  private async rerankResults(
    query: string,
    results: RetrievalResult[],
    topK: number
  ): Promise<RetrievalResult[]> {
    // Mock reranking for now - in production, use BGE reranker
    const reranked = results.map((result, index) => ({
      ...result,
      rerankScore: Math.random() * 0.3 + result.score * 0.7, // Mock reranking
    }));

    return reranked
      .sort((a, b) => (b.rerankScore || 0) - (a.rerankScore || 0))
      .slice(0, topK);
  }

  private async logQuery(
    sellerId: string,
    query: RetrievalQuery,
    results: RetrievalResult[],
    metrics: RetrievalMetrics,
    traceId?: string
  ) {
    const queryLog = await this.prisma.aiQueryLog.create({
      data: {
        sellerId,
        feature: 'RETRIEVAL',
        queryText: query.query,
        normalizedQueryText: query.query.toLowerCase().trim(),
        topK: query.topK || 10,
        latencyMs: metrics.queryLatencyMs,
        resultCount: metrics.resultCount,
        traceId,
      },
    });

    // Log individual results
    if (results.length > 0) {
      await this.prisma.aiQueryResult.createMany({
        data: results.map((result, index) => ({
          queryLogId: queryLog.id,
          chunkId: result.chunkId,
          retrievalScore: result.score,
          rerankScore: result.rerankScore,
          rank: index + 1,
          sourceRefJson: JSON.stringify({
            documentId: result.documentId,
            sourceType: result.sourceType,
            domain: result.domain,
            title: result.title,
          }),
        })),
      });
    }
  }

  async getSimilarDocuments(
    sellerId: string,
    documentId: string,
    limit: number = 5
  ): Promise<RetrievalResult[]> {
    // Get the document's embedding
    const document = await this.prisma.aiDocument.findUnique({
      where: { id: documentId },
      include: {
        chunks: {
          take: 1, // Just get the first chunk for similarity
          orderBy: { chunkIndex: 'asc' },
        },
      },
    });

    if (!document || document.chunks.length === 0) {
      return [];
    }

    const firstChunk = document.chunks[0];

    // Find similar chunks using vector similarity
    const similarChunks = await this.prisma.$queryRaw`
      SELECT
        dc.id as chunk_id,
        dc.document_id,
        d.title,
        dc.content,
        d.source_type,
        d.domain,
        1 - (dc.embedding <=> ${firstChunk}::vector(384)) as similarity,
        dc.metadata_json
      FROM ai_document_chunks dc
      JOIN ai_documents d ON dc.document_id = d.id
      WHERE dc.seller_id = ${sellerId}
        AND dc.document_id != ${documentId}
        AND d.is_active = true
        AND 1 - (dc.embedding <=> ${firstChunk}::vector(384)) >= 0.5
      ORDER BY dc.embedding <=> ${firstChunk}::vector(384)
      LIMIT ${limit}
    `;

    return (similarChunks as any[]).map(chunk => ({
      chunkId: chunk.chunk_id,
      documentId: chunk.document_id,
      title: chunk.title,
      content: chunk.content,
      sourceType: chunk.source_type,
      domain: chunk.domain,
      score: chunk.similarity,
      metadata: chunk.metadata_json ? JSON.parse(chunk.metadata_json) : undefined,
    }));
  }

  async getSearchAnalytics(
    sellerId: string,
    filters: {
      startDate?: Date;
      endDate?: Date;
      feature?: string;
    } = {}
  ) {
    const where: any = { sellerId };

    if (filters.startDate || filters.endDate) {
      where.createdAt = {};
      if (filters.startDate) where.createdAt.gte = filters.startDate;
      if (filters.endDate) where.createdAt.lte = filters.endDate;
    }

    if (filters.feature) {
      where.feature = filters.feature;
    }

    const analytics = await this.prisma.aiQueryLog.aggregate({
      where,
      _count: { id: true },
      _avg: { latencyMs: true, resultCount: true },
      _min: { latencyMs: true },
      _max: { latencyMs: true },
    });

    const topQueries = await this.prisma.aiQueryLog.groupBy({
      by: ['queryText'],
      where,
      _count: { id: true },
      orderBy: { _count: { id: 'desc' } },
      take: 10,
    });

    return {
      totalQueries: analytics._count.id || 0,
      averageLatency: analytics._avg.latencyMs || 0,
      averageResultCount: analytics._avg.resultCount || 0,
      minLatency: analytics._min.latencyMs || 0,
      maxLatency: analytics._max.latencyMs || 0,
      topQueries: topQueries.map(q => ({
        query: q.queryText,
        count: q._count.id,
      })),
    };
  }
}

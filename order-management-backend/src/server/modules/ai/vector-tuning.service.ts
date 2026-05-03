import { PrismaClient } from '@prisma/client';

export interface VectorIndexConfig {
  indexType: 'IVFFLAT' | 'HNSW';
  lists?: number;
  m?: number; // HNSW parameters
  efConstruction?: number;
  efSearch?: number;
}

export class VectorTuningService {
  constructor(private prisma: PrismaClient) { }

  async getOptimalIndexConfig(sellerId: string): Promise<VectorIndexConfig> {
    const stats = await this.getSellerVectorStats(sellerId);
    const rowCount = stats.totalChunks;

    if (rowCount < 10000) {
      // Small dataset - use IVFFlat with small lists
      return {
        indexType: 'IVFFLAT',
        lists: Math.min(rowCount / 10, 50),
      };
    } else if (rowCount < 1000000) {
      // Medium dataset - IVFFlat with moderate lists
      return {
        indexType: 'IVFFLAT',
        lists: Math.min(rowCount / 20, 500),
      };
    } else {
      // Large dataset - switch to HNSW
      return {
        indexType: 'HNSW',
        m: 16,
        efConstruction: 64,
        efSearch: 32,
      };
    }
  }

  async getSellerVectorStats(sellerId: string) {
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

  async createOptimizedIndex(sellerId: string): Promise<string> {
    const config = await this.getOptimalIndexConfig(sellerId);
    const indexName = `ai_chunks_${sellerId}_idx_${Date.now()}`;

    if (config.indexType === 'IVFFLAT') {
      await this.createIVFFlatIndex(indexName, sellerId, config.lists!);
    } else {
      await this.createHNSWIndex(indexName, sellerId, config);
    }

    return indexName;
  }

  private async createIVFFlatIndex(indexName: string, sellerId: string, lists: number) {
    const sql = `
      CREATE INDEX CONCURRENTLY ${indexName}
      ON ai_document_chunks
      USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = ${lists})
      WHERE seller_id = '${sellerId}';
    `;

    await this.prisma.$executeRawUnsafe(sql);
  }

  private async createHNSWIndex(indexName: string, sellerId: string, config: VectorIndexConfig) {
    const sql = `
      CREATE INDEX CONCURRENTLY ${indexName}
      ON ai_document_chunks
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = ${config.m}, ef_construction = ${config.efConstruction})
      WHERE seller_id = '${sellerId}';
    `;

    await this.prisma.$executeRawUnsafe(sql);
  }

  async dropOldIndexes(sellerId: string, keepLatest: number = 2) {
    // Get all indexes for this seller
    const indexes = await this.prisma.$queryRaw`
      SELECT indexname
      FROM pg_indexes
      WHERE tablename = 'ai_document_chunks'
        AND indexname LIKE 'ai_chunks_${sellerId}%'
      ORDER BY indexname DESC
    `;

    const indexNames = (indexes as any[]).map(idx => idx.indexname);

    // Keep only the latest N indexes
    const toDrop = indexNames.slice(keepLatest);

    for (const indexName of toDrop) {
      await this.prisma.$executeRawUnsafe(`DROP INDEX CONCURRENTLY ${indexName}`);
    }
  }

  async optimizeIndexPerformance(sellerId: string) {
    // Update table statistics for better query planning
    await this.prisma.$executeRawUnsafe(`
      ANALYZE ai_document_chunks;
    `);

    // Update vector index statistics
    await this.prisma.$executeRawUnsafe(`
      SELECT vector_index_stats('ai_document_chunks', 'embedding');
    `);
  }

  async getIndexPerformanceMetrics(sellerId: string) {
    // Get index usage statistics
    const indexStats = await this.prisma.$queryRaw`
      SELECT
        schemaname,
        tablename,
        indexname,
        idx_scan,
        idx_tup_read,
        idx_tup_fetch
      FROM pg_stat_user_indexes
      WHERE tablename = 'ai_document_chunks'
        AND indexname LIKE '%${sellerId}%'
    `;

    return indexStats;
  }

  async shouldReindex(sellerId: string): Promise<boolean> {
    const stats = await this.getSellerVectorStats(sellerId);
    const config = await this.getOptimalIndexConfig(sellerId);

    // Check if current index type matches optimal
    const currentIndexes = await this.prisma.$queryRaw`
      SELECT indexdef
      FROM pg_indexes
      WHERE tablename = 'ai_document_chunks'
        AND indexname LIKE '%${sellerId}%'
      LIMIT 1
    `;

    if ((currentIndexes as any[]).length === 0) {
      return true; // No index exists
    }

    const currentIndexDef = (currentIndexes as any[])[0]?.indexdef || '';

    // Check if we should switch from IVFFlat to HNSW
    if (stats.totalChunks > 1000000 && currentIndexDef.includes('ivfflat')) {
      return true;
    }

    // Check if lists parameter needs adjustment
    if (config.indexType === 'IVFFLAT' && config.lists) {
      const currentLists = this.extractListsFromIndexDef(currentIndexDef);
      if (Math.abs(currentLists - config.lists) > config.lists * 0.2) {
        return true; // Difference > 20%
      }
    }

    return false;
  }

  private extractListsFromIndexDef(indexDef: string): number {
    const match = indexDef.match(/lists\s*=\s*(\d+)/);
    return match ? parseInt(match[1]) : 100;
  }

  async scheduleReindexIfNeeded(sellerId: string) {
    if (await this.shouldReindex(sellerId)) {
      const newIndexName = await this.createOptimizedIndex(sellerId);
      await this.dropOldIndexes(sellerId);
      await this.optimizeIndexPerformance(sellerId);

      return {
        reindexed: true,
        newIndexName,
        message: 'Index reoptimized for current dataset size',
      };
    }

    return {
      reindexed: false,
      message: 'Current index configuration is optimal',
    };
  }
}

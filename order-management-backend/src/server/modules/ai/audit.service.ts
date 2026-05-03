import { PrismaClient } from '@prisma/client';

export interface CatalogAuditEvent {
  id: string;
  sellerId: string;
  eventType: 'DUPLICATE_DETECTED' | 'CANONICAL_MATCH' | 'MANUAL_APPROVAL' | 'MANUAL_REJECTION' | 'AUTO_MERGE';
  productId?: string;
  canonicalItemId?: string;
  matchScore?: number;
  previousStatus?: string;
  newStatus?: string;
  actorId?: string; // User who performed the action
  metadata?: Record<string, any>;
  createdAt: Date;
}

export interface CatalogNormalizationResult {
  success: boolean;
  duplicatesFound: number;
  autoMerged: number;
  manualReviewRequired: number;
  errors: string[];
  auditEvents: CatalogAuditEvent[];
}

export class CatalogAuditService {
  constructor(private prisma: PrismaClient) { }

  async logAuditEvent(event: Omit<CatalogAuditEvent, 'id' | 'createdAt'>) {
    const auditEvent = await this.prisma.$executeRaw`
      INSERT INTO catalog_audit_events (
        id, seller_id, event_type, product_id, canonical_item_id,
        match_score, previous_status, new_status, actor_id, metadata_json, created_at
      )
      VALUES (
        gen_random_uuid(),
        ${event.sellerId},
        ${event.eventType},
        ${event.productId || null},
        ${event.canonicalItemId || null},
        ${event.matchScore || null},
        ${event.previousStatus || null},
        ${event.newStatus || null},
        ${event.actorId || null},
        ${event.metadata ? JSON.stringify(event.metadata) : null},
        NOW()
      )
    `;

    return auditEvent;
  }

  async logDuplicateDetection(
    sellerId: string,
    productId: string,
    canonicalItemId: string,
    matchScore: number,
    metadata?: Record<string, any>
  ) {
    return this.logAuditEvent({
      sellerId,
      eventType: 'DUPLICATE_DETECTED',
      productId,
      canonicalItemId,
      matchScore,
      metadata: {
        ...metadata,
        detectionAlgorithm: 'vector_similarity',
        threshold: 0.9,
      },
    });
  }

  async logCanonicalMatch(
    sellerId: string,
    productId: string,
    canonicalItemId: string,
    matchScore: number,
    metadata?: Record<string, any>
  ) {
    return this.logAuditEvent({
      sellerId,
      eventType: 'CANONICAL_MATCH',
      productId,
      canonicalItemId,
      matchScore,
      metadata: {
        ...metadata,
        matchingAlgorithm: 'hybrid_search',
        confidence: matchScore > 0.95 ? 'high' : 'medium',
      },
    });
  }

  async logManualApproval(
    sellerId: string,
    productId: string,
    canonicalItemId: string,
    actorId: string,
    previousStatus: string,
    metadata?: Record<string, any>
  ) {
    return this.logAuditEvent({
      sellerId,
      eventType: 'MANUAL_APPROVAL',
      productId,
      canonicalItemId,
      previousStatus,
      newStatus: 'APPROVED',
      actorId,
      metadata: {
        ...metadata,
        approvalSource: 'manual_review',
      },
    });
  }

  async logManualRejection(
    sellerId: string,
    productId: string,
    canonicalItemId: string,
    actorId: string,
    previousStatus: string,
    reason: string,
    metadata?: Record<string, any>
  ) {
    return this.logAuditEvent({
      sellerId,
      eventType: 'MANUAL_REJECTION',
      productId,
      canonicalItemId,
      previousStatus,
      newStatus: 'REJECTED',
      actorId,
      metadata: {
        ...metadata,
        rejectionReason: reason,
        reviewSource: 'manual_review',
      },
    });
  }

  async logAutoMerge(
    sellerId: string,
    productId: string,
    canonicalItemId: string,
    matchScore: number,
    metadata?: Record<string, any>
  ) {
    return this.logAuditEvent({
      sellerId,
      eventType: 'AUTO_MERGE',
      productId,
      canonicalItemId,
      matchScore,
      newStatus: 'MERGED',
      metadata: {
        ...metadata,
        mergeType: 'automatic',
        confidence: 'high',
        threshold: 0.98,
      },
    });
  }

  async getAuditTrail(
    sellerId: string,
    filters: {
      startDate?: Date;
      endDate?: Date;
      eventType?: string;
      productId?: string;
      canonicalItemId?: string;
      actorId?: string;
    } = {}
  ): Promise<CatalogAuditEvent[]> {
    let whereClause = `WHERE seller_id = '${sellerId}'`;

    if (filters.startDate) {
      whereClause += ` AND created_at >= '${filters.startDate.toISOString()}'`;
    }
    if (filters.endDate) {
      whereClause += ` AND created_at <= '${filters.endDate.toISOString()}'`;
    }
    if (filters.eventType) {
      whereClause += ` AND event_type = '${filters.eventType}'`;
    }
    if (filters.productId) {
      whereClause += ` AND product_id = '${filters.productId}'`;
    }
    if (filters.canonicalItemId) {
      whereClause += ` AND canonical_item_id = '${filters.canonicalItemId}'`;
    }
    if (filters.actorId) {
      whereClause += ` AND actor_id = '${filters.actorId}'`;
    }

    const query = `
      SELECT
        id,
        seller_id as sellerId,
        event_type as eventType,
        product_id as productId,
        canonical_item_id as canonicalItemId,
        match_score as matchScore,
        previous_status as previousStatus,
        new_status as newStatus,
        actor_id as actorId,
        metadata_json as metadata,
        created_at as createdAt
      FROM catalog_audit_events
      ${whereClause}
      ORDER BY created_at DESC
      LIMIT 1000
    `;

    const results = await this.prisma.$queryRawUnsafe(query);

    return (results as any[]).map(row => ({
      ...row,
      metadata: row.metadata ? JSON.parse(row.metadata) : undefined,
    }));
  }

  async getAuditStats(sellerId: string, startDate?: Date, endDate?: Date) {
    let dateFilter = '';
    if (startDate || endDate) {
      if (startDate) dateFilter += ` AND created_at >= '${startDate.toISOString()}'`;
      if (endDate) dateFilter += ` AND created_at <= '${endDate.toISOString()}'`;
    }

    const stats = await this.prisma.$queryRaw`
      SELECT
        event_type,
        COUNT(*) as count,
        AVG(match_score) as avgScore,
        MIN(created_at) as firstOccurrence,
        MAX(created_at) as lastOccurrence
      FROM catalog_audit_events
      WHERE seller_id = ${sellerId}
        ${dateFilter ? this.prisma.$queryRawUnsafe(dateFilter) : this.prisma.$queryRaw``}
      GROUP BY event_type
      ORDER BY count DESC
    `;

    return stats;
  }

  async getNormalizationHistory(sellerId: string, productId: string) {
    const history = await this.prisma.$queryRaw`
      SELECT
        id,
        event_type as eventType,
        canonical_item_id as canonicalItemId,
        match_score as matchScore,
        previous_status as previousStatus,
        new_status as newStatus,
        actor_id as actorId,
        metadata_json as metadata,
        created_at as createdAt
      FROM catalog_audit_events
      WHERE seller_id = ${sellerId}
        AND product_id = ${productId}
      ORDER BY created_at ASC
    `;

    return (history as any[]).map(row => ({
      ...row,
      metadata: row.metadata ? JSON.parse(row.metadata) : undefined,
    }));
  }

  async createRollbackSnapshot(sellerId: string, reason: string) {
    const snapshot = await this.prisma.$queryRaw`
      INSERT INTO catalog_rollback_snapshots (
        id, seller_id, snapshot_data_json, reason, created_at
      )
      SELECT
        gen_random_uuid(),
        ${sellerId},
        json_agg(
          json_build_object(
            'productId', cm.product_id,
            'canonicalItemId', cm.canonical_item_id,
            'status', cm.status,
            'matchScore', cm.match_score
          )
        ),
        ${reason},
        NOW()
      FROM catalog_match_candidates cm
      WHERE cm.seller_id = ${sellerId}
      RETURNING id
    `;

    return (snapshot as any[])[0]?.id;
  }

  async rollbackToSnapshot(sellerId: string, snapshotId: string, actorId: string) {
    // Get snapshot data
    const snapshot = await this.prisma.$queryRaw`
      SELECT snapshot_data_json, reason, created_at
      FROM catalog_rollback_snapshots
      WHERE id = ${snapshotId} AND seller_id = ${sellerId}
    `;

    if (!snapshot || (snapshot as any[]).length === 0) {
      throw new Error('Snapshot not found');
    }

    const snapshotData = (snapshot as any[])[0];

    // Restore previous state
    for (const item of JSON.parse(snapshotData.snapshot_data_json)) {
      await this.prisma.$queryRaw`
        UPDATE catalog_match_candidates
        SET
          canonical_item_id = ${item.canonicalItemId},
          status = ${item.status},
          match_score = ${item.matchScore},
          reviewed_at = NULL,
          reviewed_by = NULL
        WHERE seller_id = ${sellerId} AND product_id = ${item.productId}
      `;
    }

    // Log rollback event
    await this.logAuditEvent({
      sellerId,
      eventType: 'MANUAL_REJECTION', // Using existing type for rollback
      previousStatus: 'ACTIVE',
      newStatus: 'ROLLED_BACK',
      actorId,
      metadata: {
        snapshotId,
        originalReason: snapshotData.reason,
        snapshotDate: snapshotData.created_at,
      },
    });
  }

  async detectAnomalies(sellerId: string, startDate?: Date, endDate?: Date) {
    // Detect unusual patterns in catalog normalization
    const anomalies = await this.prisma.$queryRaw`
      WITH event_stats AS (
        SELECT
          actor_id,
          event_type,
          COUNT(*) as event_count,
          DATE_TRUNC('hour', created_at) as hour
        FROM catalog_audit_events
        WHERE seller_id = ${sellerId}
          AND created_at >= COALESCE(${startDate || new Date(Date.now() - 24 * 60 * 60 * 1000)}, NOW() - INTERVAL '24 hours')
          AND created_at <= COALESCE(${endDate || new Date()}, NOW())
        GROUP BY actor_id, event_type, DATE_TRUNC('hour', created_at)
      ),
      avg_counts AS (
        SELECT
          actor_id,
          event_type,
          AVG(event_count) as avg_count,
          STDDEV(event_count) as stddev
        FROM event_stats
        GROUP BY actor_id, event_type
      )
      SELECT
        es.actor_id,
        es.event_type,
        es.hour,
        es.event_count,
        ac.avg_count,
        ac.stddev,
        (es.event_count - ac.avg_count) / NULLIF(ac.stddev, 0) as z_score
      FROM event_stats es
      JOIN avg_counts ac ON es.actor_id = ac.actor_id AND es.event_type = ac.event_type
      WHERE ABS(es.event_count - ac.avg_count) / NULLIF(ac.stddev, 0) > 2.5
      ORDER BY z_score DESC
    `;

    return anomalies;
  }
}

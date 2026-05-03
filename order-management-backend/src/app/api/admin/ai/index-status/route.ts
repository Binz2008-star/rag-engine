import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import { AiPolicyService } from '@/server/modules/ai/policy.service';
import { DocumentService } from '@/server/modules/ai/document.service';
import { EmbeddingService } from '@/server/modules/ai/embedding.service';

const prisma = new PrismaClient();
const policyService = new AiPolicyService(prisma);
const documentService = new DocumentService(prisma);
const embeddingService = new EmbeddingService(prisma);

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sellerId = searchParams.get('sellerId');

    if (!sellerId) {
      return NextResponse.json(
        { error: 'Seller ID is required' },
        { status: 400 }
      );
    }

    // Get policy status
    const policy = await policyService.getPolicy(sellerId);
    
    // Get document stats
    const documentStats = await documentService.getDocumentStats(sellerId);
    
    // Get embedding stats
    const embeddingStats = await embeddingService.getEmbeddingStats(sellerId);
    
    // Get recent indexing jobs
    const recentJobs = await prisma.aiIndexJob.findMany({
      where: { sellerId },
      orderBy: { createdAt: 'desc' },
      take: 10,
      select: {
        id: true,
        jobType: true,
        status: true,
        createdAt: true,
        lastError: true,
        attemptCount: true,
      },
    });

    // Get job queue stats
    const jobStats = await prisma.aiIndexJob.groupBy({
      by: ['status'],
      where: { sellerId },
      _count: { id: true },
    });

    return NextResponse.json({
      sellerId,
      policy: {
        retrievalEnabled: policy.retrievalEnabled,
        intentRoutingEnabled: policy.intentRoutingEnabled,
        catalogNormalizationEnabled: policy.catalogNormalizationEnabled,
        rerankEnabled: policy.rerankEnabled,
        benchmarkGatePassed: policy.benchmarkGatePassed,
        maxChunksPerQuery: policy.maxChunksPerQuery,
        minScoreThreshold: policy.minScoreThreshold,
        allowedDomains: policy.allowedDomainsJson ? JSON.parse(policy.allowedDomainsJson) : ['SUPPORT', 'PRODUCT', 'SELLER_KNOWLEDGE'],
      },
      documents: documentStats,
      embeddings: embeddingStats,
      jobs: {
        recent: recentJobs,
        stats: jobStats.reduce((acc, stat) => {
          acc[stat.status] = stat._count.id;
          return acc;
        }, {} as Record<string, number>),
      },
    });
  } catch (error) {
    console.error('Failed to get index status:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

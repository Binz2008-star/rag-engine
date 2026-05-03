import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import { AiPolicyService } from '@/server/modules/ai/policy.service';
import { RetrievalService } from '@/server/modules/ai/retrieval.service';
import { EmbeddingService } from '@/server/modules/ai/embedding.service';

const prisma = new PrismaClient();
const policyService = new AiPolicyService(prisma);
const embeddingService = new EmbeddingService(prisma);
const retrievalService = new RetrievalService(prisma, embeddingService);

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { query, topK = 10, domains, includeRerank = false, includeDebug = false } = body;

    // Validate input
    if (!query || typeof query !== 'string') {
      return NextResponse.json(
        { error: 'Query is required and must be a string' },
        { status: 400 }
      );
    }

    // Get seller ID from authentication (mock for now)
    const sellerId = request.headers.get('x-seller-id');
    if (!sellerId) {
      return NextResponse.json(
        { error: 'Seller authentication required' },
        { status: 401 }
      );
    }

    // Check if AI retrieval is enabled for this seller
    const isRetrievalEnabled = await policyService.isFeatureEnabled(sellerId, 'retrieval');
    if (!isRetrievalEnabled) {
      return NextResponse.json(
        { error: 'AI retrieval is not enabled for this seller' },
        { status: 403 }
      );
    }

    // Get allowed domains for this seller
    const allowedDomains = await policyService.getAllowedDomains(sellerId);
    const filteredDomains = domains ? 
      domains.filter((d: string) => allowedDomains.includes(d)) : 
      allowedDomains;

    // Generate trace ID for debugging
    const traceId = includeDebug ? `trace_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` : undefined;

    // Perform retrieval
    const { results, metrics } = await retrievalService.search(sellerId, {
      query,
      topK,
      domains: filteredDomains,
      includeRerank,
    }, traceId);

    // Format response
    const response = {
      results: results.map(result => ({
        id: result.chunkId,
        documentId: result.documentId,
        title: result.title,
        content: result.content,
        sourceType: result.sourceType,
        domain: result.domain,
        score: Math.round(result.score * 100) / 100,
        rerankScore: result.rerankScore ? Math.round(result.rerankScore * 100) / 100 : undefined,
        metadata: result.metadata,
      })),
      query: {
        text: query,
        topK,
        domains: filteredDomains,
        includeRerank,
      },
      metrics: {
        latencyMs: metrics.queryLatencyMs,
        resultCount: metrics.resultCount,
        rerankLatencyMs: metrics.rerankLatencyMs,
      },
    };

    // Add debug information if requested
    if (includeDebug && traceId) {
      (response as any).debug = {
        traceId,
        allowedDomains,
        filteredDomains,
        sellerId,
      };
    }

    return NextResponse.json(response);
  } catch (error) {
    console.error('Retrieval query failed:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    // Get seller ID from authentication (mock for now)
    const sellerId = request.headers.get('x-seller-id');
    if (!sellerId) {
      return NextResponse.json(
        { error: 'Seller authentication required' },
        { status: 401 }
      );
    }

    // Check if AI retrieval is enabled for this seller
    const isRetrievalEnabled = await policyService.isFeatureEnabled(sellerId, 'retrieval');
    if (!isRetrievalEnabled) {
      return NextResponse.json(
        { error: 'AI retrieval is not enabled for this seller' },
        { status: 403 }
      );
    }

    // Get search analytics for this seller
    const analytics = await retrievalService.getSearchAnalytics(sellerId, {
      startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // Last 30 days
    });

    // Get document stats
    const documentStats = await embeddingService.getEmbeddingStats(sellerId);

    return NextResponse.json({
      analytics,
      documentStats,
      sellerPolicy: {
        retrievalEnabled: isRetrievalEnabled,
        allowedDomains: await policyService.getAllowedDomains(sellerId),
      },
    });
  } catch (error) {
    console.error('Get retrieval stats failed:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

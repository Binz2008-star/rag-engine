import { DocumentService } from '@/server/modules/ai/document.service';
import { EmbeddingService } from '@/server/modules/ai/embedding.service';
import { AiPolicyService } from '@/server/modules/ai/policy.service';
import { PrismaClient } from '@prisma/client';
import { NextRequest, NextResponse } from 'next/server';

// Type definitions for database results
interface ProductRow {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  brand: string | null;
  sku: string | null;
  price: number;
  currency: string;
}

interface DocumentChunk {
  content: string;
  chunkIndex: number;
  documentId: string;
  sellerId: string;
  tokenCount: number;
}

interface ReindexPayload {
  sourceType: string;
  sourceId: string;
}

const prisma = new PrismaClient();
const policyService = new AiPolicyService(prisma);
const documentService = new DocumentService(prisma);
const embeddingService = new EmbeddingService(prisma);

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sellerId, jobType = 'FULL_REINDEX', sourceType, sourceId } = body;

    // Validate input
    if (!sellerId) {
      return NextResponse.json(
        { error: 'Seller ID is required' },
        { status: 400 }
      );
    }

    // Check if AI is enabled for this seller
    const isRetrievalEnabled = await policyService.isFeatureEnabled(sellerId, 'retrieval');
    if (!isRetrievalEnabled) {
      return NextResponse.json(
        { error: 'AI retrieval is not enabled for this seller' },
        { status: 403 }
      );
    }

    // Create indexing job
    const job = await prisma.aiIndexJob.create({
      data: {
        sellerId,
        jobType,
        status: 'PENDING',
        payloadJson: JSON.stringify({ sourceType, sourceId }),
      },
    });

    // Process indexing job asynchronously
    processIndexingJob(job.id).catch(console.error);

    return NextResponse.json({
      jobId: job.id,
      status: 'PENDING',
      message: 'Indexing job created and queued',
    });
  } catch (error) {
    console.error('Failed to create indexing job:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

async function processIndexingJob(jobId: string) {
  try {
    // Update job status to RUNNING
    await prisma.aiIndexJob.update({
      where: { id: jobId },
      data: { status: 'RUNNING' },
    });

    const job = await prisma.aiIndexJob.findUnique({
      where: { id: jobId },
    });

    if (!job) {
      throw new Error('Job not found');
    }

    const payload = JSON.parse(job.payloadJson || '{}');

    switch (job.jobType) {
      case 'FULL_REINDEX':
        await performFullReindex(job.sellerId);
        break;
      case 'UPSERT_DOCUMENT':
        await performDocumentUpsert(job.sellerId, payload);
        break;
      case 'DELETE_DOCUMENT':
        await performDocumentDelete(job.sellerId, payload);
        break;
      default:
        throw new Error(`Unknown job type: ${job.jobType}`);
    }

    // Mark job as completed
    await prisma.aiIndexJob.update({
      where: { id: jobId },
      data: { status: 'SUCCEEDED' },
    });
  } catch (error) {
    console.error(`Indexing job ${jobId} failed:`, error);

    // Mark job as failed
    await prisma.aiIndexJob.update({
      where: { id: jobId },
      data: {
        status: 'FAILED',
        lastError: error instanceof Error ? error.message : 'Unknown error',
        attemptCount: { increment: 1 },
      },
    });
  }
}

async function performFullReindex(sellerId: string) {
  // Index products
  await indexProducts(sellerId);

  // Index other content types can be added here
  // await indexPolicies(sellerId);
  // await indexFAQs(sellerId);
}

async function indexProducts(sellerId: string) {
  // Get all products for the seller
  const products = await prisma.$queryRaw`
    SELECT id, name, description, category, brand, sku, price, currency
    FROM products
    WHERE seller_id = ${sellerId}
  `;

  for (const product of products as ProductRow[]) {
    try {
      // Create AI document from product
      const document = await documentService.createDocumentFromSource(
        sellerId,
        { type: 'PRODUCT', data: product },
        'PRODUCT'
      );

      // Create chunks
      const chunks = await documentService.chunkDocument(document.id);

      // Map chunks to expected format for storeEmbeddings
      const mappedChunks = chunks.map((chunk: DocumentChunk) => ({
        content: chunk.content,
        index: chunk.chunkIndex,
        metadata: {
          documentId: chunk.documentId,
          sellerId: chunk.sellerId,
          tokenCount: chunk.tokenCount,
        }
      }));

      // Generate and store embeddings
      await embeddingService.storeEmbeddings(document.id, sellerId, mappedChunks);
    } catch (error) {
      console.error(`Failed to index product ${product.id}:`, error);
    }
  }
}

async function performDocumentUpsert(sellerId: string, payload: ReindexPayload) {
  const { sourceType, sourceId } = payload;

  if (!sourceType || !sourceId) {
    throw new Error('sourceType and sourceId are required for UPSERT_DOCUMENT');
  }

  // Handle different source types
  switch (sourceType) {
    case 'PRODUCT':
      await upsertProductDocument(sellerId, sourceId);
      break;
    default:
      throw new Error(`Unsupported source type: ${sourceType}`);
  }
}

async function upsertProductDocument(sellerId: string, productId: string) {
  const product = await prisma.$queryRaw`
    SELECT id, name, description, category, brand, sku, price, currency
    FROM products
    WHERE seller_id = ${sellerId} AND id = ${productId}
  `;

  if (!product || (product as ProductRow[]).length === 0) {
    throw new Error(`Product ${productId} not found`);
  }

  const productData = (product as ProductRow[])[0];

  // Create or update AI document
  const document = await documentService.createDocumentFromSource(
    sellerId,
    { type: 'PRODUCT', data: productData },
    'PRODUCT'
  );

  // Create chunks
  const chunks = await documentService.chunkDocument(document.id);

  // Map chunks to expected format for storeEmbeddings
  const mappedChunks = chunks.map((chunk: DocumentChunk) => ({
    content: chunk.content,
    index: chunk.chunkIndex,
    metadata: {
      documentId: chunk.documentId,
      sellerId: chunk.sellerId,
      tokenCount: chunk.tokenCount,
    }
  }));

  // Generate and store embeddings
  await embeddingService.storeEmbeddings(document.id, sellerId, mappedChunks);
}

async function performDocumentDelete(sellerId: string, payload: ReindexPayload) {
  const { sourceType, sourceId } = payload;

  if (!sourceType || !sourceId) {
    throw new Error('sourceType and sourceId are required for DELETE_DOCUMENT');
  }

  // Find and delete the document
  const document = await prisma.aiDocument.findFirst({
    where: {
      sellerId,
      sourceType,
      sourceId,
    },
  });

  if (document) {
    await documentService.deleteDocument(document.id);
  }
}

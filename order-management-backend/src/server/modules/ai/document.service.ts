import { PrismaClient } from '@prisma/client';
import crypto from 'crypto';

export interface DocumentSource {
  type: 'PRODUCT' | 'FAQ' | 'POLICY' | 'NOTE' | 'HELP_ARTICLE';
  id?: string;
  data: any;
}

export interface CreateDocumentInput {
  sellerId: string;
  domain: 'SUPPORT' | 'PRODUCT' | 'SELLER_KNOWLEDGE';
  sourceType: string;
  sourceId?: string;
  title: string;
  bodyText: string;
  languageCode?: string;
  metadata?: Record<string, any>;
}

export class DocumentService {
  constructor(private prisma: PrismaClient) { }

  async createDocument(input: CreateDocumentInput) {
    const checksum = this.generateChecksum(input.bodyText);

    // Check if document already exists (avoid duplicates)
    const existing = await this.prisma.aiDocument.findFirst({
      where: {
        sellerId: input.sellerId,
        sourceType: input.sourceType,
        sourceId: input.sourceId,
        checksum,
      },
    });

    if (existing) {
      return existing;
    }

    return this.prisma.aiDocument.create({
      data: {
        sellerId: input.sellerId,
        domain: input.domain,
        sourceType: input.sourceType,
        sourceId: input.sourceId,
        title: input.title,
        bodyText: input.bodyText,
        languageCode: input.languageCode || 'en',
        checksum,
      },
    });
  }

  async createDocumentFromSource(
    sellerId: string,
    source: DocumentSource,
    domain: 'SUPPORT' | 'PRODUCT' | 'SELLER_KNOWLEDGE'
  ) {
    switch (source.type) {
      case 'PRODUCT':
        return this.createProductDocument(sellerId, source.data, domain);
      case 'FAQ':
        return this.createFaqDocument(sellerId, source.data, domain);
      case 'POLICY':
        return this.createPolicyDocument(sellerId, source.data, domain);
      case 'NOTE':
        return this.createNoteDocument(sellerId, source.data, domain);
      case 'HELP_ARTICLE':
        return this.createHelpArticleDocument(sellerId, source.data, domain);
      default:
        throw new Error(`Unsupported source type: ${source.type}`);
    }
  }

  private async createProductDocument(sellerId: string, product: any, domain: 'SUPPORT' | 'PRODUCT' | 'SELLER_KNOWLEDGE') {
    const title = product.name || product.title || 'Untitled Product';
    const bodyText = [
      title,
      product.description || '',
      product.category || '',
      product.brand || '',
      product.tags ? product.tags.join(' ') : '',
      product.sku || '',
    ].filter(Boolean).join('\n');

    return this.createDocument({
      sellerId,
      domain,
      sourceType: 'PRODUCT',
      sourceId: product.id,
      title,
      bodyText,
      languageCode: this.detectLanguage(bodyText),
      metadata: {
        category: product.category,
        brand: product.brand,
        sku: product.sku,
        price: product.price,
        currency: product.currency,
      },
    });
  }

  private async createFaqDocument(sellerId: string, faq: any, domain: 'SUPPORT' | 'PRODUCT' | 'SELLER_KNOWLEDGE') {
    const title = faq.question || faq.title || 'FAQ';
    const bodyText = [
      title,
      faq.answer || faq.content || '',
      faq.category || '',
      faq.tags ? faq.tags.join(' ') : '',
    ].filter(Boolean).join('\n');

    return this.createDocument({
      sellerId,
      domain,
      sourceType: 'FAQ',
      sourceId: faq.id,
      title,
      bodyText,
      languageCode: this.detectLanguage(bodyText),
      metadata: {
        category: faq.category,
        priority: faq.priority,
        tags: faq.tags,
      },
    });
  }

  private async createPolicyDocument(sellerId: string, policy: any, domain: 'SUPPORT' | 'PRODUCT' | 'SELLER_KNOWLEDGE') {
    const title = policy.title || policy.name || 'Policy';
    const bodyText = [
      title,
      policy.content || policy.description || '',
      policy.type || '',
      policy.category || '',
    ].filter(Boolean).join('\n');

    return this.createDocument({
      sellerId,
      domain,
      sourceType: 'POLICY',
      sourceId: policy.id,
      title,
      bodyText,
      languageCode: this.detectLanguage(bodyText),
      metadata: {
        type: policy.type,
        category: policy.category,
        effectiveDate: policy.effectiveDate,
      },
    });
  }

  private async createNoteDocument(sellerId: string, note: any, domain: 'SUPPORT' | 'PRODUCT' | 'SELLER_KNOWLEDGE') {
    const title = note.title || note.subject || 'Note';
    const bodyText = [
      title,
      note.content || note.body || '',
      note.category || '',
      note.tags ? note.tags.join(' ') : '',
    ].filter(Boolean).join('\n');

    return this.createDocument({
      sellerId,
      domain,
      sourceType: 'NOTE',
      sourceId: note.id,
      title,
      bodyText,
      languageCode: this.detectLanguage(bodyText),
      metadata: {
        category: note.category,
        priority: note.priority,
        tags: note.tags,
        author: note.author,
      },
    });
  }

  private async createHelpArticleDocument(sellerId: string, article: any, domain: 'SUPPORT' | 'PRODUCT' | 'SELLER_KNOWLEDGE') {
    const title = article.title || article.headline || 'Help Article';
    const bodyText = [
      title,
      article.content || article.body || '',
      article.summary || '',
      article.category || '',
      article.tags ? article.tags.join(' ') : '',
    ].filter(Boolean).join('\n');

    return this.createDocument({
      sellerId,
      domain,
      sourceType: 'HELP_ARTICLE',
      sourceId: article.id,
      title,
      bodyText,
      languageCode: this.detectLanguage(bodyText),
      metadata: {
        category: article.category,
        priority: article.priority,
        tags: article.tags,
        author: article.author,
        lastUpdated: article.lastUpdated,
      },
    });
  }

  async updateDocument(documentId: string, updates: Partial<CreateDocumentInput>) {
    const updateData: any = {};

    if (updates.title) updateData.title = updates.title;
    if (updates.bodyText) {
      updateData.bodyText = updates.bodyText;
      updateData.checksum = this.generateChecksum(updates.bodyText);
    }
    if (updates.languageCode) updateData.languageCode = updates.languageCode;

    return this.prisma.aiDocument.update({
      where: { id: documentId },
      data: updateData,
    });
  }

  async deactivateDocument(documentId: string) {
    return this.prisma.aiDocument.update({
      where: { id: documentId },
      data: { isActive: false },
    });
  }

  async deleteDocument(documentId: string) {
    // This will cascade delete chunks due to the relation
    return this.prisma.aiDocument.delete({
      where: { id: documentId },
    });
  }

  async getDocumentsBySeller(
    sellerId: string,
    filters: {
      domain?: string;
      sourceType?: string;
      isActive?: boolean;
    } = {}
  ) {
    const where: any = { sellerId };

    if (filters.domain) where.domain = filters.domain;
    if (filters.sourceType) where.sourceType = filters.sourceType;
    if (filters.isActive !== undefined) where.isActive = filters.isActive;

    return this.prisma.aiDocument.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      include: {
        chunks: {
          select: {
            id: true,
            chunkIndex: true,
            tokenCount: true,
            createdAt: true,
          },
        },
      },
    });
  }

  async getDocumentStats(sellerId: string) {
    const totalDocuments = await this.prisma.aiDocument.count({
      where: { sellerId },
    });

    const chunkStats = await this.prisma.aiDocumentChunk.aggregate({
      where: { sellerId },
      _count: { id: true },
      _sum: { tokenCount: true },
    });

    // Get breakdown by domain and sourceType
    const documents = await this.prisma.aiDocument.findMany({
      where: { sellerId },
      select: { domain: true, sourceType: true },
    });

    const breakdown = documents.reduce((acc, doc) => {
      const key = `${doc.domain}-${doc.sourceType}`;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    return {
      totalDocuments,
      totalChunks: chunkStats._count.id || 0,
      totalTokens: chunkStats._sum.tokenCount || 0,
      breakdown: Object.entries(breakdown).map(([key, count]) => {
        const [domain, sourceType] = key.split('-');
        return { domain, sourceType, count };
      }),
    };
  }

  private generateChecksum(text: string): string {
    return crypto.createHash('sha256').update(text).digest('hex');
  }

  private detectLanguage(text: string): string {
    // Simple language detection - in production, use a proper library
    const arabicPattern = /[\u0600-\u06FF]/;
    return arabicPattern.test(text) ? 'ar' : 'en';
  }

  async chunkDocument(documentId: string, maxChunkSize: number = 500, overlap: number = 50) {
    const document = await this.prisma.aiDocument.findUnique({
      where: { id: documentId },
    });

    if (!document) {
      throw new Error('Document not found');
    }

    const chunks = this.createTextChunks(document.bodyText, maxChunkSize, overlap);

    return chunks.map((chunk, index) => ({
      documentId,
      sellerId: document.sellerId,
      chunkIndex: index,
      content: chunk,
      tokenCount: this.estimateTokenCount(chunk),
      metadataJson: JSON.stringify({
        chunkIndex: index,
        totalChunks: chunks.length,
        documentTitle: document.title,
      }),
    }));
  }

  private createTextChunks(text: string, maxSize: number, overlap: number): string[] {
    const words = text.split(/\s+/);
    const chunks: string[] = [];

    for (let i = 0; i < words.length; i += maxSize - overlap) {
      const chunk = words.slice(i, i + maxSize).join(' ');
      chunks.push(chunk);

      if (i + maxSize >= words.length) break;
    }

    return chunks;
  }

  private estimateTokenCount(text: string): number {
    return Math.ceil(text.length / 4);
  }
}

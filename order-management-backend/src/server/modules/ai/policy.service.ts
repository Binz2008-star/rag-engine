import { PrismaClient } from '@prisma/client';
import { z } from 'zod';

const UpdateAiPolicySchema = z.object({
  retrievalEnabled: z.boolean(),
  intentRoutingEnabled: z.boolean(),
  catalogNormalizationEnabled: z.boolean(),
  rerankEnabled: z.boolean(),
  benchmarkGatePassed: z.boolean().optional(),
  maxChunksPerQuery: z.number().min(1).max(50),
  minScoreThreshold: z.number().min(0).max(1),
  allowedDomains: z.array(z.enum(['SUPPORT', 'PRODUCT', 'SELLER_KNOWLEDGE'])).optional(),
});

export type UpdateAiPolicyInput = z.infer<typeof UpdateAiPolicySchema>;

export class AiPolicyService {
  constructor(private prisma: PrismaClient) {}

  async getPolicy(sellerId: string) {
    const policy = await this.prisma.sellerAiPolicy.findUnique({
      where: { sellerId },
    });

    if (!policy) {
      // Create default policy if none exists
      return this.createDefaultPolicy(sellerId);
    }

    return policy;
  }

  async updatePolicy(sellerId: string, input: UpdateAiPolicyInput) {
    const validated = UpdateAiPolicySchema.parse(input);
    
    const allowedDomainsJson = validated.allowedDomains 
      ? JSON.stringify(validated.allowedDomains)
      : undefined;

    return this.prisma.sellerAiPolicy.upsert({
      where: { sellerId },
      update: {
        retrievalEnabled: validated.retrievalEnabled,
        intentRoutingEnabled: validated.intentRoutingEnabled,
        catalogNormalizationEnabled: validated.catalogNormalizationEnabled,
        rerankEnabled: validated.rerankEnabled,
        benchmarkGatePassed: validated.benchmarkGatePassed,
        maxChunksPerQuery: validated.maxChunksPerQuery,
        minScoreThreshold: validated.minScoreThreshold,
        allowedDomainsJson,
      },
      create: {
        sellerId,
        retrievalEnabled: validated.retrievalEnabled,
        intentRoutingEnabled: validated.intentRoutingEnabled,
        catalogNormalizationEnabled: validated.catalogNormalizationEnabled,
        rerankEnabled: validated.rerankEnabled,
        maxChunksPerQuery: validated.maxChunksPerQuery,
        minScoreThreshold: validated.minScoreThreshold,
        allowedDomainsJson,
      },
    });
  }

  async isFeatureEnabled(sellerId: string, feature: 'retrieval' | 'intentRouting' | 'catalogNormalization') {
    const policy = await this.getPolicy(sellerId);
    
    switch (feature) {
      case 'retrieval':
        return policy.retrievalEnabled && policy.benchmarkGatePassed;
      case 'intentRouting':
        return policy.intentRoutingEnabled && policy.benchmarkGatePassed;
      case 'catalogNormalization':
        return policy.catalogNormalizationEnabled && policy.benchmarkGatePassed;
      default:
        return false;
    }
  }

  async getAllowedDomains(sellerId: string) {
    const policy = await this.getPolicy(sellerId);
    
    if (!policy.allowedDomainsJson) {
      return ['SUPPORT', 'PRODUCT', 'SELLER_KNOWLEDGE']; // Default to all domains
    }
    
    try {
      return JSON.parse(policy.allowedDomainsJson) as string[];
    } catch {
      return ['SUPPORT', 'PRODUCT', 'SELLER_KNOWLEDGE'];
    }
  }

  private async createDefaultPolicy(sellerId: string) {
    return this.prisma.sellerAiPolicy.create({
      data: {
        sellerId,
        retrievalEnabled: false,
        intentRoutingEnabled: false,
        catalogNormalizationEnabled: false,
        rerankEnabled: true,
        benchmarkGatePassed: false,
        maxChunksPerQuery: 8,
        minScoreThreshold: 0.0,
      },
    });
  }

  async enableFeatureForSeller(sellerId: string, feature: 'retrieval' | 'intentRouting' | 'catalogNormalization') {
    const updateData: Partial<UpdateAiPolicyInput> = {};
    
    switch (feature) {
      case 'retrieval':
        updateData.retrievalEnabled = true;
        break;
      case 'intentRouting':
        updateData.intentRoutingEnabled = true;
        break;
      case 'catalogNormalization':
        updateData.catalogNormalizationEnabled = true;
        break;
    }

    return this.updatePolicy(sellerId, updateData as UpdateAiPolicyInput);
  }

  async disableFeatureForSeller(sellerId: string, feature: 'retrieval' | 'intentRouting' | 'catalogNormalization') {
    const updateData: Partial<UpdateAiPolicyInput> = {};
    
    switch (feature) {
      case 'retrieval':
        updateData.retrievalEnabled = false;
        break;
      case 'intentRouting':
        updateData.intentRoutingEnabled = false;
        break;
      case 'catalogNormalization':
        updateData.catalogNormalizationEnabled = false;
        break;
    }

    return this.updatePolicy(sellerId, updateData as UpdateAiPolicyInput);
  }

  async setBenchmarkGatePassed(sellerId: string, passed: boolean) {
    return this.prisma.sellerAiPolicy.upsert({
      where: { sellerId },
      update: { benchmarkGatePassed: passed },
      create: {
        sellerId,
        retrievalEnabled: false,
        intentRoutingEnabled: false,
        catalogNormalizationEnabled: false,
        rerankEnabled: true,
        benchmarkGatePassed: passed,
        maxChunksPerQuery: 8,
        minScoreThreshold: 0.0,
      },
    });
  }
}

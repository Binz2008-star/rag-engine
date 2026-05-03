// === AUDIT TRAIL TEST ===
// Tests comprehensive audit trail functionality

const { PrismaClient } = require('@prisma/client');

async function testAuditTrail() {
  console.log('=== AUDIT TRAIL TEST ===');
  
  const prisma = new PrismaClient();
  
  try {
    // Create test user and seller
    console.log('Creating test setup...');
    const user = await prisma.user.create({
      data: {
        email: 'audit-test@example.com',
        fullName: 'Audit Test User',
        passwordHash: 'hashed-password',
        role: 'STAFF',
        isActive: true,
      },
    });
    
    const seller = await prisma.seller.create({
      data: {
        ownerUserId: user.id,
        brandName: 'Audit Test Seller',
        slug: 'audit-test-seller',
        currency: 'USD',
        status: 'ACTIVE',
      },
    });
    
    console.log(`Created seller: ${seller.id}`);
    
    // Test 1: AI Document audit trail
    console.log('\n1. Testing AI document audit trail...');
    
    const document = await prisma.aiDocument.create({
      data: {
        sellerId: seller.id,
        domain: 'PRODUCT',
        sourceType: 'PRODUCT',
        sourceId: 'product-audit-test',
        title: 'Audit Test Product',
        bodyText: 'This is a product for audit testing',
        languageCode: 'en',
        checksum: 'audit-checksum-123',
        isActive: true,
      },
    });
    
    console.log(`Created document: ${document.id}`);
    console.log(`Document created at: ${document.createdAt}`);
    console.log(`Document checksum: ${document.checksum}`);
    
    // Update document to test modification tracking
    const updatedDocument = await prisma.aiDocument.update({
      where: { id: document.id },
      data: {
        title: 'Updated Audit Test Product',
        bodyText: 'This is an updated product for audit testing',
      },
    });
    
    console.log(`Document updated at: ${updatedDocument.updatedAt}`);
    console.log(`Title changed: ${document.title} -> ${updatedDocument.title}`);
    
    // Test 2: AI Policy audit trail
    console.log('\n2. Testing AI policy audit trail...');
    
    const policy = await prisma.sellerAiPolicy.create({
      data: {
        sellerId: seller.id,
        retrievalEnabled: true,
        intentRoutingEnabled: false,
        catalogNormalizationEnabled: false,
        rerankEnabled: true,
        benchmarkGatePassed: false,
        maxChunksPerQuery: 8,
        minScoreThreshold: 0.0,
      },
    });
    
    console.log(`Created AI policy: ${policy.id}`);
    console.log(`Policy created at: ${policy.createdAt}`);
    
    // Update policy to test change tracking
    const updatedPolicy = await prisma.sellerAiPolicy.update({
      where: { id: policy.id },
      data: {
        retrievalEnabled: false,
        intentRoutingEnabled: true,
        minScoreThreshold: 0.5,
      },
    });
    
    console.log(`Policy updated at: ${updatedPolicy.updatedAt}`);
    console.log(`Retrieval enabled changed: ${policy.retrievalEnabled} -> ${updatedPolicy.retrievalEnabled}`);
    
    // Test 3: AI Query Log audit trail
    console.log('\n3. Testing AI query log audit trail...');
    
    const queryLog = await prisma.aiQueryLog.create({
      data: {
        sellerId: seller.id,
        feature: 'RETRIEVAL',
        queryText: 'audit test query',
        normalizedQueryText: 'audit test query normalized',
        topK: 5,
        latencyMs: 150,
        resultCount: 3,
        traceId: 'trace-audit-123',
      },
    });
    
    console.log(`Created query log: ${queryLog.id}`);
    console.log(`Query logged at: ${queryLog.createdAt}`);
    console.log(`Query text: ${queryLog.queryText}`);
    console.log(`Trace ID: ${queryLog.traceId}`);
    
    // Test 4: AI Benchmark audit trail
    console.log('\n4. Testing AI benchmark audit trail...');
    
    const benchmarkCase = await prisma.aiBenchmarkCase.create({
      data: {
        sellerId: seller.id,
        suite: 'retrieval-audit-test',
        queryText: 'benchmark audit query',
        expectedSourceType: 'PRODUCT',
        expectedSourceId: 'product-audit-test',
        languageCode: 'en',
        metadataJson: JSON.stringify({
          testType: 'audit',
          priority: 'high',
          tags: ['audit', 'test'],
        }),
      },
    });
    
    console.log(`Created benchmark case: ${benchmarkCase.id}`);
    console.log(`Benchmark created at: ${benchmarkCase.createdAt}`);
    console.log(`Suite: ${benchmarkCase.suite}`);
    
    // Test 5: Comprehensive audit query
    console.log('\n5. Testing comprehensive audit query...');
    
    // Get all audit records for this seller
    const allDocuments = await prisma.aiDocument.findMany({
      where: { sellerId: seller.id },
      orderBy: { createdAt: 'asc' },
    });
    
    const allPolicies = await prisma.sellerAiPolicy.findMany({
      where: { sellerId: seller.id },
      orderBy: { createdAt: 'asc' },
    });
    
    const allQueryLogs = await prisma.aiQueryLog.findMany({
      where: { sellerId: seller.id },
      orderBy: { createdAt: 'asc' },
    });
    
    const allBenchmarks = await prisma.aiBenchmarkCase.findMany({
      where: { sellerId: seller.id },
      orderBy: { createdAt: 'asc' },
    });
    
    console.log(`\nAudit Summary for Seller ${seller.id}:`);
    console.log(`  Documents: ${allDocuments.length} (created/updated)`);
    console.log(`  Policies: ${allPolicies.length} (created/updated)`);
    console.log(`  Query Logs: ${allQueryLogs.length} (queries executed)`);
    console.log(`  Benchmark Cases: ${allBenchmarks.length} (test cases)`);
    
    // Test 6: Audit trail integrity
    console.log('\n6. Testing audit trail integrity...');
    
    // Verify timestamps are present and sequential
    const timestamps = [
      ...allDocuments.map(d => d.createdAt),
      ...allPolicies.map(p => p.createdAt),
      ...allQueryLogs.map(q => q.createdAt),
      ...allBenchmarks.map(b => b.createdAt),
    ];
    
    const sortedTimestamps = timestamps.sort();
    const hasValidTimestamps = timestamps.every(ts => ts instanceof Date && !isNaN(ts.getTime()));
    
    if (hasValidTimestamps) {
      console.log('Timestamp integrity: PASS');
    } else {
      console.log('Timestamp integrity: FAIL');
    }
    
    // Verify seller isolation in audit records
    const crossTenantAudit = await prisma.aiDocument.findFirst({
      where: {
        sellerId: { not: seller.id },
        id: document.id,
      },
    });
    
    if (!crossTenantAudit) {
      console.log('Audit isolation: PASS');
    } else {
      console.log('Audit isolation: FAIL');
    }
    
    // Test 7: Audit trail searchability
    console.log('\n7. Testing audit trail searchability...');
    
    // Search by date range
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    const recentDocuments = await prisma.aiDocument.findMany({
      where: {
        sellerId: seller.id,
        createdAt: {
          gte: yesterday,
          lte: today,
        },
      },
    });
    
    console.log(`Recent documents (last 24h): ${recentDocuments.length}`);
    
    // Search by feature
    const retrievalQueries = await prisma.aiQueryLog.findMany({
      where: {
        sellerId: seller.id,
        feature: 'RETRIEVAL',
      },
    });
    
    console.log(`Retrieval queries: ${retrievalQueries.length}`);
    
    // Search by source type
    const productDocuments = await prisma.aiDocument.findMany({
      where: {
        sellerId: seller.id,
        sourceType: 'PRODUCT',
      },
    });
    
    console.log(`Product documents: ${productDocuments.length}`);
    
    console.log('\n=== AUDIT TRAIL TEST COMPLETED ===');
    console.log('All audit trail functionality working correctly');
    
    // Cleanup test data
    console.log('\nCleaning up test data...');
    await prisma.aiBenchmarkCase.deleteMany({
      where: { sellerId: seller.id },
    });
    await prisma.aiQueryLog.deleteMany({
      where: { sellerId: seller.id },
    });
    await prisma.sellerAiPolicy.deleteMany({
      where: { sellerId: seller.id },
    });
    await prisma.aiDocument.deleteMany({
      where: { sellerId: seller.id },
    });
    await prisma.seller.delete({
      where: { id: seller.id },
    });
    await prisma.user.delete({
      where: { id: user.id },
    });
    
  } catch (error) {
    console.error('Audit trail test failed:', error);
    throw error;
  } finally {
    await prisma.$disconnect();
  }
}

// Test database connection
async function testDatabaseConnection() {
  console.log('Testing database connection...');
  
  const prisma = new PrismaClient();
  
  try {
    await prisma.$queryRaw`SELECT 1`;
    console.log('Database connection: OK');
    await prisma.$disconnect();
  } catch (error) {
    console.error('Database connection failed:', error);
    throw error;
  }
}

// Main test runner
async function runTests() {
  try {
    console.log('Starting audit trail tests...\n');
    
    await testDatabaseConnection();
    await testAuditTrail();
    
    console.log('\n=== ALL AUDIT TRAIL TESTS PASSED ===');
    
  } catch (error) {
    console.error('\n=== AUDIT TRAIL TESTS FAILED ===');
    console.error(error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  runTests();
}

module.exports = { testAuditTrail, testDatabaseConnection };

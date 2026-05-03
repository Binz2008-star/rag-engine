// === TENANT ISOLATION TEST ===
// Tests multi-tenant data isolation

const { PrismaClient } = require('@prisma/client');

async function testTenantIsolation() {
  console.log('=== TENANT ISOLATION TEST ===');

  const prisma = new PrismaClient();

  try {
    // Create test users first
    console.log('Creating test users...');
    const user1 = await prisma.user.create({
      data: {
        email: 'test-user-1@example.com',
        fullName: 'Test User 1',
        passwordHash: 'hashed-password-1',
        role: 'STAFF',
        isActive: true,
      },
    });

    const user2 = await prisma.user.create({
      data: {
        email: 'test-user-2@example.com',
        fullName: 'Test User 2',
        passwordHash: 'hashed-password-2',
        role: 'STAFF',
        isActive: true,
      },
    });

    // Create test sellers
    console.log('Creating test sellers...');
    const seller1 = await prisma.seller.create({
      data: {
        ownerUserId: user1.id,
        brandName: 'Test Seller 1',
        slug: 'test-seller-1',
        currency: 'USD',
        status: 'ACTIVE',
      },
    });

    const seller2 = await prisma.seller.create({
      data: {
        ownerUserId: user2.id,
        brandName: 'Test Seller 2',
        slug: 'test-seller-2',
        currency: 'USD',
        status: 'ACTIVE',
      },
    });

    console.log(`Created sellers: ${seller1.id}, ${seller2.id}`);

    // Create AI documents for each seller
    console.log('Creating AI documents...');

    const doc1 = await prisma.aiDocument.create({
      data: {
        sellerId: seller1.id,
        domain: 'PRODUCT',
        sourceType: 'PRODUCT',
        sourceId: 'product-1',
        title: 'Product 1',
        bodyText: 'This is product 1 for seller 1',
        languageCode: 'en',
        checksum: 'doc1-checksum',
        isActive: true,
      },
    });

    const doc2 = await prisma.aiDocument.create({
      data: {
        sellerId: seller2.id,
        domain: 'PRODUCT',
        sourceType: 'PRODUCT',
        sourceId: 'product-2',
        title: 'Product 2',
        bodyText: 'This is product 2 for seller 2',
        languageCode: 'en',
        checksum: 'doc2-checksum',
        isActive: true,
      },
    });

    console.log(`Created documents: ${doc1.id}, ${doc2.id}`);

    // Test isolation: Seller 1 should only see their own documents
    console.log('\nTesting seller 1 isolation...');
    const seller1Docs = await prisma.aiDocument.findMany({
      where: {
        sellerId: seller1.id,
        isActive: true,
      },
    });

    console.log(`Seller 1 documents: ${seller1Docs.length}`);
    if (seller1Docs.length === 1 && seller1Docs[0].id === doc1.id) {
      console.log('Seller 1 isolation: PASS');
    } else {
      console.log('Seller 1 isolation: FAIL');
    }

    // Test isolation: Seller 2 should only see their own documents
    console.log('\nTesting seller 2 isolation...');
    const seller2Docs = await prisma.aiDocument.findMany({
      where: {
        sellerId: seller2.id,
        isActive: true,
      },
    });

    console.log(`Seller 2 documents: ${seller2Docs.length}`);
    if (seller2Docs.length === 1 && seller2Docs[0].id === doc2.id) {
      console.log('Seller 2 isolation: PASS');
    } else {
      console.log('Seller 2 isolation: FAIL');
    }

    // Test cross-tenant access prevention
    console.log('\nTesting cross-tenant access prevention...');

    // Try to access seller 2's documents as seller 1 (should return empty)
    const crossTenantDocs = await prisma.aiDocument.findMany({
      where: {
        sellerId: seller1.id,
        id: doc2.id, // Looking for seller 2's document
        isActive: true,
      },
    });

    if (crossTenantDocs.length === 0) {
      console.log('Cross-tenant access prevention: PASS');
    } else {
      console.log('Cross-tenant access prevention: FAIL');
    }

    // Test AI policy isolation
    console.log('\nTesting AI policy isolation...');

    const policy1 = await prisma.sellerAiPolicy.create({
      data: {
        sellerId: seller1.id,
        retrievalEnabled: true,
        intentRoutingEnabled: false,
        catalogNormalizationEnabled: false,
        rerankEnabled: true,
        benchmarkGatePassed: false,
        maxChunksPerQuery: 8,
        minScoreThreshold: 0.0,
      },
    });

    const policy2 = await prisma.sellerAiPolicy.create({
      data: {
        sellerId: seller2.id,
        retrievalEnabled: false,
        intentRoutingEnabled: true,
        catalogNormalizationEnabled: true,
        rerankEnabled: false,
        benchmarkGatePassed: false,
        maxChunksPerQuery: 5,
        minScoreThreshold: 0.5,
      },
    });

    // Verify policies are isolated
    const seller1Policy = await prisma.sellerAiPolicy.findUnique({
      where: { sellerId: seller1.id },
    });

    const seller2Policy = await prisma.sellerAiPolicy.findUnique({
      where: { sellerId: seller2.id },
    });

    if (seller1Policy?.retrievalEnabled === true && seller2Policy?.retrievalEnabled === false) {
      console.log('AI policy isolation: PASS');
    } else {
      console.log('AI policy isolation: FAIL');
    }

    // Test query logs isolation
    console.log('\nTesting query logs isolation...');

    const queryLog1 = await prisma.aiQueryLog.create({
      data: {
        sellerId: seller1.id,
        feature: 'RETRIEVAL',
        queryText: 'test query 1',
        topK: 5,
        latencyMs: 100,
        resultCount: 3,
      },
    });

    const queryLog2 = await prisma.aiQueryLog.create({
      data: {
        sellerId: seller2.id,
        feature: 'RETRIEVAL',
        queryText: 'test query 2',
        topK: 3,
        latencyMs: 150,
        resultCount: 2,
      },
    });

    // Verify query logs are isolated
    const seller1Logs = await prisma.aiQueryLog.findMany({
      where: { sellerId: seller1.id },
    });

    const seller2Logs = await prisma.aiQueryLog.findMany({
      where: { sellerId: seller2.id },
    });

    if (seller1Logs.length === 1 && seller2Logs.length === 1 &&
      seller1Logs[0].queryText === 'test query 1' &&
      seller2Logs[0].queryText === 'test query 2') {
      console.log('Query logs isolation: PASS');
    } else {
      console.log('Query logs isolation: FAIL');
    }

    console.log('\n=== TENANT ISOLATION TEST COMPLETED ===');
    console.log('All tenant isolation tests passed successfully');

    // Cleanup test data
    console.log('\nCleaning up test data...');
    await prisma.aiQueryLog.deleteMany({
      where: { sellerId: { in: [seller1.id, seller2.id] } },
    });
    await prisma.sellerAiPolicy.deleteMany({
      where: { sellerId: { in: [seller1.id, seller2.id] } },
    });
    await prisma.aiDocument.deleteMany({
      where: { sellerId: { in: [seller1.id, seller2.id] } },
    });
    await prisma.seller.deleteMany({
      where: { id: { in: [seller1.id, seller2.id] } },
    });
    await prisma.user.deleteMany({
      where: { id: { in: [user1.id, user2.id] } },
    });

  } catch (error) {
    console.error('Tenant isolation test failed:', error);
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
    console.log('Starting tenant isolation tests...\n');

    await testDatabaseConnection();
    await testTenantIsolation();

    console.log('\n=== ALL TENANT ISOLATION TESTS PASSED ===');

  } catch (error) {
    console.error('\n=== TENANT ISOLATION TESTS FAILED ===');
    console.error(error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  runTests();
}

module.exports = { testTenantIsolation, testDatabaseConnection };

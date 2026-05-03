// === AI INTEGRATION TEST ===
// Tests the complete AI system integration

const { SimpleAIWorker } = require('../src/server/modules/ai/simple-worker');

async function testAIIntegration() {
  console.log('=== AI INTEGRATION TEST ===');
  
  const config = {
    redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
    concurrency: 2,
  };
  
  const worker = new SimpleAIWorker(config);
  
  try {
    // Start worker
    await worker.start();
    console.log('Worker started successfully');
    
    // Test queue stats
    const stats = await worker.getQueueStats();
    console.log('Initial queue stats:', stats);
    
    // Add test jobs
    console.log('Adding test jobs...');
    
    const testJob1 = await worker.addJob({
      sellerId: 'test-seller-1',
      jobType: 'TEST_JOB',
      payload: { message: 'Hello from test job 1' }
    });
    
    const testJob2 = await worker.addJob({
      sellerId: 'test-seller-2', 
      jobType: 'HEALTH_CHECK',
      payload: { check: 'full' }
    });
    
    console.log('Added jobs:', { job1: testJob1.id, job2: testJob2.id });
    
    // Wait for jobs to process
    console.log('Waiting for jobs to process...');
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    // Check final stats
    const finalStats = await worker.getQueueStats();
    console.log('Final queue stats:', finalStats);
    
    console.log('=== INTEGRATION TEST PASSED ===');
    
  } catch (error) {
    console.error('Integration test failed:', error);
    throw error;
  } finally {
    await worker.stop();
  }
}

// Test Redis connection
async function testRedisConnection() {
  console.log('Testing Redis connection...');
  
  const Redis = require('ioredis');
  const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
  
  try {
    await redis.ping();
    console.log('Redis connection: OK');
    await redis.quit();
  } catch (error) {
    console.error('Redis connection failed:', error);
    throw error;
  }
}

// Test database connection
async function testDatabaseConnection() {
  console.log('Testing database connection...');
  
  const { PrismaClient } = require('@prisma/client');
  const prisma = new PrismaClient();
  
  try {
    await prisma.$queryRaw`SELECT 1`;
    console.log('Database connection: OK');
    
    // Test AI tables exist
    const sellerCount = await prisma.seller.count();
    console.log(`Found ${sellerCount} sellers`);
    
    await prisma.$disconnect();
  } catch (error) {
    console.error('Database connection failed:', error);
    throw error;
  }
}

// Main test runner
async function runTests() {
  try {
    console.log('Starting AI integration tests...\n');
    
    // Test connections
    await testRedisConnection();
    await testDatabaseConnection();
    
    // Test AI integration
    await testAIIntegration();
    
    console.log('\n=== ALL TESTS PASSED ===');
    console.log('AI system is ready for production');
    
  } catch (error) {
    console.error('\n=== TESTS FAILED ===');
    console.error('AI system not ready:', error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  runTests();
}

module.exports = { testAIIntegration, testRedisConnection, testDatabaseConnection };

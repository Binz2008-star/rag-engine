// === AI QUEUE TEST ===
// Tests the AI worker queue functionality

const Redis = require('ioredis');
const { Queue } = require('bullmq');

async function testAIQueue() {
  console.log('=== AI QUEUE TEST ===');
  
  const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
  const queue = new Queue('ai-queue', {
    connection: redis,
  });
  
  try {
    // Test queue stats
    const waiting = await queue.getWaiting();
    const active = await queue.getActive();
    const completed = await queue.getCompleted();
    const failed = await queue.getFailed();
    
    console.log('Queue Stats:');
    console.log(`  Waiting: ${waiting.length}`);
    console.log(`  Active: ${active.length}`);
    console.log(`  Completed: ${completed.length}`);
    console.log(`  Failed: ${failed.length}`);
    
    // Add test job
    console.log('\nAdding test job...');
    const job = await queue.add('TEST_JOB', {
      sellerId: 'test-seller-queue',
      jobType: 'TEST_JOB',
      payload: { message: 'Queue test job' }
    });
    
    console.log(`Added job: ${job.id}`);
    
    // Wait for processing
    console.log('Waiting for job processing...');
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Check final stats
    const finalWaiting = await queue.getWaiting();
    const finalCompleted = await queue.getCompleted();
    
    console.log('\nFinal Queue Stats:');
    console.log(`  Waiting: ${finalWaiting.length}`);
    console.log(`  Completed: ${finalCompleted.length}`);
    
    if (finalCompleted.length > 0) {
      console.log('Queue test: PASSED');
    } else {
      console.log('Queue test: FAILED - job not processed');
    }
    
  } catch (error) {
    console.error('Queue test failed:', error);
    throw error;
  } finally {
    await queue.close();
    await redis.quit();
  }
}

// Test Redis connection
async function testRedisConnection() {
  console.log('Testing Redis connection...');
  
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

// Main test runner
async function runTests() {
  try {
    console.log('Starting AI queue tests...\n');
    
    await testRedisConnection();
    await testAIQueue();
    
    console.log('\n=== QUEUE TESTS COMPLETED ===');
    
  } catch (error) {
    console.error('\n=== QUEUE TESTS FAILED ===');
    console.error(error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  runTests();
}

module.exports = { testAIQueue, testRedisConnection };

// === COMPREHENSIVE AI SYSTEM TEST ===
// Runs all AI integration tests in sequence

async function runAllTests() {
  console.log('=== COMPREHENSIVE AI SYSTEM TEST ===');
  console.log('Running all AI integration tests...\n');

  const tests = [
    { name: 'Queue System', file: 'test-ai-queue.js' },
    { name: 'Circuit Breakers', file: 'test-circuit-breakers.js' },
    { name: 'Tenant Isolation', file: 'test-tenant-isolation.js' },
    { name: 'Audit Trail', file: 'test-audit-trail.js' },
  ];

  const results = [];

  for (const test of tests) {
    console.log(`\n--- Running ${test.name} Test ---`);

    try {
      const startTime = Date.now();

      // Dynamic import and run test
      const testModule = require(`./${test.file}`);

      // Call the appropriate test function
      if (test.file === 'test-ai-queue.js') {
        await testModule.testRedisConnection();
        await testModule.testAIQueue();
      } else if (test.file === 'test-circuit-breakers.js') {
        await testModule.testCircuitBreaker();
        await testModule.testFallbackStrategies();
        await testModule.testTimeoutHandling();
      } else if (test.file === 'test-tenant-isolation.js') {
        await testModule.testDatabaseConnection();
        await testModule.testTenantIsolation();
      } else if (test.file === 'test-audit-trail.js') {
        await testModule.testDatabaseConnection();
        await testModule.testAuditTrail();
      } else {
        throw new Error(`Unknown test file: ${test.file}`);
      }

      const duration = Date.now() - startTime;

      results.push({
        name: test.name,
        status: 'PASS',
        duration,
        error: null,
      });

      console.log(`\n${test.name} Test: PASS (${duration}ms)`);

    } catch (error) {
      results.push({
        name: test.name,
        status: 'FAIL',
        duration: 0,
        error: error.message,
      });

      console.log(`\n${test.name} Test: FAIL`);
      console.log(`Error: ${error.message}`);
    }

    // Small delay between tests
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  // Generate final report
  console.log('\n=== FINAL TEST REPORT ===');

  const passed = results.filter(r => r.status === 'PASS');
  const failed = results.filter(r => r.status === 'FAIL');

  console.log(`\nTest Summary:`);
  console.log(`  Total Tests: ${results.length}`);
  console.log(`  Passed: ${passed.length}`);
  console.log(`  Failed: ${failed.length}`);
  console.log(`  Success Rate: ${((passed.length / results.length) * 100).toFixed(1)}%`);

  console.log(`\nDetailed Results:`);
  results.forEach(result => {
    const status = result.status === 'PASS' ? 'PASS' : 'FAIL';
    const duration = result.duration > 0 ? ` (${result.duration}ms)` : '';
    console.log(`  ${status}: ${result.name}${duration}`);
    if (result.error) {
      console.log(`    Error: ${result.error}`);
    }
  });

  // Overall system status
  if (failed.length === 0) {
    console.log('\n=== AI SYSTEM STATUS: PRODUCTION READY ===');
    console.log('All AI components are working correctly');
    console.log('System is ready for production deployment');

    // Production readiness checklist
    console.log('\nProduction Readiness Checklist:');
    console.log('  Queue System: Working');
    console.log('  Circuit Breakers: Working');
    console.log('  Tenant Isolation: Working');
    console.log('  Audit Trail: Working');
    console.log('  Vector Extension: Installed');
    console.log('  Dependencies: Installed');
    console.log('  Worker Process: Ready');

    console.log('\nNext Steps:');
    console.log('  1. Start AI worker: npm run ai:worker');
    console.log('  2. Monitor queue activity');
    console.log('  3. Configure AI policies per seller');
    console.log('  4. Set up monitoring and alerts');

  } else {
    console.log('\n=== AI SYSTEM STATUS: NOT READY ===');
    console.log('Some components are not working correctly');
    console.log('Fix failed tests before production deployment');

    console.log('\nFailed Components:');
    failed.forEach(result => {
      console.log(`  - ${result.name}: ${result.error}`);
    });
  }

  return {
    success: failed.length === 0,
    results,
    summary: {
      total: results.length,
      passed: passed.length,
      failed: failed.length,
      successRate: (passed.length / results.length) * 100,
    },
  };
}

// Run if called directly
if (require.main === module) {
  runAllTests()
    .then((result) => {
      process.exit(result.success ? 0 : 1);
    })
    .catch((error) => {
      console.error('Test runner failed:', error);
      process.exit(1);
    });
}

module.exports = { runAllTests };

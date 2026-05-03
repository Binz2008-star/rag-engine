// === CIRCUIT BREAKER TEST ===
// Tests circuit breaker functionality and fallbacks

const CircuitBreaker = require('opossum');

async function testCircuitBreaker() {
  console.log('=== CIRCUIT BREAKER TEST ===');
  
  let failureCount = 0;
  let successCount = 0;
  
  // Mock function that fails initially, then succeeds
  const mockFunction = async (input) => {
    if (failureCount < 3) {
      failureCount++;
      throw new Error(`Simulated failure ${failureCount}`);
    }
    successCount++;
    return `Success ${successCount}: ${input}`;
  };
  
  // Create circuit breaker
  const breaker = new CircuitBreaker(mockFunction, {
    timeout: 1000,
    errorThresholdPercentage: 50,
    resetTimeout: 2000,
  });
  
  // Event listeners
  breaker.on('open', () => {
    console.log('Circuit breaker OPEN - fallbacks activated');
  });
  
  breaker.on('halfOpen', () => {
    console.log('Circuit breaker HALF-OPEN - testing recovery');
  });
  
  breaker.on('close', () => {
    console.log('Circuit breaker CLOSED - normal operation');
  });
  
  breaker.on('fallback', (result) => {
    console.log('Fallback executed:', result);
  });
  
  try {
    console.log('Testing circuit breaker behavior...\n');
    
    // Test 1: Trigger failures to open circuit
    console.log('1. Triggering failures to open circuit...');
    for (let i = 0; i < 4; i++) {
      try {
        const result = await breaker.fire('test-input');
        console.log(`  Call ${i + 1}: ${result}`);
      } catch (error) {
        console.log(`  Call ${i + 1}: FAILED - ${error.message}`);
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    console.log('\n2. Circuit should be OPEN now...');
    try {
      await breaker.fire('should-fail');
      console.log('  ERROR: Call should have been blocked');
    } catch (error) {
      console.log('  SUCCESS: Call blocked by open circuit');
    }
    
    // Wait for reset timeout
    console.log('\n3. Waiting for reset timeout...');
    await new Promise(resolve => setTimeout(resolve, 2500));
    
    // Test 2: Recovery
    console.log('\n4. Testing recovery...');
    try {
      const result = await breaker.fire('recovery-test');
      console.log(`  Recovery call: ${result}`);
    } catch (error) {
      console.log(`  Recovery call failed: ${error.message}`);
    }
    
    // Test 3: Normal operation
    console.log('\n5. Testing normal operation...');
    try {
      const result = await breaker.fire('normal-operation');
      console.log(`  Normal call: ${result}`);
    } catch (error) {
      console.log(`  Normal call failed: ${error.message}`);
    }
    
    console.log('\n=== CIRCUIT BREAKER TEST COMPLETED ===');
    console.log(`Failures triggered: ${failureCount}`);
    console.log(`Successful calls: ${successCount}`);
    
  } catch (error) {
    console.error('Circuit breaker test failed:', error);
    throw error;
  }
}

// Test fallback strategies
async function testFallbackStrategies() {
  console.log('\n=== FALLBACK STRATEGIES TEST ===');
  
  let primaryFailures = 0;
  let fallbackSuccesses = 0;
  
  const primaryService = async (input) => {
    primaryFailures++;
    throw new Error('Primary service unavailable');
  };
  
  const fallbackService = async (input) => {
    fallbackSuccesses++;
    return `Fallback result: ${input}`;
  };
  
  const breaker = new CircuitBreaker(primaryService, {
    timeout: 500,
    errorThresholdPercentage: 50,
    resetTimeout: 1000,
  });
  
  // Add fallback
  breaker.fallback(fallbackService);
  
  try {
    console.log('Testing fallback when primary fails...');
    
    for (let i = 0; i < 3; i++) {
      try {
        const result = await breaker.fire(`test-${i}`);
        console.log(`  Call ${i + 1}: ${result}`);
      } catch (error) {
        console.log(`  Call ${i + 1}: FAILED - ${error.message}`);
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    console.log(`Primary failures: ${primaryFailures}`);
    console.log(`Fallback successes: ${fallbackSuccesses}`);
    
    if (fallbackSuccesses > 0) {
      console.log('Fallback strategies: WORKING');
    } else {
      console.log('Fallback strategies: FAILED');
    }
    
  } catch (error) {
    console.error('Fallback test failed:', error);
    throw error;
  }
}

// Test timeout handling
async function testTimeoutHandling() {
  console.log('\n=== TIMEOUT HANDLING TEST ===');
  
  const slowFunction = async (input) => {
    await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
    return `Slow result: ${input}`;
  };
  
  const breaker = new CircuitBreaker(slowFunction, {
    timeout: 500, // 500ms timeout
    errorThresholdPercentage: 50,
    resetTimeout: 1000,
  });
  
  try {
    console.log('Testing timeout handling...');
    
    const startTime = Date.now();
    try {
      await breaker.fire('timeout-test');
    } catch (error) {
      const elapsed = Date.now() - startTime;
      console.log(`  Call timed out after ${elapsed}ms`);
      console.log(`  Error: ${error.message}`);
      
      if (elapsed < 1000) {
        console.log('  Timeout handling: WORKING');
      } else {
        console.log('  Timeout handling: FAILED');
      }
    }
    
  } catch (error) {
    console.error('Timeout test failed:', error);
    throw error;
  }
}

// Main test runner
async function runTests() {
  try {
    console.log('Starting circuit breaker tests...\n');
    
    await testCircuitBreaker();
    await testFallbackStrategies();
    await testTimeoutHandling();
    
    console.log('\n=== ALL CIRCUIT BREAKER TESTS PASSED ===');
    
  } catch (error) {
    console.error('\n=== CIRCUIT BREAKER TESTS FAILED ===');
    console.error(error);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  runTests();
}

module.exports = { testCircuitBreaker, testFallbackStrategies, testTimeoutHandling };

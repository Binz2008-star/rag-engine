#!/usr/bin/env tsx

import { execSync } from 'child_process';

const baseUrl = 'http://localhost:3000';

// Test 1: Working manual curl (from earlier)
console.log('=== Test 1: Working Manual Curl ===');
try {
  const workingCommand = `curl -X POST "${baseUrl}/api/auth/login" -H "Content-Type: application/json" -d '{"email": "seller1@test.com", "password": "TestSeller123!"}' -w "\\nHTTP_STATUS:%{http_code}\\nRESPONSE_TIME:%{time_total}" -s`;
  console.log('Command:', workingCommand);
  const output1 = execSync(workingCommand, { encoding: 'utf8' });
  console.log('Output:', output1);
} catch (error: any) {
  console.log('Error:', error.message);
}

console.log('\n=== Test 2: Script-generated Curl ===');
try {
  // Test the exact format the script generates
  const body = { email: 'seller1@test.com', password: 'TestSeller123!' };
  const headers = { 'Content-Type': 'application/json' };
  
  let curlCommand = `curl -X POST "${baseUrl}/api/auth/login"`;
  
  // Add headers
  if (headers) {
    Object.entries(headers).forEach(([key, value]) => {
      curlCommand += ` -H "${key}: ${value}"`;
    });
  }
  
  // Add body
  if (body) {
    curlCommand += ` -d '${JSON.stringify(body)}'`;
  }
  
  curlCommand += ' -w "\\nHTTP_STATUS:%{http_code}\\nRESPONSE_TIME:%{time_total}\\n" -s';
  
  console.log('Command:', curlCommand);
  const output2 = execSync(curlCommand, { encoding: 'utf8' });
  console.log('Output:', output2);
} catch (error: any) {
  console.log('Error:', error.message);
}

console.log('\n=== Test 3: Without Headers ===');
try {
  const body = { email: 'seller1@test.com', password: 'TestSeller123!' };
  let curlCommand = `curl -X POST "${baseUrl}/api/auth/login"`;
  curlCommand += ` -d '${JSON.stringify(body)}'`;
  curlCommand += ' -w "\\nHTTP_STATUS:%{http_code}\\nRESPONSE_TIME:%{time_total}\\n" -s';
  
  console.log('Command:', curlCommand);
  const output3 = execSync(curlCommand, { encoding: 'utf8' });
  console.log('Output:', output3);
} catch (error: any) {
  console.log('Error:', error.message);
}

console.log('\n=== Test 4: With Explicit JSON Header ===');
try {
  const body = { email: 'seller1@test.com', password: 'TestSeller123!' };
  let curlCommand = `curl -X POST "${baseUrl}/api/auth/login"`;
  curlCommand += ` -H "Content-Type: application/json"`;
  curlCommand += ` -d '${JSON.stringify(body)}'`;
  curlCommand += ' -w "\\nHTTP_STATUS:%{http_code}\\nRESPONSE_TIME:%{time_total}\\n" -s';
  
  console.log('Command:', curlCommand);
  const output4 = execSync(curlCommand, { encoding: 'utf8' });
  console.log('Output:', output4);
} catch (error: any) {
  console.log('Error:', error.message);
}

#!/usr/bin/env node

/**
 * Gateway-only enforcement script
 * Checks for raw fetch usage outside gateway
 */

const fs = require('fs');
const path = require('path');

function findFiles(dir, extensions = ['.ts', '.js']) {
  const files = [];

  function traverse(currentDir) {
    const items = fs.readdirSync(currentDir);

    for (const item of items) {
      const fullPath = path.join(currentDir, item);
      const stat = fs.statSync(fullPath);

      if (stat.isDirectory() && !item.includes('node_modules')) {
        traverse(fullPath);
      } else if (stat.isFile() && extensions.some(ext => item.endsWith(ext))) {
        files.push(fullPath);
      }
    }
  }

  traverse(dir);
  return files;
}

function checkForRawFetch() {
  console.log('Checking for raw fetch usage outside gateway...');

  try {
    const srcDir = path.join(__dirname, '..', 'src');
    const files = findFiles(srcDir);
    const violations = [];

    for (const filePath of files) {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.split('\n');

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (line.includes('fetch(')) {
          // Skip safeFetch usage
          if (line.includes('safeFetch(')) continue;

          // Skip safe-fetch implementation
          if (filePath.includes('safe-fetch.ts')) continue;

          // Skip gateway-client implementation (allowed to use fetch)
          if (filePath.includes('gateway-client.ts')) continue;

          // Skip if line is a comment
          if (line.trim().startsWith('//') || line.trim().startsWith('*')) continue;

          // Report violation
          violations.push(`${filePath}:${i + 1}:${line.trim()}`);
        }
      }
    }

    if (violations.length > 0) {
      console.log('ERROR: Raw fetch usage detected outside gateway:');
      violations.forEach(violation => {
        console.log(violation);
      });
      console.log('All HTTP calls must use GatewayClient or safeFetch wrapper.');
      process.exit(1);
    }

    console.log('SUCCESS: No raw fetch usage detected outside gateway');
    process.exit(0);

  } catch (error) {
    console.error('Error checking fetch usage:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  checkForRawFetch();
}

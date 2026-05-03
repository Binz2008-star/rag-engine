const crypto = require('crypto');

// Generate secure random secrets
const jwtSecret = crypto.randomBytes(32).toString('base64');
const nextauthSecret = crypto.randomBytes(32).toString('base64');

console.log('=== Generated Secrets ===');
console.log('JWT_SECRET=' + jwtSecret);
console.log('NEXTAUTH_SECRET=' + nextauthSecret);
console.log('');
console.log('Add these to Render Environment Variables:');
console.log('1. JWT_SECRET=' + jwtSecret);
console.log('2. NEXTAUTH_SECRET=' + nextauthSecret);
console.log('3. DATABASE_URL=postgresql://neondb_owner:npg_DV1cIBCap9JU@ep-shiny-dew-anomey4x-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require');

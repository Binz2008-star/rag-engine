# Required Environment Variables for Deployment

## Critical Variables (Must Add to Render)

### 1. JWT_SECRET

```
Jdj4RXBqaijX0qpcDJ1I+uGZzvg7B77V5DO7ZI3cLjs=
```

### 2. NEXTAUTH_SECRET

```
qzuz+dfqiK6uZ3ynRN+jjRhh++EOI8LjfjjHyq1Apuo=
```

### 3. DATABASE_URL

Already configured:

```
postgresql://neondb_owner:npg_DV1cIBCap9JU@ep-shiny-dew-anomey4x-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## Add to Render Dashboard

1. Go to Render Dashboard
2. Select your service
3. Environment tab
4. Add these three variables:
   - JWT_SECRET
   - NEXTAUTH_SECRET
   - DATABASE_URL (verify it's there)

## Quick Generate Commands

Run these to generate secrets:

```bash
# Generate JWT_SECRET
JWT_SECRET=$(openssl rand -base64 32)
echo "JWT_SECRET=$JWT_SECRET"

# Generate NEXTAUTH_SECRET
NEXTAUTH_SECRET=$(openssl rand -base64 32)
echo "NEXTAUTH_SECRET=$NEXTAUTH_SECRET"
```

## After Adding Variables

Once all three are added, trigger a new deployment. The build should succeed.

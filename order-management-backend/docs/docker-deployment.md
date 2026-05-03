# Docker Production Deployment

## Step 1: Build Docker Image

```bash
docker build -t order-management-backend .
```

## Step 2: Environment Variables

Create `.env.production`:
```bash
DATABASE_URL=postgresql://username:password@host:port/database
JWT_SECRET=your-32-plus-character-secret-here
NODE_ENV=production

# Rate Limiting (optional)
REDIS_URL=redis://username:password@host:port
# OR
UPSTASH_REDIS_REST_URL=https://your-project.upstash.io/redis
UPSTASH_REDIS_REST_TOKEN=your-upstash-token
```

## Step 3: Run Container

```bash
docker run -d \
  --name order-backend \
  --env-file .env.production \
  -p 3000:3000 \
  order-management-backend
```

## Step 4: Database Migration

```bash
docker exec -it order-backend npm run db:deploy
```

## Step 5: Health Check

```bash
curl http://localhost:3000/api/health
```

## Docker Compose (Optional)

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/orderdb
      - JWT_SECRET=your-secret-here
      - NODE_ENV=production
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=orderdb
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

Run with:
```bash
docker-compose up -d
```

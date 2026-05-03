// === VECTOR EXTENSION SETUP ===
// Adds pgvector extension to PostgreSQL database

const { PrismaClient } = require('@prisma/client');

async function setupVectorExtension() {
  const prisma = new PrismaClient();
  
  try {
    console.log('Setting up vector extension...');
    
    // Create the vector extension
    await prisma.$executeRaw`CREATE EXTENSION IF NOT EXISTS vector;`;
    console.log('Vector extension created successfully');
    
    // Add embedding column to ai_document_chunks if it doesn't exist
    try {
      await prisma.$executeRaw`
        ALTER TABLE ai_document_chunks 
        ADD COLUMN IF NOT EXISTS embedding vector(384)
      `;
      console.log('Embedding column added successfully');
    } catch (error) {
      console.log('Embedding column already exists or error:', error.message);
    }
    
    // Add FTS column if it doesn't exist
    try {
      await prisma.$executeRaw`
        ALTER TABLE ai_document_chunks 
        ADD COLUMN IF NOT EXISTS fts tsvector
      `;
      console.log('FTS column added successfully');
    } catch (error) {
      console.log('FTS column already exists or error:', error.message);
    }
    
    // Create vector index if it doesn't exist
    try {
      await prisma.$executeRaw`
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ai_document_chunks_embedding_idx 
        ON ai_document_chunks 
        USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100)
      `;
      console.log('Vector index created successfully');
    } catch (error) {
      console.log('Vector index already exists or error:', error.message);
    }
    
    // Create FTS index if it doesn't exist
    try {
      await prisma.$executeRaw`
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ai_document_chunks_fts_idx 
        ON ai_document_chunks 
        USING GIN (fts)
      `;
      console.log('FTS index created successfully');
    } catch (error) {
      console.log('FTS index already exists or error:', error.message);
    }
    
    // Create trigger for FTS updates if it doesn't exist
    try {
      await prisma.$executeRaw`
        CREATE OR REPLACE FUNCTION update_document_chunk_fts()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.fts := to_tsvector('english', NEW.content);
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
      `;
      
      await prisma.$executeRaw`
        DROP TRIGGER IF EXISTS ai_document_chunk_fts_trigger ON ai_document_chunks
      `;
      
      await prisma.$executeRaw`
        CREATE TRIGGER ai_document_chunk_fts_trigger
        BEFORE INSERT OR UPDATE ON ai_document_chunks
        FOR EACH ROW EXECUTE FUNCTION update_document_chunk_fts()
      `;
      console.log('FTS trigger created successfully');
    } catch (error) {
      console.log('FTS trigger setup error:', error.message);
    }
    
    console.log('Vector extension setup complete!');
    
  } catch (error) {
    console.error('Vector extension setup failed:', error);
    throw error;
  } finally {
    await prisma.$disconnect();
  }
}

// Run if called directly
if (require.main === module) {
  setupVectorExtension()
    .then(() => {
      console.log('Setup completed successfully');
      process.exit(0);
    })
    .catch((error) => {
      console.error('Setup failed:', error);
      process.exit(1);
    });
}

module.exports = { setupVectorExtension };

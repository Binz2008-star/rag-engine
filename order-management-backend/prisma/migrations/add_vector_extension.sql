-- Add PostgreSQL vector extension for AI embeddings
-- This migration enables pgvector for similarity search

-- Enable the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to ai_document_chunks
ALTER TABLE ai_document_chunks 
ADD COLUMN embedding vector(384);

-- Add full-text search column for hybrid search
ALTER TABLE ai_document_chunks 
ADD COLUMN fts tsvector;

-- Create vector index for similarity search
-- Using IVFFlat for approximate nearest neighbor search
CREATE INDEX CONCURRENTLY ai_document_chunks_embedding_idx 
ON ai_document_chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Create GIN index for full-text search
CREATE INDEX CONCURRENTLY ai_document_chunks_fts_idx 
ON ai_document_chunks 
USING GIN (fts);

-- Add trigger to automatically update FTS column
CREATE OR REPLACE FUNCTION update_document_chunk_fts()
RETURNS TRIGGER AS $$
BEGIN
  NEW.fts := to_tsvector('english', NEW.content);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ai_document_chunk_fts_trigger
BEFORE INSERT OR UPDATE ON ai_document_chunks
FOR EACH ROW EXECUTE FUNCTION update_document_chunk_fts();

-- Create function for hybrid search
CREATE OR REPLACE FUNCTION hybrid_search(
  seller_id_param TEXT,
  query_embedding vector(384),
  query_text TEXT,
  top_k INTEGER DEFAULT 10,
  min_score FLOAT DEFAULT 0.0,
  weight_vector FLOAT DEFAULT 0.7,
  weight_fts FLOAT DEFAULT 0.3
)
RETURNS TABLE(
  chunk_id TEXT,
  document_id TEXT,
  chunk_index INTEGER,
  content TEXT,
  vector_score FLOAT,
  fts_score FLOAT,
  combined_score FLOAT,
  source_type TEXT,
  source_id TEXT
) AS $$
BEGIN
  RETURN QUERY
  WITH vector_search AS (
    SELECT 
      c.id as chunk_id,
      c.document_id,
      c.chunk_index,
      c.content,
      (1 - (c.embedding <=> query_embedding)) as vector_score,
      d.source_type,
      d.source_id
    FROM ai_document_chunks c
    JOIN ai_documents d ON c.document_id = d.id
    WHERE c.seller_id = seller_id_param
      AND d.is_active = true
      AND (1 - (c.embedding <=> query_embedding)) >= min_score
    ORDER BY c.embedding <=> query_embedding
    LIMIT top_k * 2 -- Get more candidates for reranking
  ),
  fts_search AS (
    SELECT 
      c.id as chunk_id,
      ts_rank(c.fts, plainto_tsquery('english', query_text)) as fts_score
    FROM ai_document_chunks c
    JOIN ai_documents d ON c.document_id = d.id
    WHERE c.seller_id = seller_id_param
      AND d.is_active = true
      AND c.fts @@ plainto_tsquery('english', query_text)
  )
  SELECT 
    v.chunk_id,
    v.document_id,
    v.chunk_index,
    v.content,
    COALESCE(v.vector_score, 0) as vector_score,
    COALESCE(f.fts_score, 0) as fts_score,
    (COALESCE(v.vector_score, 0) * weight_vector + COALESCE(f.fts_score, 0) * weight_fts) as combined_score,
    v.source_type,
    v.source_id
  FROM vector_search v
  LEFT JOIN fts_search f ON v.chunk_id = f.chunk_id
  ORDER BY combined_score DESC
  LIMIT top_k;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON EXTENSION vector IS 'Vector similarity search extension for AI embeddings';
COMMENT ON COLUMN ai_document_chunks.embedding IS '384-dimensional embedding vector for semantic search';
COMMENT ON COLUMN ai_document_chunks.fts IS 'Full-text search vector for hybrid search';
COMMENT ON FUNCTION hybrid_search IS 'Hybrid search combining vector similarity and full-text search';

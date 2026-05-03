-- Add pgvector extension for AI vector search
CREATE EXTENSION IF NOT EXISTS vector;

-- Add vector and full-text search columns to document chunks
ALTER TABLE ai_document_chunks 
ADD COLUMN embedding vector(384),
ADD COLUMN fts tsvector;

-- Create full-text search index
CREATE INDEX ai_document_chunks_fts_idx ON ai_document_chunks USING GIN (fts);

-- Create vector similarity index using IVFFlat for approximate nearest neighbor search
CREATE INDEX ai_document_chunks_embedding_idx ON ai_document_chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Function to update FTS column when content changes
CREATE OR REPLACE FUNCTION update_ai_document_chunks_fts()
RETURNS TRIGGER AS $$
BEGIN
  NEW.fts := to_tsvector('english', NEW.content);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update FTS on content changes
CREATE TRIGGER ai_document_chunks_fts_update
  BEFORE INSERT OR UPDATE ON ai_document_chunks
  FOR EACH ROW EXECUTE FUNCTION update_ai_document_chunks_fts();

-- Function to populate FTS for existing records
CREATE OR REPLACE FUNCTION populate_ai_document_chunks_fts()
RETURNS void AS $$
BEGIN
  UPDATE ai_document_chunks 
  SET fts = to_tsvector('english', content)
  WHERE fts IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Hybrid search function combining FTS and vector similarity
CREATE OR REPLACE FUNCTION hybrid_ai_search(
  p_seller_id TEXT,
  p_query_text TEXT,
  p_query_vector vector(384),
  p_limit INT DEFAULT 10,
  p_fts_weight FLOAT DEFAULT 0.3,
  p_vector_weight FLOAT DEFAULT 0.7
)
RETURNS TABLE(
  chunk_id TEXT,
  document_id TEXT,
  content TEXT,
  title TEXT,
  fts_score FLOAT,
  vector_score FLOAT,
  combined_score FLOAT
) AS $$
BEGIN
  RETURN QUERY
  WITH fts_results AS (
    SELECT 
      dc.id,
      dc.document_id,
      dc.content,
      d.title,
      ts_rank(dc.fts, plainto_tsquery('english', p_query_text)) as score
    FROM ai_document_chunks dc
    JOIN ai_documents d ON dc.document_id = d.id
    WHERE dc.seller_id = p_seller_id
      AND d.is_active = true
      AND dc.fts @@ plainto_tsquery('english', p_query_text)
    ORDER BY score DESC
    LIMIT p_limit * 2
  ),
  vector_results AS (
    SELECT 
      dc.id,
      dc.document_id,
      dc.content,
      d.title,
      1 - (dc.embedding <=> p_query_vector) as score
    FROM ai_document_chunks dc
    JOIN ai_documents d ON dc.document_id = d.id
    WHERE dc.seller_id = p_seller_id
      AND d.is_active = true
    ORDER BY dc.embedding <=> p_query_vector
    LIMIT p_limit * 2
  )
  SELECT 
    COALESCE(f.id, v.id) as chunk_id,
    COALESCE(f.document_id, v.document_id) as document_id,
    COALESCE(f.content, v.content) as content,
    COALESCE(f.title, v.title) as title,
    COALESCE(f.score, 0) as fts_score,
    COALESCE(v.score, 0) as vector_score,
    (COALESCE(f.score, 0) * p_fts_weight + COALESCE(v.score, 0) * p_vector_weight) as combined_score
  FROM fts_results f
  FULL OUTER JOIN vector_results v ON f.id = v.id
  ORDER BY combined_score DESC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Add comment for documentation
COMMENT ON FUNCTION hybrid_ai_search IS 'Hybrid search combining full-text search and vector similarity for AI document chunks';

-- Phase 2 Migration: Lead Scoring & RAG Integration
-- Run once on Neon DB

-- Add lead scoring columns
ALTER TABLE leads 
ADD COLUMN IF NOT EXISTS lead_score INTEGER,
ADD COLUMN IF NOT EXISTS score_band VARCHAR(20),
ADD COLUMN IF NOT EXISTS rag_intent VARCHAR(50),
ADD COLUMN IF NOT EXISTS rag_confidence FLOAT,
ADD COLUMN IF NOT EXISTS rag_method VARCHAR(50),
ADD COLUMN IF NOT EXISTS proposal_context TEXT,
ADD COLUMN IF NOT EXISTS recommended_action VARCHAR(255),
ADD COLUMN IF NOT EXISTS scored_at TIMESTAMP;

-- Add index for efficient hot/warm lead queries
CREATE INDEX IF NOT EXISTS idx_leads_score_band ON leads(score_band);
CREATE INDEX IF NOT EXISTS idx_leads_lead_score ON leads(lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_scored_at ON leads(scored_at DESC);

-- Add columns to agent_conversations for RAG tracking
ALTER TABLE agent_conversations
ADD COLUMN IF NOT EXISTS rag_intent VARCHAR(50),
ADD COLUMN IF NOT EXISTS rag_confidence FLOAT,
ADD COLUMN IF NOT EXISTS rag_method VARCHAR(50),
ADD COLUMN IF NOT EXISTS lead_score INTEGER,
ADD COLUMN IF NOT EXISTS score_band VARCHAR(20);

-- Create view for hot leads dashboard
CREATE OR REPLACE VIEW hot_leads AS
SELECT 
    id,
    full_name,
    company_name,
    email,
    phone,
    services_required,
    lead_score,
    score_band,
    rag_intent,
    rag_confidence,
    recommended_action,
    scored_at,
    created_at
FROM leads
WHERE score_band IN ('HOT', 'WARM')
ORDER BY lead_score DESC, scored_at DESC;

COMMENT ON COLUMN leads.lead_score IS 'Calculated score 0-100 based on 6 dimensions';
COMMENT ON COLUMN leads.score_band IS 'HOT (≥80), WARM (≥60), MEDIUM (≥40), COLD (<40)';
COMMENT ON COLUMN leads.rag_intent IS 'Intent classification from RAG backend';
COMMENT ON COLUMN leads.rag_confidence IS 'Confidence score from RAG backend';
COMMENT ON COLUMN leads.proposal_context IS 'RAG-grounded context for proposals';

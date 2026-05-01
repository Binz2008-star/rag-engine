-- DEPRECATED: see 001_init.sql
-- This file is kept for backward compatibility but is no longer used.
-- Use 001_init.sql for new installations.

-- Create database tables for Robin AI Pipeline

-- Leads table
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    services_required TEXT[],
    source VARCHAR(100),
    status VARCHAR(50) DEFAULT 'new',
    email_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Lead events table
CREATE TABLE IF NOT EXISTS lead_events (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    event_type VARCHAR(100),
    payload JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Agent conversations table
CREATE TABLE IF NOT EXISTS agent_conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE,
    visitor_name VARCHAR(255),
    visitor_company VARCHAR(255),
    visitor_email VARCHAR(255),
    visitor_phone VARCHAR(50),
    services_enquired TEXT[],
    conversation_summary TEXT,
    lead_captured BOOLEAN DEFAULT FALSE,
    lead_id INTEGER REFERENCES leads(id),
    jotform_agent_id VARCHAR(255),
    started_at TIMESTAMP DEFAULT NOW()
);

-- Form submissions table
CREATE TABLE IF NOT EXISTS form_submissions (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(255) UNIQUE,
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_lead_events_lead_id ON lead_events(lead_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_session_id ON agent_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_form_submissions_lead_id ON form_submissions(lead_id);

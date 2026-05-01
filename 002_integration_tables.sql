-- Integration tables compatible with existing leads table (integer IDs)
-- Run this in Neon SQL Editor

-- Tasks table (integer foreign key to leads.id)
CREATE TABLE IF NOT EXISTS tasks (
  id SERIAL PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
  task_type text NOT NULL,
  title text NOT NULL,
  due_at timestamp with time zone,
  priority text NOT NULL DEFAULT 'normal',
  status text NOT NULL DEFAULT 'open',
  assigned_to text,
  created_by text NOT NULL DEFAULT 'system',
  completed_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),

  CONSTRAINT tasks_status_check CHECK (
    status IN ('open', 'done', 'cancelled')
  ),

  CONSTRAINT tasks_priority_check CHECK (
    priority IN ('low', 'normal', 'high', 'urgent')
  )
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status, due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_lead_id ON tasks(lead_id);

-- Integration events table (idempotency key for n8n integration)
CREATE TABLE IF NOT EXISTS integration_events (
  id SERIAL PRIMARY KEY,
  event_type text NOT NULL,
  source_system text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'received',
  error_message text,
  processed_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_integration_events_key ON integration_events(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_integration_events_status ON integration_events(status);
CREATE INDEX IF NOT EXISTS idx_integration_events_created ON integration_events(created_at DESC);

-- CRM sync log (integer foreign key to leads.id)
CREATE TABLE IF NOT EXISTS crm_sync_log (
  id SERIAL PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
  system text NOT NULL DEFAULT 'close',
  action text NOT NULL,
  request_payload jsonb,
  response_payload jsonb,
  sync_status text NOT NULL,
  error_message text,
  attempted_at timestamp with time zone NOT NULL DEFAULT now(),
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crm_sync_lead_id ON crm_sync_log(lead_id);
CREATE INDEX IF NOT EXISTS idx_crm_sync_status ON crm_sync_log(sync_status);

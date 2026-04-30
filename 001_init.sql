CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  emirate text,
  industry text,
  address text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
  full_name text NOT NULL,
  email text UNIQUE,
  phone text,
  role_title text,
  is_primary boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_code text NOT NULL UNIQUE,
  service_name text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
  primary_contact_id uuid REFERENCES contacts(id) ON DELETE SET NULL,
  source text NOT NULL DEFAULT 'jotform',
  stage text NOT NULL DEFAULT 'New Lead',
  status text NOT NULL DEFAULT 'open',
  urgency text NOT NULL DEFAULT 'low',
  emirate text,
  units_count integer,
  estimated_value_aed numeric(12,2),
  assigned_to text,
  last_contacted_at timestamptz,
  next_followup_at timestamptz,
  lost_reason text,
  notes text,
  close_lead_id text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT leads_stage_check CHECK (
    stage IN (
      'New Lead',
      'Contacted',
      'Qualified',
      'Proposal Sent',
      'Negotiation',
      'Closed Won',
      'Closed Lost'
    )
  ),

  CONSTRAINT leads_status_check CHECK (
    status IN ('open', 'won', 'lost')
  ),

  CONSTRAINT leads_urgency_check CHECK (
    urgency IN ('low', 'medium', 'high', 'emergency')
  )
);

CREATE TABLE IF NOT EXISTS lead_services (
  lead_id uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  service_id uuid NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
  quantity_units numeric,
  PRIMARY KEY (lead_id, service_id)
);

CREATE TABLE IF NOT EXISTS form_submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid REFERENCES leads(id) ON DELETE SET NULL,
  provider text NOT NULL DEFAULT 'jotform',
  external_submission_id text NOT NULL,
  raw_payload jsonb NOT NULL,
  parsed_payload jsonb,
  received_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, external_submission_id)
);

CREATE TABLE IF NOT EXISTS outreach_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid REFERENCES leads(id) ON DELETE CASCADE,
  contact_id uuid REFERENCES contacts(id) ON DELETE SET NULL,
  channel text NOT NULL,
  direction text NOT NULL,
  template_id text,
  subject text,
  message_excerpt text,
  outcome text,
  sent_by text,
  provider_message_id text,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb,

  CONSTRAINT outreach_channel_check CHECK (
    channel IN ('email', 'sms', 'call', 'whatsapp', 'linkedin')
  ),

  CONSTRAINT outreach_direction_check CHECK (
    direction IN ('outbound', 'inbound')
  )
);

CREATE TABLE IF NOT EXISTS tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid REFERENCES leads(id) ON DELETE CASCADE,
  task_type text NOT NULL,
  title text NOT NULL,
  due_at timestamptz,
  priority text NOT NULL DEFAULT 'normal',
  status text NOT NULL DEFAULT 'open',
  assigned_to text,
  created_by text NOT NULL DEFAULT 'system',
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT tasks_status_check CHECK (
    status IN ('open', 'done', 'cancelled')
  ),

  CONSTRAINT tasks_priority_check CHECK (
    priority IN ('low', 'normal', 'high', 'urgent')
  )
);

CREATE TABLE IF NOT EXISTS crm_sync_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid REFERENCES leads(id) ON DELETE CASCADE,
  system text NOT NULL DEFAULT 'close',
  action text NOT NULL,
  request_payload jsonb,
  response_payload jsonb,
  sync_status text NOT NULL,
  error_message text,
  attempted_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integration_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,
  source_system text NOT NULL,
  idempotency_key text NOT NULL UNIQUE,
  payload jsonb NOT NULL,
  status text NOT NULL DEFAULT 'received',
  error_message text,
  processed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  platform text NOT NULL,
  start_date date,
  end_date date,
  budget_aed numeric(12,2),
  objective text,
  tracking_code text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS social_posts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid REFERENCES campaigns(id) ON DELETE SET NULL,
  platform text NOT NULL,
  post_date date,
  content_theme text,
  post_url text,
  status text NOT NULL DEFAULT 'planned',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS campaign_performance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id uuid REFERENCES campaigns(id) ON DELETE CASCADE,
  post_id uuid REFERENCES social_posts(id) ON DELETE SET NULL,
  metric_date date NOT NULL,
  impressions integer DEFAULT 0,
  engagements integer DEFAULT 0,
  clicks integer DEFAULT 0,
  leads_generated integer DEFAULT 0,
  won_deals integer DEFAULT 0,
  revenue_aed numeric(12,2) DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO services (service_code, service_name)
VALUES
  ('GREASE_TRAP', 'Grease Trap Cleaning & Maintenance'),
  ('DESLUDGING', 'Sewage Tank Desludging'),
  ('BIO_TREATMENT', 'Biological Treatment'),
  ('ODOUR_CONTROL', 'Odour Control'),
  ('UCO_RECYCLING', 'Used Cooking Oil Recycling'),
  ('HP_JETTING', 'High-Pressure Jetting'),
  ('INDUSTRIAL_CLEANING', 'Industrial Cleaning')
ON CONFLICT (service_code) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_emirate ON leads(emirate);
CREATE INDEX IF NOT EXISTS idx_leads_next_followup ON leads(next_followup_at);
CREATE INDEX IF NOT EXISTS idx_outreach_lead_date ON outreach_log(lead_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(status, due_at);
CREATE INDEX IF NOT EXISTS idx_integration_events_key ON integration_events(idempotency_key);

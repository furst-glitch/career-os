-- Audit Logs og GDPR
-- Sporbarhed for brugerhandlinger og compliance-requests

CREATE TABLE public.audit_logs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  action        text NOT NULL,
  resource_type text NOT NULL,
  resource_id   uuid,
  metadata      jsonb NOT NULL DEFAULT '{}',
  ip_address    inet,
  user_agent    text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.gdpr_requests (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  request_type    text NOT NULL CHECK (request_type IN ('export', 'delete', 'rectify')),
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  requested_at    timestamptz NOT NULL DEFAULT now(),
  completed_at    timestamptz,
  export_url      text,                      -- Signed URL til eksportfil (30 dages TTL)
  notes           text
);

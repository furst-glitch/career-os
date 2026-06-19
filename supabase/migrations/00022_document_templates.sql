-- P3: Document Templates
CREATE TABLE IF NOT EXISTS document_templates (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name          text        NOT NULL,
  type          text        NOT NULL DEFAULT 'cover_letter',
  language      text        NOT NULL DEFAULT 'da',
  content       text        NOT NULL DEFAULT '',
  writing_style text        NOT NULL DEFAULT 'professional',
  focus_areas   text[]      NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE document_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "templates_owner"
  ON document_templates FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS document_templates_user
  ON document_templates (user_id, created_at DESC);

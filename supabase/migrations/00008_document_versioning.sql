-- Document Versioning
-- Komplet sporbarhed og lineage for alle dokumenter

CREATE TABLE public.document_versions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  pipeline_id     uuid,                      -- FK tilføjes efter application_pipeline er oprettet
  document_type   document_type NOT NULL,
  version_number  int NOT NULL DEFAULT 1,
  title           text NOT NULL,
  content         text NOT NULL,
  content_hash    text NOT NULL,             -- SHA256 til duplikatdetektering
  language        language_code NOT NULL DEFAULT 'da',
  generated_by    document_generated_by NOT NULL DEFAULT 'user',
  agent_id        uuid REFERENCES public.agent_registry(id) ON DELETE SET NULL,
  ai_usage_id     uuid,                      -- FK tilføjes efter ai_usage er oprettet
  metadata        jsonb NOT NULL DEFAULT '{}',
  is_active       bool NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.document_relationships (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_doc_id   uuid REFERENCES public.document_versions(id) ON DELETE CASCADE NOT NULL,
  child_doc_id    uuid REFERENCES public.document_versions(id) ON DELETE CASCADE NOT NULL,
  relationship    doc_relationship_type NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (parent_doc_id != child_doc_id)
);

-- Junction: pipeline ↔ dokument (tilføjes efter application_pipeline er oprettet)
-- Se: ALTER TABLE i 00009_application_pipeline.sql

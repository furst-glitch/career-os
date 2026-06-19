-- Migration 00030: Add master_cv_id to document_versions
--
-- application_service.save_cover_letter() links generated documents to a
-- master CV so we can track which CV was the basis for each application doc.
-- The column is nullable so older documents without this link remain valid.

ALTER TABLE public.document_versions
  ADD COLUMN IF NOT EXISTS master_cv_id uuid
    REFERENCES public.master_cvs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_document_versions_master_cv
  ON public.document_versions (master_cv_id)
  WHERE master_cv_id IS NOT NULL;

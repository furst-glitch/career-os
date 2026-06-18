-- Application Pipeline + Jobs
-- Komplet livscyklus for jobansøgninger

CREATE TABLE public.jobs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  title         text NOT NULL,
  company       text NOT NULL,
  location      text,
  url           text,
  description   text,
  requirements  text[] NOT NULL DEFAULT '{}',
  salary_min    int,
  salary_max    int,
  source        text,
  posted_at     timestamptz,
  expires_at    timestamptz,
  is_saved      bool NOT NULL DEFAULT false,
  raw_data      jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.application_pipeline (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  job_id          uuid REFERENCES public.jobs(id) ON DELETE CASCADE NOT NULL,
  current_status  application_status NOT NULL DEFAULT 'draft',
  priority        application_priority NOT NULL DEFAULT 'medium',
  deadline        date,
  source          text,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, job_id)
);

CREATE TABLE public.application_status_history (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id   uuid REFERENCES public.application_pipeline(id) ON DELETE CASCADE NOT NULL,
  status        application_status NOT NULL,
  changed_at    timestamptz NOT NULL DEFAULT now(),
  changed_by    changed_by_type NOT NULL DEFAULT 'user',
  notes         text,
  context       jsonb NOT NULL DEFAULT '{}'
);

-- Junction: pipeline ↔ document_versions
CREATE TABLE public.pipeline_documents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id   uuid REFERENCES public.application_pipeline(id) ON DELETE CASCADE NOT NULL,
  document_id   uuid REFERENCES public.document_versions(id) ON DELETE CASCADE NOT NULL,
  document_role text NOT NULL,               -- 'cv' | 'cover_letter' | 'portfolio'
  added_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pipeline_id, document_id)
);

-- Nu tilføj FK fra document_versions til pipeline
ALTER TABLE public.document_versions
  ADD CONSTRAINT fk_document_pipeline
  FOREIGN KEY (pipeline_id) REFERENCES public.application_pipeline(id) ON DELETE SET NULL;

-- Auto-log status-ændringer
CREATE OR REPLACE FUNCTION public.log_pipeline_status_change()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.current_status IS DISTINCT FROM NEW.current_status THEN
    INSERT INTO public.application_status_history (pipeline_id, status, changed_by)
    VALUES (NEW.id, NEW.current_status, 'system');
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER pipeline_status_changed
  AFTER UPDATE ON public.application_pipeline
  FOR EACH ROW EXECUTE FUNCTION public.log_pipeline_status_change();

CREATE TRIGGER application_pipeline_updated_at
  BEFORE UPDATE ON public.application_pipeline
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

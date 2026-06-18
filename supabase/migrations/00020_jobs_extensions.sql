-- Jobs Extensions — Sprint 3.1
-- Tilføjer manglende kolonner til jobs-tabellen

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS match_score  numeric(4,1),
  ADD COLUMN IF NOT EXISTS job_type     text NOT NULL DEFAULT 'full_time',
  ADD COLUMN IF NOT EXISTS remote_type  text NOT NULL DEFAULT 'hybrid',
  ADD COLUMN IF NOT EXISTS notes        text,
  ADD COLUMN IF NOT EXISTS updated_at   timestamptz NOT NULL DEFAULT now();

CREATE TRIGGER jobs_updated_at
  BEFORE UPDATE ON public.jobs
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Index til hurtig match-score sortering
CREATE INDEX IF NOT EXISTS jobs_user_match ON public.jobs (user_id, match_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS jobs_user_saved ON public.jobs (user_id, is_saved) WHERE is_saved = true;

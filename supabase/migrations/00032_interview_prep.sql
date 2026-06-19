-- Migration 00032: Interview preparation packages
--
-- Stores the full interview prep package generated when a candidate
-- is called for an interview. Linked to a pipeline entry.

CREATE TABLE public.interview_prep_packages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  pipeline_id     uuid REFERENCES public.application_pipeline(id) ON DELETE CASCADE NOT NULL UNIQUE,
  company_research    text,
  role_description    text,
  interview_guide     text,
  status          text NOT NULL DEFAULT 'pending',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.interview_prep_packages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "interview_prep: own"
  ON public.interview_prep_packages
  FOR ALL USING (auth.uid() = user_id);

CREATE TRIGGER interview_prep_updated_at
  BEFORE UPDATE ON public.interview_prep_packages
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

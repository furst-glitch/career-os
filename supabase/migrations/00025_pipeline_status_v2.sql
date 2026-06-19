-- Pipeline Status 2.0
-- Tilføjer 11 nye statusser til ansøgningspipelinen.
-- Eksisterende statusser bevares for bagudkompatibilitet.

ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'fundet';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'gemt';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'cv_genereret';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'ansoegning_genereret';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'ansoegt';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'samtale_1';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'samtale_2';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'case_stadie';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'tilbud';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'ansat';
ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'afslag';

-- Interview prep: gemmer genereret interviewmateriale per pipeline-entry
CREATE TABLE IF NOT EXISTS public.interview_prep (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id   uuid REFERENCES public.application_pipeline(id) ON DELETE CASCADE NOT NULL,
  user_id       uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  status        text NOT NULL, -- samtale_1 | samtale_2
  content       text NOT NULL,
  generated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pipeline_id, status)
);

ALTER TABLE public.interview_prep ENABLE ROW LEVEL SECURITY;

CREATE POLICY "interview_prep_owner" ON public.interview_prep
  FOR ALL USING (auth.uid() = user_id);

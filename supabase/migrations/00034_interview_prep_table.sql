-- Migration 00034: Opret interview_prep tabel
--
-- interview_prep_service.py bruger denne tabel til at gemme
-- den genererede samtalepakke. Migration 00032 oprettede
-- interview_prep_packages med en anden struktur — denne migration
-- opretter den tabel som koden faktisk forventer.

CREATE TABLE IF NOT EXISTS public.interview_prep (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid        REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  pipeline_id  uuid        REFERENCES public.application_pipeline(id) ON DELETE CASCADE NOT NULL,
  status       text        NOT NULL DEFAULT 'samtale_1',
  content      text        NOT NULL DEFAULT '',
  generated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pipeline_id, status)
);

ALTER TABLE public.interview_prep ENABLE ROW LEVEL SECURITY;

CREATE POLICY "interview_prep: own"
  ON public.interview_prep
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS interview_prep_pipeline_idx
  ON public.interview_prep (pipeline_id, status);

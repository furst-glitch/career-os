-- Profile Completeness Score
-- Beregnet score pr. sektion + samlet. Upsert ved ændring i profil.

CREATE TABLE public.profile_scores (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,

  -- Sektionsscores 0-100
  experiences    int NOT NULL DEFAULT 0 CHECK (experiences    BETWEEN 0 AND 100),
  achievements   int NOT NULL DEFAULT 0 CHECK (achievements   BETWEEN 0 AND 100),
  projects       int NOT NULL DEFAULT 0 CHECK (projects       BETWEEN 0 AND 100),
  systems        int NOT NULL DEFAULT 0 CHECK (systems        BETWEEN 0 AND 100),
  leadership     int NOT NULL DEFAULT 0 CHECK (leadership     BETWEEN 0 AND 100),
  certifications int NOT NULL DEFAULT 0 CHECK (certifications BETWEEN 0 AND 100),
  skills         int NOT NULL DEFAULT 0 CHECK (skills         BETWEEN 0 AND 100),

  -- Vægtet samlet score 0-100
  overall        int NOT NULL DEFAULT 0 CHECK (overall        BETWEEN 0 AND 100),

  -- Sektioner med score under tærsklen (til UI og Discovery Agent)
  missing_areas  text[] NOT NULL DEFAULT '{}',

  calculated_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.profile_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "profile_scores: own" ON public.profile_scores
  FOR ALL USING (auth.uid() = user_id);

CREATE INDEX idx_profile_scores_user ON public.profile_scores (user_id);

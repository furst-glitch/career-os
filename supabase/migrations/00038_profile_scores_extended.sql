-- Profile Scores: tilføj uddannelse og kontakt som scorede sektioner
-- Ny vægtning: education 10%, contact 10%, projects reduceret til 5%

ALTER TABLE public.profile_scores
  ADD COLUMN IF NOT EXISTS education int NOT NULL DEFAULT 0 CHECK (education BETWEEN 0 AND 100),
  ADD COLUMN IF NOT EXISTS contact   int NOT NULL DEFAULT 0 CHECK (contact   BETWEEN 0 AND 100);

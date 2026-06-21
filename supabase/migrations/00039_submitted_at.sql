-- Gem ansøgningsdato automatisk når status skifter til 'ansoegt'
ALTER TABLE application_pipeline
  ADD COLUMN IF NOT EXISTS submitted_at timestamptz;

COMMENT ON COLUMN application_pipeline.submitted_at IS
  'Tidspunkt for første statusskift til ansoegt — sættes automatisk af API';

-- Sprint: Full job content scraping
-- Tilføjer kolonner til at gemme fuld jobtekst scraped fra kildesider

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS full_description    text,
  ADD COLUMN IF NOT EXISTS responsibilities    text,
  ADD COLUMN IF NOT EXISTS company_description text,
  ADD COLUMN IF NOT EXISTS scraped_at          timestamptz;

-- Index til hurtig opslag af jobs der mangler scraping
CREATE INDEX IF NOT EXISTS jobs_unscraped
  ON public.jobs (user_id, source, scraped_at)
  WHERE scraped_at IS NULL AND url IS NOT NULL;

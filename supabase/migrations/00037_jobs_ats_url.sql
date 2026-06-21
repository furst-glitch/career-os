-- Sprint: ATS URL tracking for job scraping
-- Gemmer URL'en hvorfra fuld jobtekst er hentet (eksternt ATS eller Jobindex jobannonce)

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS ats_url text;

COMMENT ON COLUMN public.jobs.ats_url IS
  'URL hvorfra full_description er scraped — enten eksternt ATS (HR Manager, Emply m.fl.) eller Jobindex jobannonce-URL';

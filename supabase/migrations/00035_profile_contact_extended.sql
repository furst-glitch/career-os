-- Migration 00035: Udvidede kontaktfelter til user_profiles
--
-- Tilføjer alle felter der vises på Personprofil-siden og bruges
-- automatisk i CV og ansøgningsgenerering via MemorySnapshotService.

ALTER TABLE public.user_profiles
  ADD COLUMN IF NOT EXISTS address           text,
  ADD COLUMN IF NOT EXISTS city              text,
  ADD COLUMN IF NOT EXISTS postal_code       text,
  ADD COLUMN IF NOT EXISTS website           text,
  ADD COLUMN IF NOT EXISTS salary_expectation integer,
  ADD COLUMN IF NOT EXISTS notice_period     text;

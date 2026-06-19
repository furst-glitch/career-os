-- Migration 00031: Add contact fields to user_profiles
--
-- Enables profile page where users fill in name, email, phone and location.
-- These fields flow into generated cover letters and CVs via the snapshot service.

ALTER TABLE public.user_profiles
  ADD COLUMN IF NOT EXISTS email        text,
  ADD COLUMN IF NOT EXISTS phone        text,
  ADD COLUMN IF NOT EXISTS location     text,
  ADD COLUMN IF NOT EXISTS linkedin_url text,
  ADD COLUMN IF NOT EXISTS full_name    text;

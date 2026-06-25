-- Fix salary_prep_sessions schema conflict between 00011 and 00040.
--
-- 00011_interview_center.sql created salary_prep_sessions with interview-center columns
-- (job_id, target_salary, market_min/max/median, negotiation_script, batna, talking_points).
--
-- 00040_career_coach_labor.sql tried to CREATE TABLE IF NOT EXISTS with the AI coach schema
-- (messages, package_text, package_a4_text, updated_at) but was silently skipped if 00011 ran first.
--
-- This migration adds the missing AI-coach columns to the existing table using
-- ADD COLUMN IF NOT EXISTS for idempotency. Existing columns from 00011 are NOT dropped.

ALTER TABLE public.salary_prep_sessions
    ADD COLUMN IF NOT EXISTS messages jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS package_text text,
    ADD COLUMN IF NOT EXISTS package_a4_text text,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

-- Add trigger for updated_at if not already present (00040 may have created it if the table didn't exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'salary_prep_sessions_updated_at'
          AND tgrelid = 'public.salary_prep_sessions'::regclass
    ) THEN
        CREATE TRIGGER salary_prep_sessions_updated_at
            BEFORE UPDATE ON public.salary_prep_sessions
            FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
    END IF;
END $$;

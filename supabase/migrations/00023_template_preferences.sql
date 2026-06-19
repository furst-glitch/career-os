-- Sprint 7: Template preferences stored per user
ALTER TABLE public.user_profiles
  ADD COLUMN IF NOT EXISTS default_cv_template  text NOT NULL DEFAULT 'ats_professional',
  ADD COLUMN IF NOT EXISTS default_app_template text NOT NULL DEFAULT 'corporate';

-- Sprint 1: Experience Discovery Engine
-- Tilføjer profiltabeller til de 7 kandidat-dimensioner

-- ── CV UPLOADS (parsing-tracking) ─────────────────────────────────────────────

CREATE TABLE public.cv_uploads (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  file_name     text NOT NULL,
  mime_type     text NOT NULL,
  raw_text      text,                        -- Ekstraheret råtekst
  parsed_data   jsonb NOT NULL DEFAULT '{}', -- LLM-struktureret output
  status        text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'parsing', 'completed', 'failed')),
  error         text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ── PROFIL-UDVIDELSER TIL MASTER CV ───────────────────────────────────────────

CREATE TABLE public.cv_projects (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id  uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  name          text NOT NULL,
  description   text,
  role          text,
  technologies  text[] NOT NULL DEFAULT '{}',
  outcomes      text,
  url           text,
  period_start  date,
  period_end    date,
  sort_order    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cv_achievements (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id  uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  experience_id uuid REFERENCES public.cv_experiences(id) ON DELETE SET NULL,
  title         text NOT NULL,
  description   text,
  metric        text,                        -- "Øgede salg med 40%"
  impact_level  text NOT NULL DEFAULT 'medium'
                CHECK (impact_level IN ('low', 'medium', 'high')),
  year          int,
  sort_order    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cv_systems (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id  uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  name          text NOT NULL,
  category      text,                        -- "CRM" | "ERP" | "Cloud" | "DevOps"
  proficiency   text NOT NULL DEFAULT 'intermediate'
                CHECK (proficiency IN ('beginner', 'intermediate', 'advanced', 'expert')),
  years_used    numeric(4,1),
  sort_order    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cv_leadership (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id     uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  experience_id    uuid REFERENCES public.cv_experiences(id) ON DELETE SET NULL,
  title            text NOT NULL,
  scope            text,                     -- "Ledede 8-personers team"
  direct_reports   int,
  period_start     date,
  period_end       date,
  responsibilities text[] NOT NULL DEFAULT '{}',
  sort_order       int NOT NULL DEFAULT 0,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.cv_certifications (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  master_cv_id    uuid REFERENCES public.master_cvs(id) ON DELETE CASCADE NOT NULL,
  name            text NOT NULL,
  issuer          text,
  issued_at       date,
  expires_at      date,
  credential_id   text,
  credential_url  text,
  sort_order      int NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ── PROFIL GAPS (AI-identificerede mangler) ────────────────────────────────────

CREATE TABLE public.profile_gaps (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  session_id   uuid REFERENCES public.discovery_sessions(id) ON DELETE SET NULL,
  section      text NOT NULL
               CHECK (section IN ('experiences', 'achievements', 'projects', 'skills', 'systems', 'leadership', 'certifications')),
  description  text NOT NULL,
  priority     text NOT NULL DEFAULT 'medium'
               CHECK (priority IN ('high', 'medium', 'low')),
  is_resolved  bool NOT NULL DEFAULT false,
  resolved_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ── UDVIDELSE AF EKSISTERENDE TABELLER ────────────────────────────────────────

-- master_cvs mangler Sprint 1-felter
ALTER TABLE public.master_cvs
  ADD COLUMN IF NOT EXISTS language       language_code NOT NULL DEFAULT 'da',
  ADD COLUMN IF NOT EXISTS target_title   text,
  ADD COLUMN IF NOT EXISTS raw_content    text,
  ADD COLUMN IF NOT EXISTS is_generated   bool NOT NULL DEFAULT false;

-- cv_experiences mangler technologies (sprint 1 tilføjer dette)
ALTER TABLE public.cv_experiences
  ADD COLUMN IF NOT EXISTS technologies text[] NOT NULL DEFAULT '{}';

-- ── DISCOVERY SESSION UDVIDELSE ────────────────────────────────────────────────

ALTER TABLE public.discovery_sessions
  ADD COLUMN IF NOT EXISTS cv_upload_id uuid REFERENCES public.cv_uploads(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS profile_complete bool NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS gaps_total int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS gaps_resolved int NOT NULL DEFAULT 0;

-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE public.cv_uploads       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_achievements  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_systems       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_leadership    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cv_certifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profile_gaps     ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cv_uploads: own"       ON public.cv_uploads       FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "profile_gaps: own"     ON public.profile_gaps      FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "cv_projects: own"      ON public.cv_projects
  FOR ALL USING (EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid()));

CREATE POLICY "cv_achievements: own"  ON public.cv_achievements
  FOR ALL USING (EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid()));

CREATE POLICY "cv_systems: own"       ON public.cv_systems
  FOR ALL USING (EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid()));

CREATE POLICY "cv_leadership: own"    ON public.cv_leadership
  FOR ALL USING (EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid()));

CREATE POLICY "cv_certifications: own" ON public.cv_certifications
  FOR ALL USING (EXISTS (SELECT 1 FROM public.master_cvs m WHERE m.id = master_cv_id AND m.user_id = auth.uid()));

-- ── INDEXES ───────────────────────────────────────────────────────────────────

CREATE INDEX idx_cv_uploads_user        ON public.cv_uploads (user_id, created_at DESC);
CREATE INDEX idx_cv_projects_cv         ON public.cv_projects (master_cv_id, sort_order);
CREATE INDEX idx_cv_achievements_cv     ON public.cv_achievements (master_cv_id, impact_level);
CREATE INDEX idx_cv_systems_cv          ON public.cv_systems (master_cv_id, category);
CREATE INDEX idx_cv_leadership_cv       ON public.cv_leadership (master_cv_id, sort_order);
CREATE INDEX idx_cv_certifications_cv   ON public.cv_certifications (master_cv_id, sort_order);
CREATE INDEX idx_profile_gaps_user      ON public.profile_gaps (user_id, is_resolved, priority);

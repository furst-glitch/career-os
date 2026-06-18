-- Interview Center
-- Pakker, virksomhedsresearch, rolleanalyse, guides, lønforberedelse og træningssessioner

CREATE TABLE public.company_research (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  company_name    text NOT NULL,
  company_domain  text,
  culture_summary text,
  recent_news     jsonb NOT NULL DEFAULT '[]',   -- [{ title, date, summary, url }]
  interview_style text,
  known_questions text[] NOT NULL DEFAULT '{}',
  values          text[] NOT NULL DEFAULT '{}',
  red_flags       text[] NOT NULL DEFAULT '{}',
  strengths       text[] NOT NULL DEFAULT '{}',
  glassdoor_data  jsonb NOT NULL DEFAULT '{}',
  researched_at   timestamptz NOT NULL DEFAULT now(),
  cached_until    timestamptz NOT NULL DEFAULT (now() + interval '30 days'),
  UNIQUE (user_id, company_domain)
);

CREATE TABLE public.role_analyses (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  job_id            uuid REFERENCES public.jobs(id) ON DELETE CASCADE NOT NULL,
  required_skills   jsonb NOT NULL DEFAULT '[]',  -- [{ skill, importance, evidence }]
  nice_to_haves     text[] NOT NULL DEFAULT '{}',
  implicit_reqs     text[] NOT NULL DEFAULT '{}',
  focus_areas       text[] NOT NULL DEFAULT '{}',
  seniority_level   seniority_level,
  fit_score         numeric(3,2) CHECK (fit_score BETWEEN 0 AND 1),
  gaps              text[] NOT NULL DEFAULT '{}',
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.salary_prep_sessions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  job_id              uuid REFERENCES public.jobs(id) ON DELETE SET NULL,
  target_salary       int,
  market_min          int,
  market_max          int,
  market_median       int,
  data_sources        text[] NOT NULL DEFAULT '{}',
  negotiation_script  text,
  batna               text,
  anchoring_advice    text,
  talking_points      text[] NOT NULL DEFAULT '{}',
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.knowledge_guides (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title             text NOT NULL,
  category          text NOT NULL,
  content           text NOT NULL,
  tags              text[] NOT NULL DEFAULT '{}',
  language          language_code NOT NULL DEFAULT 'da',
  applicable_roles  text[] NOT NULL DEFAULT '{}',
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.interview_packages (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  job_id                uuid REFERENCES public.jobs(id) ON DELETE CASCADE NOT NULL,
  pipeline_id           uuid REFERENCES public.application_pipeline(id) ON DELETE SET NULL,
  title                 text NOT NULL,
  company_research_id   uuid REFERENCES public.company_research(id) ON DELETE SET NULL,
  role_analysis_id      uuid REFERENCES public.role_analyses(id) ON DELETE SET NULL,
  salary_prep_id        uuid REFERENCES public.salary_prep_sessions(id) ON DELETE SET NULL,
  readiness_score       numeric(3,2) DEFAULT 0 CHECK (readiness_score BETWEEN 0 AND 1),
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.interview_sessions (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  interview_package_id uuid REFERENCES public.interview_packages(id) ON DELETE SET NULL,
  job_id              uuid REFERENCES public.jobs(id) ON DELETE SET NULL,
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused')),
  focus_areas         text[] NOT NULL DEFAULT '{}',
  total_questions     int NOT NULL DEFAULT 0,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.interview_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    uuid REFERENCES public.interview_sessions(id) ON DELETE CASCADE NOT NULL,
  question      text NOT NULL,
  question_type text,
  user_answer   text,
  ai_feedback   text,
  score         numeric(3,2) CHECK (score BETWEEN 0 AND 1),
  sort_order    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER interview_packages_updated_at
  BEFORE UPDATE ON public.interview_packages
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER interview_sessions_updated_at
  BEFORE UPDATE ON public.interview_sessions
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

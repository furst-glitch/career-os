-- Search Intelligence
-- Lærende keyword-system med relevans-signaler og performance-tracking

CREATE TABLE public.user_keywords (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  keyword         text NOT NULL,
  keyword_type    keyword_type NOT NULL DEFAULT 'user_defined',
  weight          numeric(3,2) NOT NULL DEFAULT 0.5 CHECK (weight BETWEEN 0 AND 1),
  is_active       bool NOT NULL DEFAULT true,
  source_context  text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  last_matched_at timestamptz,
  UNIQUE (user_id, keyword)
);

CREATE TABLE public.job_relevance_signals (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  job_id          uuid REFERENCES public.jobs(id) ON DELETE CASCADE NOT NULL,
  signal_type     job_signal_type NOT NULL,
  signal_strength numeric(3,2) NOT NULL,     -- applied=1.0, saved=0.8, viewed=0.2, dismissed=-0.5
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.search_profiles (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  name        text NOT NULL DEFAULT 'Standard søgning',
  keyword_ids uuid[] NOT NULL DEFAULT '{}',
  filters     jsonb NOT NULL DEFAULT '{}',   -- { location, type, salary_min, remote_only }
  is_active   bool NOT NULL DEFAULT true,
  last_run_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.keyword_performance (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword_id      uuid REFERENCES public.user_keywords(id) ON DELETE CASCADE NOT NULL,
  jobs_found      int NOT NULL DEFAULT 0,
  jobs_relevant   int NOT NULL DEFAULT 0,
  jobs_dismissed  int NOT NULL DEFAULT 0,
  precision_score numeric(3,2),              -- relevant / found
  recorded_at     date NOT NULL DEFAULT CURRENT_DATE,
  UNIQUE (keyword_id, recorded_at)
);

CREATE TRIGGER search_profiles_updated_at
  BEFORE UPDATE ON public.search_profiles
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

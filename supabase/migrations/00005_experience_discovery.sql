-- Experience Discovery Engine
-- Struktureret indsamling af erfaringer, STAR-stories og kompetencer

CREATE TABLE public.experiences (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  title           text NOT NULL,
  organisation    text,
  experience_type experience_type NOT NULL,
  period_start    date,
  period_end      date,                      -- NULL = nuværende
  description     text,
  is_discoverable bool NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.star_stories (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  experience_id    uuid REFERENCES public.experiences(id) ON DELETE CASCADE,
  title            text NOT NULL,
  situation        text,
  task             text,
  action           text,
  result           text,
  impact_metric    text,                     -- Kvantificeret: "Reducerede tid med 40%"
  competencies     text[] NOT NULL DEFAULT '{}',
  keywords         text[] NOT NULL DEFAULT '{}',
  quality_score    numeric(3,2) CHECK (quality_score BETWEEN 0 AND 1),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.competency_library (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  name          text NOT NULL,
  category      competency_category NOT NULL,
  proficiency   competency_proficiency NOT NULL DEFAULT 'working',
  evidence_count int NOT NULL DEFAULT 0,
  last_used_at  date,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, name)
);

CREATE TABLE public.discovery_sessions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  session_type    discovery_session_type NOT NULL,
  experience_id   uuid REFERENCES public.experiences(id) ON DELETE SET NULL,
  status          discovery_session_status NOT NULL DEFAULT 'active',
  messages        jsonb[] NOT NULL DEFAULT '{}',
  extracted_data  jsonb NOT NULL DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER experiences_updated_at
  BEFORE UPDATE ON public.experiences
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER star_stories_updated_at
  BEFORE UPDATE ON public.star_stories
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER discovery_sessions_updated_at
  BEFORE UPDATE ON public.discovery_sessions
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

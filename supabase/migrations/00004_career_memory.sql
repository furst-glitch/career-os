-- Career Memory Engine
-- Vedvarende, semantisk søgbar karrierehukommelse pr. bruger

CREATE TABLE public.career_memories (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  content         text NOT NULL,
  embedding       vector(1536),              -- OpenAI text-embedding-3-small dimensioner
  memory_type     memory_type NOT NULL,
  source          memory_source NOT NULL DEFAULT 'user_input',
  relevance_score numeric(3,2) NOT NULL DEFAULT 0.5 CHECK (relevance_score BETWEEN 0 AND 1),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.career_goals (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  goal_type   goal_type NOT NULL,
  title       text NOT NULL,
  description text,
  target_date date,
  status      goal_status NOT NULL DEFAULT 'active',
  priority    int NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.career_preferences (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  industries      text[] NOT NULL DEFAULT '{}',
  company_sizes   text[] NOT NULL DEFAULT '{}',
  work_styles     text[] NOT NULL DEFAULT '{}',
  values          text[] NOT NULL DEFAULT '{}',
  location_prefs  jsonb NOT NULL DEFAULT '{}',
  deal_breakers   text[] NOT NULL DEFAULT '{}',
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.career_milestones (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  title         text NOT NULL,
  description   text,
  occurred_at   date NOT NULL,
  impact_level  milestone_impact NOT NULL DEFAULT 'medium',
  category      milestone_category NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER career_memories_updated_at
  BEFORE UPDATE ON public.career_memories
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

CREATE TRIGGER career_goals_updated_at
  BEFORE UPDATE ON public.career_goals
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- RPC til semantisk søgning i minder
CREATE OR REPLACE FUNCTION public.match_memories(
  query_embedding vector(1536),
  p_user_id       uuid,
  match_count     int DEFAULT 5,
  match_threshold numeric DEFAULT 0.7
)
RETURNS TABLE (
  id              uuid,
  content         text,
  memory_type     memory_type,
  relevance_score numeric,
  similarity      float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    cm.id,
    cm.content,
    cm.memory_type,
    cm.relevance_score,
    1 - (cm.embedding <=> query_embedding) AS similarity
  FROM public.career_memories cm
  WHERE cm.user_id = p_user_id
    AND cm.embedding IS NOT NULL
    AND 1 - (cm.embedding <=> query_embedding) > match_threshold
  ORDER BY cm.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- RPC til kontekst-snapshot (bruges af alle agenter)
CREATE OR REPLACE FUNCTION public.get_memory_snapshot(p_user_id uuid)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_goals text;
  v_prefs text;
  v_milestones text;
BEGIN
  SELECT string_agg(title || ': ' || COALESCE(description, ''), E'\n')
  INTO v_goals
  FROM public.career_goals
  WHERE user_id = p_user_id AND status = 'active'
  ORDER BY priority, created_at;

  SELECT 'Industrier: ' || array_to_string(industries, ', ') ||
         ' | Arbejdsstil: ' || array_to_string(work_styles, ', ')
  INTO v_prefs
  FROM public.career_preferences
  WHERE user_id = p_user_id;

  SELECT string_agg(title || ' (' || occurred_at::text || ')', ', ')
  INTO v_milestones
  FROM public.career_milestones
  WHERE user_id = p_user_id
  ORDER BY occurred_at DESC
  LIMIT 5;

  RETURN 'KARRIEREMÅL: ' || COALESCE(v_goals, 'Ingen') ||
         E'\nPRÆFERENCER: ' || COALESCE(v_prefs, 'Ikke sat') ||
         E'\nSENESTE MILEPÆLE: ' || COALESCE(v_milestones, 'Ingen');
END;
$$;
